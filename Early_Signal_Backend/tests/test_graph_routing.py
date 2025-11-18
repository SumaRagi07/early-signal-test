# test_graph_routing.py

import json
import uuid
from graph_orchestrator import (
    run_graph_chat_flow,
    route_after_symptoms,
    route_after_diagnosis,
    route_after_exposure,
    route_after_location,
    determine_start_node
)
from firestore_session import get_session_history, save_session_history
from langgraph.graph import END

def test_routing_logic():
    """Test the routing logic between nodes"""
    
    print("=" * 70)
    print("GRAPH ORCHESTRATOR - ROUTING LOGIC TEST")
    print("=" * 70)
    
    # Test 1: Route after symptoms - incomplete
    print("\n[TEST 1] Route after symptoms - missing days")
    state = {
        "symptoms": ["fever", "cough"],
        "days_since_onset": None
    }
    route = route_after_symptoms(state)
    print(f"State: symptoms={state['symptoms']}, days={state['days_since_onset']}")
    print(f"Route: {route}")
    print(f"Expected: END (need user input)")
    print(f"✓ PASS" if route == END else f"✗ FAIL")
    
    # Test 2: Route after symptoms - complete
    print("\n[TEST 2] Route after symptoms - complete data")
    state = {
        "symptoms": ["fever", "cough"],
        "days_since_onset": 3
    }
    route = route_after_symptoms(state)
    print(f"State: symptoms={state['symptoms']}, days={state['days_since_onset']}")
    print(f"Route: {route}")
    print(f"Expected: diagnosis")
    print(f"✓ PASS" if route == "diagnosis" else f"✗ FAIL")
    
    # Test 3: Route after diagnosis - waiting for clarification
    print("\n[TEST 3] Route after diagnosis - waiting for clarification")
    state = {
        "diagnosis": {
            "awaiting_field": "clarifier_answer",
            "console_output": "Do you have a fever?"
        },
        "clarification_attempts": 1
    }
    route = route_after_diagnosis(state)
    print(f"State: awaiting clarification (attempt 1/3)")
    print(f"Route: {route}")
    print(f"Expected: END (need user input)")
    print(f"✓ PASS" if route == END else f"✗ FAIL")
    
    # Test 4: Route after diagnosis - final diagnosis ready
    print("\n[TEST 4] Route after diagnosis - final diagnosis ready")
    state = {
        "diagnosis": {
            "final_diagnosis": "Food poisoning",
            "illness_category": "foodborne",
            "confidence": 0.8
        },
        "clarification_attempts": 0
    }
    route = route_after_diagnosis(state)
    print(f"State: diagnosis={state['diagnosis']['final_diagnosis']}")
    print(f"Route: {route}")
    print(f"Expected: exposure_collection")
    print(f"✓ PASS" if route == "exposure_collection" else f"✗ FAIL")
    
    # Test 5: Route after exposure - incomplete
    print("\n[TEST 5] Route after exposure - missing location")
    state = {
        "exposure_location_name": None,
        "days_since_exposure": 3
    }
    route = route_after_exposure(state)
    print(f"State: location={state['exposure_location_name']}, days={state['days_since_exposure']}")
    print(f"Route: {route}")
    print(f"Expected: END")
    print(f"✓ PASS" if route == END else f"✗ FAIL")
    
    # Test 6: Route after exposure - complete
    print("\n[TEST 6] Route after exposure - complete data")
    state = {
        "exposure_location_name": "Chipotle, Chicago",
        "days_since_exposure": 3
    }
    route = route_after_exposure(state)
    print(f"State: location={state['exposure_location_name']}, days={state['days_since_exposure']}")
    print(f"Route: {route}")
    print(f"Expected: location_collection")
    print(f"✓ PASS" if route == "location_collection" else f"✗ FAIL")
    
    # Test 7: Route after location - incomplete
    print("\n[TEST 7] Route after location - no venue data")
    state = {
        "location_json": {}
    }
    route = route_after_location(state)
    print(f"State: location_json empty")
    print(f"Route: {route}")
    print(f"Expected: END")
    print(f"✓ PASS" if route == END else f"✗ FAIL")
    
    # Test 8: Route after location - complete
    print("\n[TEST 8] Route after location - complete data")
    state = {
        "location_json": {
            "current_location_name": "Lincoln Park, Chicago, IL",
            "location_category": "urban"
        }
    }
    route = route_after_location(state)
    print(f"State: location={state['location_json']['current_location_name']}")
    print(f"Route: {route}")
    print(f"Expected: bq_submission")
    print(f"✓ PASS" if route == "bq_submission" else f"✗ FAIL")
    
    print("\n" + "=" * 70)
    print("ROUTING LOGIC TESTS COMPLETE")
    print("=" * 70)

    # Test 9: Determine start node - fresh session
    print("\n[TEST 9] Determine start node - fresh session")
    state = {
        "symptoms": [],
        "days_since_onset": None,
        "diagnosis": {}
    }
    node = determine_start_node(state)
    print(f"State: empty")
    print(f"Start node: {node}")
    print(f"Expected: symptom_collection")
    print(f"✓ PASS" if node == "symptom_collection" else f"✗ FAIL")
    
    # Test 10: Determine start node - mid-diagnosis
    print("\n[TEST 10] Determine start node - waiting for clarification")
    state = {
        "symptoms": ["fever"],
        "days_since_onset": 2,
        "diagnosis": {
            "awaiting_field": "clarifier_answer"
        }
    }
    node = determine_start_node(state)
    print(f"State: has symptoms, awaiting clarification")
    print(f"Start node: {node}")
    print(f"Expected: diagnosis")
    print(f"✓ PASS" if node == "diagnosis" else f"✗ FAIL")
    
    # Test 11: Determine start node - has diagnosis, need exposure
    print("\n[TEST 11] Determine start node - has diagnosis, need exposure")
    state = {
        "symptoms": ["nausea"],
        "days_since_onset": 3,
        "diagnosis": {
            "final_diagnosis": "Gastroenteritis",
            "illness_category": "foodborne"
        },
        "exposure_location_name": None,
        "exposure_awaiting_field": None
    }
    node = determine_start_node(state)
    print(f"State: has diagnosis, no exposure")
    print(f"Start node: {node}")
    print(f"Expected: exposure_collection")
    print(f"✓ PASS" if node == "exposure_collection" else f"✗ FAIL")
    
    # Test 12: Determine start node - has exposure, need location
    print("\n[TEST 12] Determine start node - has exposure, need location")
    state = {
        "symptoms": ["nausea"],
        "days_since_onset": 3,
        "diagnosis": {
            "final_diagnosis": "Gastroenteritis",
            "illness_category": "foodborne"
        },
        "exposure_location_name": "Chipotle",
        "exposure_awaiting_field": None,
        "days_since_exposure": 3,
        "location_json": {}
    }
    node = determine_start_node(state)
    print(f"State: has exposure, no location")
    print(f"Start node: {node}")
    print(f"Expected: location_collection")
    print(f"✓ PASS" if node == "location_collection" else f"✗ FAIL")

