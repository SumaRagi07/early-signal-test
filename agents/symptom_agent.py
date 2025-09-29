# agents/symptom_agent.py
import json
import re
from helpers import strip_fences, generate, fix_json

AGENT_NAME = "symptom_agent"
SYSTEM_PROMPT = f"""
You are {AGENT_NAME}, a clinical intake assistant.
From the user's free-form text, extract:

Required Output Format (JSON ONLY):
{{
    "symptoms": ["symptom1", "symptom2"],
    "days_since_onset": integer   // omit if not present
}}

Rules:
1. Return an empty list if no clear symptoms.
2. If the user didn’t specify timing, ask **one** follow-up:  
   “Could you tell me how many days ago your symptoms began?”
3. Use simple phrases (e.g. "sore throat", "fever").
"""

def run_agent(user_msg: str, history: list):
    prompt = f"""
    Extract symptoms and onset timing from:
    User: "{user_msg}"
    """
    raw, history = generate(prompt, history, SYSTEM_PROMPT)
    try:
        cleaned = strip_fences(raw)
        data = fix_json(cleaned)
    except Exception:
        data = {"symptoms": []}

    # Fallback: split if LLM failed to extract any symptoms
    if not data.get("symptoms"):
        tokens = re.split(r',|\band\b', user_msg.lower())
        data["symptoms"] = [t.strip() for t in tokens if t.strip()]

    # If both symptoms and days_since_onset are present, return both
    if data.get("symptoms") and data.get("days_since_onset") is not None:
        return json.dumps({
            "symptoms": data["symptoms"],
            "days_since_onset": data["days_since_onset"]
        }), history

    # If symptoms but no onset
    if data.get("symptoms") and data.get("days_since_onset") is None:
        return json.dumps({
            "symptoms": data["symptoms"],
            "awaiting_field": "days_since_onset",
            "console_output": "Could you tell me how many days ago your symptoms began?"
        }), history

    # If onset but no symptoms
    if data.get("days_since_onset") is not None and (not data.get("symptoms") or not any(data["symptoms"])):
        return json.dumps({
            "days_since_onset": data["days_since_onset"],
            "awaiting_field": "symptoms",
            "console_output": "Can you describe your symptoms?"
        }), history

    # If still nothing, ask for symptoms
    return json.dumps({
        "awaiting_field": "symptoms",
        "console_output": "Can you describe your symptoms?"
    }), history