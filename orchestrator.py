import json
import sys
from datetime import datetime, timezone
import uuid

from helpers import (
    normalize_agent_response, parse_json_from_response,
    serialize_history, deserialize_history
)
from config import PROJECT_ID, PINECONE_INDEX_NAME, TABLE_ID
from agents.symptom_agent import run_agent as run_symptom
from agents.exposure_agent import run_agent as run_exposure
from agents.diagnostic_agent import run_agent as run_diagnostic
from agents.location_agent import run_agent as run_location
from agents.bq_submitter_agent import run_agent as run_bq
from agents.care_agent import run_agent as run_care

from firestore_session import get_session_history, save_session_history

REPORT_COUNTER = 0

def check_environment():
    required = [PROJECT_ID, PINECONE_INDEX_NAME, TABLE_ID]
    if not all(required):
        print("❌ Missing environment configurations!")
        return False
    return True

def is_valid_symptom_list(symptoms):
    if not symptoms or not isinstance(symptoms, list):
        return False
    invalid = all(any(word in s.lower() for word in ['day', 'week', 'ago', 'yesterday', 'today']) for s in symptoms)
    return not invalid

def is_valid_location(loc):
    if not loc or not isinstance(loc, str):
        return False
    l = loc.strip().lower()
    return l and l not in ["i don't know", "unknown", "not sure", "idk", "no idea"]

def is_valid_days(days):
    if days is None:
        return False
    try:
        days = int(days)
        return days >= 0
    except Exception:
        return False

