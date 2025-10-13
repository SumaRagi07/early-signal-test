# agents/exposure_agent.py - Version 7.3 (Debug + Fixed)

import json
from typing import Tuple

try:
    from helpers import geocode_location, parse_json_from_response, generate
except ImportError:
    def geocode_location(location):
        return None, None
    def parse_json_from_response(text):
        return {}
    def generate(prompt, history, system_prompt):
        return "{}", history


AGENT_NAME = "exposure_agent"

SYSTEM_PROMPT = f"""
You are {AGENT_NAME}, a medical exposure investigator for a public health system.

Your job is to extract:
1. **Where** the patient was exposed (specific venue/location name)
2. **When** they were exposed (number of days ago as an integer)

**CRITICAL EXTRACTION RULES:**
- Extract location names even from simple phrases like "Whole Foods", "the park", "a restaurant in Chinatown"
- Extract numbers even from simple phrases like "5", "3 days ago", "yesterday"
- Be LENIENT - if there's any location or timing information, extract it
- Strip conversational filler like "I ate at", "I was at", "I went to"
- If you see BOTH location and timing, return complete data immediately

**Output Format:**

If extracting location (even partial):
{{
  "exposure_location_name": "Venue Name, City"
}}

If extracting days:
{{
  "days_since_exposure": 3
}}

If extracting both:
{{
  "exposure_location_name": "Venue Name, City",
  "days_since_exposure": 3
}}

If unable to extract anything meaningful:
{{
  "needs_clarification": true
}}

**IMPORTANT:** 
- Always return ONLY valid JSON, no other text
- Be LENIENT in extraction - extract ANY location or time information you find
- Don't mark locations as "unknown" unless truly impossible to extract
"""


def is_invalid_answer(text):
    """Check if answer is a non-answer."""
    if not text:
        return True
    text_lower = text.lower().strip()
    invalid_responses = [
        "i don't know", "dont know", "don't know", "unknown", 
        "not sure", "idk", "no idea", "nowhere", "n/a", "na"
    ]
    return text_lower in invalid_responses


