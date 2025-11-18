# test_location_agent.py

import json
from agents.location_agent import run_agent

def test_location_agent():
    """Test the location agent with various inputs"""
    
    # Initialize empty history
    history = []
    
    print("=" * 70)
    print("LOCATION AGENT - STANDALONE TEST")
    print("=" * 70)
    
    # Test 1: Initial call - ask for city/state
    print("\n[TEST 1] Initial call (no prior data)")
    user_input = ""
    result, history = run_agent(user_input, history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 2: User provides city and state
    print("\n[TEST 2] User provides city and state")
    history = []  # Reset
    user_input = "Chicago, IL"
    result, history = run_agent(user_input, history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 3: Follow-up - ask for venue with city/state context
    print("\n[TEST 3] Follow-up asking for venue")
    history = []
    payload = {
        "awaiting_field": "venue",
        "user_input": "near Millennium Park",
        "city_state": "Chicago, IL"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 4: User provides full location in one response
    print("\n[TEST 4] User provides detailed location")
    history = []
    user_input = "New York City, New York"
    result, history = run_agent(user_input, history)
    result_data = json.loads(result)
    print(f"First response: {json.dumps(result_data, indent=2)}")
    
    # Then venue
    if result_data.get("awaiting_field") == "venue":
        payload = {
            "awaiting_field": "venue",
            "user_input": "Times Square",
            "city_state": "New York City, New York"
        }
        result, history = run_agent(json.dumps(payload), history)
        print(f"Second response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 5: User provides neighborhood/area
    print("\n[TEST 5] User provides neighborhood")
    history = []
    payload = {
        "awaiting_field": "venue",
        "user_input": "Lincoln Park neighborhood",
        "city_state": "Chicago, IL"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 6: User provides specific address
    print("\n[TEST 6] User provides specific address")
    history = []
    payload = {
        "awaiting_field": "venue",
        "user_input": "123 Main Street",
        "city_state": "San Francisco, CA"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 7: User provides landmark
    print("\n[TEST 7] User provides landmark")
    history = []
    payload = {
        "awaiting_field": "venue",
        "user_input": "near Navy Pier",
        "city_state": "Chicago, IL"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 8: Vague location
    print("\n[TEST 8] User provides vague location")
    history = []
    payload = {
        "awaiting_field": "venue",
        "user_input": "downtown",
        "city_state": "Boston, MA"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 9: User says "I don't know"
    print("\n[TEST 9] User says 'I don't know' to venue")
    history = []
    payload = {
        "awaiting_field": "venue",
        "user_input": "I don't know",
        "city_state": "Chicago, IL"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 10: International location
    print("\n[TEST 10] International location")
    history = []
    user_input = "Toronto, Ontario, Canada"
    result, history = run_agent(user_input, history)
    result_data = json.loads(result)
    print(f"First response: {json.dumps(result_data, indent=2)}")
    
    if result_data.get("awaiting_field") == "venue":
        payload = {
            "awaiting_field": "venue",
            "user_input": "CN Tower area",
            "city_state": "Toronto, Ontario, Canada"
        }
        result, history = run_agent(json.dumps(payload), history)
        print(f"Second response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 11: Just state (no city)
    print("\n[TEST 11] User provides only state")
    history = []
    user_input = "Illinois"
    result, history = run_agent(user_input, history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    # Test 12: Multiple venues in response
    print("\n[TEST 12] User mentions multiple places")
    history = []
    payload = {
        "awaiting_field": "venue",
        "user_input": "between Wrigley Field and Lincoln Park Zoo",
        "city_state": "Chicago, IL"
    }
    result, history = run_agent(json.dumps(payload), history)
    print(f"Agent Response: {json.dumps(json.loads(result), indent=2)}")
    
    print("\n" + "=" * 70)
    print("TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_location_agent()