# main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from graph_orchestrator import run_chat_flow
from firestore_session import get_session_history

app = FastAPI()

class ChatRequest(BaseModel):
    user_input: str
    session_id: str  # ADD THIS - session_id is required

def determine_awaiting_field(state: dict) -> str:
    """Helper to determine what field we're waiting for based on state"""
    # Check completion from end to beginning
    if state.get("care_advice"):
        return None  # Complete
    
    if state.get("report"):
        return None  # Complete (care advice is auto-generated)
    
    # Check if we have location
    location_json = state.get("location_json", {})
    if not location_json.get("current_location_name"):
        if state.get("location_city_state"):
            return "venue"  # Have city, need venue
        return "location_city_state"  # Need city
    
    # Check if we have exposure
    if not state.get("exposure_location_name") or state.get("days_since_exposure") is None:
        # Check what's missing
        if state.get("exposure_awaiting_field"):
            return state.get("exposure_awaiting_field")
        return "exposure_location"
    
    # Check if we have diagnosis
    diagnosis = state.get("diagnosis", {})
    if not diagnosis.get("final_diagnosis"):
        if "awaiting_field" in diagnosis and diagnosis["awaiting_field"] == "clarifier_answer":
            return "clarifier_answer"
        return "diagnosis"  # Waiting for diagnosis to complete
    
    # Check if we have symptoms
    if not state.get("symptoms") or state.get("days_since_onset") is None:
        if state.get("symptoms"):
            return "days_since_onset"
        return "symptoms"
    
    return None


@app.get("/session/{session_id}")
async def get_session_state(session_id: str):
    """
    Return current session state for frontend recovery.
    Allows app to resume conversation after restart.
    """
    try:
        session = get_session_history(session_id)
        
        if not session:
            return {
                "exists": False,
                "message": "No session found"
            }
        
        state = session.get("state", {})
        
        # Determine what we're currently waiting for
        awaiting_field = determine_awaiting_field(state)
        
        # Build response with all relevant state
        response = {
            "exists": True,
            "symptoms": state.get("symptoms"),
            "days_since_onset": state.get("days_since_onset"),
            "diagnosis": state.get("diagnosis"),
            "exposure_location_name": state.get("exposure_location_name"),
            "days_since_exposure": state.get("days_since_exposure"),
            "location_city_state": state.get("location_city_state"),
            "location_venue": state.get("location_venue"),
            "report": state.get("report"),
            "care_advice": state.get("care_advice"),
            "awaiting_field": awaiting_field,
            "is_complete": bool(state.get("care_advice"))  # Complete if we have care advice
        }
        
        print(f"📋 Session {session_id[:8]}... state retrieved: awaiting={awaiting_field}")
        return response
        
    except Exception as e:
        print(f"❌ Error fetching session state: {e}")
        return {
            "exists": False,
            "error": str(e)
        }


@app.post("/chat")
async def chat(request: ChatRequest):
    print(f"\n🛬 Received input from API: {request.user_input}")
    print(f"📋 Session ID: {request.session_id}")
    
    try:
        # Pass session_id to orchestrator
        result, _ = run_chat_flow(
            user_input=request.user_input, 
            session_id=request.session_id
        )
        
        print(f"\n🧠 Result from orchestrator: {result}")
        
        # Add awaiting_field to response for better frontend state tracking
        if result:
            # Try to determine what we're waiting for from the result
            if result.get("console_output") and not result.get("care_advice"):
                # We're asking a question - try to infer what we're waiting for
                console = result.get("console_output", "").lower()
                
                if "symptoms" in console or "experiencing" in console:
                    result["awaiting_field"] = "symptoms"
                elif "days ago" in console or "when did" in console:
                    result["awaiting_field"] = "days_since_onset"
                elif "exposed" in console or "where" in console and "exposure" in console:
                    result["awaiting_field"] = "exposure_location"
                elif "city" in console or "state" in console:
                    result["awaiting_field"] = "location_city_state"
                elif "venue" in console or "restaurant" in console or "building" in console:
                    result["awaiting_field"] = "venue"
        
        return result or {"error": "No response generated"}
        
    except Exception as e:
        print(f"❌ Exception in orchestrator: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "console_output": "Sorry, something went wrong. Please try again or start a new session."
        }


@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "EarlySignal Backend"}
