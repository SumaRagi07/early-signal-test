# agents/exposure_agent.py

import json
from helpers import generate, compute_days_ago, geocode_location, parse_json_from_response
from typing import List, Dict, Tuple

AGENT_NAME = "exposure_agent"
SYSTEM_PROMPT = f"""
You are {AGENT_NAME}, a medical‐epidemiology expert for a public health system.

As a medical exposure investigator, your job is to figure out:
  1) **Where** the patient was exposed (public venue + city)
  2) **When** they were exposed (days ago)

Use the illness_category to tailor your questions:
  - Respiratory: Ask about gatherings/travel.
  - Foodborne: Ask about what/where they ate.
  - Waterborne: Ask about drinking/swimming.
  - Insect-borne: Ask about outdoor activities or bites.

**Return ONLY** when you have both in the format below:

```json
{{
  "exposure_location_name": "Specific Venue, City",
  "exposure_latitude": 37.7,
  "exposure_longitude": -122.4,
  "days_since_exposure": 5
}}
"""
def missing_exposure_fields(data):
    missing = []
    if not data.get("exposure_location_name"):
        missing.append("location")
    if data.get("days_since_exposure") is None:
        missing.append("days")
    return missing

def is_invalid_answer(text):
    # Add more variants as needed
    return not text or text.lower().strip() in [
        "i don't know", "dont know", "don't know", "unknown", "not sure", "idk", "no idea"
    ]

def run_agent(user_msg: str, history: list) -> Tuple[str, list]:
    try:
        payload = json.loads(user_msg) if isinstance(user_msg, str) and user_msg.strip().startswith('{') else {}
    except Exception:
        payload = {}

    # If orchestrator passes a marker, use it
    if payload.get("awaiting_field") == "exposure_followup":
        user_reply = payload.get("user_input", "")
        if is_invalid_answer(user_reply):
            # Repeat the last prompt, do not accept "I don't know"
            return json.dumps({
                "awaiting_field": "exposure_followup",
                "console_output": "Sorry, it's important for public health. Please provide the specific place/venue/city where you think you were exposed, and how many days ago. This information is required."
            }), history
        response_text, history = generate(user_reply, history, SYSTEM_PROMPT)
        data = parse_json_from_response(response_text)
        if isinstance(data, dict):
            # Defensive: check if LLM tried to fill with "unknown"
            if is_invalid_answer(data.get("exposure_location_name", "")) or data.get("days_since_exposure") in [None, "", "unknown"]:
                return json.dumps({
                    "awaiting_field": "exposure_followup",
                    "console_output": "Sorry, it's important for public health. Please provide the specific place/venue/city where you think you were exposed, and how many days ago. This information is required."
                }), history
            missing = missing_exposure_fields(data)
            if not missing:
                if "days_since_exposure" not in data or data["days_since_exposure"] is None:
                    date_text = data.get("exposure_date_text", "")
                    data["days_since_exposure"] = (
                        compute_days_ago(date_text) if isinstance(date_text, str) else None
                    )
                try:
                    lat, lon = geocode_location(data["exposure_location_name"])
                except Exception:
                    lat = lon = None
                data["exposure_latitude"] = lat
                data["exposure_longitude"] = lon
                return json.dumps(data), history
            else:
                # Prompt for missing info, with context if available
                if missing == ["location"]:
                    prompt = "Where do you think you were exposed? (Please specify the venue or city. This is required.)"
                elif missing == ["days"]:
                    where = data.get("exposure_location_name", "that location")
                    prompt = f"How many days ago were you at {where}? (This is required.)"
                else:
                    prompt = "Where and when do you think you were exposed? (Please provide both the venue/city and how many days ago. This information is required.)"
                return json.dumps({
                    "awaiting_field": "exposure_followup",
                    "console_output": prompt
                }), history
        else:
            # LLM didn't produce valid JSON, try again
            return json.dumps({
                "awaiting_field": "exposure_followup",
                "console_output": "Sorry, I didn't get that. Where and when do you think you were exposed? (Please provide both venue/city and days ago. This is required.)"
            }), history

    # First prompt construction
    diagnosis = payload.get("diagnosis", "unknown")
    symptoms = payload.get("symptom_summary", "")
    illness_category = payload.get("illness_category", "other").lower()
    days_since_exposure = payload.get("days_since_exposure", None)

    first_message = (
        f"I've been told I might have {diagnosis}, "
        f"with main symptoms: {symptoms}" +
        (f" which began {days_since_exposure} days ago." if days_since_exposure is not None else "") +
        " Can you help figure out where and when I was exposed?"
    )
    response_text, history = generate(first_message, history, SYSTEM_PROMPT)
    data = parse_json_from_response(response_text)
    if isinstance(data, dict):
        if is_invalid_answer(data.get("exposure_location_name", "")) or data.get("days_since_exposure") in [None, "", "unknown"]:
            return json.dumps({
                "awaiting_field": "exposure_followup",
                "console_output": "Sorry, it's important for public health. Please provide the specific place/venue/city where you think you were exposed, and how many days ago. This information is required."
            }), history
        missing = missing_exposure_fields(data)
        if not missing:
            if "days_since_exposure" not in data or data["days_since_exposure"] is None:
                date_text = data.get("exposure_date_text", "")
                data["days_since_exposure"] = (
                    compute_days_ago(date_text) if isinstance(date_text, str) else None
                )
            try:
                lat, lon = geocode_location(data["exposure_location_name"])
            except Exception:
                lat = lon = None
            data["exposure_latitude"] = lat
            data["exposure_longitude"] = lon
            return json.dumps(data), history
        else:
            if missing == ["location"]:
                prompt = "Where do you think you were exposed? (Please specify the venue or city. This is required.)"
            elif missing == ["days"]:
                where = data.get("exposure_location_name", "that location")
                prompt = f"How many days ago were you at {where}? (This is required.)"
            else:
                prompt = "Where and when do you think you were exposed? (Please provide both the venue/city and how many days ago. This information is required.)"
            return json.dumps({
                "awaiting_field": "exposure_followup",
                "console_output": prompt
            }), history
    else:
        return json.dumps({
            "awaiting_field": "exposure_followup",
            "console_output": "Where and when do you think you were exposed? (Please provide both the venue/city and how many days ago. This information is required.)"
        }), history