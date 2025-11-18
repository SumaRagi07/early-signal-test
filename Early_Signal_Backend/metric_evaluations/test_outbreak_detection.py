#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import io

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
Test Script: Outbreak Cluster Identification (v3.0 - CORRECTED)
Tests the cluster validation agent's ability to correctly identify and validate against outbreaks.

CORRECTED: Test expectations now match actual cluster data from database
- Hyde Park COVID: 27 cases, 44% consensus → WEAK_MATCH (not CONFIRMED)
- E. coli: 7 cases, 100% consensus → CONFIRMED ✓
- Lyme disease: 7-11 cases, 100% consensus → CONFIRMED ✓
- Times Square Salmonella: 10 cases, 80% consensus → CONFIRMED ✓

Real Clusters in Database (as of Oct 26, 2025):
1. Hyde Park - Airborne (COVID-19 44%, mixed cluster, 27 cases)
2. Oak Street Beach - Waterborne (E. coli 100%, 7 cases)
3. Pittsburgh - Insect-borne (Lyme 100%, 7-11 cases)
4. Times Square - Foodborne (Salmonella 80%, 10 cases)
5. Central Park - Foodborne (Gastroenteritis 100%, 4 cases)
"""

import json
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, '/mnt/project')

from agents.cluster_validation_agent import run_agent as run_cluster_validation

# ============================================================================
# TRACT COORDINATES - From actual database centroids
# ============================================================================

# Hyde Park Chicago (tract 17031081403) - Mixed airborne cluster
HYDE_PARK_LAT = 41.8929908
HYDE_PARK_LON = -87.6209561

# Times Square Manhattan (tract 36061011900) - Salmonella cluster  
TIMES_SQUARE_LAT = 40.758
TIMES_SQUARE_LON = -73.9855

# Pittsburgh (tract 42003070800) - Lyme disease cluster
PITTSBURGH_PARK_LAT = 40.4414481
PITTSBURGH_PARK_LON = -79.9195738

# Oak Street Beach Chicago (tract 17031081202) - E. coli cluster
OAK_STREET_LAT = 41.9043769
OAK_STREET_LON = -87.6242374

# Central Park NYC (tract 36061013700) - Gastroenteritis cluster
CENTRAL_PARK_LAT = 40.7664
CENTRAL_PARK_LON = -73.9797

# ============================================================================
# TEST CASES - CORRECTED based on actual cluster data
# ============================================================================

TEST_CASES = [
    # ========================================================================
    # TRUE POSITIVE - CONFIRMED CASES (High consensus: 80-100%)
    # ========================================================================
    {
        "name": "TP-CONFIRMED: E. coli at Oak Street Beach (Waterborne)",
        "user_disease": "E. coli (STEC)",
        "user_confidence": 0.80,
        "exposure_latitude": OAK_STREET_LAT,
        "exposure_longitude": OAK_STREET_LON,
        "days_since_exposure": 10,  # Oct 13-16 cluster
        "illness_category": "waterborne",
        "expected_cluster_found": True,
        "expected_validation": "CONFIRMED",
        "cluster_disease": "E. coli (STEC)",
        "notes": "Real cluster: 7 cases, 100% E. coli consensus, waterborne"
    },
    {
        "name": "TP-CONFIRMED: Lyme disease at Pittsburgh Park (Insect-borne)",
        "user_disease": "Lyme disease",
        "user_confidence": 0.75,
        "exposure_latitude": PITTSBURGH_PARK_LAT,
        "exposure_longitude": PITTSBURGH_PARK_LON,
        "days_since_exposure": 7,  # Oct 19-21 cluster (recent)
        "illness_category": "insect-borne",
        "expected_cluster_found": True,
        "expected_validation": "CONFIRMED",
        "cluster_disease": "Lyme disease",
        "notes": "Real cluster: 7 cases, 100% Lyme consensus, insect-borne"
    },
    {
        "name": "TP-CONFIRMED: Salmonella at Times Square (Foodborne)",
        "user_disease": "Salmonella",
        "user_confidence": 0.75,
        "exposure_latitude": TIMES_SQUARE_LAT,
        "exposure_longitude": TIMES_SQUARE_LON,
        "days_since_exposure": 12,  # Oct 14-20 cluster
        "illness_category": "foodborne",
        "expected_cluster_found": True,
        "expected_validation": "CONFIRMED",
        "cluster_disease": "Salmonella",
        "notes": "Real cluster: 10 cases, 80% Salmonella consensus, foodborne"
    },
    {
        "name": "TP-CONFIRMED: Gastroenteritis at Central Park (Foodborne)",
        "user_disease": "Gastroenteritis",
        "user_confidence": 0.70,
        "exposure_latitude": CENTRAL_PARK_LAT,
        "exposure_longitude": CENTRAL_PARK_LON,
        "days_since_exposure": 1,  # Oct 25-26 cluster (very recent)
        "illness_category": "foodborne",
        "expected_cluster_found": True,
        "expected_validation": "CONFIRMED",
        "cluster_disease": "Gastroenteritis",
        "notes": "Real cluster: 4 cases, 100% Gastroenteritis consensus, foodborne"
    },
    
    # ========================================================================
    # WEAK MATCH CASES (Low consensus: 30-60%)
    # ========================================================================
    {
        "name": "WEAK_MATCH: COVID-19 at Hyde Park (Low Consensus)",
        "user_disease": "COVID-19",
        "user_confidence": 0.75,
        "exposure_latitude": HYDE_PARK_LAT,
        "exposure_longitude": HYDE_PARK_LON,
        "days_since_exposure": 3,  # Oct 25-26 cluster
        "illness_category": "airborne",
        "expected_cluster_found": True,
        "expected_validation": "WEAK_MATCH",  # 44% consensus, below 60% threshold
        "cluster_disease": "COVID-19",
        "notes": "Mixed cluster: 27 cases, COVID-19 predominant but only 44% consensus"
    },
    {
        "name": "WEAK_MATCH: Chickenpox at Hyde Park (Mixed Cluster)",
        "user_disease": "Chickenpox", 
        "user_confidence": 0.70,
        "exposure_latitude": HYDE_PARK_LAT,
        "exposure_longitude": HYDE_PARK_LON,
        "days_since_exposure": 4,
        "illness_category": "airborne",
        "expected_cluster_found": True,
        "expected_validation": "WEAK_MATCH",  # Not predominant disease
        "cluster_disease": "COVID-19",
        "notes": "User has Chickenpox but COVID-19 predominant (44% consensus)"
    },
    {
        "name": "WEAK_MATCH: Influenza at Hyde Park (Different Disease)",
        "user_disease": "Influenza",
        "user_confidence": 0.70,
        "exposure_latitude": HYDE_PARK_LAT,
        "exposure_longitude": HYDE_PARK_LON,
        "days_since_exposure": 4,
        "illness_category": "airborne",  # Correct category
        "expected_cluster_found": True,
        "expected_validation": "WEAK_MATCH",  # 44% consensus too low for ALTERNATIVE
        "cluster_disease": "COVID-19",
        "notes": "Same category but consensus too low (44%) to suggest alternative"
    },
    
    # ========================================================================
    # ALTERNATIVE DIAGNOSIS CASES (60%+ consensus, different disease)
    # ========================================================================
    {
        "name": "ALTERNATIVE: Norovirus → Salmonella (Same Category)",
        "user_disease": "Norovirus",
        "user_confidence": 0.65,
        "exposure_latitude": TIMES_SQUARE_LAT,
        "exposure_longitude": TIMES_SQUARE_LON,
        "days_since_exposure": 12,
        "illness_category": "foodborne",  # Correct category
        "expected_cluster_found": True,
        "expected_validation": "ALTERNATIVE",  # 80% consensus, same category
        "cluster_disease": "Salmonella",
        "notes": "Strong cluster (80% Salmonella), same category → suggest alternative"
    },
    {
        "name": "ALTERNATIVE: E. coli → Gastroenteritis (Same Category)",
        "user_disease": "E. coli (STEC)",
        "user_confidence": 0.70,
        "exposure_latitude": CENTRAL_PARK_LAT,
        "exposure_longitude": CENTRAL_PARK_LON,
        "days_since_exposure": 1,
        "illness_category": "foodborne",  # Correct category
        "expected_cluster_found": True,
        "expected_validation": "ALTERNATIVE",  # 100% consensus, same category
        "cluster_disease": "Gastroenteritis",
        "notes": "Perfect consensus (100% Gastro), same category → suggest alternative"
    },
    {
        "name": "ALTERNATIVE: Strep throat → COVID-19 (Same Category)",
        "user_disease": "Strep throat",
        "user_confidence": 0.65,
        "exposure_latitude": HYDE_PARK_LAT,
        "exposure_longitude": HYDE_PARK_LON,
        "days_since_exposure": 3,
        "illness_category": "airborne",  # Same category
        "expected_cluster_found": True,
        "expected_validation": "WEAK_MATCH",  # 44% consensus too low even with category match
        "cluster_disease": "COVID-19",
        "notes": "Same category but consensus (44%) below threshold for ALTERNATIVE"
    },
    
    # ========================================================================
    # TRUE NEGATIVE CASES (No cluster exists)
    # ========================================================================
    {
        "name": "TN: Common Cold - Random Chicago Location",
        "user_disease": "Common cold",
        "user_confidence": 0.80,
        "exposure_latitude": 41.85,  # Random location, no cluster
        "exposure_longitude": -87.65,
        "days_since_exposure": 3,
        "illness_category": "airborne",
        "expected_cluster_found": False,
        "expected_validation": "NO_MATCH",
        "cluster_disease": None,
        "notes": "Random location with no outbreak cluster"
    },
    {
        "name": "TN: Influenza - Rural Pennsylvania",
        "user_disease": "Influenza",
        "user_confidence": 0.75,
        "exposure_latitude": 40.0,  # Rural area, no cluster
        "exposure_longitude": -77.5,
        "days_since_exposure": 5,
        "illness_category": "airborne",
        "expected_cluster_found": False,
        "expected_validation": "NO_MATCH",
        "cluster_disease": None,
        "notes": "Individual flu case, not part of tracked outbreak"
    },
    {
        "name": "TN: Norovirus - Random NYC Location",
        "user_disease": "Norovirus",
        "user_confidence": 0.70,
        "exposure_latitude": 40.75,  # Not near any cluster
        "exposure_longitude": -74.0,
        "days_since_exposure": 4,
        "illness_category": "foodborne",
        "expected_cluster_found": False,
        "expected_validation": "NO_MATCH",
        "cluster_disease": None,
        "notes": "Different part of NYC, no cluster"
    },
    {
        "name": "TN: West Nile - Southern California",
        "user_disease": "West Nile virus",
        "user_confidence": 0.65,
        "exposure_latitude": 34.05,  # LA area, no cluster
        "exposure_longitude": -118.25,
        "days_since_exposure": 8,
        "illness_category": "insect-borne",
        "expected_cluster_found": False,
        "expected_validation": "NO_MATCH",
        "cluster_disease": None,
        "notes": "Individual case in California, no outbreak cluster"
    },
    
    # ========================================================================
    # TEMPORAL EDGE CASES
    # ========================================================================
    {
        "name": "TEMPORAL: Oak Street - Recent Exposure (Should Match)",
        "user_disease": "E. coli (STEC)",
        "user_confidence": 0.75,
        "exposure_latitude": OAK_STREET_LAT,
        "exposure_longitude": OAK_STREET_LON,
        "days_since_exposure": 13,  # Oct 13 exposure, cluster Oct 13-16
        "illness_category": "waterborne",
        "expected_cluster_found": True,
        "expected_validation": "CONFIRMED",
        "cluster_disease": "E. coli (STEC)",
        "notes": "Exposure at start of cluster window, should match"
    },
    {
        "name": "TEMPORAL: Oak Street - Too Old (Should Not Match)",
        "user_disease": "E. coli (STEC)",
        "user_confidence": 0.75,
        "exposure_latitude": OAK_STREET_LAT,
        "exposure_longitude": OAK_STREET_LON,
        "days_since_exposure": 35,  # Sep 21, cluster ended Oct 16
        "illness_category": "waterborne",
        "expected_cluster_found": False,  # Outside 30-day window
        "expected_validation": "NO_MATCH",
        "cluster_disease": None,
        "notes": "Exposure too old (35 days), outside temporal window"
    },
    {
        "name": "TEMPORAL: Lyme - Old Cluster (Should Not Match)",
        "user_disease": "Lyme disease",
        "user_confidence": 0.70,
        "exposure_latitude": PITTSBURGH_PARK_LAT,
        "exposure_longitude": PITTSBURGH_PARK_LON,
        "days_since_exposure": 50,  # Way too old
        "illness_category": "insect-borne",
        "expected_cluster_found": False,  # Cluster from Oct 2-9, too old
        "expected_validation": "NO_MATCH",
        "cluster_disease": None,
        "notes": "Old October 2-9 cluster, outside 30-day window"
    },
    
    # ========================================================================
    # SPATIAL EDGE CASES (Adjacent tract testing)
    # ========================================================================
    {
        "name": "SPATIAL: Near Oak Street (Adjacent Tract)",
        "user_disease": "E. coli (STEC)",
        "user_confidence": 0.75,
        "exposure_latitude": 41.9050,  # Slightly offset from cluster center
        "exposure_longitude": -87.6250,
        "days_since_exposure": 13,
        "illness_category": "waterborne",
        "expected_cluster_found": True,  # Should match via adjacent tract
        "expected_validation": "CONFIRMED",
        "cluster_disease": "E. coli (STEC)",
        "notes": "Near cluster center, should match via spatial fuzzy matching"
    },
    {
        "name": "SPATIAL: Far from All Clusters",
        "user_disease": "COVID-19",
        "user_confidence": 0.75,
        "exposure_latitude": 41.95,  # North of all Chicago clusters
        "exposure_longitude": -87.70,
        "days_since_exposure": 3,
        "illness_category": "airborne",
        "expected_cluster_found": False,
        "expected_validation": "NO_MATCH",
        "cluster_disease": None,
        "notes": "Too far from any cluster"
    },
    
    # ========================================================================
    # CATEGORY MATCHING TESTS
    # ========================================================================
    {
        "name": "CATEGORY: Same category boosts alternative confidence",
        "user_disease": "Campylobacter",
        "user_confidence": 0.70,
        "exposure_latitude": TIMES_SQUARE_LAT,
        "exposure_longitude": TIMES_SQUARE_LON,
        "days_since_exposure": 12,
        "illness_category": "foodborne",  # Matches cluster category
        "expected_cluster_found": True,
        "expected_validation": "ALTERNATIVE",  # 80% consensus, same category
        "cluster_disease": "Salmonella",
        "notes": "Category match → higher confidence alternative (base 0.55)"
    },
    {
        "name": "CATEGORY: Wrong category lowers alternative confidence",
        "user_disease": "Common cold",
        "user_confidence": 0.70,
        "exposure_latitude": TIMES_SQUARE_LAT,
        "exposure_longitude": TIMES_SQUARE_LON,
        "days_since_exposure": 12,
        "illness_category": "airborne",  # Wrong! Cluster is foodborne
        "expected_cluster_found": True,
        "expected_validation": "WEAK_MATCH",  # Category mismatch → skeptical
        "cluster_disease": "Salmonella",
        "notes": "Category mismatch (airborne vs foodborne) → WEAK_MATCH despite 80% consensus"
    }
]

# ============================================================================
# TEST EXECUTION
# ============================================================================

def run_single_test(test_case: Dict) -> Dict:
    """
    Run a single test case by directly calling cluster validation agent.
    """
    print(f"\n{'='*80}")
    print(f"Testing: {test_case['name']}")
    print(f"{'='*80}")
    print(f"Expected: Cluster={test_case['expected_cluster_found']}, "
          f"Validation={test_case['expected_validation']}")
    print(f"Location: ({test_case['exposure_latitude']:.4f}, {test_case['exposure_longitude']:.4f})")
    print(f"Disease: {test_case['user_disease']} (Category: {test_case['illness_category']})")
    print(f"Days since exposure: {test_case['days_since_exposure']}")
    print(f"Notes: {test_case['notes']}")
    
    # Build input payload for cluster validation agent
    payload = {
        "user_disease": test_case['user_disease'],
        "user_confidence": test_case['user_confidence'],
        "exposure_latitude": test_case['exposure_latitude'],
        "exposure_longitude": test_case['exposure_longitude'],
        "days_since_exposure": test_case['days_since_exposure'],
        "illness_category": test_case['illness_category']
    }
    
    try:
        # Call cluster validation agent directly
        result_json, _ = run_cluster_validation(json.dumps(payload), [])
        result = json.loads(result_json)
        
        cluster_found = result.get("cluster_found", False)
        validation_result = result.get("validation_result")
        refined_diagnosis = result.get("refined_diagnosis")
        refined_confidence = result.get("refined_confidence")
        original_diagnosis = result.get("original_diagnosis")
        reasoning = result.get("reasoning", "")
        
        print(f"\nActual Result:")
        print(f"  Cluster Found: {cluster_found}")
        print(f"  Validation: {validation_result}")
        print(f"  Refined Diagnosis: {refined_diagnosis}")
        print(f"  Refined Confidence: {refined_confidence:.2%}" if refined_confidence else "  Refined Confidence: N/A")
        print(f"  Reasoning: {reasoning[:150]}..." if len(reasoning) > 150 else f"  Reasoning: {reasoning}")
        
        # For ALTERNATIVE cases, check if category matching affected confidence
        if validation_result == "ALTERNATIVE":
            user_cat = test_case['illness_category']
            cluster_data = result.get("cluster_data", {})
            cluster_cat = cluster_data.get("predominant_category", "")
            
            if user_cat == cluster_cat:
                print(f"  ✓ Category Match: {user_cat} (higher base confidence)")
            else:
                print(f"  ✗ Category Mismatch: user={user_cat}, cluster={cluster_cat} (lower confidence)")
        
    except Exception as e:
        print(f"\n❌ ERROR during test execution: {e}")
        import traceback
        traceback.print_exc()
        
        cluster_found = False
        validation_result = None
        refined_diagnosis = None
        refined_confidence = None
        original_diagnosis = None
    
    # Evaluate correctness
    cluster_match = cluster_found == test_case['expected_cluster_found']
    
    # Normalize validation_result (None → "NO_MATCH")
    actual_validation = validation_result if validation_result else "NO_MATCH"
    validation_match = actual_validation == test_case['expected_validation']
    
    # For cases expecting cluster, check if disease matches
    disease_match = None
    if test_case['expected_cluster_found'] and cluster_found and test_case['cluster_disease']:
        expected_disease = test_case['cluster_disease'].lower()
        if refined_diagnosis:
            disease_match = expected_disease in refined_diagnosis.lower()
        else:
            disease_match = False
    
    correct = cluster_match and validation_match
    
    # Status indicator
    if correct:
        print(f"\n✅ PASS")
    else:
        print(f"\n❌ FAIL")
        if not cluster_match:
            print(f"   Cluster detection mismatch: expected {test_case['expected_cluster_found']}, got {cluster_found}")
        if not validation_match:
            print(f"   Validation type mismatch: expected {test_case['expected_validation']}, got {actual_validation}")
    
    return {
        "name": test_case['name'],
        "expected_cluster": test_case['expected_cluster_found'],
        "actual_cluster": cluster_found,
        "expected_validation": test_case['expected_validation'],
        "actual_validation": actual_validation,
        "cluster_match": cluster_match,
        "validation_match": validation_match,
        "disease_match": disease_match,
        "correct": correct,
        "refined_diagnosis": refined_diagnosis,
        "original_diagnosis": original_diagnosis,
        "refined_confidence": refined_confidence,
        "cluster_disease": test_case.get('cluster_disease'),
        "illness_category": test_case['illness_category']
    }


def calculate_metrics(results: List[Dict]) -> Dict:
    """
    Calculate comprehensive cluster identification metrics.
    """
    # Confusion matrix for cluster detection
    tp = sum(1 for r in results if r['expected_cluster'] and r['actual_cluster'])
    tn = sum(1 for r in results if not r['expected_cluster'] and not r['actual_cluster'])
    fp = sum(1 for r in results if not r['expected_cluster'] and r['actual_cluster'])
    fn = sum(1 for r in results if r['expected_cluster'] and not r['actual_cluster'])
    
    total = len(results)
    
    # Primary metrics
    accuracy = (tp + tn) / total if total > 0 else 0
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0  # Recall
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    f1 = 2 * (precision * sensitivity) / (precision + sensitivity) if (precision + sensitivity) > 0 else 0
    
    # Validation accuracy (for cases where cluster was found)
    validation_correct = sum(1 for r in results if r['validation_match'] and r['actual_cluster'])
    clusters_found = sum(1 for r in results if r['actual_cluster'])
    validation_accuracy = validation_correct / clusters_found if clusters_found > 0 else 0
    
    # Overall correctness (cluster detection AND validation type both correct)
    overall_correct = sum(1 for r in results if r['correct'])
    overall_accuracy = overall_correct / total if total > 0 else 0
    
    # Category-specific metrics
    by_validation_type = {}
    for expected_type in ["CONFIRMED", "WEAK_MATCH", "ALTERNATIVE", "NO_MATCH"]:
        cases = [r for r in results if r['expected_validation'] == expected_type]
        correct_cases = [r for r in cases if r['validation_match']]
        by_validation_type[expected_type] = {
            "total": len(cases),
            "correct": len(correct_cases),
            "accuracy": len(correct_cases) / len(cases) if cases else 0
        }
    
    return {
        "total_tests": total,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "accuracy": accuracy,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "f1_score": f1,
        "validation_accuracy": validation_accuracy,
        "overall_accuracy": overall_accuracy,
        "overall_correct": overall_correct,
        "by_validation_type": by_validation_type
    }


def print_results(results: List[Dict], metrics: Dict):
    """Pretty print test results and comprehensive metrics."""
    print("\n" + "="*80)
    print("OUTBREAK CLUSTER IDENTIFICATION TEST RESULTS (v3.0 - CORRECTED)")
    print("="*80)
    
    # Categorize results by type
    tp_results = [r for r in results if r['expected_cluster'] and r['actual_cluster']]
    tn_results = [r for r in results if not r['expected_cluster'] and not r['actual_cluster']]
    fp_results = [r for r in results if not r['expected_cluster'] and r['actual_cluster']]
    fn_results = [r for r in results if r['expected_cluster'] and not r['actual_cluster']]
    
    # Individual test results by category
    print("\n" + "="*80)
    print("TRUE POSITIVES (Correctly Identified Clusters)")
    print("="*80)
    for r in tp_results:
        status = "✅ PASS" if r['correct'] else "⚠️  PARTIAL"
        print(f"{status} | {r['name']}")
        print(f"       Validation: {r['actual_validation']} (expected {r['expected_validation']})")
        if r['refined_diagnosis']:
            conf_str = f" [{r['refined_confidence']:.0%}]" if r['refined_confidence'] else ""
            print(f"       Diagnosis: {r['refined_diagnosis']}{conf_str}")
    
    if tn_results:
        print("\n" + "="*80)
        print("TRUE NEGATIVES (Correctly Identified No Cluster)")
        print("="*80)
        for r in tn_results:
            print(f"✅ PASS | {r['name']}")
    
    if fp_results:
        print("\n" + "="*80)
        print("FALSE POSITIVES (Incorrectly Found Cluster)")
        print("="*80)
        for r in fp_results:
            print(f"❌ FAIL | {r['name']}")
            print(f"       System incorrectly identified a cluster")
    
    if fn_results:
        print("\n" + "="*80)
        print("FALSE NEGATIVES (Missed Real Cluster)")
        print("="*80)
        for r in fn_results:
            print(f"❌ FAIL | {r['name']}")
            print(f"       System failed to detect outbreak cluster")
    
    # Confusion matrix
    print("\n" + "="*80)
    print("CONFUSION MATRIX (Cluster Detection)")
    print("="*80)
    print(f"                      Predicted: Cluster    Predicted: No Cluster")
    print(f"Actual: Cluster              {metrics['true_positives']:>3} (TP)                {metrics['false_negatives']:>3} (FN)")
    print(f"Actual: No Cluster           {metrics['false_positives']:>3} (FP)                {metrics['true_negatives']:>3} (TN)")
    
    # Primary metrics
    print("\n" + "="*80)
    print("PERFORMANCE METRICS")
    print("="*80)
    print(f"Overall Accuracy:            {metrics['overall_accuracy']:>6.1%} "
          f"({metrics['overall_correct']}/{metrics['total_tests']} tests fully correct)")
    print(f"")
    print(f"Cluster Detection Metrics:")
    print(f"  Detection Accuracy:        {metrics['accuracy']:>6.1%} "
          f"(correctly identified presence/absence)")
    print(f"  Sensitivity (Recall):      {metrics['sensitivity']:>6.1%} "
          f"(% of real clusters found)")
    print(f"  Specificity:               {metrics['specificity']:>6.1%} "
          f"(% of non-clusters correctly identified)")
    print(f"  Precision:                 {metrics['precision']:>6.1%} "
          f"(% of flagged clusters that are real)")
    print(f"  F1 Score:                  {metrics['f1_score']:>6.1%} "
          f"(harmonic mean of precision/recall)")
    print(f"")
    print(f"Validation Type Accuracy:    {metrics['validation_accuracy']:>6.1%} "
          f"(correct CONFIRMED/WEAK_MATCH/ALTERNATIVE when cluster found)")
    
    # By validation type
    print(f"")
    print(f"Accuracy by Validation Type:")
    for vtype, stats in metrics['by_validation_type'].items():
        if stats['total'] > 0:
            print(f"  {vtype:15s}  {stats['accuracy']:>6.1%}  ({stats['correct']}/{stats['total']})")
    
    # Key insights
    print("\n" + "="*80)
    print("KEY INSIGHTS")
    print("="*80)
    
    # Critical issues
    if metrics['false_positives'] > 0:
        print(f"⚠️  {metrics['false_positives']} FALSE POSITIVE(S): "
              f"System flagged clusters that don't exist")
    
    if metrics['false_negatives'] > 0:
        print(f"⚠️  {metrics['false_negatives']} FALSE NEGATIVE(S): "
              f"System missed real outbreak clusters")
    
    # Performance warnings
    if metrics['sensitivity'] < 0.85:
        print(f"⚠️  LOW SENSITIVITY ({metrics['sensitivity']:.1%}): "
              f"System may be missing real outbreaks")
    
    if metrics['specificity'] < 0.85:
        print(f"⚠️  LOW SPECIFICITY ({metrics['specificity']:.1%}): "
              f"System may be over-alerting on non-outbreaks")
    
    if metrics['validation_accuracy'] < 0.80:
        print(f"⚠️  LOW VALIDATION ACCURACY ({metrics['validation_accuracy']:.1%}): "
              f"System struggles to correctly classify validation types")
    
    # Success indicators
    if metrics['overall_accuracy'] >= 0.85:
        print(f"✅ EXCELLENT PERFORMANCE: {metrics['overall_accuracy']:.1%} overall accuracy")
    elif metrics['overall_accuracy'] >= 0.75:
        print(f"✅ GOOD PERFORMANCE: {metrics['overall_accuracy']:.1%} overall accuracy")
    
    if metrics['sensitivity'] >= 0.90 and metrics['specificity'] >= 0.90:
        print(f"✅ EXCELLENT DETECTION: High sensitivity ({metrics['sensitivity']:.1%}) "
              f"and specificity ({metrics['specificity']:.1%})")
    
    print("="*80)
    
    # Performance summary
    print("\n" + "="*80)
    print("PERFORMANCE SUMMARY")
    print("="*80)
    
    if metrics['overall_accuracy'] >= 0.90:
        grade = "A (EXCELLENT)"
    elif metrics['overall_accuracy'] >= 0.80:
        grade = "B (GOOD)"
    elif metrics['overall_accuracy'] >= 0.70:
        grade = "C (ACCEPTABLE)"
    elif metrics['overall_accuracy'] >= 0.60:
        grade = "D (NEEDS IMPROVEMENT)"
    else:
        grade = "F (FAILING)"
    
    print(f"Overall Grade: {grade}")
    print(f"")
    print(f"The cluster validation system correctly handled {metrics['overall_correct']} "
          f"out of {metrics['total_tests']} test cases ({metrics['overall_accuracy']:.1%}).")
    
    if metrics['false_negatives'] == 0 and metrics['false_positives'] == 0:
        print(f"✅ PERFECT DETECTION: No false positives or false negatives!")
    
    print("="*80)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("OUTBREAK CLUSTER IDENTIFICATION TEST (v3.0 - CORRECTED)")
    print("Using Real Cluster Data with Corrected Expectations")
    print("="*80)
    print(f"Running {len(TEST_CASES)} test cases...")
    print(f"")
    print(f"Validated Clusters:")
    print(f"  • Oak Street Beach (E. coli 100%, 7 cases)")
    print(f"  • Pittsburgh Park (Lyme 100%, 7 cases)")
    print(f"  • Times Square (Salmonella 80%, 10 cases)")
    print(f"  • Central Park (Gastroenteritis 100%, 4 cases)")
    print(f"  • Hyde Park (COVID-19 44%, 27 cases - WEAK_MATCH)")
    print("="*80)
    
    results = []
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n[Test {i}/{len(TEST_CASES)}]")
        try:
            result = run_single_test(test_case)
            results.append(result)
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR in test '{test_case['name']}': {e}")
            import traceback
            traceback.print_exc()
            
            # Add failed result
            results.append({
                "name": test_case['name'],
                "expected_cluster": test_case['expected_cluster_found'],
                "actual_cluster": False,
                "expected_validation": test_case['expected_validation'],
                "actual_validation": None,
                "cluster_match": False,
                "validation_match": False,
                "disease_match": None,
                "correct": False,
                "refined_diagnosis": None,
                "original_diagnosis": None,
                "refined_confidence": None,
                "cluster_disease": test_case.get('cluster_disease'),
                "illness_category": test_case['illness_category']
            })
    
    # Calculate and print comprehensive metrics
    metrics = calculate_metrics(results)
    print_results(results, metrics)
    
    # Exit with appropriate code
    # Pass if overall accuracy >= 85% AND high detection rates
    passing = (
        metrics['overall_accuracy'] >= 0.85 and 
        metrics['sensitivity'] >= 0.90 and
        metrics['specificity'] >= 0.90
    )
    
    sys.exit(0 if passing else 1)