# agents/care_agent.py
import json
from helpers import generate, parse_json_from_response

AGENT_NAME = "care_agent"
SYSTEM_PROMPT = """
You are care_agent. You receive a JSON report with keys like
final_diagnosis, days_since_symptom_onset, illness_category, etc.
Suggest a list of practical self-care tips tailored to the illness
(e.g. rest, hydration, over-the-counter meds), note typical incubation
periods, and advise clearly when to see a doctor if things worsen.
Respond **ONLY** in JSON:
{
  "self_care_tips": ["…","…"],
  "when_to_seek_help": "…"
}
"""

def run_agent(report_json: str, history: list):
    # generate() actually returns (assistant_message, updated_history)
    response_str, new_history = generate(
        report_json,
        history,
        SYSTEM_PROMPT
    )
    # Try to ensure that if the LLM returns a string with code fencing/formatting, it's clean JSON
    try:
        response_json = parse_json_from_response(response_str)
        if isinstance(response_json, dict):
            return json.dumps(response_json), new_history
        else:
            # Try to parse as JSON
            return json.dumps(json.loads(response_str)), new_history
    except Exception:
        # Fallback
        return json.dumps({
            "self_care_tips": [],
            "when_to_seek_help": "Sorry, could not generate advice."
        }), new_history
