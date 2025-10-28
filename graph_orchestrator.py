# graph_orchestrator.py

"""
LangGraph-based orchestrator for public health chatbot
This replaces the sequential workflow with a state graph that allows:
- Conditional branching (skip unnecessary clarifications)
- No separate clarification agent (handled in diagnostic_agent)
- Max 3 clarification attempts enforced
- Better state management
- GPS coordinate support for automatic location detection

Removed in this version:
- Clarification agent node (diagnostic agent handles this internally)
- Clarification router function (no longer needed)
"""

import json
from datetime import datetime, timezone
from typing import TypedDict, Annotated, Literal
import operator
import uuid

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from helpers import (
    parse_json_from_response,
    serialize_history, 
    deserialize_history,
    reverse_geocode  # NEW - for GPS coordinate → location name conversion
)
from config import PROJECT_ID, PINECONE_INDEX_NAME, TABLE_ID
from agents.symptom_agent import run_agent as run_symptom
from agents.exposure_agent import run_agent as run_exposure
from agents.diagnostic_agent import run_agent as run_diagnostic
from agents.location_agent import run_agent as run_location
from agents.bq_submitter_agent import run_agent as run_bq
from agents.cluster_validation_agent import run_agent as run_cluster_validation
from agents.care_agent import run_agent as run_care
from firestore_session import get_session_history, save_session_history


# ============================================================================
# STATE DEFINITION
# ============================================================================
class ChatState(TypedDict):
    """
    Shared state that flows through all nodes in the graph.
    Using Annotated with operator.add for lists means new items get appended.
    """
    # User interaction
    user_input: str
    session_id: str
    user_id: str
    console_output: str
    
    # Conversation history (for LLM context)
    history: Annotated[list, operator.add]
    
    # Symptom collection
    symptoms: list[str]
    days_since_onset: int
    
    # Diagnosis
    diagnosis: dict
    clarifier_context: Annotated[list, operator.add]  # Accumulates Q&A pairs
    clarification_attempts: int  # Track how many times we've asked for clarification
    
    # Exposure tracking
    exposure_location_name: str
    exposure_latitude: float
    exposure_longitude: float
    days_since_exposure: int
    exposure_awaiting_field: str
    exposure_partial_location: str
    exposure_partial_days: int
    
    # Current location
    location_city_state: str
    location_venue: str
    location_json: dict
    
    # Final outputs
    report: dict
    cluster_validation: dict 
    care_advice: dict
    
    # Control flags
    is_complete: bool


# ============================================================================
# VALIDATION HELPERS
# ============================================================================
def is_valid_symptom_list(symptoms):
    """Check if symptom list is valid (not empty, not temporal phrases)"""
    if not symptoms or not isinstance(symptoms, list):
        return False
    # Invalid if ALL symptoms are temporal phrases
    invalid = all(any(word in s.lower() for word in ['day', 'week', 'ago', 'yesterday', 'today']) 
                  for s in symptoms)
    return not invalid


def is_valid_location(loc):
    """Check if location string is valid (not empty, not 'unknown' variants)"""
    if not loc or not isinstance(loc, str):
        return False
    l = loc.strip().lower()
    return l and l not in ["i don't know", "unknown", "not sure", "idk", "no idea"]


def is_valid_days(days):
    """Check if days value is valid (non-negative integer)"""
    if days is None:
        return False
    try:
        days = int(days)
        return days >= 0
    except Exception:
        return False

def determine_start_node(state: dict) -> str:
    """
    Determine which node to start from based on current state.
    Prevents re-running completed stages when resuming a conversation.
    """
    # Check completion from end to beginning (reverse order)
    
    # Has everything - shouldn't happen, but just in case
    if state.get("care_advice"):
        return "symptom_collection"  # Already done
    
    # Has cluster validation but no care advice
    if state.get("cluster_validation"):
        return "care_advice"

    # Has report but no cluster validation
    if state.get("report"):
        return "cluster_validation"
    
    # Has location, ready for submission
    # FIXED: GPS location alone shouldn't trigger submission - need exposure data too
    if (state.get("location_json", {}).get("current_location_name") and
        state.get("exposure_location_name")):
        return "bq_submission"
    
    # Has exposure, need location
    if state.get("exposure_location_name") and state.get("days_since_exposure") is not None:
        return "location_collection"
    
    # Has diagnosis, need exposure (or waiting for exposure data)
    diagnosis = state.get("diagnosis", {})
    if diagnosis.get("final_diagnosis") and "awaiting_field" not in diagnosis:
        return "exposure_collection"
    
    # Has symptoms, need diagnosis (or waiting for clarification)
    if state.get("symptoms") and state.get("days_since_onset") is not None:
        return "diagnosis"
    
    # Default: start at beginning
    return "symptom_collection"

# ============================================================================
# GRAPH NODES (Each node is a step in the workflow)
# ============================================================================

