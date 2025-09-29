# agents/diagnostic_agent.py

import json
from typing import List, Dict, Tuple
from helpers import generate, strip_fences

AGENT_NAME = 'diagnostic_agent'
SYSTEM_PROMPT = f"""
You are {AGENT_NAME}, a medical diagnostic expert for a public health tracking system. 

**Input**
You will receive a JSON string with:
- "symptoms": list of strings
- "days_since_onset": integer
- (optional) "clarifier_context": list of {{"question":str, "answer":str}}

Follow STRICT rules:

1. When needing more info:
- Ask ONE clear, clinically relevant question per response
- Use NATURAL LANGUAGE only (no JSON)
- Example: "Are you experiencing any shortness of breath?"

2. When "generate_final_diagnosis" is True and you are ready to diagnose:
   - Return ONLY this JSON (no other text):
{{
  "final_diagnosis": "Condition Name",
  "illness_category": "airborne" | "foodborne" | "waterborne" | "insect-borne" | "other",
  "confidence": 0.00,
  "reasoning": "Concise clinical justification."
}}
"""

def run_agent(user_msg: str, history: List[Dict]) -> Tuple[str, List[Dict]]:
    # Parse user_msg, which may include clarifier_context and/or an explicit step
    try:
        data = json.loads(user_msg)
    except Exception:
        # Defensive: fallback for malformed payload
        return json.dumps({
            "awaiting_field": "symptoms",
            "console_output": "Please describe your symptoms."
        }), history

    # Unpack context
    symptoms = data.get("symptoms", [])
    days_since_onset = data.get("days_since_onset")
    clarifier_context = data.get("clarifier_context", [])
    clarifier_state = data.get("clarifier_state", {})  # orchestrator may use for tracking

    # If this is a user answer to a clarifying question, append to context
    if "last_clarifier_question" in data and "clarifier_answer" in data:
        clarifier_context.append({
            "question": data["last_clarifier_question"],
            "answer": data["clarifier_answer"]
        })

    # Always pass context to LLM
    payload = {
        "symptoms": symptoms,
        "days_since_onset": days_since_onset,
        "clarifier_context": clarifier_context
    }
    # Has orchestrator forced diagnosis? (for stepwise control)
    if data.get("generate_final_diagnosis"):
        payload["generate_final_diagnosis"] = True

    # Run one turn of LLM
    raw, history = generate(json.dumps(payload), history, SYSTEM_PROMPT)
    text = strip_fences(raw).strip()
    
    # Try to parse as diagnosis JSON
    try:
        parsed = json.loads(text)
        if all(k in parsed for k in ("final_diagnosis", "illness_category")):
            return json.dumps(parsed), history
    except json.JSONDecodeError:
        # Not a JSON, so it's a clarifier question (natural language string)
        pass

    # If it's not a diagnosis, treat as follow-up question
    # Save the question for the orchestrator to pass back with the next user answer.
    return json.dumps({
        "awaiting_field": "clarifier_answer",
        "console_output": text,
        "symptoms": symptoms,
        "days_since_onset": days_since_onset,
        "clarifier_context": clarifier_context,
        "last_clarifier_question": text
    }), history