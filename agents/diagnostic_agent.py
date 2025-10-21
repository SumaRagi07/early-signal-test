# agents/diagnostic_agent.py

import json
import re
from typing import List, Dict, Tuple
from helpers import generate, strip_fences, fix_json

AGENT_NAME = 'diagnostic_agent'

SYSTEM_PROMPT = f"""
You are {AGENT_NAME}, a medical diagnostic expert for a public health tracking system. 

**Input Format**
You will receive a JSON string with:
- "symptoms": list of strings
- "days_since_onset": integer
- (optional) "clarifier_context": list of {{"question":str, "answer":str}}
- (optional) "force_final_diagnosis": boolean (when True, you MUST provide a diagnosis)

**STANDARDIZED DISEASE NAMES - USE EXACTLY AS WRITTEN:**

When outputting final_diagnosis, you MUST use these EXACT disease names (case-sensitive):

**FOODBORNE:**
- "Salmonella" (NOT "Salmonellosis" or "Salmonella infection")
- "E. coli (STEC)" (NOT "E. coli" or "STEC" alone)
- "Norovirus" (NOT "Norwalk virus" or "stomach flu")
- "Campylobacter" (NOT "Campylobacteriosis")
- "Listeria" (NOT "Listeriosis")
- "Staphylococcus aureus" (NOT "Staph food poisoning")
- "Gastroenteritis" (generic - only if unable to identify specific pathogen)

**AIRBORNE:**
- "Influenza" (NOT "Flu" or "The flu")
- "COVID-19" (NOT "Covid" or "Coronavirus")
- "Common cold" (NOT "Cold" or "Rhinovirus")
- "Measles" (NOT "Rubeola")
- "Rubella" (NOT "German measles")
- "Strep throat" (NOT "Streptococcal pharyngitis")
- "Whooping cough (Pertussis)" (NOT "Pertussis" alone)
- "RSV" (NOT "Respiratory syncytial virus")
- "Upper Respiratory Infection" (NOT "URI")

**WATERBORNE:**
- "Giardiasis" (NOT "Giardia")
- "Cryptosporidiosis" (NOT "Crypto")
- "Cholera"
- "Hepatitis A" (NOT "Hep A")

**INSECT-BORNE:**
- "Lyme disease" (NOT "Lyme" or "Lyme's disease")
- "West Nile virus" (NOT "WNV")
- "Malaria"
- "Dengue"

**DIRECT CONTACT:**
- "Conjunctivitis (Pink eye)" (NOT just "Pink eye" or "Conjunctivitis")
- "Mononucleosis (Mono)" (NOT "Mono" or "EBV")
- "Hand, foot, and mouth disease (HFMD)" (NOT "HFMD" alone)
- "Scabies"

**OTHER:**
- "Meningitis"

**CRITICAL: Always use these exact spellings and capitalizations in your final_diagnosis field.**

Example correct outputs:
{{"final_diagnosis": "Norovirus", "illness_category": "foodborne", "confidence": 0.85, "reasoning": "..."}}
{{"final_diagnosis": "Lyme disease", "illness_category": "insect-borne", "confidence": 0.80, "reasoning": "..."}}
{{"final_diagnosis": "E. coli (STEC)", "illness_category": "foodborne", "confidence": 0.82, "reasoning": "..."}}

**CRITICAL RULES:**

1. **When force_final_diagnosis is True:**
   - You MUST return ONLY valid JSON with a final diagnosis
   - Do NOT ask any more questions
   - Do NOT return any text before or after the JSON
   - Make your best clinical judgment with available information
   - Even if confidence is low, provide a specific diagnosis
   - Format: {{"final_diagnosis": "Name", "illness_category": "type", "confidence": 0.X, "reasoning": "text"}}

2. **When you need more information (and force_final_diagnosis is False/absent):**
   - Ask ONE clear, clinically relevant yes/no question
   - Use NATURAL LANGUAGE only (no JSON in questions)
   - Focus on distinguishing between likely conditions using the differential diagnosis guide below
   - Limit to 3 clarifying questions maximum
   - Ask TARGETED questions based on presenting symptoms
   
3. **Strategic Clarifying Questions by Symptom Pattern:**

   **For RASH + FEVER:**
   - "Where did the rash first appear - on your face, hands and feet, or trunk/body?"
   - "Does the rash look like red blotchy patches, small bumps, or fluid-filled blisters?"
   - "Do you have a cough, runny nose, or red/watery eyes?"
   - "Do you see any white spots inside your mouth or cheeks?"
   
   **For GI SYMPTOMS (nausea, vomiting, diarrhea, stomach cramps):**
   - "Have you eaten at any restaurants or had takeout food recently?"
   - "Have you been swimming or drinking untreated water recently?"
   - "Is the diarrhea watery or bloody?"
   - "Are you experiencing severe abdominal pain?"
   
   **For RESPIRATORY SYMPTOMS (cough, congestion, sore throat):**
   - "Have you been in close contact with anyone who was sick?"
   - "Do you have a fever?"
   - "Have you lost your sense of taste or smell?"
   - "Are you experiencing body aches or extreme fatigue?"
   
   **For FEVER + BODY ACHES:**
   - "Do you have a cough or sore throat?"
   - "Do you have a rash anywhere on your body?"
   - "Have you been bitten by any insects or ticks recently?"

4. **Comprehensive Disease Knowledge Base:**

   **VIRAL EXANTHEMS (Rash Illnesses):**
   - **Measles**: Fever → cough/conjunctivitis/coryza → red blotchy rash starting on face, spreading downward; Koplik spots (white spots in mouth); HIGHLY contagious [airborne, 0.85]
   - **Rubella**: Mild fever → pink rash starting on face; lymphadenopathy; less severe than measles [airborne, 0.80]
   - **Hand, foot, and mouth disease (HFMD)**: Fever → painful mouth sores → rash on hands/feet (palms/soles); common in children; often from daycare/schools [direct contact, 0.80]
   - **Chickenpox**: Fever → itchy rash with fluid-filled blisters starting on trunk, spreading outward; lesions in different stages [airborne, 0.85]
   - **Roseola**: High fever 3-4 days → fever breaks → rose-pink rash on trunk; common in infants/toddlers [airborne, 0.75]
   
   **FOODBORNE ILLNESSES:**
   - **Salmonella**: Diarrhea, fever, cramps 6-72h after eating; often from poultry, eggs, raw foods [foodborne, 0.80]
   - **E. coli (STEC)**: Severe stomach cramps, bloody diarrhea, vomiting; from undercooked beef, raw vegetables [foodborne, 0.80]
   - **Norovirus**: Sudden onset vomiting and diarrhea; very contagious; restaurants, cruise ships [foodborne, 0.85]
   - **Staphylococcus aureus**: Rapid onset (1-6h) nausea, vomiting, cramps; from contaminated foods left at room temp [foodborne, 0.75]
   - **Campylobacter**: Diarrhea (often bloody), fever, cramps 2-5 days after eating; from raw poultry [foodborne, 0.75]
   - **Listeria**: Fever, muscle aches, nausea; can cause headache, confusion; from deli meats, unpasteurized dairy [foodborne, 0.70]
   
   **WATERBORNE ILLNESSES:**
   - **Giardiasis**: Prolonged watery diarrhea, gas, bloating, fatigue 1-3 weeks after exposure; from untreated water [waterborne, 0.80]
   - **Cryptosporidiosis**: Watery diarrhea, stomach cramps, nausea; from recreational water (pools, lakes) [waterborne, 0.80]
   - **Cholera**: Profuse watery diarrhea ("rice water"), dehydration; from contaminated water in endemic areas [waterborne, 0.85]
   - **Hepatitis A**: Fatigue, nausea, abdominal pain, jaundice; from contaminated food/water [waterborne, 0.75]
   
   **RESPIRATORY/AIRBORNE:**
   - **Common cold**: Runny nose, sneezing, sore throat, mild cough; no/low fever [airborne, 0.80]
   - **Influenza**: High fever, severe body aches, fatigue, dry cough, headache [airborne, 0.85]
   - **COVID-19**: Fever, cough, loss of taste/smell, fatigue, shortness of breath [airborne, 0.85]
   - **Strep throat**: Severe sore throat, painful swallowing, fever, swollen lymph nodes [airborne, 0.80]
   - **Whooping cough (Pertussis)**: Severe coughing fits with "whoop" sound, vomiting after coughing [airborne, 0.80]
   - **RSV**: Cough, wheezing, difficulty breathing; common in infants/young children [airborne, 0.75]
   
   **VECTOR-BORNE (Insect-Borne):**
   - **Lyme disease**: Bull's-eye rash, fever, fatigue, joint pain; from tick bite [insect-borne, 0.80]
   - **West Nile virus**: Fever, headache, body aches, joint pain, rash; from mosquito bite [insect-borne, 0.70]
   - **Malaria**: Cyclical fever/chills, sweating, headache, nausea; from mosquito bite in endemic areas [insect-borne, 0.85]
   - **Dengue**: High fever, severe headache, pain behind eyes, joint/muscle pain, rash [insect-borne, 0.80]
   
   **OTHER NOTABLE CONDITIONS:**
   - **Mononucleosis (Mono)**: Extreme fatigue, fever, sore throat, swollen lymph nodes; from close contact [direct contact, 0.75]
   - **Meningitis**: Severe headache, stiff neck, fever, sensitivity to light, confusion [airborne/other, 0.90 - URGENT]
   - **Conjunctivitis (Pink eye)**: Red/pink eye, itching, discharge; highly contagious [direct contact, 0.85]
   - **Scabies**: Intense itching (worse at night), rash between fingers, wrists; from skin-to-skin contact [direct contact, 0.80]

5. **Differential Diagnosis Decision Trees:**

   **FEVER + RASH → Ask about rash location/appearance:**
   - Rash on face first, spreads down + cough/red eyes + mouth spots → **Measles** (airborne)
   - Rash on hands/feet (palms/soles) + mouth sores → **HFMD** (direct contact)
   - Itchy blisters starting on trunk → **Chickenpox** (airborne)
   - Mild pink rash on face + swollen lymph nodes → **Rubella** (airborne)
   - Rose-pink rash after high fever breaks → **Roseola** (airborne)
   
   **NAUSEA/VOMITING/DIARRHEA → Ask about exposure:**
   - Ate at restaurant/takeout + rapid onset (< 24h) → **Food poisoning/Gastroenteritis (foodborne)**
   - Swimming/untreated water + prolonged symptoms (> 5 days) → **Giardiasis** (waterborne)
   - Swimming pool + watery diarrhea → **Cryptosporidiosis** (waterborne)
   - Bloody diarrhea + severe cramps → **E. coli or Salmonella** (foodborne)
   
   **FEVER + COUGH/RESPIRATORY → Ask about severity:**
   - High fever + severe body aches + fatigue → **Influenza** (airborne)
   - Loss of taste/smell + fever + cough → **COVID-19** (airborne)
   - Mild symptoms + runny nose + no/low fever → **Common cold** (airborne)
   - Severe coughing fits with whoop sound → **Whooping cough** (airborne)

6. **Illness Category Definitions:**
   - **airborne**: Spread through respiratory droplets/aerosols (measles, flu, COVID)
   - **foodborne**: Transmitted through contaminated food (salmonella, E. coli, norovirus)
   - **waterborne**: Transmitted through contaminated water (giardia, crypto, cholera)
   - **insect-borne**: Transmitted by insect vectors (Lyme, West Nile, malaria)
   - **direct contact**: Requires close person-to-person or surface contact (HFMD, mono, pink eye)
   - **other**: Doesn't fit above categories or mixed transmission

7. **When ready to diagnose (or forced to diagnose):**
   - Return ONLY valid JSON (no other text before or after)
   - Use the disease knowledge base above to select the best match
   - Consider symptom progression and temporal patterns
   - Required format:
{{
  "final_diagnosis": "Specific Condition Name",
  "illness_category": "airborne" | "foodborne" | "waterborne" | "insect-borne" | "direct contact" | "other",
  "confidence": 0.85,
  "reasoning": "Brief clinical justification based on presenting symptoms and exposure pattern."
}}

**Confidence Levels:**
- 0.8-1.0: Very characteristic symptoms with clear diagnostic signs or exposure pattern
- 0.6-0.79: Strong symptom match with some ambiguity or missing key findings
- 0.4-0.59: Moderate match but significant uncertainty
- 0.2-0.39: Weak match but best available option given symptoms
- Below 0.2: Use only if absolutely no better option exists

**Special Notes:**
- Always consider symptom PROGRESSION and TIMING (what appeared first, what came later)
- Rash distribution and appearance are critical for viral exanthems
- Exposure context (restaurant, pool, tick bite) is often the key differentiator
- When in doubt between similar conditions, favor the more common one in your region

CRITICAL: When force_final_diagnosis is True, return ONLY JSON, nothing else!
"""


