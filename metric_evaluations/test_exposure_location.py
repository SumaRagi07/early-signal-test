#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import io

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
Test Script: Exposure Location Geocoding
Tests the exposure agent's ability to extract location names and geocode them accurately.

This tests ONLY the geocoding component - not the full conversation flow.
The agent receives a user's response to "Where were you exposed?" and must:
1. Extract the location name from natural language
2. Geocode it to lat/lon coordinates
3. Return accurate coordinates within tolerance

Metrics:
- Extraction success rate (could the agent extract a location?)
- Geocoding success rate (did geocoding return coordinates?)
- Geographic accuracy (are coordinates within tolerance of expected?)
- Distance error distribution (how far off are failed cases?)
"""

import sys
import json
from typing import Dict, List
from math import radians, cos, sin, asin, sqrt

# Add parent directory to path
sys.path.insert(0, '/mnt/project')

from agents.exposure_agent import run_agent as run_exposure_agent

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees).
    Returns distance in kilometers.
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    
    return c * r


# ============================================================================
# REAL VERIFIED LOCATIONS
# ============================================================================

# From actual database clusters
OAK_STREET_BEACH_LAT = 41.9043769
OAK_STREET_BEACH_LON = -87.6242374

HYDE_PARK_LAT = 41.8929908
HYDE_PARK_LON = -87.6209561

# Well-known Chicago landmarks (easily verifiable via Google Maps)
MILLENNIUM_PARK_LAT = 41.8826
MILLENNIUM_PARK_LON = -87.6226

NAVY_PIER_LAT = 41.8919
NAVY_PIER_LON = -87.6051

WRIGLEY_FIELD_LAT = 41.9484
WRIGLEY_FIELD_LON = -87.6553

WILLIS_TOWER_LAT = 41.8789
WILLIS_TOWER_LON = -87.6359

LINCOLN_PARK_ZOO_LAT = 41.9212
LINCOLN_PARK_ZOO_LON = -87.6340

OHARE_AIRPORT_LAT = 41.9742
OHARE_AIRPORT_LON = -87.9073

CHICAGO_LOOP_LAT = 41.8781
CHICAGO_LOOP_LON = -87.6298

# NYC landmarks for variety
TIMES_SQUARE_LAT = 40.7580
TIMES_SQUARE_LON = -73.9855

CENTRAL_PARK_LAT = 40.7829
CENTRAL_PARK_LON = -73.9654


# ============================================================================
# TEST CASES
# ============================================================================

TEST_CASES = [
    # ========================================================================
    # CATEGORY 1: SPECIFIC LANDMARKS (Should be highly accurate)
    # ========================================================================
    {
        "category": "Specific Landmark",
        "user_input": "Millennium Park",
        "expected_location_contains": "millennium",
        "expected_lat": MILLENNIUM_PARK_LAT,
        "expected_lon": MILLENNIUM_PARK_LON,
        "tolerance_km": 1.0,
        "notes": "Exact landmark name, no city"
    },
    {
        "category": "Specific Landmark",
        "user_input": "Navy Pier, Chicago",
        "expected_location_contains": "navy",
        "expected_lat": NAVY_PIER_LAT,
        "expected_lon": NAVY_PIER_LON,
        "tolerance_km": 1.0,
        "notes": "Landmark with city"
    },
    {
        "category": "Specific Landmark",
        "user_input": "Wrigley Field in Chicago",
        "expected_location_contains": "wrigley",
        "expected_lat": WRIGLEY_FIELD_LAT,
        "expected_lon": WRIGLEY_FIELD_LON,
        "tolerance_km": 1.0,
        "notes": "Landmark with 'in' preposition"
    },
    {
        "category": "Specific Landmark",
        "user_input": "Oak Street Beach",
        "expected_location_contains": "oak street",
        "expected_lat": OAK_STREET_BEACH_LAT,
        "expected_lon": OAK_STREET_BEACH_LON,
        "tolerance_km": 0.5,
        "notes": "Beach location - real cluster site"
    },
    {
        "category": "Specific Landmark",
        "user_input": "Times Square, New York",
        "expected_location_contains": "times",
        "expected_lat": TIMES_SQUARE_LAT,
        "expected_lon": TIMES_SQUARE_LON,
        "tolerance_km": 1.0,
        "notes": "NYC landmark for variety"
    },
    
    # ========================================================================
    # CATEGORY 2: GENERIC CHAINS WITH NEIGHBORHOOD
    # ========================================================================
    {
        "category": "Chain + Neighborhood",
        "user_input": "Whole Foods in West Loop",
        "expected_location_contains": "whole foods",
        "expected_lat": 41.8825,  # West Loop approximate
        "expected_lon": -87.6500,
        "tolerance_km": 3.0,
        "notes": "Generic chain + specific neighborhood"
    },
    {
        "category": "Chain + Neighborhood",
        "user_input": "Starbucks on Michigan Avenue",
        "expected_location_contains": "starbucks",
        "expected_lat": 41.8870,  # Michigan Ave approximate
        "expected_lon": -87.6240,
        "tolerance_km": 3.0,
        "notes": "Chain + major street"
    },
    {
        "category": "Chain + Neighborhood",
        "user_input": "Chipotle in Lincoln Park",
        "expected_location_contains": "chipotle",
        "expected_lat": 41.9242,  # Lincoln Park
        "expected_lon": -87.6431,
        "tolerance_km": 3.0,
        "notes": "Chain + neighborhood"
    },
    {
        "category": "Chain + Neighborhood",
        "user_input": "McDonald's downtown Chicago",
        "expected_location_contains": "mcdonald",
        "expected_lat": CHICAGO_LOOP_LAT,
        "expected_lon": CHICAGO_LOOP_LON,
        "tolerance_km": 3.0,
        "notes": "Chain + downtown area"
    },
    {
        "category": "Chain + Neighborhood",
        "user_input": "Jewel-Osco in Hyde Park",
        "expected_location_contains": "jewel",
        "expected_lat": HYDE_PARK_LAT,
        "expected_lon": HYDE_PARK_LON,
        "tolerance_km": 2.0,
        "notes": "Regional chain + neighborhood"
    },
    
    # ========================================================================
    # CATEGORY 3: VAGUE/GENERIC DESCRIPTIONS
    # ========================================================================
    {
        "category": "Vague",
        "user_input": "a restaurant in Chinatown",
        "expected_location_contains": "restaurant",
        "expected_lat": 41.8525,  # Chinatown Chicago
        "expected_lon": -87.6321,
        "tolerance_km": 5.0,
        "notes": "Very vague - just 'a restaurant'"
    },
    {
        "category": "Vague",
        "user_input": "the park near my house",
        "expected_location_contains": "park",
        "expected_lat": CHICAGO_LOOP_LAT,  # Will likely default to city center
        "expected_lon": CHICAGO_LOOP_LON,
        "tolerance_km": 10.0,  # Very lenient - no specific location
        "notes": "Extremely vague - no identifiable location"
    },
    {
        "category": "Vague",
        "user_input": "a coffee shop in Wicker Park",
        "expected_location_contains": "coffee",
        "expected_lat": 41.9096,  # Wicker Park
        "expected_lon": -87.6774,
        "tolerance_km": 5.0,
        "notes": "Vague venue + specific neighborhood"
    },
    
    # ========================================================================
    # CATEGORY 4: RECREATIONAL/OUTDOOR LOCATIONS
    # ========================================================================
    {
        "category": "Recreational",
        "user_input": "Lake Michigan beach on the North Side",
        "expected_location_contains": "lake michigan",
        "expected_lat": 41.9278,
        "expected_lon": -87.6369,
        "tolerance_km": 5.0,
        "notes": "Natural feature + general area"
    },
    {
        "category": "Recreational",
        "user_input": "Lincoln Park Zoo",
        "expected_location_contains": "zoo",
        "expected_lat": LINCOLN_PARK_ZOO_LAT,
        "expected_lon": LINCOLN_PARK_ZOO_LON,
        "tolerance_km": 1.0,
        "notes": "Specific attraction"
    },
    {
        "category": "Recreational",
        "user_input": "public swimming pool in South Chicago",
        "expected_location_contains": "pool",
        "expected_lat": 41.7500,  # South Chicago approximate
        "expected_lon": -87.6500,
        "tolerance_km": 10.0,
        "notes": "Generic facility + area"
    },
    
    # ========================================================================
    # CATEGORY 5: WORKPLACES/INDOOR VENUES
    # ========================================================================
    {
        "category": "Workplace",
        "user_input": "O'Hare Airport",
        "expected_location_contains": "o'hare",
        "expected_lat": OHARE_AIRPORT_LAT,
        "expected_lon": OHARE_AIRPORT_LON,
        "tolerance_km": 2.0,
        "notes": "Major transit hub"
    },
    {
        "category": "Workplace",
        "user_input": "my office in the Loop",
        "expected_location_contains": "office",
        "expected_lat": CHICAGO_LOOP_LAT,
        "expected_lon": CHICAGO_LOOP_LON,
        "tolerance_km": 5.0,
        "notes": "Generic workplace + business district"
    },
    {
        "category": "Workplace",
        "user_input": "Willis Tower",
        "expected_location_contains": "willis",
        "expected_lat": WILLIS_TOWER_LAT,
        "expected_lon": WILLIS_TOWER_LON,
        "tolerance_km": 1.0,
        "notes": "Specific building"
    },
    
    # ========================================================================
    # CATEGORY 6: EDGE CASES - CONVERSATIONAL FILLER
    # ========================================================================
    {
        "category": "Edge - Filler",
        "user_input": "I ate at Chipotle on Michigan Avenue",
        "expected_location_contains": "chipotle",
        "expected_lat": 41.8870,
        "expected_lon": -87.6240,
        "tolerance_km": 3.0,
        "notes": "Should strip 'I ate at' filler"
    },
    {
        "category": "Edge - Filler",
        "user_input": "I was at Navy Pier downtown",
        "expected_location_contains": "navy",
        "expected_lat": NAVY_PIER_LAT,
        "expected_lon": NAVY_PIER_LON,
        "tolerance_km": 1.0,
        "notes": "Should strip 'I was at' filler"
    },
    {
        "category": "Edge - Filler",
        "user_input": "I went to the beach at Oak Street",
        "expected_location_contains": "oak",
        "expected_lat": OAK_STREET_BEACH_LAT,
        "expected_lon": OAK_STREET_BEACH_LON,
        "tolerance_km": 1.0,
        "notes": "Should strip 'I went to' filler"
    },
    
    # ========================================================================
    # CATEGORY 7: EDGE CASES - AMBIGUOUS
    # ========================================================================
    {
        "category": "Edge - Ambiguous",
        "user_input": "Central Park",
        "expected_location_contains": "central",
        "expected_lat": CENTRAL_PARK_LAT,  # NYC Central Park (more famous)
        "expected_lon": CENTRAL_PARK_LON,
        "tolerance_km": 10.0,  # Lenient - could be Chicago's Central Park too
        "notes": "Ambiguous - exists in multiple cities"
    },
    {
        "category": "Edge - Ambiguous",
        "user_input": "the airport",
        "expected_location_contains": "airport",
        "expected_lat": OHARE_AIRPORT_LAT,  # Likely defaults to major one
        "expected_lon": OHARE_AIRPORT_LON,
        "tolerance_km": 20.0,  # Very lenient - could be Midway too
        "notes": "Very ambiguous - multiple airports"
    },
]


# ============================================================================
# TEST EXECUTION
# ============================================================================

def run_single_test(test_case: Dict) -> Dict:
    """
    Test a single exposure location extraction and geocoding.
    
    This simulates the exposure agent being called AFTER the user has responded
    to "Where were you exposed?" - so we pass user_input in the payload.
    """
    print(f"\n{'='*70}")
    print(f"[{test_case['category']}] Testing: {test_case['user_input']}")
    print(f"Expected: ~({test_case['expected_lat']:.4f}, {test_case['expected_lon']:.4f})")
    print(f"Tolerance: {test_case['tolerance_km']} km")
    print(f"Notes: {test_case['notes']}")
    
    # Build payload for exposure agent
    # This simulates the orchestrator calling exposure agent with user's response
    # The agent should extract BOTH location and days from this single input
    payload = {
        "user_input": test_case['user_input'] + " 3 days ago",  # Add days to make it complete
        "illness_category": "foodborne",
        "diagnosis": "Food poisoning",
        "symptom_summary": "nausea, vomiting",
        "days_since_exposure": 0  # This is symptom onset, not exposure days
    }
    
    extracted_location = None
    extracted_lat = None
    extracted_lon = None
    location_match = False
    geocode_success = False
    distance_km = None
    within_tolerance = False
    
    try:
        # Call exposure agent
        result_json, _ = run_exposure_agent(json.dumps(payload), [])
        result = json.loads(result_json)
        
        # Extract location data
        extracted_location = result.get("exposure_location_name")
        extracted_lat = result.get("exposure_latitude")
        extracted_lon = result.get("exposure_longitude")
        
        print(f"\nResult:")
        if extracted_location:
            print(f"  Location: {extracted_location}")
            location_match = test_case['expected_location_contains'].lower() in extracted_location.lower()
            
            if extracted_lat is not None and extracted_lon is not None:
                geocode_success = True
                print(f"  Coordinates: ({extracted_lat:.4f}, {extracted_lon:.4f})")
                
                # Calculate distance
                distance_km = haversine_distance(
                    test_case['expected_lat'],
                    test_case['expected_lon'],
                    extracted_lat,
                    extracted_lon
                )
                
                within_tolerance = distance_km <= test_case['tolerance_km']
                
                print(f"  Distance: {distance_km:.2f} km {'✓' if within_tolerance else '✗'}")
            else:
                print(f"  Coordinates: Failed to geocode")
        else:
            print(f"  Location: Failed to extract")
        
        # Status
        if location_match and geocode_success and within_tolerance:
            print(f"\n✅ PASS")
        elif location_match and geocode_success:
            print(f"\n⚠️  PARTIAL (extracted + geocoded, but outside tolerance)")
        elif location_match:
            print(f"\n⚠️  PARTIAL (extracted, but geocoding failed)")
        else:
            print(f"\n❌ FAIL")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    return {
        "category": test_case['category'],
        "user_input": test_case['user_input'],
        "extracted_location": extracted_location,
        "expected_contains": test_case['expected_location_contains'],
        "location_match": location_match,
        "geocode_success": geocode_success,
        "within_tolerance": within_tolerance,
        "distance_km": distance_km,
        "extracted_lat": extracted_lat,
        "extracted_lon": extracted_lon,
        "tolerance_km": test_case['tolerance_km'],
        "full_pass": location_match and geocode_success and within_tolerance
    }


def calculate_metrics(results: List[Dict]) -> Dict:
    """
    Calculate comprehensive geocoding metrics.
    """
    total = len(results)
    
    # Extraction metrics
    extraction_success = sum(1 for r in results if r['extracted_location'] is not None)
    location_match = sum(1 for r in results if r['location_match'])
    
    # Geocoding metrics
    geocode_success = sum(1 for r in results if r['geocode_success'])
    
    # Accuracy metrics
    within_tolerance = sum(1 for r in results if r['within_tolerance'])
    full_pass = sum(1 for r in results if r['full_pass'])
    
    # Distance statistics
    distances = [r['distance_km'] for r in results if r['distance_km'] is not None]
    if distances:
        avg_distance = sum(distances) / len(distances)
        min_distance = min(distances)
        max_distance = max(distances)
        median_distance = sorted(distances)[len(distances)//2]
    else:
        avg_distance = min_distance = max_distance = median_distance = None
    
    # By category breakdown
    categories = {}
    for r in results:
        cat = r['category']
        if cat not in categories:
            categories[cat] = {
                'total': 0,
                'extracted': 0,
                'geocoded': 0,
                'accurate': 0,
                'full_pass': 0
            }
        categories[cat]['total'] += 1
        if r['extracted_location']:
            categories[cat]['extracted'] += 1
        if r['geocode_success']:
            categories[cat]['geocoded'] += 1
        if r['within_tolerance']:
            categories[cat]['accurate'] += 1
        if r['full_pass']:
            categories[cat]['full_pass'] += 1
    
    # Distance error distribution
    error_buckets = {
        '0-1 km': 0,
        '1-3 km': 0,
        '3-5 km': 0,
        '5-10 km': 0,
        '>10 km': 0
    }
    for d in distances:
        if d <= 1:
            error_buckets['0-1 km'] += 1
        elif d <= 3:
            error_buckets['1-3 km'] += 1
        elif d <= 5:
            error_buckets['3-5 km'] += 1
        elif d <= 10:
            error_buckets['5-10 km'] += 1
        else:
            error_buckets['>10 km'] += 1
    
    return {
        "total_tests": total,
        "extraction_success_rate": extraction_success / total,
        "location_match_rate": location_match / total,
        "geocoding_success_rate": geocode_success / total,
        "geographic_accuracy_rate": within_tolerance / total,
        "full_pass_rate": full_pass / total,
        "extraction_success": extraction_success,
        "location_match": location_match,
        "geocode_success": geocode_success,
        "within_tolerance": within_tolerance,
        "full_pass": full_pass,
        "avg_distance_km": avg_distance,
        "min_distance_km": min_distance,
        "max_distance_km": max_distance,
        "median_distance_km": median_distance,
        "by_category": categories,
        "error_distribution": error_buckets
    }


def print_results(results: List[Dict], metrics: Dict):
    """Pretty print comprehensive results."""
    print("\n" + "="*70)
    print("EXPOSURE LOCATION GEOCODING TEST RESULTS")
    print("="*70)
    
    # Summary by result type
    full_pass = [r for r in results if r['full_pass']]
    partial = [r for r in results if r['geocode_success'] and not r['full_pass']]
    extraction_fail = [r for r in results if r['location_match'] and not r['geocode_success']]
    total_fail = [r for r in results if not r['location_match']]
    
    print(f"\n{'='*70}")
    print(f"SUMMARY: {len(full_pass)}/{len(results)} FULL PASS")
    print(f"{'='*70}")
    print(f"✅ Full Pass:           {len(full_pass):>3} (extracted + geocoded + accurate)")
    print(f"⚠️  Partial Pass:        {len(partial):>3} (geocoded but outside tolerance)")
    print(f"⚠️  Extraction Only:     {len(extraction_fail):>3} (extracted but geocoding failed)")
    print(f"❌ Total Fail:          {len(total_fail):>3} (extraction failed)")
    
    # Overall metrics
    print(f"\n{'='*70}")
    print(f"CLASSIFICATION METRICS")
    print(f"{'='*70}")
    print(f"Extraction Success Rate:    {metrics['extraction_success_rate']:>6.1%}  "
          f"({metrics['extraction_success']}/{metrics['total_tests']})")
    print(f"Location Match Rate:        {metrics['location_match_rate']:>6.1%}  "
          f"({metrics['location_match']}/{metrics['total_tests']})")
    print(f"Geocoding Success Rate:     {metrics['geocoding_success_rate']:>6.1%}  "
          f"({metrics['geocode_success']}/{metrics['total_tests']})")
    print(f"Geographic Accuracy Rate:   {metrics['geographic_accuracy_rate']:>6.1%}  "
          f"({metrics['within_tolerance']}/{metrics['total_tests']})")
    print(f"Full Pass Rate:             {metrics['full_pass_rate']:>6.1%}  "
          f"({metrics['full_pass']}/{metrics['total_tests']})")
    
    # Distance statistics
    if metrics['avg_distance_km'] is not None:
        print(f"\n{'='*70}")
        print(f"DISTANCE ERROR STATISTICS")
        print(f"{'='*70}")
        print(f"Average Distance Error:     {metrics['avg_distance_km']:>6.2f} km")
        print(f"Median Distance Error:      {metrics['median_distance_km']:>6.2f} km")
        print(f"Min Distance Error:         {metrics['min_distance_km']:>6.2f} km")
        print(f"Max Distance Error:         {metrics['max_distance_km']:>6.2f} km")
        
        print(f"\nError Distribution:")
        for bucket, count in metrics['error_distribution'].items():
            pct = count / len([r for r in results if r['distance_km'] is not None])
            print(f"  {bucket:10s}  {pct:>6.1%}  ({count} cases)")
    
    # By category performance
    print(f"\n{'='*70}")
    print(f"PERFORMANCE BY CATEGORY")
    print(f"{'='*70}")
    print(f"{'Category':<25} {'Total':<7} {'Extract':<9} {'Geocode':<9} {'Accurate':<10} {'Pass Rate':<10}")
    print(f"{'-'*25} {'-'*7} {'-'*9} {'-'*9} {'-'*10} {'-'*10}")
    
    for cat, stats in sorted(metrics['by_category'].items()):
        extract_rate = stats['extracted'] / stats['total'] if stats['total'] > 0 else 0
        geocode_rate = stats['geocoded'] / stats['total'] if stats['total'] > 0 else 0
        accurate_rate = stats['accurate'] / stats['total'] if stats['total'] > 0 else 0
        pass_rate = stats['full_pass'] / stats['total'] if stats['total'] > 0 else 0
        
        print(f"{cat:<25} {stats['total']:<7} {extract_rate:<9.1%} {geocode_rate:<9.1%} "
              f"{accurate_rate:<10.1%} {pass_rate:<10.1%}")
    
    # Detailed results
    print(f"\n{'='*70}")
    print(f"DETAILED RESULTS")
    print(f"{'='*70}")
    
    if full_pass:
        print(f"\n✅ FULL PASS ({len(full_pass)} cases):")
        for r in full_pass:
            print(f"  [{r['category']}] {r['user_input']}")
            print(f"    → {r['extracted_location']} ({r['distance_km']:.2f} km)")
    
    if partial:
        print(f"\n⚠️  PARTIAL PASS ({len(partial)} cases):")
        for r in partial:
            print(f"  [{r['category']}] {r['user_input']}")
            print(f"    → {r['extracted_location']} ({r['distance_km']:.2f} km, tolerance: {r['tolerance_km']} km)")
    
    if extraction_fail:
        print(f"\n⚠️  EXTRACTION ONLY ({len(extraction_fail)} cases):")
        for r in extraction_fail:
            print(f"  [{r['category']}] {r['user_input']}")
            print(f"    → {r['extracted_location']} (geocoding failed)")
    
    if total_fail:
        print(f"\n❌ TOTAL FAIL ({len(total_fail)} cases):")
        for r in total_fail:
            print(f"  [{r['category']}] {r['user_input']}")
            print(f"    → Extraction failed")
    
    # Key insights
    print(f"\n{'='*70}")
    print(f"KEY INSIGHTS")
    print(f"{'='*70}")
    
    if metrics['full_pass_rate'] >= 0.90:
        print(f"✅ EXCELLENT: {metrics['full_pass_rate']:.1%} full pass rate")
    elif metrics['full_pass_rate'] >= 0.75:
        print(f"✅ GOOD: {metrics['full_pass_rate']:.1%} full pass rate")
    elif metrics['full_pass_rate'] >= 0.60:
        print(f"⚠️  ACCEPTABLE: {metrics['full_pass_rate']:.1%} full pass rate")
    else:
        print(f"❌ NEEDS IMPROVEMENT: {metrics['full_pass_rate']:.1%} full pass rate")
    
    if metrics['extraction_success_rate'] < 0.90:
        print(f"⚠️  LOW EXTRACTION RATE: {metrics['extraction_success_rate']:.1%}")
    
    if metrics['geocoding_success_rate'] < 0.80:
        print(f"⚠️  LOW GEOCODING RATE: {metrics['geocoding_success_rate']:.1%}")
    
    if metrics['geographic_accuracy_rate'] < 0.70:
        print(f"⚠️  LOW GEOGRAPHIC ACCURACY: {metrics['geographic_accuracy_rate']:.1%}")
    
    if metrics['avg_distance_km'] and metrics['avg_distance_km'] > 5:
        print(f"⚠️  HIGH AVERAGE ERROR: {metrics['avg_distance_km']:.2f} km")
    
    print(f"{'='*70}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("EXPOSURE LOCATION GEOCODING TEST")
    print("="*70)
    print(f"Testing {len(TEST_CASES)} location extraction & geocoding cases...")
    print(f"\nTest Categories:")
    print(f"  • Specific Landmarks (high accuracy expected)")
    print(f"  • Chain + Neighborhood (moderate accuracy)")
    print(f"  • Vague Descriptions (low accuracy acceptable)")
    print(f"  • Recreational/Outdoor")
    print(f"  • Workplaces/Indoor")
    print(f"  • Edge Cases (filler text, ambiguous)")
    print("="*70)
    
    results = []
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n[Test {i}/{len(TEST_CASES)}]")
        try:
            result = run_single_test(test_case)
            results.append(result)
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            
            # Add failed result
            results.append({
                "category": test_case['category'],
                "user_input": test_case['user_input'],
                "extracted_location": None,
                "expected_contains": test_case['expected_location_contains'],
                "location_match": False,
                "geocode_success": False,
                "within_tolerance": False,
                "distance_km": None,
                "extracted_lat": None,
                "extracted_lon": None,
                "tolerance_km": test_case['tolerance_km'],
                "full_pass": False
            })
    
    # Calculate and print metrics
    metrics = calculate_metrics(results)
    print_results(results, metrics)
    
    # Exit with appropriate code
    # Pass if: extraction >= 90%, geocoding >= 80%, accuracy >= 70%
    passing = (
        metrics['extraction_success_rate'] >= 0.90 and
        metrics['geocoding_success_rate'] >= 0.80 and
        metrics['geographic_accuracy_rate'] >= 0.70
    )
    
    sys.exit(0 if passing else 1)