def symptom_collection_node(state: ChatState) -> ChatState:
    """
    Node 1: Collect symptoms and onset timing from user.
    Calls the symptom agent to extract structured data from user input.
    """
    
    user_input = state.get("user_input", "")
    history = deserialize_history(state.get("history", []))
    
    # Get current values from state (preserve what we already have)
    current_symptoms = state.get("symptoms", [])
    current_days = state.get("days_since_onset")
    
    # Prepare payload with current state so agent knows what we have
    symptom_payload = {
        "user_input": user_input,
        "current_symptoms": current_symptoms,
        "current_days": current_days
    }
    
    # Call the symptom agent with state context
    sym_json, updated_history = run_symptom(json.dumps(symptom_payload), history)
    sym = parse_json_from_response(sym_json) or {}
    
    # Update state with extracted symptoms
    updates = {
        "history": serialize_history(updated_history),
        "console_output": sym.get("console_output", "")
    }
    
    # Update with new values if provided, otherwise preserve current values
    if "symptoms" in sym and is_valid_symptom_list(sym["symptoms"]):
        updates["symptoms"] = sym["symptoms"]
        current_symptoms = sym["symptoms"]
    elif current_symptoms:
        # Preserve existing symptoms if agent didn't return new ones
        updates["symptoms"] = current_symptoms
    
    if "days_since_onset" in sym and sym["days_since_onset"] is not None:
        updates["days_since_onset"] = sym["days_since_onset"]
        current_days = sym["days_since_onset"]
    elif current_days is not None:
        # Preserve existing days if agent didn't return new ones
        updates["days_since_onset"] = current_days
    
    # Check if we have BOTH symptoms and days
    has_symptoms = bool(current_symptoms) and is_valid_symptom_list(current_symptoms)
    has_days = current_days is not None and is_valid_days(current_days)
    
    return updates


def diagnosis_node(state: ChatState) -> ChatState:
    """
    Node 2: Generate diagnosis from symptoms.
    The diagnostic agent handles clarification internally - no separate clarification node needed.
    """
    
    history = deserialize_history(state.get("history", []))
    diagnosis = state.get("diagnosis", {})
    
    # Check if we're in clarification mode (diagnosis is waiting for answer)
    is_clarifying = "awaiting_field" in diagnosis and diagnosis["awaiting_field"] == "clarifier_answer"
    
    # If we're clarifying, add the user's answer to context
    clarifier_context = list(state.get("clarifier_context", []))
    if is_clarifying and state.get("user_input"):
        last_question = diagnosis.get("console_output", "")
        clarifier_context.append({
            "question": last_question,
            "answer": state.get("user_input")
        })
    
    # Check if we've hit max clarifications - force final diagnosis
    attempts = state.get("clarification_attempts", 0)
    force_final = attempts >= 3
    
    # Prepare payload for diagnostic agent
    diag_payload = {
        "symptoms": state.get("symptoms", []),
        "days_since_onset": state.get("days_since_onset", 0),
        "clarifier_context": clarifier_context,
        "force_final_diagnosis": force_final
    }
    
    # Call diagnostic agent (it handles clarification internally)
    diag_json, updated_history = run_diagnostic(json.dumps(diag_payload), history)
    diag = parse_json_from_response(diag_json)
    
    updates = {
        "history": serialize_history(updated_history),
        "diagnosis": diag,
        "console_output": "",
        "clarifier_context": clarifier_context
    }
    
    # Check if agent is asking for clarification (and we haven't hit limit)
    if "awaiting_field" in diag and diag["awaiting_field"] == "clarifier_answer" and not force_final:
        updates["console_output"] = diag.get("console_output", "Please answer:")
        updates["clarification_attempts"] = attempts + 1
        return updates
    
    # We have a final diagnosis (or were forced to make one)
    if "final_diagnosis" in diag and diag["final_diagnosis"]:
        confidence = diag.get("confidence", 0)
        final_diag = diag.get("final_diagnosis", "Unknown")
        
        # Clean the diagnosis dict - remove awaiting_field and clarification metadata
        clean_diagnosis = {
            "final_diagnosis": final_diag,
            "illness_category": diag.get("illness_category", "other"),
            "confidence": confidence,
            "reasoning": diag.get("reasoning", "")
        }
        
        updates["diagnosis"] = clean_diagnosis
        
        if final_diag == "Unknown (insufficient data)":
            updates["console_output"] = "We couldn't identify your condition. Please consult a healthcare professional."
        elif confidence < 0.5:
            updates["console_output"] = f"Low confidence diagnosis: {final_diag} ({confidence:.0%})"
        else:
            updates["console_output"] = f"Preliminary Diagnosis: {final_diag} ({confidence:.0%} confidence)"
        
        # Reset clarification counter
        updates["clarification_attempts"] = 0
        
        # CRITICAL FIX: Clear user_input so it doesn't get passed to next node
        updates["user_input"] = ""
        
    else:
        # Agent didn't respect force_final_diagnosis flag
        updates["console_output"] = "Unable to generate diagnosis. Please consult a healthcare professional."
        updates["clarification_attempts"] = 0
        updates["user_input"] = ""

    return updates