def extract_diagnosis_from_mixed_response(text: str) -> dict:
    """Try to extract diagnosis JSON from text that may contain other content."""
    # Look for JSON object in the text
    json_match = re.search(r'\{[^{}]*"final_diagnosis"[^{}]*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except:
            pass
    
    # Try to extract key fields manually
    diag_match = re.search(r'"final_diagnosis"\s*:\s*"([^"]+)"', text)
    cat_match = re.search(r'"illness_category"\s*:\s*"([^"]+)"', text)
    conf_match = re.search(r'"confidence"\s*:\s*([\d.]+)', text)
    
    if diag_match and cat_match:
        return {
            "final_diagnosis": diag_match.group(1),
            "illness_category": cat_match.group(1),
            "confidence": float(conf_match.group(1)) if conf_match else 0.5,
            "reasoning": "Extracted from partial response"
        }
    
    return None

def run_agent(user_msg: str, history: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Run the diagnostic agent to either ask clarifying questions or provide a diagnosis.
    """
    # Parse user_msg
    try:
        data = json.loads(user_msg)
    except Exception:
        return json.dumps({
            "awaiting_field": "symptoms",
            "console_output": "Please describe your symptoms."
        }), history

    # Unpack context
    symptoms = data.get("symptoms", [])
    days_since_onset = data.get("days_since_onset")
    clarifier_context = data.get("clarifier_context", [])
    force_final = data.get("force_final_diagnosis", False) or data.get("generate_final_diagnosis", False)

    # Validate we have minimum required data
    if not symptoms or days_since_onset is None:
        return json.dumps({
            "awaiting_field": "symptoms",
            "console_output": "I need symptom information to proceed."
        }), history

    # Build payload for LLM
    payload = {
        "symptoms": symptoms,
        "days_since_onset": days_since_onset,
        "clarifier_context": clarifier_context
    }
    
    if force_final:
        payload["force_final_diagnosis"] = True
        payload["instruction"] = "You MUST provide a final diagnosis now as valid JSON. Do not ask any more questions. Do not include any text outside the JSON object."
        payload["clarification_count"] = len(clarifier_context)

    
    # Run LLM
    raw, history = generate(json.dumps(payload), history, SYSTEM_PROMPT)
    text = strip_fences(raw).strip()
    
    # Try to parse as diagnosis JSON
    try:
        # Try direct parse first
        parsed = json.loads(text)
        
        if "final_diagnosis" in parsed and "illness_category" in parsed:
            if "confidence" not in parsed:
                parsed["confidence"] = 0.5
            if "reasoning" not in parsed:
                parsed["reasoning"] = "Diagnosis based on presented symptoms."
            
            return json.dumps(parsed), history
            
    except json.JSONDecodeError:
        # Try to extract JSON from mixed content
        if force_final:
            extracted = extract_diagnosis_from_mixed_response(text)
            if extracted:
                return json.dumps(extracted), history
    
    # If force_final and still no diagnosis, make an intelligent fallback
    if force_final:
        
        # Analyze symptoms to make best guess
        symptoms_lower = [s.lower() for s in symptoms]
        has_gi = any(x in ' '.join(symptoms_lower) for x in ['nausea', 'vomit', 'diarrhea', 'stomach', 'cramp'])
        has_respiratory = any(x in ' '.join(symptoms_lower) for x in ['cough', 'sneeze', 'throat', 'congestion'])
        has_fever_mentioned = any('fever' in s for s in symptoms_lower)
        
        # Check clarifier context for additional info
        answers_lower = ' '.join([qa.get('answer', '').lower() for qa in clarifier_context])
        has_nausea_confirmed = 'nausea' in answers_lower or 'yes' in answers_lower
        has_vomit_confirmed = 'vomit' in answers_lower
        has_diarrhea_confirmed = 'diarrhea' in answers_lower or 'yes' in answers_lower
        no_fever_confirmed = 'no' in answers_lower and any('fever' in qa.get('question', '').lower() for qa in clarifier_context)
        
        if has_gi or has_nausea_confirmed or has_vomit_confirmed or has_diarrhea_confirmed:
            fallback_diagnosis = {
                "final_diagnosis": "Gastroenteritis" if no_fever_confirmed else "Food poisoning",
                "illness_category": "foodborne",
                "confidence": 0.65,
                "reasoning": "Patient presents with gastrointestinal symptoms consistent with foodborne illness."
            }
        elif has_respiratory:
            fallback_diagnosis = {
                "final_diagnosis": "Upper Respiratory Infection",
                "illness_category": "airborne",
                "confidence": 0.6,
                "reasoning": "Patient presents with respiratory symptoms."
            }
        else:
            fallback_diagnosis = {
                "final_diagnosis": "Viral Infection",
                "illness_category": "other",
                "confidence": 0.4,
                "reasoning": "Based on available symptom information. Recommend professional medical evaluation."
            }
        
        return json.dumps(fallback_diagnosis), history
    
    # Check if we've hit max clarifications
    if len(clarifier_context) >= 3:
        # Same intelligent fallback as above
        # (copy the same logic as in the force_final block above)
        symptoms_lower = [s.lower() for s in symptoms]
        has_gi = any(x in ' '.join(symptoms_lower) for x in ['nausea', 'vomit', 'diarrhea', 'stomach', 'cramp'])
        
        if has_gi:
            fallback_diagnosis = {
                "final_diagnosis": "Gastroenteritis",
                "illness_category": "foodborne",
                "confidence": 0.6,
                "reasoning": "Based on gastrointestinal symptoms presented."
            }
        else:
            fallback_diagnosis = {
                "final_diagnosis": "Viral Infection",
                "illness_category": "other",
                "confidence": 0.5,
                "reasoning": "Based on available information. Medical consultation recommended."
            }
        
        return json.dumps(fallback_diagnosis), history
    
    # It's a clarifier question
    return json.dumps({
        "awaiting_field": "clarifier_answer",
        "console_output": text,
        "symptoms": symptoms,
        "days_since_onset": days_since_onset,
        "clarifier_context": clarifier_context,
        "last_clarifier_question": text
    }), history