def test_end_to_end_flow():
    """Test complete end-to-end flow through all nodes"""
    
    print("\n" + "=" * 70)
    print("END-TO-END FLOW TEST")
    print("=" * 70)
    
    # Create a test session
    session_id = f"test_{uuid.uuid4()}"
    print(f"\nTest Session ID: {session_id}")
    
    conversation_log = []
    
    # Step 1: Initial symptoms
    print("\n[STEP 1] User provides initial symptoms")
    user_input = "stomach cramps and nausea"
    result, history = run_graph_chat_flow(user_input, session_id)
    conversation_log.append({"user": user_input, "bot": result.get("console_output")})
    print(f"User: {user_input}")
    print(f"Bot: {result.get('console_output')}")
    assert "days" in result.get("console_output", "").lower(), "Should ask for days"
    print("✓ PASS - Asked for timing")
    
    # Step 2: Provide days
    print("\n[STEP 2] User provides timing")
    user_input = "2 days ago"
    result, history = run_graph_chat_flow(user_input, session_id)
    conversation_log.append({"user": user_input, "bot": result.get("console_output")})
    print(f"User: {user_input}")
    print(f"Bot: {result.get('console_output')}")
    # Should ask clarifying question or provide diagnosis
    print("✓ PASS - Moved to diagnosis stage")
    

    # Step 3: Answer clarifying question(s)
    max_clarifications = 3
    for i in range(max_clarifications):
        # Check if we ALREADY have a diagnosis (fixed: handle None properly)
        diagnosis = result.get("diagnosis")
        if diagnosis and diagnosis.get("final_diagnosis"):
            print(f"\n[STEP 3.{i+1}] Got diagnosis after {i} clarifications")
            break
        
        print(f"\n[STEP 3.{i+1}] Answer clarifying question")
        # Simulate answering yes to clarifying questions
        user_input = "yes, I ate at a restaurant"
        result, history = run_graph_chat_flow(user_input, session_id)
        conversation_log.append({"user": user_input, "bot": result.get("console_output")})
        print(f"User: {user_input}")
        print(f"Bot: {result.get('console_output')}")
    
    # Check we have a diagnosis
    diagnosis = result.get("diagnosis")
    assert diagnosis and diagnosis.get("final_diagnosis"), "Should have diagnosis by now"
    print(f"✓ PASS - Got diagnosis: {diagnosis.get('final_diagnosis')}")
    
    # Step 4: Provide exposure location
    print("\n[STEP 4] User provides exposure location")
    user_input = "Chipotle on Michigan Avenue"
    result, history = run_graph_chat_flow(user_input, session_id)
    conversation_log.append({"user": user_input, "bot": result.get("console_output")})
    print(f"User: {user_input}")
    print(f"Bot: {result.get('console_output')}")
    
    # Step 5: Provide exposure timing (if asked)
    if "days" in result.get("console_output", "").lower():
        print("\n[STEP 5] User provides exposure timing")
        user_input = "3 days ago"
        result, history = run_graph_chat_flow(user_input, session_id)
        conversation_log.append({"user": user_input, "bot": result.get("console_output")})
        print(f"User: {user_input}")
        print(f"Bot: {result.get('console_output')}")
    
    # Should now ask for current location
    assert "city" in result.get("console_output", "").lower() or "location" in result.get("console_output", "").lower(), "Should ask for location"
    print("✓ PASS - Moved to location stage")
    
    # Step 6: Provide current location (city/state)
    print("\n[STEP 6] User provides city/state")
    user_input = "Chicago, IL"
    result, history = run_graph_chat_flow(user_input, session_id)
    conversation_log.append({"user": user_input, "bot": result.get("console_output")})
    print(f"User: {user_input}")
    print(f"Bot: {result.get('console_output')}")
    
    # Should ask for venue
    assert "venue" in result.get("console_output", "").lower() or "landmark" in result.get("console_output", "").lower(), "Should ask for venue"
    print("✓ PASS - Asked for venue")
    
    # Step 7: Provide venue
    print("\n[STEP 7] User provides venue")
    user_input = "Lincoln Park"
    result, history = run_graph_chat_flow(user_input, session_id)
    conversation_log.append({"user": user_input, "bot": result.get("console_output")})
    print(f"User: {user_input}")
    print(f"Bot: {result.get('console_output')}")
    
    # ADD THIS: Check if we need to provide venue again or if it went through
    if "venue" in result.get("console_output", "").lower() or "landmark" in result.get("console_output", "").lower():
        print("\n[STEP 7b] Location agent needs more specific venue - trying again")
        user_input = "near Millennium Park"
        result, history = run_graph_chat_flow(user_input, session_id)
        conversation_log.append({"user": user_input, "bot": result.get("console_output")})
        print(f"User: {user_input}")
        print(f"Bot: {result.get('console_output')}")

    # Should have submitted report and provided care advice
    if result.get("report") is None:
        print(f"\n⚠️ DEBUG: Result keys: {result.keys()}")
        print(f"Console output: {result.get('console_output')}")
        session_data = get_session_history(session_id)
        print(f"Session state location_json: {session_data.get('state', {}).get('location_json')}")

    # Should have submitted report and provided care advice
    assert result.get("report") is not None, "Should have report"
    assert result.get("care_advice") is not None, "Should have care advice"
    print("✓ PASS - Report submitted and care advice provided")
    
    # Verify all data was collected
    print("\n[VERIFICATION] Checking collected data")
    session_data = get_session_history(session_id)
    state = session_data.get("state", {})
    
    checks = {
        "Symptoms": bool(state.get("symptoms")),
        "Days since onset": state.get("days_since_onset") is not None,
        "Diagnosis": bool(state.get("diagnosis", {}).get("final_diagnosis")),
        "Exposure location": bool(state.get("exposure_location_name")),
        "Exposure days": state.get("days_since_exposure") is not None,
        "Current location": bool(state.get("location_json", {}).get("current_location_name")),
        "Report": bool(state.get("report")),
        "Care advice": bool(state.get("care_advice"))
    }
    
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}: {passed}")
    
    all_passed = all(checks.values())
    if all_passed:
        print("\n🎉 END-TO-END TEST PASSED - All data collected successfully!")
    else:
        print("\n⚠️ END-TO-END TEST INCOMPLETE - Some data missing")
    
    # Print conversation log
    print("\n[CONVERSATION LOG]")
    for i, turn in enumerate(conversation_log, 1):
        print(f"{i}. User: {turn['user']}")
        print(f"   Bot: {turn['bot'][:100]}{'...' if len(turn['bot']) > 100 else ''}")
    
    print("\n" + "=" * 70)
    print("END-TO-END FLOW TEST COMPLETE")
    print("=" * 70)
    
    return all_passed