def exposure_collection_node(state: ChatState) -> ChatState:
    """
    Node 3: Collect exposure location and timing.
    """
    
    history = deserialize_history(state.get("history", []))
    diagnosis = state.get("diagnosis", {})
    user_input = state.get("user_input", "")
    
    # Prepare payload for exposure agent
    exp_payload = {
        "illness_category": diagnosis.get("illness_category", ""),
        "diagnosis": diagnosis.get("final_diagnosis", ""),
        "symptom_summary": ", ".join(state.get("symptoms", [])),
        "days_since_exposure": state.get("days_since_onset")
    }
    
    # Include user_input if we have it (either first time or follow-up)
    if user_input:
        exp_payload["user_input"] = user_input
        
        # Include partial data from state if it exists (for follow-up calls)
        if state.get("exposure_partial_location"):
            exp_payload["partial_location"] = state.get("exposure_partial_location")
        if state.get("exposure_partial_days") is not None:
            exp_payload["partial_days"] = state.get("exposure_partial_days")
    
    # Call exposure agent WITH STATE
    exp_json, updated_history = run_exposure(json.dumps(exp_payload), history, state)
    exp = parse_json_from_response(exp_json)
        
    updates = {
        "history": serialize_history(updated_history),
        "console_output": exp.get("console_output", "Where do you think you were exposed?")
    }
    
    # Track if we're waiting for exposure info
    if exp.get("awaiting_field"):
        updates["exposure_awaiting_field"] = exp.get("awaiting_field")
        
        # Save partial data to state
        if exp.get("partial_location"):
            updates["exposure_partial_location"] = exp.get("partial_location")
        if exp.get("partial_days") is not None:
            updates["exposure_partial_days"] = exp.get("partial_days")
    
    # Extract exposure data if provided (complete data = no awaiting_field)
    if "exposure_location_name" in exp and exp.get("exposure_location_name"):
        # Check if this is actually complete (has both location and days)
        has_location = exp.get("exposure_location_name") is not None
        has_days = exp.get("days_since_exposure") is not None
        
        if has_location and has_days:
            # COMPLETE DATA - store everything and clear awaiting flag
            updates["exposure_location_name"] = exp["exposure_location_name"]
            updates["exposure_latitude"] = exp.get("exposure_latitude")
            updates["exposure_longitude"] = exp.get("exposure_longitude")
            updates["days_since_exposure"] = exp["days_since_exposure"]
            updates["exposure_awaiting_field"] = None
            updates["exposure_partial_location"] = None
            updates["exposure_partial_days"] = None
            updates["user_input"] = ""  # Clear input for next node
    
    return updates

def location_collection_node(state: ChatState) -> ChatState:
    """
    Node 4: Collect current location (city/state and venue).
    UPDATED: Skip if GPS coordinates already provided.
    """
    
    # NEW: Check if location already provided via GPS
    location_json = state.get("location_json", {})
    if (location_json.get("current_location_name") and 
        location_json.get("current_latitude") is not None and
        location_json.get("current_longitude") is not None):
        
        print("✅ Using GPS-provided location, skipping location questions")
        
        # Return immediately with no console output (silent skip)
        return {
            "location_json": location_json,
            "console_output": ""
        }
    
    # EXISTING CODE: Ask for location manually
    history = deserialize_history(state.get("history", []))
    user_input = state.get("user_input", "")
    
    # Determine what we're asking for
    has_city = state.get("location_city_state")
    has_venue = state.get("location_venue")
    
    if not has_city:
        # First interaction - just ask for city/state
        loc_payload = user_input
    else:
        # Second interaction - we have city, now get venue
        loc_payload = json.dumps({
            "awaiting_field": "venue",
            "user_input": user_input,
            "city_state": state.get("location_city_state")
        })
    
    # Call location agent
    loc_json, updated_history = run_location(loc_payload, history)
    loc = parse_json_from_response(loc_json)
    
    updates = {
        "history": serialize_history(updated_history),
        "console_output": loc.get("console_output", "Please provide your location.")
    }
    
    # Update state based on what we got
    if not has_city and user_input:
        # First response - store city/state
        updates["location_city_state"] = user_input
    elif has_city and not has_venue:
        # Second response - store venue and full location data
        # FIXED: Check if location agent returned data (even if just city fallback)
        if "current_location_name" in loc:
            updates["location_venue"] = user_input
            updates["location_json"] = loc
        # ADDED: If location agent didn't return data, keep asking
        else:
            updates["console_output"] = loc.get("console_output", "Please provide a more specific location.")
    
    return updates


