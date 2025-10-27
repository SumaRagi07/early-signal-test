# agents/location_agent.py
import json
from typing import List, Dict, Tuple
from helpers import generate, geocode_location, parse_json_from_response

AGENT_NAME = "location_agent"
SYSTEM_PROMPT = f"""
You are the {AGENT_NAME} for a public health system.

Your job is to determine where the user is currently staying while recovering from their illness.

Your goal is to produce both:
  • A precise location description
  • A classification of the area as urban, suburban, or rural

Follow these STRICT rules:

1. FIRST QUESTION (ask exactly this):
   "To help me understand your current situation, could you tell me what city and state you're in right now?"

2. For the user's response:
   - Extract just the location (e.g., "I'm in Chicago" → "Chicago")
   - Ask ONE follow-up: "Could you specify a venue name, landmark, neighborhood, cross-street, or address?"   

2. Classify the "location_category" as one of:
   - `"urban"` for cities and dense metro areas  
   - `"suburban"` for residential outskirts and towns  
   - `"rural"` for countryside or sparsely populated areas  

Return ONLY this raw JSON (no formatting, no extra text):
```json
{{
  "current_location_name": "Austin, TX",
  "current_latitude": 30.2672,
  "current_longitude": -97.7431,
  "location_category": "urban" | "suburban" | "rural" | null
}} 
"""

def run_agent(user_msg: str, history: List[Dict]) -> Tuple[str, List[Dict]]:
    try:
        data = json.loads(user_msg) if isinstance(user_msg, str) and user_msg.strip().startswith('{') else None
    except Exception:
        data = None

    # Check if location was already provided via GPS
    if data and data.get("skip_location_questions"):
        # Location already set in orchestrator, just return it
        return json.dumps({
            "current_location_name": data.get("current_location_name"),
            "current_latitude": data.get("current_latitude"),
            "current_longitude": data.get("current_longitude"),
            "location_category": data.get("location_category") or "urban"
        }), history
    
    # Ask for location if not provided
    if not user_msg or (data and data.get("awaiting_field") == "city_state"):
        return json.dumps({
            "awaiting_field": "city_state",
            "console_output": "To help me understand your current situation, could you tell me what city and state you're in right now?"
        }), history

    if data and data.get("awaiting_field") == "venue":
        city_state = data.get("city_state", "")
        venue_response = data.get("user_input", "")
        if not venue_response:
            return json.dumps({
                "awaiting_field": "venue",
                "console_output": f"Could you specify a venue name, landmark, neighborhood, cross-street, or address in {city_state}?"
            }), history
        full_location = f"{venue_response}, {city_state}" if city_state else venue_response
        response_text, history = generate(full_location, history, SYSTEM_PROMPT)
        location_data = parse_json_from_response(response_text)
        if (
            isinstance(location_data, dict)
            and location_data.get("current_location_name")
            and location_data.get("location_category")
        ):
            loc = full_location  # FIXED: Use user's combined input instead of LLM's simplified output
            try:
                lat, lon = geocode_location(loc)
            except Exception:
                lat = lon = None
            location_data["current_location_name"] = full_location
            location_data["current_latitude"] = lat
            location_data["current_longitude"] = lon
            return json.dumps(location_data), history
        else:
            # Fallback: just use what we have, don't keep re-prompting
            return json.dumps({
                "current_location_name": full_location,
                "current_latitude": None,
                "current_longitude": None,
                "location_category": None
            }), history

    city_response = user_msg.strip()
    if not city_response:
        return json.dumps({
            "awaiting_field": "city_state",
            "console_output": "To help me understand your current situation, could you tell me what city and state you're in right now?"
        }), history

    return json.dumps({
        "awaiting_field": "venue",
        "console_output": f"Could you specify a venue name, landmark, neighborhood, cross-street, or address in {city_response}?",
        "city_state": city_response
    }), history