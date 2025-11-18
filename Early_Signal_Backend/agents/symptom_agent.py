# agents/symptom_agent.py
import json
import re
from helpers import strip_fences, generate, fix_json

AGENT_NAME = "symptom_agent"
SYSTEM_PROMPT = f"""
You are {AGENT_NAME}, a clinical intake assistant.
From the user's free-form text, extract symptoms and timing.

CRITICAL RULES:
1. Symptoms are medical complaints (fever, cough, pain, nausea, etc.)
2. Timing phrases like "3 days ago", "yesterday" are NOT symptoms
3. Pure numbers like "3" are NOT symptoms
4. If user only provides timing, extract days_since_onset but leave symptoms empty

Required Output Format (JSON ONLY):
{{
    "symptoms": ["symptom1", "symptom2"],  // empty list if none found
    "days_since_onset": integer  // omit if not present
}}

Examples:
- "I have fever and cough" → {{"symptoms": ["fever", "cough"]}}
- "3 days ago" → {{"days_since_onset": 3}}
- "fever started 2 days ago" → {{"symptoms": ["fever"], "days_since_onset": 2}}
"""

def is_temporal_phrase(text):
    """Check if text is purely temporal (not a symptom)"""
    text_lower = text.strip().lower()
    temporal_patterns = [
        r'^\d+$',  # Just a number
        r'^\d+\s*(day|days|week|weeks)(\s+ago)?$',  # "3 days ago"
        r'^(yesterday|today|last week)$',
        r'^(ago|day|days)$'
    ]
    return any(re.match(pattern, text_lower) for pattern in temporal_patterns)


def extract_days_directly(text: str) -> int:
    """
    Directly parse timing from user input without LLM.
    Returns number of days or None if not found.
    """
    text_lower = text.strip().lower()
    
    # Match pure number (most common case when we ask "how many days ago?")
    if re.match(r'^\d+$', text_lower):
        return int(text_lower)
    
    # Match "X days" or "X days ago"
    match = re.search(r'(\d+)\s*days?\s*(ago)?', text_lower)
    if match:
        return int(match.group(1))
    
    # Match "yesterday"
    if 'yesterday' in text_lower:
        return 1
    
    # Match "today"
    if 'today' in text_lower:
        return 0
    
    # Match "last week" or "a week ago"
    if 'last week' in text_lower or 'a week ago' in text_lower:
        return 7
    
    return None


def run_agent(user_msg: str, history: list, current_state: dict = None):
    """Extract symptoms and timing from user input"""
    
    # Parse if it's a JSON payload with state
    if current_state is None:
        try:
            if user_msg.strip().startswith('{'):
                payload = json.loads(user_msg)
                current_state = payload
                user_msg = payload.get("user_input", user_msg)
        except:
            current_state = {}
    
    current_symptoms = current_state.get("current_symptoms", []) if current_state else []
    current_days = current_state.get("current_days")
    
    # DIRECT PARSING: If we have symptoms and are waiting for days, parse directly
    if current_symptoms and current_days is None:
        days = extract_days_directly(user_msg)
        if days is not None:
            # Success! Return complete data without LLM call
            return json.dumps({
                "symptoms": current_symptoms,
                "days_since_onset": days
            }), history
        # If direct parse failed, user might have given more symptoms or unclear input
        # Fall through to LLM
    
    # DIRECT PARSING: If we have days and are waiting for symptoms
    # Just use LLM for symptom extraction, preserve days
    if current_days is not None and not current_symptoms:
        # Use LLM only for symptoms, we already have timing
        pass  # Fall through to LLM
    
    # Build context-aware prompt for LLM
    context = ""
    if current_symptoms and current_days is None:
        context = f"\nWe already have symptoms: {current_symptoms}. User is answering: 'How many days ago did symptoms start?' Extract ONLY days_since_onset."
    elif current_days is not None and not current_symptoms:
        context = f"\nWe already know onset was {current_days} days ago. User is answering: 'What symptoms?' Extract ONLY symptoms."
    
    prompt = f"""
    Extract symptoms and onset timing from:
    User: "{user_msg}"
    {context}
    
    Remember: Timing phrases are NOT symptoms! Numbers alone are NOT symptoms!
    """
    
    raw, history = generate(prompt, history, SYSTEM_PROMPT)
    
    try:
        cleaned = strip_fences(raw)
        data = fix_json(cleaned)
    except Exception:
        data = {}
    
    # Validate and clean symptoms
    if data.get("symptoms"):
        valid_symptoms = [
            s for s in data["symptoms"] 
            if s and not is_temporal_phrase(s)
        ]
        data["symptoms"] = valid_symptoms if valid_symptoms else []
    
    # CRITICAL: Merge with existing state (preserve what we already collected)
    if current_symptoms and not data.get("symptoms"):
        data["symptoms"] = current_symptoms
    
    if current_days is not None and data.get("days_since_onset") is None:
        data["days_since_onset"] = current_days
    
    # Decision tree for what to return
    has_symptoms = bool(data.get("symptoms"))
    has_days = data.get("days_since_onset") is not None
    
    # Success: We have both
    if has_symptoms and has_days:
        return json.dumps({
            "symptoms": data["symptoms"],
            "days_since_onset": data["days_since_onset"]
        }), history
    
    # Have symptoms, need days
    if has_symptoms and not has_days:
        return json.dumps({
            "symptoms": data["symptoms"],
            "awaiting_field": "days_since_onset",
            "console_output": "How many days ago did your symptoms start?"
        }), history
    
    # Have days, need symptoms
    if not has_symptoms and has_days:
        return json.dumps({
            "days_since_onset": data["days_since_onset"],
            "awaiting_field": "symptoms",
            "console_output": "What symptoms are you experiencing?"
        }), history
    
    # Have neither - start fresh
    return json.dumps({
        "awaiting_field": "symptoms",
        "console_output": "Please describe your symptoms."
    }), history