def bq_submission_node(state: ChatState) -> ChatState:
    """
    Node 5: Submit collected data to BigQuery.
    This is the critical data persistence step.
    """
    
    history = deserialize_history(state.get("history", []))
    
    # Build the report from collected state
    report_id = hash(state.get("session_id", "")) % 1000000
    
    diagnosis = state.get("diagnosis", {})
    location_json = state.get("location_json", {})
    
    # Get user_id from state with fallback to "1" (as string)
    user_id = state.get("user_id")
    
    # Use Firebase UID directly as string, or fallback to "1"
    if user_id and user_id != "anonymous":
        user_id_str = str(user_id)  # Keep Firebase UID as-is
        print(f"[Backend] Using Firebase user_id: {user_id_str}")
    else:
        user_id_str = "1"  # Fallback as string
        print(f"[Backend] No user_id provided, using fallback: 1")
    
    report = {
        "report_id": report_id,
        "user_id": user_id_str,  # STRING, not integer!
        "report_timestamp": datetime.now(timezone.utc).isoformat(),
        "symptom_text": ", ".join(state.get("symptoms", [])),
        "days_since_symptom_onset": state.get("days_since_onset"),
        "final_diagnosis": diagnosis.get("final_diagnosis", ""),
        "illness_category": diagnosis.get("illness_category", ""),
        "confidence": diagnosis.get("confidence", 0),
        "reasoning": diagnosis.get("reasoning", ""),
        "exposure_location_name": state.get("exposure_location_name"),
        "exposure_latitude": state.get("exposure_latitude"),
        "exposure_longitude": state.get("exposure_longitude"),
        "days_since_exposure": state.get("days_since_exposure"),
        "current_location_name": location_json.get("current_location_name", ""),
        "current_latitude": location_json.get("current_latitude", ""),
        "current_longitude": location_json.get("current_longitude", ""),
        "restaurant_visit": False,
        "outdoor_activity": False,
        "water_exposure": False,
        "location_category": location_json.get("location_category", ""),
        "contagious_flag": diagnosis.get("illness_category") == "airborne",
        "alertable_flag": diagnosis.get("illness_category") in [
            "airborne", "waterborne", "insect-borne", "foodborne"
        ]
    }
    
    print(f"[Backend] Submitting report with user_id: {user_id_str}")
    
    # Call BQ submission agent
    result_json, updated_history = run_bq(json.dumps(report), history)
    result_bq = parse_json_from_response(result_json)
    
    updates = {
        "history": serialize_history(updated_history),
        "report": report
    }
    
    if result_bq.get("status") == "success":
        updates["console_output"] = ""
    else:
        updates["console_output"] = "Submission error. Please try again."
        updates["is_complete"] = True
    
    return updates

def cluster_validation_node(state: ChatState) -> ChatState:
    """
    Node 5.5: Validate diagnosis against active outbreak clusters.
    
    This runs AFTER BQ submission to cross-reference the user's diagnosis
    against active disease outbreak clusters in their area.
    """
    
    history = deserialize_history(state.get("history", []))
    diagnosis = state.get("diagnosis", {})
    
    # Extract data needed for cluster validation
    user_disease = diagnosis.get("final_diagnosis")
    user_confidence = diagnosis.get("confidence", 0.5)
    exposure_lat = state.get("exposure_latitude")
    exposure_lon = state.get("exposure_longitude")
    days_since_exposure = state.get("days_since_exposure")
    illness_category = diagnosis.get("illness_category")
    
    # NEW: Get current location coordinates
    location_json = state.get("location_json", {})
    current_lat = location_json.get("current_latitude")
    current_lon = location_json.get("current_longitude")
    
    # Skip cluster validation if we don't have required data
    if not all([user_disease, exposure_lat is not None, exposure_lon is not None, 
                days_since_exposure is not None]):
        print("⚠️  Skipping cluster validation - missing exposure data")
        return {
            "history": serialize_history(history),
            "cluster_validation": {},
            "console_output": ""
        }
    
    # Prepare payload for cluster validation agent
    validation_payload = {
        "user_disease": user_disease,
        "user_confidence": user_confidence,
        "exposure_latitude": exposure_lat,
        "exposure_longitude": exposure_lon,
        "days_since_exposure": days_since_exposure,
        "illness_category": illness_category,
        # NEW: Pass current location
        "current_latitude": current_lat,
        "current_longitude": current_lon
    }
    
    print(f"🔍 Validating diagnosis against outbreak clusters...")
    
    # Call cluster validation agent
    validation_json, updated_history = run_cluster_validation(
        json.dumps(validation_payload), 
        history
    )
    validation_result = parse_json_from_response(validation_json)
        
    updates = {
        "history": serialize_history(updated_history),
        "cluster_validation": validation_result,
        "console_output": ""
    }
    
    # Check if diagnosis was refined by cluster data
    if validation_result.get("cluster_found"):
        validation_type = validation_result.get("validation_result")
        
        print(f"✅ Cluster validation: {validation_type}")
        
        # Update diagnosis if cluster suggested an alternative
        if validation_type in ["ALTERNATIVE", "CONFIRMED"]:
            refined_diagnosis = {
                "final_diagnosis": validation_result.get("refined_diagnosis"),
                "illness_category": diagnosis.get("illness_category"),
                "confidence": validation_result.get("refined_confidence"),
                "reasoning": validation_result.get("reasoning"),
                "cluster_validated": True,
                "original_diagnosis": validation_result.get("original_diagnosis"),
                "original_diagnosis_confidence": user_confidence,
                "validation_type": validation_type
            }
            updates["diagnosis"] = refined_diagnosis
            
            # Add cluster alert to console output if provided
            cluster_message = validation_result.get("console_output", "")
            if cluster_message:
                updates["console_output"] = cluster_message
    else:
        print("ℹ️  No outbreak clusters matched")
    
    return updates

