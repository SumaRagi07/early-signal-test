# agents/clarification_agent.py

import json
from typing import Tuple, List, Dict
from helpers import strip_fences, generate

AGENT_NAME = "clarification_agent"

SYSTEM_PROMPT = f"""
You are {AGENT_NAME}, an expert medical interviewer. Your task is to generate the most 
clinically discriminating questions to differentiate between potential diagnoses.

Input Format:
{{
  "matches": [
    {{"id": "diagnosis_name", "score": 0.95}},
    ...
  ],
  "symptoms": ["symptom1", ...]
}}

Output Format (JSON only):
{{
  "questions": [
    {{
      "text": "question text",
      "clinical_significance": "what this answer indicates",
      "differentiates": ["primary_condition", "secondary_condition"]
    }},
    ...
  ]
}}

Guidelines:
1. Ask 2-3 questions maximum
2. Prioritize questions that best discriminate between the top diagnoses
3. For each question:
   - Specify exactly what clinical feature it tests
   - List which diagnoses it primarily differentiates
4. Never include hardcoded medical rules - derive them dynamically
"""

def run_agent(user_msg: str, history: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Stateless API version.
    Returns a JSON list of questions, or signals completion if all are answered.
    """
    # Parse input
    try:
        data = json.loads(user_msg)
        matches = data.get("matches", [])
        symptoms = data.get("symptoms", [])
        clarifier_answers = data.get("clarifier_answers", [])  # orchestrator may pass this
    except Exception:
        matches, symptoms, clarifier_answers = [], [], []

    # If orchestrator is sending back answers, just pass through (no LLM needed here)
    if "clarifier_questions" in data and len(clarifier_answers) >= len(data["clarifier_questions"]):
        # All questions answered, nothing more to clarify
        return json.dumps({
            "clarifier_complete": True,
            "clarifier_questions": data["clarifier_questions"],
            "clarifier_answers": clarifier_answers
        }), history

    # If no clarifier questions present, generate them now
    descs = [f"{m['id']} (score={m['score']:.2f})" for m in matches]
    user_prompt = (
        f"Patient presents with: {', '.join(symptoms) if symptoms else 'No symptoms reported'}\n"
        f"Possible diagnoses: {', '.join(descs) if descs else 'None'}\n\n"
        "Ask 2–3 focused clinical questions to distinguish these conditions."
    )

    # Call LLM to produce questions (just once per series)
    response_text, new_history = generate(
        user_message=user_prompt,
        history=history,
        system_prompt=SYSTEM_PROMPT
    )
    clean_json = strip_fences(response_text)
    try:
        payload = json.loads(clean_json)
        questions = payload.get("questions", [])
    except Exception:
        # Defensive fallback: no questions parsed
        questions = []

    # Prepare output for orchestrator: list of questions, and which answer is needed next
    if questions:
        next_index = len(clarifier_answers)
        if next_index < len(questions):
            # There are still clarifier questions to be answered
            return json.dumps({
                "awaiting_field": "clarifier_answer",
                "console_output": questions[next_index]["text"],
                "clarifier_questions": questions,
                "clarifier_answers": clarifier_answers,
                "clarifier_index": next_index
            }), new_history
        else:
            # All answered
            return json.dumps({
                "clarifier_complete": True,
                "clarifier_questions": questions,
                "clarifier_answers": clarifier_answers
            }), new_history
    else:
        # No clarifiers, just pass through
        return json.dumps({
            "clarifier_complete": True,
            "clarifier_questions": [],
            "clarifier_answers": []
        }), new_history