def run_chat_flow(user_input: str, session_id: str = None):
    global REPORT_COUNTER

    if not session_id:
        session_id = str(uuid.uuid4())

    session = get_session_history(session_id)

    if isinstance(session, list):
        session = {"history": session, "state": {}}
    elif session is None:
        session = {"history": [], "state": {}}

    history = deserialize_history(session.get("history", []))

    default_state = {
        "step": "symptom",
        "symptoms": None,
        "days_since_onset": None,
        "diagnosis": None,
        "exposure_location_name": None,
        "days_since_exposure": None,
        "exposure_latitude": None,
        "exposure_longitude": None,
        "location_city_state": None,
        "location_venue": None,
        "location_json": None,
        "report": None,
        "care_advice": None,
        "clarifier_context": [],
        "location_prompted": False,
        "awaiting_exposure_field": None,
        "awaiting_location_field": None,
    }
    state = session.get("state", {})
    for k, v in default_state.items():
        if k not in state:
            state[k] = v

    result = {
        "diagnosis": None,
        "care_advice": None,
        "report": None,
        "console_output": ""
    }

    if not user_input and state["step"] == "symptom":
        result["console_output"] = "⚠️ Please describe your symptoms to begin."
        return result, serialize_history(history)

    if user_input and user_input.lower() in ("exit", "quit", "bye"):
        result["console_output"] = "👋 Goodbye!"
        return result, []

    try:
        # --- SYMPTOM STEP ---
        if state["step"] == "symptom":
            print("=== SYMPTOM STEP ===")
            print("State BEFORE agent call:", state)
            print("User input:", user_input)
            sym_json, history = run_symptom(user_input, history)
            sym = parse_json_from_response(sym_json) or {}
            print("Agent output:", sym)
            if "symptoms" in sym and is_valid_symptom_list(sym["symptoms"]):
                state["symptoms"] = sym["symptoms"]
            if "days_since_onset" in sym and sym["days_since_onset"] is not None:
                state["days_since_onset"] = sym["days_since_onset"]

            print("State AFTER merge:", state)

            if not state.get("symptoms"):
                result["console_output"] = sym.get("console_output", "Can you describe your symptoms?")
                save_session_history(session_id, {"history": serialize_history(history), "state": state})
                return result, serialize_history(history)
            if state.get("days_since_onset") is None:
                result["console_output"] = sym.get("console_output", "How many days ago did these symptoms begin?")
                save_session_history(session_id, {"history": serialize_history(history), "state": state})
                return result, serialize_history(history)

            state["step"] = "diagnostic"
            save_session_history(session_id, {"history": serialize_history(history), "state": state})

        # --- DIAGNOSTIC STEP ---
        if state["step"] == "diagnostic":
            print("=== DIAGNOSTIC STEP ===")
            print("State entering diagnostic:", state)
            diag_payload = {
                "symptoms": state["symptoms"],
                "days_since_onset": state["days_since_onset"],
                "clarifier_context": state.get("clarifier_context", [])
            }
            if session.get("last_clarifier_question") and user_input:
                diag_payload["clarifier_context"].append({
                    "question": session["last_clarifier_question"],
                    "answer": user_input
                })
            diag_json, history = run_diagnostic(json.dumps(diag_payload), history)
            diag = parse_json_from_response(diag_json)
            print("Diagnostic agent output:", diag)
            if "awaiting_field" in diag and diag["awaiting_field"] == "clarifier_answer":
                session["last_clarifier_question"] = diag["last_clarifier_question"]
                state["clarifier_context"] = diag.get("clarifier_context", [])
                result["console_output"] = diag.get("console_output", "Please answer:")
                save_session_history(session_id, {"history": serialize_history(history), "state": state, "last_clarifier_question": session.get("last_clarifier_question")})
                return result, serialize_history(history)
            state["diagnosis"] = diag
            result["diagnosis"] = diag
            if diag.get("final_diagnosis") == "Unknown (insufficient data)":
                result["console_output"] = "❌ We couldn't identify your condition based on the data. Please consult a professional."
                save_session_history(session_id, {"history": serialize_history(history), "state": state})
                return result, serialize_history(history)
            if diag.get("confidence", 0) < 0.5:
                result["console_output"] = f"⚠️ Low confidence in diagnosis: {diag['final_diagnosis']}"
            else:
                result["console_output"] = f"🧪 Most Likely Diagnosis: {diag['final_diagnosis']} ({diag['confidence']:.0%})"
            state["step"] = "exposure"
            save_session_history(session_id, {"history": serialize_history(history), "state": state})

        # --- EXPOSURE STEP ---
        if state["step"] == "exposure":
            print("=== EXPOSURE STEP ===")
            print("State entering exposure:", state)
            # If not yet filled, ask for location first
            if not state.get("exposure_location_name"):
                exp_payload = {
                    "illness_category": state["diagnosis"]["illness_category"],
                    "diagnosis": state["diagnosis"]["final_diagnosis"],
                    "symptom_summary": ", ".join(state["symptoms"]),
                    "days_since_exposure": state["days_since_onset"]
                }
                if state["awaiting_exposure_field"] == "location" and user_input:
                    exp_payload = {
                        "awaiting_field": "exposure_followup",
                        "user_input": user_input,
                    }
                exp_json, history = run_exposure(json.dumps(exp_payload), history)
                exp = parse_json_from_response(exp_json)
                print("Exposure agent output:", exp)
                if "exposure_location_name" in exp and is_valid_location(exp["exposure_location_name"]):
                    state["exposure_location_name"] = exp["exposure_location_name"]
                    state["exposure_latitude"] = exp.get("exposure_latitude")
                    state["exposure_longitude"] = exp.get("exposure_longitude")
                    state["days_since_exposure"] = exp.get("days_since_exposure")
                    if not is_valid_days(state["days_since_exposure"]):
                        state["awaiting_exposure_field"] = "days"
                        result["console_output"] = f"How many days ago were you at {state['exposure_location_name']}?"
                        save_session_history(session_id, {"history": serialize_history(history), "state": state})
                        return result, serialize_history(history)
                    else:
                        state["step"] = "location"
                        save_session_history(session_id, {"history": serialize_history(history), "state": state})
                elif "awaiting_field" in exp and exp["awaiting_field"] == "exposure_followup":
                    state["awaiting_exposure_field"] = "location"
                    result["console_output"] = exp.get("console_output", "Please specify where you think you were exposed.")
                    save_session_history(session_id, {"history": serialize_history(history), "state": state})
                    return result, serialize_history(history)
                else:
                    state["awaiting_exposure_field"] = "location"
                    result["console_output"] = "Where do you think you were exposed? (Please specify the venue or city.)"
                    save_session_history(session_id, {"history": serialize_history(history), "state": state})
                    return result, serialize_history(history)
            elif not is_valid_days(state.get("days_since_exposure")):
                # Prompt for days since exposure
                if user_input and state["awaiting_exposure_field"] == "days":
                    exp_payload = {
                        "awaiting_field": "exposure_followup",
                        "user_input": user_input,
                    }
                    exp_json, history = run_exposure(json.dumps(exp_payload), history)
                    exp = parse_json_from_response(exp_json)
                    if "days_since_exposure" in exp and is_valid_days(exp["days_since_exposure"]):
                        state["days_since_exposure"] = exp["days_since_exposure"]
                        state["step"] = "location"
                        state["awaiting_exposure_field"] = None
                        save_session_history(session_id, {"history": serialize_history(history), "state": state})
                    else:
                        result["console_output"] = exp.get("console_output", "How many days ago were you at your exposure location?")
                        save_session_history(session_id, {"history": serialize_history(history), "state": state})
                        return result, serialize_history(history)
                else:
                    result["console_output"] = f"How many days ago were you at {state['exposure_location_name']}?"
                    state["awaiting_exposure_field"] = "days"
                    save_session_history(session_id, {"history": serialize_history(history), "state": state})
                    return result, serialize_history(history)
            else:
                # Both are set, can move on
                state["step"] = "location"
                save_session_history(session_id, {"history": serialize_history(history), "state": state})

        # --- LOCATION STEP ---
        if state["step"] == "location":
            print("=== LOCATION STEP ===")
            print("State entering location:", state)
            if not state.get("location_city_state"):
                # First ask for city/state
                if state["awaiting_location_field"] == "city_state" and user_input:
                    loc_payload = user_input
                    loc_json, history = run_location(loc_payload, history)
                    loc = parse_json_from_response(loc_json)
                    if "awaiting_field" in loc and loc["awaiting_field"] == "venue":
                        state["location_city_state"] = user_input
                        state["awaiting_location_field"] = "venue"
                        result["console_output"] = loc["console_output"]
                        save_session_history(session_id, {"history": serialize_history(history), "state": state})
                        return result, serialize_history(history)
                    else:
                        result["console_output"] = loc.get("console_output", "Please provide your city and state.")
                        save_session_history(session_id, {"history": serialize_history(history), "state": state})
                        return result, serialize_history(history)
                else:
                    state["awaiting_location_field"] = "city_state"
                    result["console_output"] = "To help me understand your current situation, could you tell me what city and state you're in right now?"
                    save_session_history(session_id, {"history": serialize_history(history), "state": state})
                    return result, serialize_history(history)
            elif not state.get("location_venue"):
                # Then ask for venue/address
                if state["awaiting_location_field"] == "venue" and user_input:
                    loc_payload = json.dumps({
                        "awaiting_field": "venue",
                        "user_input": user_input,
                        "city_state": state["location_city_state"]
                    })
                    loc_json, history = run_location(loc_payload, history)
                    loc = parse_json_from_response(loc_json)
                    if "current_location_name" in loc and loc.get("location_category"):
                        state["location_venue"] = user_input
                        state["location_json"] = loc
                        state["step"] = "bq"
                        state["awaiting_location_field"] = None
                        save_session_history(session_id, {"history": serialize_history(history), "state": state})
                    else:
                        result["console_output"] = loc.get("console_output", "Please provide a venue, landmark, or address.")
                        save_session_history(session_id, {"history": serialize_history(history), "state": state})
                        return result, serialize_history(history)
                else:
                    state["awaiting_location_field"] = "venue"
                    result["console_output"] = f"Could you specify a venue name, landmark, neighborhood, cross-street, or address in {state['location_city_state']}?"
                    save_session_history(session_id, {"history": serialize_history(history), "state": state})
                    return result, serialize_history(history)
            else:
                # Both set, move to BQ
                state["step"] = "bq"
                save_session_history(session_id, {"history": serialize_history(history), "state": state})

        # --- BQ STEP ---
        if state["step"] == "bq":
            print("=== BQ STEP ===")
            print("State entering bq:", state)
            REPORT_COUNTER_LOCAL = session.get("REPORT_COUNTER", REPORT_COUNTER) + 1
            session["REPORT_COUNTER"] = REPORT_COUNTER_LOCAL
            report = {
                "report_id": REPORT_COUNTER_LOCAL,
                "user_id": 1,
                "report_timestamp": datetime.now(timezone.utc).isoformat(),
                "symptom_text": ", ".join(state["symptoms"]),
                "days_since_symptom_onset": state["days_since_onset"],
                "final_diagnosis": state["diagnosis"]["final_diagnosis"],
                "illness_category": state["diagnosis"]["illness_category"],
                "confidence": state["diagnosis"]["confidence"],
                "reasoning": state["diagnosis"].get("reasoning"),
                "exposure_location_name": state.get("exposure_location_name"),
                "exposure_latitude": state.get("exposure_latitude"),
                "exposure_longitude": state.get("exposure_longitude"),
                "days_since_exposure": state.get("days_since_exposure"),
                "current_location_name": state["location_json"].get("current_location_name") if state["location_json"] else "",
                "current_latitude": state["location_json"].get("current_latitude") if state["location_json"] else "",
                "current_longitude": state["location_json"].get("current_longitude") if state["location_json"] else "",
                "restaurant_visit": False,
                "outdoor_activity": False,
                "water_exposure": False,
                "location_category": state["location_json"].get("location_category") if state["location_json"] else "",
                "contagious_flag": state["diagnosis"]["illness_category"] == "airborne",
                "alertable_flag": state["diagnosis"]["illness_category"] in [
                    "airborne", "waterborne", "insect-borne", "foodborne"]
            }
            state["report"] = report
            result["report"] = report
            result_json, history = run_bq(json.dumps(report), history)
            result_bq = parse_json_from_response(result_json)
            print("BQ agent output:", result_bq)
            if result_bq.get("status") != "success":
                result["console_output"] = result_bq.get("console_output", "❌ Submission error.")
                save_session_history(session_id, {"history": serialize_history(history), "state": state})
                return result, serialize_history(history)
            state["step"] = "care"
            result["console_output"] = "Your report has been submitted successfully! Here is some care advice for you."
            save_session_history(session_id, {"history": serialize_history(history), "state": state})

        # --- CARE STEP ---
        if state["step"] == "care":
            print("=== CARE STEP ===")
            print("State entering care:", state)
            care_str, history = run_care(json.dumps(state["report"]), history)
            care = parse_json_from_response(care_str)
            print("Care agent output:", care)
            state["care_advice"] = care
            result["care_advice"] = care
            tips = care.get("self_care_tips", [])
            when_to_seek = care.get("when_to_seek_help", "")
            care_msg = "\n".join(f"• {tip}" for tip in tips)
            result["console_output"] += f"\n\n🩺 Self-Care Tips:\n{care_msg}\n\n📞 Seek help if: {when_to_seek}"
            state["step"] = "done"
            save_session_history(session_id, {"history": serialize_history(history), "state": state})
            return result, serialize_history(history)

        save_session_history(session_id, {"history": serialize_history(history), "state": state})
        return result, serialize_history(history)

    except Exception as e:
        print(f"⚠️ Top-level error: {e}")
        result["console_output"] = "⚠️ Sorry, something went wrong. Please try again."
        return result, serialize_history(history)