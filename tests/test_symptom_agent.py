# test_symptom_agent.py

import json
from agents.symptom_agent import run_agent

def test_symptom_agent():
    """Test the symptom agent with various inputs"""
    
    # Initialize empty history
    history = []
    
    print("=" * 70)
    print("SYMPTOM AGENT - STANDALONE TEST")
    print("=" * 70)
    
    # Test 1: Initial call (no prior data)
    print("\n[TEST 1] Initial call - user provides symptoms only")
    payload = {
        "user_input": "I have a fever and headache",
        "current_symptoms": [],
        "current_days": None
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 2: User provides complete information (symptoms + days)
    print("\n[TEST 2] User provides symptoms AND days together")
    history = []
    payload = {
        "user_input": "stomach cramps and nausea started 3 days ago",
        "current_symptoms": [],
        "current_days": None
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 3: Follow-up - user provides days after symptoms collected
    print("\n[TEST 3] Follow-up: User provides days (pure number)")
    history = []
    payload = {
        "user_input": "5",
        "current_symptoms": ["fever", "cough"],
        "current_days": None
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 4: Follow-up - user provides days (temporal phrase)
    print("\n[TEST 4] Follow-up: User provides days (yesterday)")
    history = []
    payload = {
        "user_input": "yesterday",
        "current_symptoms": ["sore throat", "runny nose"],
        "current_days": None
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 5: Follow-up - user provides days (phrase)
    print("\n[TEST 5] Follow-up: User provides days (3 days ago)")
    history = []
    payload = {
        "user_input": "3 days ago",
        "current_symptoms": ["vomiting", "diarrhea"],
        "current_days": None
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 6: User provides only timing
    print("\n[TEST 6] User provides only timing (no symptoms)")
    history = []
    payload = {
        "user_input": "2 days ago",
        "current_symptoms": [],
        "current_days": None
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 7: Follow-up - user provides symptoms after days collected
    print("\n[TEST 7] Follow-up: User provides symptoms (have days)")
    history = []
    payload = {
        "user_input": "fever and body aches",
        "current_symptoms": [],
        "current_days": 4
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 8: User provides vague symptoms
    print("\n[TEST 8] User provides vague symptoms")
    history = []
    payload = {
        "user_input": "not feeling well",
        "current_symptoms": [],
        "current_days": None
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 9: Multiple symptoms
    print("\n[TEST 9] User provides multiple detailed symptoms")
    history = []
    payload = {
        "user_input": "I have stomach cramps, nausea, vomiting, and diarrhea",
        "current_symptoms": [],
        "current_days": None
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 10: Edge case - pure number that could be symptom or days
    print("\n[TEST 10] Edge case: Pure number with existing symptoms")
    history = []
    payload = {
        "user_input": "2",
        "current_symptoms": ["headache"],
        "current_days": None
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 11: Last week
    print("\n[TEST 11] Temporal phrase: last week")
    history = []
    payload = {
        "user_input": "last week",
        "current_symptoms": ["cough", "congestion"],
        "current_days": None
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 12: Natural language with everything
    print("\n[TEST 12] Natural language with symptoms and timing")
    history = []
    payload = {
        "user_input": "I've been experiencing severe headaches and dizziness for about 4 days now",
        "current_symptoms": [],
        "current_days": None
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    print("\n" + "=" * 70)
    print("TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_symptom_agent()