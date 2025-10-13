# test_exposure_agent.py

import json
from agents.exposure_agent import run_agent

def test_exposure_agent():
    """Test the exposure agent with various inputs"""
    
    # Initialize empty history
    history = []
    
    print("=" * 70)
    print("EXPOSURE AGENT - STANDALONE TEST")
    print("=" * 70)
    
    # Test 1: Initial call (no user input)
    print("\n[TEST 1] Initial call from diagnosis node (foodborne)")
    payload = {
        "diagnosis": "Food poisoning",
        "illness_category": "foodborne",
        "symptom_summary": "nausea, vomiting, stomach cramps",
        "days_since_exposure": 2
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 2: User provides complete information
    print("\n[TEST 2] User provides location AND days")
    payload = {
        "diagnosis": "Food poisoning",
        "illness_category": "foodborne",
        "user_input": "I ate at Chipotle on Michigan Avenue 3 days ago"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 3: User provides only location
    print("\n[TEST 3] User provides only location")
    history = []  # Reset history
    payload = {
        "diagnosis": "Food poisoning",
        "illness_category": "foodborne",
        "user_input": "I ate at Whole Foods in Lincoln Park"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 4: Follow-up with days (using partial_location from previous response)
    print("\n[TEST 4] Follow-up: User provides days")
    prev_result = json.loads(result)
    payload = {
        "user_input": "5 days ago",
        "partial_location": prev_result.get("partial_location")
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 5: User provides only days
    print("\n[TEST 5] User provides only days")
    history = []  # Reset history
    payload = {
        "diagnosis": "Gastroenteritis",
        "illness_category": "waterborne",
        "user_input": "4 days ago"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 6: Invalid answer (I don't know)
    print("\n[TEST 6] User says 'I don't know'")
    history = []
    payload = {
        "diagnosis": "Food poisoning",
        "illness_category": "foodborne",
        "user_input": "I don't know"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 7: Natural language with filler
    print("\n[TEST 7] Natural language with filler words")
    history = []
    payload = {
        "diagnosis": "Food poisoning",
        "illness_category": "foodborne",
        "user_input": "I ate at this restaurant called Lou Malnati's in Chicago about 2 days ago"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    print("\n" + "=" * 70)
    print("TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_exposure_agent()