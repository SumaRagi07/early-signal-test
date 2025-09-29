# agents/diagnoser_agent.py

import json
from typing import Tuple, List, Dict
from helpers import strip_fences, generate
from config import MODEL

SYSTEM_PROMPT = """
You are an expert medical diagnostician. Analyze the case and provide:
1. Specific diagnosis
2. Illness category (pick ONE):
   - foodborne (contaminated food/water)
   - respiratory (airborne transmission) 
   - insect-borne (vector-borne)
   - waterborne (contaminated water)
   - other (non-transmissible/unknown)
3. Clinical justification

Based on inputs:
**Patient Symptoms**: {symptoms}

**Top Candidate Diagnoses**: {diagnoses}

**Clarification Answers**: {clarification_answers}

**Output JSON Format**:
{{
  "diagnosis": "most_likely_condition",
  "confidence": 0.0-1.0,
  "illness_category": "foodborne",
  "reason": "clinical_justification"
}}
"""

def run_agent(clarification_context: Dict, history: List[Dict]) -> Tuple[str, List[Dict]]:
    """Simplified diagnosis agent with robust error handling"""
    
    # 1. Safely unpack input (with defaults)
    input_data = json.loads(clarification_context) if isinstance(clarification_context, str) else clarification_context
    
    symptoms = ", ".join(input_data.get("original_symptoms", ["Unknown symptoms"]))
    matches = input_data.get("matches", [])
    diagnoses = [m.get("id", "Unknown") for m in matches[:3]]
    
    # 2. Build clarification text
    qa_pairs = input_data.get("question_answer_pairs", [])
    clarifications = "\n".join(
        f"- Q: {qa.get('question', '?')}\n  A: {str(qa.get('answer', 'No answer'))}"
        for qa in qa_pairs
    ) or "No additional clarifications"

    # 3. Generate the prompt
    prompt = SYSTEM_PROMPT.format(
        symptoms=symptoms,
        diagnoses=", ".join(diagnoses),
        clarification_answers=clarifications
    )

    # 4. Get LLM response
    try:
        response, new_history = generate(
            user_message=prompt,
            history=history,
            system_prompt="You must return valid JSON with diagnosis, confidence, and reason fields"
        )
        response_text = response.text if hasattr(response, 'text') else str(response)
        diagnosis_json = strip_fences(response_text)
        
        # 5. Validate JSON structure
        result = json.loads(diagnosis_json)
        required = ["diagnosis", "confidence", "reason", "illness_category"]
        if not all(k in result for k in required):
            raise ValueError("Missing required fields")
        
        # Validate category
        if result["illness_category"] not in {"foodborne", "respiratory", "insect-borne", "waterborne", "other"}:
            result["illness_category"] = "other"
            
        return json.dumps(result), new_history
        
    except Exception as e:
        # Fallback to top match if analysis fails
        top_match = matches[0] if matches else {"id": "Unknown", "score": 0.7}
        return json.dumps({
            "diagnosis": top_match.get("id"),
            "confidence": top_match.get("score", 0.7) * 0.9,
            "reason": f"Fallback diagnosis: {str(e)}",
            "illness_category": "other"
        }), history