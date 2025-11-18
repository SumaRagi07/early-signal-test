# test_diagnostic_agent.py

import json
from agents.diagnostic_agent import run_agent

def test_diagnostic_agent():
    """Test the diagnostic agent with various inputs"""
    
    # Initialize empty history
    history = []
    
    print("=" * 70)
    print("DIAGNOSTIC AGENT - STANDALONE TEST")
    print("=" * 70)
    
    # Test 1: Simple GI symptoms
    print("\n[TEST 1] Simple GI symptoms - should ask clarifying question")
    payload = {
        "symptoms": ["stomach cramps", "nausea"],
        "days_since_onset": 2,
        "clarifier_context": []
    }
    result, history = run_agent(json.dumps(payload), history)
    result_data = json.loads(result)
    print(f"Agent Response: {json.dumps(result_data, indent=2)}")
    print(f"Is asking question: {result_data.get('awaiting_field') == 'clarifier_answer'}")
    
    # Test 2: Clear foodborne case
    print("\n[TEST 2] Clear foodborne symptoms with context")
    history = []
    payload = {
        "symptoms": ["vomiting", "diarrhea", "stomach cramps"],
        "days_since_onset": 1,
        "clarifier_context": [
            {
                "question": "Have you eaten at any restaurants recently?",
                "answer": "yes, I ate at a restaurant yesterday"
            }
        ]
    }
    result, history = run_agent(json.dumps(payload), history)
    result_data = json.loads(result)
    print(f"Agent Response: {json.dumps(result_data, indent=2)}")
    print(f"Has final diagnosis: {'final_diagnosis' in result_data}")
    if 'final_diagnosis' in result_data:
        print(f"Diagnosis: {result_data['final_diagnosis']}")
        print(f"Category: {result_data['illness_category']}")
        print(f"Confidence: {result_data['confidence']}")
    
    # Test 3: Waterborne case
    print("\n[TEST 3] Waterborne symptoms with swimming context")
    history = []
    payload = {
        "symptoms": ["diarrhea", "stomach pain"],
        "days_since_onset": 4,
        "clarifier_context": [
            {
                "question": "Have you been swimming recently?",
                "answer": "yes, I went swimming in a lake 5 days ago"
            }
        ]
    }
    result, history = run_agent(json.dumps(payload), history)
    result_data = json.loads(result)
    print(f"Agent Response: {json.dumps(result_data, indent=2)}")
    if 'final_diagnosis' in result_data:
        print(f"Category should be waterborne: {result_data['illness_category']}")
    
    # Test 4: Respiratory symptoms
    print("\n[TEST 4] Clear respiratory symptoms")
    history = []
    payload = {
        "symptoms": ["cough", "runny nose", "sore throat"],
        "days_since_onset": 3,
        "clarifier_context": []
    }
    result, history = run_agent(json.dumps(payload), history)
    result_data = json.loads(result)
    print(f"Agent Response: {json.dumps(result_data, indent=2)}")
    
    # Test 5: Force final diagnosis (max clarifications reached)
    print("\n[TEST 5] Force final diagnosis - max clarifications")
    history = []
    payload = {
        "symptoms": ["fever", "headache"],
        "days_since_onset": 2,
        "clarifier_context": [
            {"question": "Do you have a cough?", "answer": "no"},
            {"question": "Do you have body aches?", "answer": "yes"},
            {"question": "Have you been around sick people?", "answer": "yes"}
        ],
        "force_final_diagnosis": True
    }
    result, history = run_agent(json.dumps(payload), history)
    result_data = json.loads(result)
    print(f"Agent Response: {json.dumps(result_data, indent=2)}")
    print(f"MUST have final diagnosis: {'final_diagnosis' in result_data}")
    
    # Test 6: Ambiguous GI - should distinguish foodborne vs waterborne
    print("\n[TEST 6] Ambiguous GI - should ask about exposure")
    history = []
    payload = {
        "symptoms": ["nausea", "stomach cramps"],
        "days_since_onset": 3,
        "clarifier_context": []
    }
    result, history = run_agent(json.dumps(payload), history)
    result_data = json.loads(result)
    print(f"Agent Response: {json.dumps(result_data, indent=2)}")
    if result_data.get('awaiting_field') == 'clarifier_answer':
        question = result_data.get('console_output', '').lower()
        print(f"Asking about food/water: {'restaurant' in question or 'eat' in question or 'swim' in question or 'water' in question}")
    
    # Test 7: Progressive clarification (simulate full flow)
    print("\n[TEST 7] Progressive clarification - full flow")
    history = []
    
    # Initial
    payload = {
        "symptoms": ["stomach cramps"],
        "days_since_onset": 2,
        "clarifier_context": []
    }
    result, history = run_agent(json.dumps(payload), history)
    result_data = json.loads(result)
    print(f"Step 1: {result_data.get('console_output', 'Got diagnosis')}")
    
    if result_data.get('awaiting_field') == 'clarifier_answer':
        # Answer first question
        clarifier_context = [
            {
                "question": result_data.get('console_output'),
                "answer": "yes, I have nausea and vomiting"
            }
        ]
        payload = {
            "symptoms": ["stomach cramps"],
            "days_since_onset": 2,
            "clarifier_context": clarifier_context
        }
        result, history = run_agent(json.dumps(payload), history)
        result_data = json.loads(result)
        print(f"Step 2: {result_data.get('console_output', result_data.get('final_diagnosis'))}")
        
        if result_data.get('awaiting_field') == 'clarifier_answer':
            # Answer second question
            clarifier_context.append({
                "question": result_data.get('console_output'),
                "answer": "yes, I ate at a restaurant"
            })
            payload = {
                "symptoms": ["stomach cramps"],
                "days_since_onset": 2,
                "clarifier_context": clarifier_context
            }
            result, history = run_agent(json.dumps(payload), history)
            result_data = json.loads(result)
            print(f"Step 3 (should be diagnosis): {json.dumps(result_data, indent=2)}")
    
    # Test 8: Insufficient data
    print("\n[TEST 8] Insufficient data - no symptoms")
    history = []
    payload = {
        "symptoms": [],
        "days_since_onset": 2,
        "clarifier_context": []
    }
    result, history = run_agent(json.dumps(payload), history)
    result_data = json.loads(result)
    print(f"Agent Response: {json.dumps(result_data, indent=2)}")
    
    # Test 9: Force diagnosis with minimal info (fallback scenario)
    print("\n[TEST 9] Force diagnosis with minimal GI info")
    history = []
    payload = {
        "symptoms": ["stomach pain"],
        "days_since_onset": 1,
        "clarifier_context": [],
        "force_final_diagnosis": True
    }
    result, history = run_agent(json.dumps(payload), history)
    result_data = json.loads(result)
    print(f"Agent Response: {json.dumps(result_data, indent=2)}")
    print(f"Should have fallback diagnosis: {'final_diagnosis' in result_data}")
    
    print("\n" + "=" * 70)
    print("TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_diagnostic_agent()