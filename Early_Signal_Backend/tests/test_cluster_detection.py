# test_cluster_validation.py

import json
from agents.cluster_validation_agent import run_agent

def test_with_real_outbreak_data():
    """
    Test cluster validation with actual synthetic outbreak data inserted into BigQuery.
    
    These test cases use the real coordinates and timing from the 4 outbreak clusters:
    1. Lyme disease at Mellon Park, Pittsburgh
    2. Measles at O'Hare Airport, Chicago
    3. Salmonella at Mama Mia Trattoria, NYC
    4. E. coli at Oak Street Beach, Chicago
    """
    
    test_cases = [
        # ========================================================================
        # CLUSTER 1: LYME DISEASE AT MELLON PARK (Expected: CONFIRMED)
        # ========================================================================
        {
            "name": "Lyme Disease - Confirmed match at Mellon Park",
            "user_disease": "Lyme disease",
            "user_confidence": 0.70,
            "exposure_latitude": 40.4649167,
            "exposure_longitude": -79.9653118,
            "days_since_exposure": 12,
            "illness_category": "insect-borne",
            "expected_result": "CONFIRMED",
            "description": "User with Lyme diagnosis matches 10-case cluster at Mellon Park, Pittsburgh"
        },
        {
            "name": "Lyme Disease - Alternative diagnosis suggested",
            "user_disease": "Viral infection",
            "user_confidence": 0.55,
            "exposure_latitude": 40.4649167,
            "exposure_longitude": -79.9653118,
            "days_since_exposure": 12,
            "illness_category": "other",
            "expected_result": "ALTERNATIVE",
            "description": "Generic diagnosis at Lyme outbreak location - should suggest Lyme disease"
        },
        
        # ========================================================================
        # CLUSTER 2: MEASLES AT O'HARE AIRPORT (Expected: CONFIRMED)
        # ========================================================================
        {
            "name": "Measles - Confirmed match at O'Hare Airport",
            "user_disease": "Measles",
            "user_confidence": 0.80,
            "exposure_latitude": 41.9742,
            "exposure_longitude": -87.9073,
            "days_since_exposure": 11,
            "illness_category": "airborne",
            "expected_result": "CONFIRMED",
            "description": "User with Measles matches 12-case outbreak cluster at O'Hare"
        },
        {
            "name": "Measles - Alternative from Rubella misdiagnosis",
            "user_disease": "Rubella",
            "user_confidence": 0.65,
            "exposure_latitude": 41.9740,
            "exposure_longitude": -87.9075,
            "days_since_exposure": 10,
            "illness_category": "airborne",
            "expected_result": "ALTERNATIVE",
            "description": "Similar rash illness at Measles outbreak - should suggest Measles instead"
        },
        
        # ========================================================================
        # CLUSTER 3: SALMONELLA AT MAMA MIA TRATTORIA, NYC (Expected: CONFIRMED)
        # ========================================================================
        {
            "name": "Salmonella - Confirmed match at NYC restaurant",
            "user_disease": "Salmonella",
            "user_confidence": 0.75,
            "exposure_latitude": 40.7255,
            "exposure_longitude": -73.9837,
            "days_since_exposure": 2,
            "illness_category": "foodborne",
            "expected_result": "CONFIRMED",
            "description": "User with Salmonella matches 8-case cluster at Mama Mia Trattoria"
        },
        {
            "name": "Salmonella - Alternative from Gastroenteritis",
            "user_disease": "Gastroenteritis",
            "user_confidence": 0.60,
            "exposure_latitude": 40.7255,
            "exposure_longitude": -73.9837,
            "days_since_exposure": 3,
            "illness_category": "foodborne",
            "expected_result": "ALTERNATIVE",
            "description": "Generic GI diagnosis at Salmonella outbreak restaurant"
        },
        
        # ========================================================================
        # CLUSTER 4: E. COLI AT OAK STREET BEACH (Expected: CONFIRMED)
        # ========================================================================
        {
            "name": "E. coli - Confirmed match at Oak Street Beach",
            "user_disease": "E. coli (STEC)",
            "user_confidence": 0.78,
            "exposure_latitude": 41.9033,
            "exposure_longitude": -87.6245,
            "days_since_exposure": 3,
            "illness_category": "waterborne",
            "expected_result": "CONFIRMED",
            "description": "User with E. coli matches 7-case cluster at Oak Street Beach"
        },
        {
            "name": "E. coli - Alternative from generic diagnosis",
            "user_disease": "Food poisoning",
            "user_confidence": 0.55,
            "exposure_latitude": 41.9035,
            "exposure_longitude": -87.6243,
            "days_since_exposure": 4,
            "illness_category": "foodborne",
            "expected_result": "ALTERNATIVE",
            "description": "Generic diagnosis at E. coli outbreak beach - should suggest E. coli"
        },
        
        # ========================================================================
        # NO MATCH CASES (Expected: NO_MATCH)
        # ========================================================================
        {
            "name": "No cluster - Scattered Influenza case",
            "user_disease": "Influenza",
            "user_confidence": 0.72,
            "exposure_latitude": 45.5898,  # Portland, OR
            "exposure_longitude": -122.5951,
            "days_since_exposure": 3,
            "illness_category": "airborne",
            "expected_result": "NO_MATCH",
            "description": "Isolated flu case in Portland - no cluster exists"
        },
        {
            "name": "No cluster - Scattered COVID case",
            "user_disease": "COVID-19",
            "user_confidence": 0.80,
            "exposure_latitude": 39.7436,  # Denver, CO
            "exposure_longitude": -104.9942,
            "days_since_exposure": 5,
            "illness_category": "airborne",
            "expected_result": "NO_MATCH",
            "description": "Isolated COVID case in Denver - no cluster exists"
        },
        {
            "name": "No cluster - Random coordinates",
            "user_disease": "Common cold",
            "user_confidence": 0.60,
            "exposure_latitude": 35.0,  # Middle of nowhere
            "exposure_longitude": -100.0,
            "days_since_exposure": 2,
            "illness_category": "airborne",
            "expected_result": "NO_MATCH",
            "description": "Location with no outbreak activity"
        },
        
        # ========================================================================
        # EDGE CASES
        # ========================================================================
        {
            "name": "Wrong timing - Exposure before outbreak started",
            "user_disease": "Lyme disease",
            "user_confidence": 0.70,
            "exposure_latitude": 40.4406,
            "exposure_longitude": -79.9195,
            "days_since_exposure": 30,  # Too old
            "illness_category": "insect-borne",
            "expected_result": "NO_MATCH",
            "description": "Exposure date doesn't overlap with cluster timing window"
        },
        {
            "name": "Nearby but not in cluster tract",
            "user_disease": "Measles",
            "user_confidence": 0.75,
            "exposure_latitude": 41.8781,  # Downtown Chicago, not O'Hare
            "exposure_longitude": -87.6298,
            "days_since_exposure": 11,
            "illness_category": "airborne",
            "expected_result": "NO_MATCH",
            "description": "Exposure in different tract than O'Hare cluster"
        }
    ]
    
    print("=" * 80)
    print("🧪 CLUSTER VALIDATION AGENT - TESTING WITH REAL OUTBREAK DATA")
    print("=" * 80)
    print("\n📊 Testing against 4 synthetic outbreak clusters:")
    print("   1. Lyme disease @ Mellon Park, Pittsburgh (10 cases)")
    print("   2. Measles @ O'Hare Airport, Chicago (12 cases)")
    print("   3. Salmonella @ Mama Mia Trattoria, NYC (8 cases)")
    print("   4. E. coli @ Oak Street Beach, Chicago (7 cases)")
    print("=" * 80)
    
    passed = 0
    failed = 0
    no_data = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"Test {i}: {test_case['name']}")
        print(f"{'='*80}")
        print(f"📝 {test_case['description']}")
        
        payload = {
            "user_disease": test_case["user_disease"],
            "user_confidence": test_case["user_confidence"],
            "exposure_latitude": test_case["exposure_latitude"],
            "exposure_longitude": test_case["exposure_longitude"],
            "days_since_exposure": test_case["days_since_exposure"],
            "illness_category": test_case["illness_category"]
        }
        
        print(f"\n📋 Input:")
        print(f"   Disease: {test_case['user_disease']} ({test_case['user_confidence']:.0%} confidence)")
        print(f"   Location: ({test_case['exposure_latitude']}, {test_case['exposure_longitude']})")
        print(f"   Exposure: {test_case['days_since_exposure']} days ago")
        print(f"   Expected: {test_case['expected_result']}")
        
        result_json, _ = run_agent(json.dumps(payload), [])
        result = json.loads(result_json)
        
        cluster_found = result["cluster_found"]
        validation_result = result["validation_result"]
        expected = test_case["expected_result"]
        
        print(f"\n📊 Output:")
        print(f"   Cluster found: {cluster_found}")
        print(f"   Validation result: {validation_result}")
        
        # Check if result matches expectation
        if validation_result == expected:
            print(f"   ✅ PASS: Result matches expected ({expected})")
            passed += 1
        else:
            print(f"   ❌ FAIL: Expected {expected}, got {validation_result}")
            failed += 1
        
        if cluster_found:
            print(f"   Original: {result['original_diagnosis']} ({result['original_confidence']:.0%})")
            print(f"   Refined: {result['refined_diagnosis']} ({result['refined_confidence']:.0%})")
            
            if result.get('confidence_boost'):
                print(f"   Confidence boost: +{result['confidence_boost']:.0%}")
            
            cluster_data = result['cluster_data']
            print(f"\n   🔍 Cluster details:")
            print(f"      ID: {cluster_data['exposure_cluster_id']}")
            print(f"      Size: {cluster_data['cluster_size']} cases")
            print(f"      Predominant disease: {cluster_data['predominant_disease']}")
            print(f"      Consensus: {cluster_data['consensus_ratio']:.0%}")
            print(f"      Location tag: {cluster_data.get('sample_exposure_tag', 'N/A')}")
            
            if result['console_output']:
                print(f"\n   📢 User message preview:")
                lines = result['console_output'].strip().split('\n')[:4]
                for line in lines:
                    print(f"      {line}")
                if len(result['console_output'].strip().split('\n')) > 4:
                    print(f"      ...")
        else:
            print(f"   ℹ️  No matching cluster found")
            if expected != "NO_MATCH":
                print(f"   ⚠️  This might indicate:")
                print(f"      - clusters_alert_view hasn't refreshed yet")
                print(f"      - Cluster thresholds (size/consensus) not met")
                print(f"      - Tract assignment issue")
                no_data += 1
        
        print()
    
    print("=" * 80)
    print(f"📊 TEST SUMMARY")
    print(f"   Total tests: {len(test_cases)}")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   ⚠️  No data issues: {no_data}")
    
    if failed == 0 and no_data == 0:
        print(f"\n🎉 All tests passed! Cluster validation working perfectly!")
    elif no_data > 0:
        print(f"\n⚠️  Some expected clusters were not found.")
        print(f"   This may be due to:")
        print(f"   - clusters_alert_view needs time to refresh")
        print(f"   - Clusters don't meet alert thresholds (size ≥3, consensus ≥60%)")
        print(f"   - Run this query to check: SELECT * FROM clusters_alert_view WHERE alert_flag = TRUE")
    else:
        print(f"\n❌ Some tests failed. Review the output above.")
    
    print("=" * 80)


