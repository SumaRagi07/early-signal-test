# helpers.py
"""
Shared helper functions for all agents and the orchestrator.
"""
import json
import re
import sys
from google import genai
from google.genai import types
from config import PROJECT_ID, LOCATION, MODEL
from datetime import datetime, timedelta
import requests

# --- Markdown fence stripper ---
def strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

# --- Chat history serialization helpers ---
def serialize_history(history: list) -> list:
    """
    Converts a list of types.Content to a list of dicts for session storage.
    """
    result = []
    for msg in history:
        # If types.Content object
        if hasattr(msg, 'role') and hasattr(msg, 'parts'):
            part_text = msg.parts[0].text if msg.parts else ""
            result.append({"role": msg.role, "content": part_text})
        # Already a dict
        elif isinstance(msg, dict):
            result.append({"role": msg.get("role"), "content": msg.get("content")})
    return result

def deserialize_history(history: list) -> list:
    """
    Converts a list of dicts (from session) to a list of types.Content for LLM.
    """
    result = []
    for msg in history:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            result.append(types.Content(role=msg["role"], parts=[types.Part.from_text(text=msg["content"])]))
    return result

# --- Gemini chat generate ---
def generate(user_message: str, history: list, system_prompt: str):
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    # Apply custom system prompt
    custom = system_prompt
    # Append user message
    if user_message:
        history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )
    # Configure
    cfg = types.GenerateContentConfig(
        temperature=0.2,
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_ONLY_HIGH"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_ONLY_HIGH"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_LOW_AND_ABOVE"),
        ],
        response_mime_type="text/plain",
        system_instruction=[types.Part.from_text(text=custom)]
    )
    # Stream responses
    resp_text = ""
    for chunk in client.models.generate_content_stream(
        model=MODEL, contents=history, config=cfg
    ):
        resp_text += chunk.text
    # Append model reply to history
    history.append(
        types.Content(role="model", parts=[types.Part.from_text(text=resp_text.strip())])
    )
    return resp_text.strip(), history

# --- JSON extractor ---
def extract_json(raw_text: str):
    clean = strip_fences(raw_text)
    return json.loads(clean)

# --- Date parser (compute days ago) ---
import dateparser

def compute_days_ago(text_date, today=None):
    if not text_date or not isinstance(text_date, str):
        print("⚠️ No valid text_date provided to compute_days_ago.")
        return None

    if not today:
        today = datetime.now()

    text_date = text_date.lower().strip()

    if "over the weekend" in text_date:
        last_sunday = today - timedelta(days=today.weekday() + 1)
        return max((today - last_sunday).days, 0)

    # Normalize phrasing
    text_date = re.sub(r'\b(this past|last|the past|past)\b', '', text_date)
    text_date = re.sub(r'\b(morning|afternoon|evening|night)\b', '', text_date)

    parsed = dateparser.parse(
        text_date,
        settings={
            'PREFER_DATES_FROM': 'past',
            'RELATIVE_BASE': today
        }
    )

    if parsed:
        return max((today - parsed).days, 0)

    print(f"⚠️ Could not parse date: {text_date}")
    return None

def determine_final_diagnosis(top_matches, clarification_answers):
    evidence = {
        "answers": clarification_answers,
        "positive_keywords": ["yes", "y", "true", "present"],
        "negative_keywords": ["no", "n", "false", "absent"]
    }
    scored_matches = []
    for match in top_matches:
        score = match["score"]
        reasoning = []
        if "fever" in match["id"].lower():
            if any("fever" in ans.lower() for ans in clarification_answers):
                score += 0.2
                reasoning.append("Patient confirmed fever")
        scored_matches.append({
            "id": match["id"],
            "final_score": min(1.0, score),
            "reasoning": "; ".join(reasoning) if reasoning else "No additional evidence"
        })
    final_match = max(scored_matches, key=lambda x: x["final_score"])
    return {
        "diagnosis": final_match["id"],
        "confidence": final_match["final_score"],
        "reasoning": final_match["reasoning"] or f"Highest initial score ({final_match['final_score']})"
    }

def geocode_location(location_name):
    try:
        if not location_name:
            return None, None
        cleaned = location_name.replace("’", "'").replace("‘", "'").strip()
        candidates = [cleaned]
        if "," in cleaned:
            candidates.append(cleaned.split(",")[0].strip())
        for query in candidates:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json"},
                headers={"User-Agent": "EarlySignalExposureAgent"}
            )
            data = response.json()
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                return lat, lon
    except Exception as e:
        print(f"Geocoding failed for '{location_name}': {e}")
    return None, None

def parse_json_from_response(text):
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        return json.loads(match.group()) if match else None
    except Exception as e:
        print("❌ Failed to parse JSON:", e)
        return None

def fix_json(response: str) -> dict:
    try:
        return json.loads(response.strip("`").replace("'", '"'))
    except:
        return {"text": response, "error": "auto_fixed"}

def get_input(prompt: str) -> str:
    text = input(prompt).strip()
    if text.lower() in ("quit", "exit"):
        print("👋 Goodbye!")
        sys.exit(0)
    return text

def normalize_agent_response(raw_response: str, response_type: str) -> dict:
    try:
        cleaned = strip_fences(raw_response)
        data = fix_json(cleaned)
        if data is None:
            data = {}
        if response_type == "exposure":
            if not isinstance(data, dict):
                data = {"questions": [str(data)]}
            if "questions" in data and isinstance(data["questions"], str):
                data["questions"] = [data["questions"]]
        if response_type == "location":
            if not isinstance(data, dict):
                data = {"location_name": str(data)}
            normalized = {
                "current_location_name": data.get("location_name") or data.get("location") or data.get("current_location_name"),
                "current_latitude": data.get("latitude") or data.get("lat") or data.get("current_latitude"),
                "current_longitude": data.get("longitude") or data.get("lon") or data.get("current_longitude"),
                "location_category": data.get("location_category")
            }
            data = normalized
        return data
    except Exception as e:
        print(f"⚠️ Normalization error ({response_type}): {str(e)}")
        return {"error": f"Failed to normalize {response_type} response"}