def run_agent(user_msg: str, history: list) -> Tuple[str, list]:
    """
    LLM-based exposure agent compatible with graph orchestrator.
    Uses generate() for flexible natural language understanding.
    """
    # Parse the incoming message
    payload = {}
    try:
        if isinstance(user_msg, str) and user_msg.strip():
            if user_msg.strip().startswith('{'):
                payload = json.loads(user_msg)
            else:
                payload = {"user_input": user_msg}
    except json.JSONDecodeError:
        payload = {}
    except Exception:
        payload = {}
    
    # Get context from payload
    user_input = payload.get("user_input", "").strip()
    partial_location = payload.get("partial_location")
    partial_days = payload.get("partial_days")
    illness_category = payload.get("illness_category", "").lower()
    diagnosis = payload.get("diagnosis", "your condition")
    
    # Build the prompt for the LLM based on context
    if user_input:
        # User has provided input - we're in follow-up mode
        
        if is_invalid_answer(user_input):
            return json.dumps({
                "awaiting_field": "exposure_info",
                "console_output": "Please provide the specific place where you think you were exposed and how many days ago. This information is important for public health tracking."
            }), history
        
        # Build context-aware prompt with explicit instructions
        if partial_location and partial_days is None:
            # We have location, asking for days - be very explicit
            prompt = f"""The patient was at "{partial_location}". 
They just said: "{user_input}"

Extract ONLY the number of days from their response. Look for:
- Pure numbers: "5" → {{"days_since_exposure": 5}}
- Time phrases: "3 days ago" → {{"days_since_exposure": 3}}
- Temporal words: "yesterday" → {{"days_since_exposure": 1}}

CRITICAL: We already have location="{partial_location}", ONLY extract days as integer."""

        elif partial_days is not None and not partial_location:
            # We have days, asking for location - be very explicit
            prompt = f"""The exposure was {partial_days} days ago.
They just said: "{user_input}"

Extract ONLY the location/venue name from their response.
Strip filler words like "at", "I was at", etc.

CRITICAL: Check if the location is too GENERIC (like "school", "work", "restaurant" without a name).
If generic, return {{"needs_specificity": true, "generic_location": "school", "console_output": "Could you be more specific? Which school or what area?"}}

Examples:
- "Chipotle" → {{"exposure_location_name": "Chipotle"}}
- "school" → {{"needs_specificity": true, "generic_location": "school"}}
- "my office" → {{"needs_specificity": true, "generic_location": "work"}}
- "Lincoln Elementary" → {{"exposure_location_name": "Lincoln Elementary"}}

CRITICAL: We already have days={partial_days}, ONLY extract location."""

        else:
            # Initial response - extract both
            prompt = f"""Patient has {diagnosis} ({illness_category}).
They said: "{user_input}"

Extract the exposure location AND/OR days ago from their statement.
Be LENIENT - extract ANY location or timing you can find.

Examples:
- "Chipotle 3 days ago" → {{"exposure_location_name": "Chipotle", "days_since_exposure": 3}}
- "Chipotle on Michigan Avenue" → {{"exposure_location_name": "Chipotle, Michigan Avenue"}}
- "3 days ago" → {{"days_since_exposure": 3}}

Return whatever you can extract."""
        
        # Call LLM
        response_text, updated_history = generate(prompt, history, SYSTEM_PROMPT)
        
        data = parse_json_from_response(response_text)
        
        if not isinstance(data, dict):
            # LLM didn't return valid JSON - return error
            return json.dumps({
                "awaiting_field": "exposure_info",
                "console_output": "Sorry, I didn't understand that. Where and when were you exposed? Please provide the location and how many days ago."
            }), updated_history
        
        # Check if LLM says location is too generic
        if data.get("needs_specificity"):
            generic_loc = data.get("generic_location", "that location")
            custom_msg = data.get("console_output")
            if custom_msg:
                return json.dumps({
                    "awaiting_field": "exposure_location_specificity",
                    "console_output": custom_msg
                }), updated_history
            else:
                return json.dumps({
                    "awaiting_field": "exposure_location_specificity",
                    "console_output": f"Could you be more specific about {generic_loc}? Please provide the name or at least the neighborhood/area."
                }), updated_history
        
        # CRITICAL: Check if LLM couldn't extract anything
        if data.get("needs_clarification"):
            return json.dumps({
                "awaiting_field": "exposure_info",
                "console_output": "Please provide both the location (venue/city) and when (how many days ago) you were exposed."
            }), updated_history
        
        # CRITICAL FIX: Merge with partial data BEFORE checking completeness
        if partial_location and not data.get("exposure_location_name"):
            data["exposure_location_name"] = partial_location
        if partial_days is not None and data.get("days_since_exposure") is None:
            data["days_since_exposure"] = partial_days
        
        # Check if LLM returned invalid/unknown for location
        location_value = data.get("exposure_location_name", "")
        if location_value and is_invalid_answer(location_value):
            data["exposure_location_name"] = None
        
        # Check if we have complete data NOW (after merging)
        has_location = data.get("exposure_location_name") and not is_invalid_answer(data.get("exposure_location_name", ""))
        has_days = data.get("days_since_exposure") is not None
        
        if has_location and has_days:
            # Complete! Geocode and return
            try:
                lat, lon = geocode_location(data["exposure_location_name"])
            except Exception:
                lat, lon = None, None
            
            result = {
                "exposure_location_name": data["exposure_location_name"],
                "exposure_latitude": lat,
                "exposure_longitude": lon,
                "days_since_exposure": data["days_since_exposure"],
                "console_output": f"Recorded exposure at {data['exposure_location_name']} ({data['days_since_exposure']} days ago)"
            }
            return json.dumps(result), updated_history
        
        # Partial data - ask for what's missing
        if has_location and not has_days:
            result = {
                "awaiting_field": "exposure_days",
                "console_output": f"How many days ago were you at {data['exposure_location_name']}?",
                "partial_location": data["exposure_location_name"]
            }
            return json.dumps(result), updated_history
        
        if not has_location and has_days:
            result = {
                "awaiting_field": "exposure_location",
                "console_output": "Where specifically were you exposed? Please provide the venue name or location.",
                "partial_days": data["days_since_exposure"]
            }
            return json.dumps(result), updated_history
        
        # Neither extracted successfully
        return json.dumps({
            "awaiting_field": "exposure_info",
            "console_output": "Please provide both the location (venue/city) and when (how many days ago) you were exposed."
        }), updated_history
    
    else:
        # No user input - this is the FIRST call from diagnosis node
        # OR user sent empty/whitespace input (like just pressing enter)
        
        # Generate category-specific initial question
        if illness_category == "foodborne":
            initial_question = "Where did you eat recently that might have caused your symptoms? Please include the restaurant/venue name and how many days ago."
        elif illness_category == "waterborne":
            initial_question = "Where were you exposed to water that might have caused your symptoms? (e.g., swimming pool, lake, etc.) Please include when this was."
        elif illness_category == "airborne":
            initial_question = "Where do you think you were exposed to someone who was sick? Please provide the location and how many days ago."
        elif illness_category == "insect-borne":
            initial_question = "Where were you when you might have been bitten or stung? Please provide the location and how many days ago."
        else:
            # Default for unknown categories
            initial_question = "Where and when do you think you were exposed? Please provide the location and how many days ago."
        
        return json.dumps({
            "awaiting_field": "exposure_info",
            "console_output": initial_question
        }), history