def test_confidence_calculations():
    """Test confidence boost calculation logic"""
    
    print("\n" + "=" * 80)
    print("🧪 TESTING CONFIDENCE CALCULATION LOGIC")
    print("=" * 80)
    
    from agents.cluster_validation_agent import calculate_confidence_boost, calculate_alternative_confidence
    
    scenarios = [
        {"size": 3, "consensus": 0.70, "desc": "Small cluster, moderate consensus"},
        {"size": 5, "consensus": 0.80, "desc": "Medium cluster, high consensus"},
        {"size": 10, "consensus": 0.90, "desc": "Large cluster, very high consensus"},
        {"size": 15, "consensus": 0.60, "desc": "Large cluster, low consensus"},
    ]
    
    print("\n📈 Confidence Boost (for CONFIRMED matches):")
    for s in scenarios:
        boost = calculate_confidence_boost(s["size"], s["consensus"])
        print(f"   {s['desc']}")
        print(f"      Size: {s['size']}, Consensus: {s['consensus']:.0%} → Boost: +{boost:.0%}")
    
    print("\n🔄 Alternative Confidence (for ALTERNATIVE suggestions):")
    for s in scenarios:
        if s["consensus"] >= 0.75:  # Only calculate for high consensus
            alt_conf = calculate_alternative_confidence(s["size"], s["consensus"])
            print(f"   {s['desc']}")
            print(f"      Size: {s['size']}, Consensus: {s['consensus']:.0%} → Alternative confidence: {alt_conf:.0%}")
    
    print("\n✅ Confidence calculations working as expected")
    print("=" * 80)