def care_advice_node(state: ChatState) -> ChatState:
    """
    Node 6: Generate personalized care advice.
    Final step before completion.
    """
    
    history = deserialize_history(state.get("history", []))
    report = state.get("report", {})
    
    # Call care agent
    care_json, updated_history = run_care(json.dumps(report), history)
    care = parse_json_from_response(care_json)
    
    return {
        "history": serialize_history(updated_history),
        "care_advice": care,
        "console_output": "",
        "is_complete": True
    }


# ============================================================================
# CONDITIONAL EDGES (Router functions that decide next step)
# ============================================================================

def route_after_symptoms(state: ChatState) -> Literal["diagnosis", END]:
    """
    Decide if we have enough symptom info to proceed to diagnosis.
    If not, END to wait for user input.
    """
    has_symptoms = bool(state.get("symptoms")) and is_valid_symptom_list(state.get("symptoms", []))
    has_days = state.get("days_since_onset") is not None and is_valid_days(state.get("days_since_onset"))
    
    if has_symptoms and has_days:
        return "diagnosis"
    else:
        return END

def route_after_diagnosis(state: ChatState) -> Literal["exposure_collection", END]:
    """
    Decide next step after diagnosis.
    Auto-routes to exposure immediately when diagnosis is final.
    """
    diagnosis = state.get("diagnosis", {})
    
    # Check if we're waiting for clarification (must END to get user input)
    if "awaiting_field" in diagnosis and diagnosis["awaiting_field"] == "clarifier_answer":
        attempts = state.get("clarification_attempts", 0)
        if attempts < 3:
            return END
    
    # Check if diagnosis failed (insufficient data)
    final_diag = diagnosis.get("final_diagnosis", "")
    if final_diag == "Unknown (insufficient data)":
        return END
    
    # We have a final diagnosis - AUTO-ROUTE to exposure (no waiting for "ok")
    if final_diag and "awaiting_field" not in diagnosis:
        return "exposure_collection"
    
    # Default: wait for more processing
    return END

def route_after_exposure(state: ChatState) -> Literal["location_collection", "bq_submission", END]:
    """
    Check if we have complete exposure info.
    UPDATED: Skip location collection if GPS already provided.
    """
    has_location = is_valid_location(state.get("exposure_location_name"))
    has_days = is_valid_days(state.get("days_since_exposure"))
    
    if not (has_location and has_days):
        return END
    
    # NEW: Check if we already have GPS location
    location_json = state.get("location_json", {})
    if (location_json.get("current_latitude") is not None and 
        location_json.get("current_longitude") is not None and
        location_json.get("current_location_name")):
        # Skip location collection, go straight to submission
        print("🚀 GPS location available, skipping location questions → BQ submission")
        return "bq_submission"
    
    # Ask for location manually
    return "location_collection"