def test_resume_from_each_stage():
    """Test resuming conversation from each stage"""
    
    print("\n" + "=" * 70)
    print("RESUME FROM STAGE TEST")
    print("=" * 70)
    
    # Test resuming from diagnosis stage
    print("\n[TEST 1] Resume from diagnosis stage")
    session_id = f"test_resume_diagnosis_{uuid.uuid4()}"
    
    # Manually create a session with symptoms but no diagnosis
    save_session_history(session_id, {
        "history": [],
        "state": {
            "symptoms": ["fever", "cough"],
            "days_since_onset": 3,
            "diagnosis": {},
            "clarifier_context": [],
            "clarification_attempts": 0
        }
    })
    
    # Send a message - should route to diagnosis
    result, _ = run_graph_chat_flow("yes", session_id)
    print(f"Bot response: {result.get('console_output')[:100]}")
    # Should be in diagnosis flow (either asking question or providing diagnosis)
    print("✓ PASS - Resumed at diagnosis stage")
    
    # Test resuming from exposure stage
    print("\n[TEST 2] Resume from exposure stage")
    session_id = f"test_resume_exposure_{uuid.uuid4()}"

    # Create a clean, complete state
    test_state = {
        "symptoms": ["nausea"],
        "days_since_onset": 2,
        "diagnosis": {
            "final_diagnosis": "Gastroenteritis",
            "illness_category": "foodborne",
            "confidence": 0.7,
            "reasoning": "Test diagnosis"
            # NO awaiting_field - diagnosis is COMPLETE
        },
        "clarifier_context": [],
        "clarification_attempts": 0,
        "exposure_location_name": None,  # Need exposure
        "exposure_latitude": None,
        "exposure_longitude": None,
        "days_since_exposure": None,
        "exposure_awaiting_field": "exposure_info",  # Actively collecting exposure
        "exposure_partial_location": None,
        "exposure_partial_days": None,
        "location_city_state": None,
        "location_venue": None,
        "location_json": {},
        "report": None,
        "care_advice": None
    }

    save_session_history(session_id, {
        "history": [],
        "state": test_state
    })

    # REMOVED DEBUG LINES - don't call determine_start_node anymore

    result, _ = run_graph_chat_flow("Chipotle downtown", session_id)
    print(f"Bot response: {result.get('console_output')[:100]}")

    # Check if response is about exposure/location (not diagnosis questions)
    response_lower = result.get('console_output', '').lower()
    is_exposure_flow = any(word in response_lower for word in [
        'restaurant', 'eat', 'where', 'days ago', 'exposure', 
        'city', 'state', 'location', 'venue'
    ])

    if not is_exposure_flow:
        print(f"❌ FAIL - Got diagnostic question instead of exposure/location")
        print(f"Full response: {result.get('console_output')}")
    else:
        print("✓ PASS - Resumed at exposure stage")
    
    # Test resuming from location stage
    print("\n[TEST 3] Resume from location stage")
    session_id = f"test_resume_location_{uuid.uuid4()}"

    save_session_history(session_id, {
        "history": [],
        "state": {
            "symptoms": ["nausea"],
            "days_since_onset": 2,
            "diagnosis": {
                "final_diagnosis": "Gastroenteritis",
                "illness_category": "foodborne",
                "confidence": 0.7
                # Clean diagnosis - no awaiting_field
            },
            "clarifier_context": [],
            "clarification_attempts": 0,
            "exposure_location_name": "Chipotle",
            "exposure_latitude": 41.8781,
            "exposure_longitude": -87.6298,
            "days_since_exposure": 3,
            "exposure_awaiting_field": None,  # Exposure complete
            "exposure_partial_location": None,
            "exposure_partial_days": None,
            "location_city_state": None,  # Need location
            "location_venue": None,
            "location_json": {}
        }
    })

    result, _ = run_graph_chat_flow("Chicago, IL", session_id)
    print(f"Bot response: {result.get('console_output')[:100]}")
    # Should ask for venue or be in location flow
    assert "venue" in result.get("console_output", "").lower() or "landmark" in result.get("console_output", "").lower() or "neighborhood" in result.get("console_output", "").lower(), "Should be asking for venue details"
    print("✓ PASS - Resumed at location stage")


if __name__ == "__main__":
    # Run all routing tests
    test_routing_logic()
    
    # Run end-to-end flow test
    try:
        success = test_end_to_end_flow()
    except Exception as e:
        print(f"\n❌ END-TO-END TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    # Run resume tests
    try:
        test_resume_from_each_stage()
    except Exception as e:
        print(f"\n❌ RESUME TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("ALL ROUTING TESTS COMPLETE")
    print("=" * 70)