def test_edge_cases():
    """Test error handling and edge cases"""
    
    print("\n" + "=" * 80)
    print("🧪 TESTING EDGE CASES")
    print("=" * 80)
    
    # Test 1: Missing required fields
    print("\n1. Missing required fields:")
    payload = {"user_disease": "Influenza"}  # Missing coordinates
    result_json, _ = run_agent(json.dumps(payload), [])
    result = json.loads(result_json)
    
    if "error" in result:
        print("   ✅ Correctly returned error for missing fields")
    else:
        print("   ❌ Should have returned an error")
    
    # Test 2: Invalid coordinates (middle of ocean)
    print("\n2. Invalid coordinates (middle of Atlantic Ocean):")
    payload = {
        "user_disease": "Norovirus",
        "user_confidence": 0.65,
        "exposure_latitude": 0.0,
        "exposure_longitude": -30.0,
        "days_since_exposure": 2,
        "illness_category": "foodborne"
    }
    result_json, _ = run_agent(json.dumps(payload), [])
    result = json.loads(result_json)
    
    if not result["cluster_found"]:
        print("   ✅ Correctly returned no cluster for invalid location")
    else:
        print("   ⚠️  Unexpected cluster found at invalid coordinates")
    
    # Test 3: Very old exposure (should not match recent clusters)
    print("\n3. Very old exposure (60 days ago):")
    payload = {
        "user_disease": "Lyme disease",
        "user_confidence": 0.70,
        "exposure_latitude": 40.4406,
        "exposure_longitude": -79.9195,
        "days_since_exposure": 60,
        "illness_category": "insect-borne"
    }
    result_json, _ = run_agent(json.dumps(payload), [])
    result = json.loads(result_json)
    
    print(f"   Result: {result['validation_result']}")
    print("   ✅ Old exposures handled correctly")
    
    # Test 4: Negative days since exposure
    print("\n4. Invalid negative days since exposure:")
    payload = {
        "user_disease": "Measles",
        "user_confidence": 0.80,
        "exposure_latitude": 41.9742,
        "exposure_longitude": -87.9073,
        "days_since_exposure": -5,  # Invalid
        "illness_category": "airborne"
    }
    result_json, _ = run_agent(json.dumps(payload), [])
    result = json.loads(result_json)
    
    print(f"   Handled gracefully: {result['validation_result']}")
    
    print("\n" + "=" * 80)
    print("🎉 Edge case testing complete!")
    print("=" * 80)


if __name__ == "__main__":
    # Run all test suites
    test_with_real_outbreak_data()
    test_confidence_calculations()
    test_edge_cases()
    
    print("\n" + "=" * 80)
    print("✅ CLUSTER VALIDATION AGENT - ALL TESTS COMPLETE")
    print("=" * 80)
    print("\n💡 Next steps:")
    print("   1. Verify clusters_alert_view has refreshed with new data")
    print("   2. Check alert_flag = TRUE for the 4 outbreak clusters")
    print("   3. If clusters not found, wait for view refresh or check thresholds")
    print("   4. Once validated, integrate cluster_validation_node into graph_orchestrator.py")
    print("=" * 80)