def route_after_location(state: ChatState) -> Literal["bq_submission", END]:
    """
    Check if we have complete location info.
    """
    has_full_data = bool(state.get("location_json", {}).get("current_location_name"))
    
    if has_full_data:
        return "bq_submission"
    else:
        return END


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_chat_graph():
    """
    Build the LangGraph state graph.
    
    Flow: symptom_collection -> diagnosis -> exposure_collection -> 
          location_collection -> bq_submission -> care_advice -> END
    
    Each node can END to wait for more user input.
    State persists between calls via Firestore.
    """
    workflow = StateGraph(ChatState)
    
    # Add all nodes (no clarification node - diagnostic agent handles it)
    workflow.add_node("symptom_collection", symptom_collection_node)
    workflow.add_node("diagnosis", diagnosis_node)
    workflow.add_node("exposure_collection", exposure_collection_node)
    workflow.add_node("location_collection", location_collection_node)
    workflow.add_node("bq_submission", bq_submission_node)
    workflow.add_node("cluster_validation", cluster_validation_node)
    workflow.add_node("care_advice", care_advice_node)
    
    # Set entry point
    workflow.set_entry_point("symptom_collection")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "symptom_collection",
        route_after_symptoms,
        {
            "diagnosis": "diagnosis",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "diagnosis",
        route_after_diagnosis,
        {
            "exposure_collection": "exposure_collection",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "exposure_collection",
        route_after_exposure,
        {
            "location_collection": "location_collection",
            "bq_submission": "bq_submission",  # NEW: Direct route when GPS available
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "location_collection",
        route_after_location,
        {
            "bq_submission": "bq_submission",
            END: END
        }
    )
    
    # Final path to completion
    workflow.add_edge("bq_submission", "cluster_validation")
    workflow.add_edge("cluster_validation", "care_advice")
    workflow.add_edge("care_advice", END)
    
    # Compile with checkpointing
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# ============================================================================
# MAIN EXECUTION FUNCTION
# ============================================================================

def run_graph_chat_flow(
    user_input: str, 
    session_id: str = None,
    user_id: str = None,
    current_latitude: float = None,   # NEW: GPS latitude
    current_longitude: float = None   # NEW: GPS longitude
):
    """
    Main entry point for the graph-based chatbot.
    UPDATED: Now accepts optional GPS coordinates for automatic location detection.
    """
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Handle empty input at start
    if not user_input:
        session = get_session_history(session_id)
        if not session or not session.get("state", {}).get("symptoms"):
            return {
                "diagnosis": None,
                "care_advice": None,
                "report": None,
                "console_output": "Please describe your symptoms to begin."
            }, []
    
    # Handle exit commands
    if user_input and user_input.lower() in ("exit", "quit", "bye"):
        return {
            "diagnosis": None,
            "care_advice": None,
            "report": None,
            "console_output": "Goodbye!"
        }, []

    # Load session from Firestore
    session = get_session_history(session_id)

    if isinstance(session, list):
        session = {"history": session, "state": {}}
    elif session is None:
        session = {"history": [], "state": {}}
    
    # Initialize state from saved session
    initial_state = {
        "user_input": user_input,
        "session_id": session_id,
        "user_id": user_id or session.get("state", {}).get("user_id") or "anonymous",  # NEW
        "console_output": "",
        "history": session.get("history", []),
        "symptoms": session.get("state", {}).get("symptoms", []) or [],
        "days_since_onset": session.get("state", {}).get("days_since_onset"),
        "diagnosis": session.get("state", {}).get("diagnosis", {}),
        "clarifier_context": session.get("state", {}).get("clarifier_context", []),
        "clarification_attempts": session.get("state", {}).get("clarification_attempts", 0),
        "exposure_location_name": session.get("state", {}).get("exposure_location_name"),
        "exposure_latitude": session.get("state", {}).get("exposure_latitude"),
        "exposure_longitude": session.get("state", {}).get("exposure_longitude"),
        "days_since_exposure": session.get("state", {}).get("days_since_exposure"),
        "exposure_awaiting_field": session.get("state", {}).get("exposure_awaiting_field"),
        "exposure_partial_location": session.get("state", {}).get("exposure_partial_location"),
        "exposure_partial_days": session.get("state", {}).get("exposure_partial_days"),
        "location_city_state": session.get("state", {}).get("location_city_state"),
        "location_venue": session.get("state", {}).get("location_venue"),
        "location_json": session.get("state", {}).get("location_json", {}),
        "report": session.get("state", {}).get("report"),
        "cluster_validation": session.get("state", {}).get("cluster_validation", {}),
        "care_advice": session.get("state", {}).get("care_advice"),
        "is_complete": False
    }
    
    # NEW: Add location coordinates to initial state if provided
    # BUT ONLY if we haven't already stored location AND we're past the exposure stage
    if current_latitude is not None and current_longitude is not None:
        # Check if we haven't already stored location
        if not session.get("state", {}).get("location_json", {}).get("current_location_name"):
            # Reverse geocode to get location name
            location_name = reverse_geocode(current_latitude, current_longitude)
            
            # Infer location category (simple heuristic - can enhance later)
            location_category = "urban"  # Default assumption for GPS locations
            
            initial_state["location_json"] = {
                "current_location_name": location_name or f"GPS Location ({current_latitude:.4f}, {current_longitude:.4f})",
                "current_latitude": current_latitude,
                "current_longitude": current_longitude,
                "location_category": location_category
            }
            
            # Mark that we have location data (so routers skip location_collection)
            initial_state["location_city_state"] = location_name or "GPS location"
            initial_state["location_venue"] = "Provided via GPS"
            
            print(f"📍 Using GPS-provided location: {location_name or 'coordinates'}")
    
    # Create the graph
    graph = create_chat_graph()
    
    # Determine where to start based on what we already have
    start_node = determine_start_node(initial_state)
    
    print(f"🔍 DEBUG: start_node = {start_node}")
    print(f"🔍 DEBUG: initial_state symptoms = {initial_state.get('symptoms')}")
    print(f"🔍 DEBUG: initial_state diagnosis = {initial_state.get('diagnosis')}")
    print(f"🔍 DEBUG: initial_state exposure = {initial_state.get('exposure_location_name')}")
    
    try:
        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": 25
        }
        
        # If resuming mid-flow, start at the appropriate node
        if start_node != "symptom_collection":
            # Manually run the determined start node
            current_state = dict(initial_state)
            
            # Map of node names to functions
            node_map = {
                "diagnosis": diagnosis_node,
                "exposure_collection": exposure_collection_node,
                "location_collection": location_collection_node,
                "bq_submission": bq_submission_node,
                "cluster_validation": cluster_validation_node,
                "care_advice": care_advice_node
            }
            
            # Execute the determined start node
            if start_node in node_map:
                node_func = node_map[start_node]
                updates = node_func(current_state)
                current_state.update(updates)
                
                # CRITICAL FIX: Check if we just completed diagnosis and should auto-continue
                if start_node == "diagnosis":
                    next_route = route_after_diagnosis(current_state)
                    if next_route == "exposure_collection":
                        
                        # Save the diagnosis output before calling exposure node
                        diagnosis_output = current_state.get("console_output", "")
                        
                        # Call exposure node
                        updates = exposure_collection_node(current_state)
                        current_state.update(updates)
                        
                        # Combine both outputs so user sees diagnosis + exposure question
                        exposure_output = current_state.get("console_output", "")
                        if diagnosis_output and exposure_output:
                            current_state["console_output"] = f"{diagnosis_output}\n\n{exposure_output}"
                        elif diagnosis_output:
                            current_state["console_output"] = diagnosis_output
                        elif exposure_output:
                            current_state["console_output"] = exposure_output
                
                # Check if we should auto-continue based on routers
                # IMPORTANT: Only auto-continue if we're RESUMING (have exposure data already)
                if start_node == "exposure_collection":
                    # Check if exposure is complete and should continue to location
                    next_route = route_after_exposure(current_state)
                    
                    # Only auto-continue if we HAVE exposure data (resuming mid-flow)
                    has_exposure = (
                        current_state.get("exposure_location_name") and 
                        current_state.get("days_since_exposure") is not None
                    )
                    
                    if has_exposure and next_route == "location_collection":
                        updates = location_collection_node(current_state)
                        current_state.update(updates)
                        
                        # Check if location is also complete
                        next_route = route_after_location(current_state)
                        if next_route == "bq_submission":
                            updates = bq_submission_node(current_state)
                            current_state.update(updates)
                            
                            # Auto-continue to cluster validation
                            updates = cluster_validation_node(current_state)
                            current_state.update(updates)

                            updates = care_advice_node(current_state)
                            current_state.update(updates)
                    
                    # NEW: Handle GPS skip to BQ submission (only if we have exposure)
                    elif has_exposure and next_route == "bq_submission":
                        updates = bq_submission_node(current_state)
                        current_state.update(updates)
                        
                        # Auto-continue to cluster validation
                        updates = cluster_validation_node(current_state)
                        current_state.update(updates)

                        updates = care_advice_node(current_state)
                        current_state.update(updates)
                
                elif start_node == "location_collection":
                    # Check if location is complete
                    next_route = route_after_location(current_state)
                    if next_route == "bq_submission":
                        updates = bq_submission_node(current_state)
                        current_state.update(updates)
                        
                        # Auto-continue to cluster validation
                        updates = cluster_validation_node(current_state)
                        current_state.update(updates)

                        updates = care_advice_node(current_state)
                        current_state.update(updates)
                
                final_state = current_state

            else:
                # Shouldn't happen, but fallback to normal flow
                final_state = graph.invoke(initial_state, config)
        else:
            # Normal flow from beginning - let graph handle everything
            final_state = graph.invoke(initial_state, config)
        
        # Extract results - only send diagnosis/care_advice/report if newly generated
        newly_diagnosed = (
            final_state.get("diagnosis") and 
            initial_state.get("diagnosis", {}).get("final_diagnosis") != final_state.get("diagnosis", {}).get("final_diagnosis")
        )

        # Also check if diagnosis was cluster-validated (confidence boost)
        cluster_validated = (
            final_state.get("diagnosis", {}).get("cluster_validated") == True and
            not initial_state.get("diagnosis", {}).get("cluster_validated")
        )

        newly_care_advice = (
            final_state.get("care_advice") and
            not initial_state.get("care_advice")
        )

        newly_report = (
            final_state.get("report") and
            not initial_state.get("report")
        )

        newly_cluster_validation = (
            final_state.get("cluster_validation") and
            not initial_state.get("cluster_validation")
        )

        result = {
            "diagnosis": final_state.get("diagnosis") if (newly_diagnosed or cluster_validated) else None,
            "care_advice": final_state.get("care_advice") if newly_care_advice else None,
            "report": final_state.get("report") if newly_report else None,
            "cluster_validation": final_state.get("cluster_validation") if newly_cluster_validation else None,
            "console_output": final_state.get("console_output", "")
        }
        
        # Prepare state to save
        state_to_save = {
            "user_id": final_state.get("user_id"),  # NEW
            "symptoms": final_state.get("symptoms", []),
            "days_since_onset": final_state.get("days_since_onset"),
            "diagnosis": final_state.get("diagnosis", {}),
            "clarifier_context": final_state.get("clarifier_context", []),
            "clarification_attempts": final_state.get("clarification_attempts", 0),
            "exposure_location_name": final_state.get("exposure_location_name"),
            "exposure_latitude": final_state.get("exposure_latitude"),
            "exposure_longitude": final_state.get("exposure_longitude"),
            "days_since_exposure": final_state.get("days_since_exposure"),
            "exposure_awaiting_field": final_state.get("exposure_awaiting_field"),
            "exposure_partial_location": final_state.get("exposure_partial_location"),
            "exposure_partial_days": final_state.get("exposure_partial_days"),
            "location_city_state": final_state.get("location_city_state"),
            "location_venue": final_state.get("location_venue"),
            "location_json": final_state.get("location_json"),
            "report": final_state.get("report"),
            "cluster_validation": final_state.get("cluster_validation", {}),
            "care_advice": final_state.get("care_advice")
        }

        save_session_history(session_id, {
            "history": final_state.get("history", []),
            "state": state_to_save
        })
        return result, final_state.get("history", [])
        
    except Exception as e:
        print(f"Graph execution error: {e}")
        import traceback
        traceback.print_exc()
        
        result = {
            "diagnosis": None,
            "care_advice": None,
            "report": None,
            "console_output": "Sorry, something went wrong. Please try again."
        }
        return result, session.get("history", [])
    
# For backwards compatibility
run_chat_flow = run_graph_chat_flow

if __name__ == "__main__":
    """
    Interactive CLI for testing the LangGraph health chatbot.

    Features:
    - Persistent session across conversation turns
    - Rich console output with emoji indicators
    - Session state display for debugging
    - Graceful error handling
    """
    import sys

    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "🏥 HEALTH CHATBOT - LANGGRAPH v15" + " " * 20 + "║")
    print("╚" + "═" * 68 + "╝")
    print("\nI'll help you report symptoms and track potential disease exposure.")
    print("\nCommands:")
    print("  • Type your responses naturally")
    print("  • 'debug' - Show current session state")
    print("  • 'reset' - Start a new session")
    print("  • 'quit' - Exit the chatbot")
    print("\n" + "─" * 70 + "\n")

    # Initialize session
    session_id = str(uuid.uuid4())
    turn_count = 0

    shown_diagnosis = False
    shown_report = False

    print(f"📋 Session ID: {session_id[:8]}...")
    print("🤖 Bot: Hello! Please describe any symptoms you're experiencing.\n")

    while True:
        try:
            # Get user input
            user_input = input("💬 You: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n👋 Thank you for using the health chatbot. Take care!")
                sys.exit(0)

            if user_input.lower() == "reset":
                session_id = str(uuid.uuid4())
                turn_count = 0
                shown_diagnosis = False
                shown_report = False
                print(f"\n🔄 New session started: {session_id[:8]}...")
                print("🤖 Bot: Hello! Please describe any symptoms you're experiencing.\n")
                continue

            if user_input.lower() == "debug":
                # Show session state from Firestore
                session_data = get_session_history(session_id)
                if session_data:
                    state = session_data.get("state", {})
                    print("\n" + "─" * 70)
                    print("🔍 DEBUG - Current Session State:")
                    print(f"   Symptoms: {state.get('symptoms', 'None')}")
                    print(f"   Days since onset: {state.get('days_since_onset', 'None')}")
                    print(f"   Diagnosis: {state.get('diagnosis', {}).get('final_diagnosis', 'None')}")
                    print(f"   Exposure location: {state.get('exposure_location_name', 'None')}")
                    print(f"   Current location: {state.get('location_city_state', 'None')}")
                    print(f"   Conversation turns: {turn_count}")
                    print("─" * 70 + "\n")
                else:
                    print("\n⚠️ No session data found\n")
                continue

            # Process input through chatbot
            print()  # Blank line for readability
            result, _ = run_graph_chat_flow(user_input, session_id)
            turn_count += 1

            # Display bot response
            console_output = result.get("console_output", "")
            if console_output:
                print(f"🤖 Bot: {console_output}")

            # Show diagnosis if newly available
            diagnosis = result.get("diagnosis")
            if diagnosis and diagnosis.get("final_diagnosis"):
                diag_name = diagnosis["final_diagnosis"]
                confidence = diagnosis.get("confidence", 0)
                category = diagnosis.get("illness_category", "unknown")
                
                # Check if this was cluster validated
                if diagnosis.get("cluster_validated"):
                    validation_type = diagnosis.get("validation_type", "CONFIRMED")
                    original_conf = diagnosis.get("original_diagnosis_confidence", 0)
                    
                    if validation_type == "CONFIRMED":
                        print(f"\n   ✅ Confirmed Diagnosis: {diag_name}")
                        print(f"   📈 Confidence: {original_conf:.0%} → {confidence:.0%} (boosted by outbreak data)")
                        print(f"   🏷️  Category: {category}")
                    elif validation_type == "ALTERNATIVE":
                        original_diag = diagnosis.get("original_diagnosis", "Unknown")
                        print(f"\n   🔄 Updated Diagnosis: {original_diag} → {diag_name}")
                        print(f"   📈 Confidence: {confidence:.0%} (based on outbreak cluster)")
                        print(f"   🏷️  Category: {category}")
                    
                    shown_diagnosis = True
                # Only show if not already displayed in console_output
                elif diag_name not in console_output and not shown_diagnosis:
                    print(f"\n   📊 Diagnosis: {diag_name}")
                    print(f"   🏷️  Category: {category}")
                    print(f"   📈 Confidence: {confidence:.0%}")
                    shown_diagnosis = True

            # Show submission confirmation
            report = result.get("report")
            if report and not shown_report:
                print(f"\n   ✅ Report submitted to BigQuery")
                print(f"   🆔 Report ID: {report.get('report_id')}")
                shown_report = True

            # Show care advice summary
            care = result.get("care_advice")
            if care and care.get("self_care_tips"):
                tips = care["self_care_tips"]
                print(f"\n   💊 Care tips provided ({len(tips)} total)")

                print("\n" + "─" * 70)
                print("✅ Health report complete. Thank you for using the chatbot!")
                print("💡 Type 'reset' to start a new report, or 'quit' to exit.")
                print("─" * 70 + "\n")

            print()  # Blank line after bot response

        except KeyboardInterrupt:
            print("\n\n👋 Conversation interrupted. Goodbye!")
            sys.exit(0)

        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("💡 Try again or type 'reset' for a new session\n")
            import traceback
            traceback.print_exc()