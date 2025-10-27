#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import io

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
Test Script: Illness Category Classification
Tests the diagnostic agent's ability to correctly classify illness categories.

Categories tested:
- foodborne
- airborne
- waterborne
- insect-borne
- direct contact
"""

import sys
import json
from typing import Dict, List
import uuid

# Add parent directory to path to import graph_orchestrator
sys.path.insert(0, '/mnt/project')

from graph_orchestrator import run_graph_chat_flow

# ============================================================================
# TEST CASES
# ============================================================================

TEST_CASES = [
    # FOODBORNE CASES (4 tests)
    {
        "name": "Salmonella from Restaurant",
        "inputs": [
            "I've been having bad diarrhea with a fever and my stomach really hurts",
            "3 days ago",
            "Chipotle on Michigan Avenue",
            "2 days ago",
            "Chicago, IL",
            "Downtown"
        ],
        "expected_category": "foodborne"
    },
    {
        "name": "E. coli with Bloody Diarrhea",
        "inputs": [
            "My stomach is killing me and there's blood when I go to the bathroom",
            "2 days",
            "Local burger joint",
            "3 days ago",
            "Chicago, IL",
            "Lincoln Park"
        ],
        "expected_category": "foodborne"
    },
    {
        "name": "Norovirus Rapid Onset",
        "inputs": [
            "Started throwing up out of nowhere and can't stop going to the bathroom",
            "1 day ago",
            "Wedding reception hall",
            "yesterday",
            "Chicago, IL",
            "West Loop"
        ],
        "expected_category": "foodborne"
    },
    {
        "name": "Food Poisoning from Deli",
        "inputs": [
            "Feel sick to my stomach and threw up, happened really fast after eating",
            "6 hours ago",
            "Corner deli",
            "this morning",
            "Chicago, IL",
            "Hyde Park"
        ],
        "expected_category": "foodborne"
    },
    
    # AIRBORNE CASES (3 tests)
    {
        "name": "Influenza Classic Symptoms",
        "inputs": [
            "I feel terrible - running a high temperature, my whole body is sore, and I can't stop coughing",
            "2 days ago",
            "Office building",
            "4 days ago",
            "Chicago, IL",
            "Loop"
        ],
        "expected_category": "airborne"
    },
    {
        "name": "COVID-19 with Loss of Smell",
        "inputs": [
            "I have a fever and cough, but the weird thing is I can't taste or smell anything at all",
            "3 days",
            "Gym",
            "5 days ago",
            "Chicago, IL",
            "River North"
        ],
        "expected_category": "airborne"
    },
    {
        "name": "Common Cold Symptoms",
        "inputs": [
            "My nose won't stop running, I'm sneezing constantly, and my throat hurts a bit",
            "2 days ago",
            "Coffee shop",
            "3 days ago",
            "Chicago, IL",
            "Wicker Park"
        ],
        "expected_category": "airborne"
    },
    
    # WATERBORNE CASES (2 tests)
    {
        "name": "Giardiasis from Lake",
        "inputs": [
            "I've had liquid diarrhea for over a week now, really gassy and bloated, super tired",
            "2 weeks ago",
            "Lake Michigan beach",
            "3 weeks ago",
            "Chicago, IL",
            "North Side"
        ],
        "expected_category": "waterborne"
    },
    {
        "name": "Cryptosporidiosis from Pool",
        "inputs": [
            "Can't stop having liquid bowel movements and my stomach is cramping up",
            "5 days ago",
            "Public swimming pool",
            "7 days ago",
            "Chicago, IL",
            "South Side"
        ],
        "expected_category": "waterborne"
    },
    
    # INSECT-BORNE CASE (1 test)
    {
        "name": "Lyme Disease from Tick",
        "inputs": [
            "There's a weird circular red mark on my leg, I have a temperature, and my joints are aching",
            "5 days ago",
            "Forest preserve hiking trail",
            "1 week ago",
            "Chicago, IL",
            "Northwest suburbs"
        ],
        "expected_category": "insect-borne"
    }
]

# ============================================================================
# TEST EXECUTION
# ============================================================================

def run_single_test(test_case: Dict) -> Dict:
    """
    Run a single test case through the chatbot.
    
    Returns:
        Dict with test results including predicted and expected categories
    """
    session_id = str(uuid.uuid4())
    
    print(f"\n{'='*70}")
    print(f"Testing: {test_case['name']}")
    print(f"{'='*70}")
    
    predicted_category = None
    
    # Simulate conversation
    for i, user_input in enumerate(test_case['inputs']):
        print(f"\nTurn {i+1}: {user_input}")
        
        result, _ = run_graph_chat_flow(user_input, session_id)
        
        # Check if we got a diagnosis
        if result.get('diagnosis') and result['diagnosis'].get('illness_category'):
            predicted_category = result['diagnosis']['illness_category']
            print(f"[OK] Diagnosis received: {result['diagnosis'].get('final_diagnosis')}")
            print(f"  Category: {predicted_category}")
    
    return {
        "name": test_case['name'],
        "expected": test_case['expected_category'],
        "predicted": predicted_category,
        "correct": predicted_category == test_case['expected_category']
    }


def calculate_metrics(results: List[Dict]) -> Dict:
    """
    Calculate classification metrics from test results.
    
    Returns:
        Dict with accuracy, precision, recall, F1 per category
    """
    # Overall accuracy
    correct = sum(1 for r in results if r['correct'])
    accuracy = correct / len(results) if results else 0
    
    # Per-category metrics
    categories = set(r['expected'] for r in results)
    category_metrics = {}
    
    for category in categories:
        tp = sum(1 for r in results if r['expected'] == category and r['predicted'] == category)
        fp = sum(1 for r in results if r['expected'] != category and r['predicted'] == category)
        fn = sum(1 for r in results if r['expected'] == category and r['predicted'] != category)
        tn = sum(1 for r in results if r['expected'] != category and r['predicted'] != category)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        category_metrics[category] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": tp + fn  # Total actual cases
        }
    
    return {
        "accuracy": accuracy,
        "total_tests": len(results),
        "correct": correct,
        "category_metrics": category_metrics
    }


def print_results(results: List[Dict], metrics: Dict):
    """Pretty print test results and metrics."""
    print("\n" + "="*70)
    print("TEST RESULTS SUMMARY")
    print("="*70)
    
    # Individual test results
    print("\nIndividual Test Results:")
    print("-" * 70)
    for r in results:
        status = "[PASS]" if r['correct'] else "[FAIL]"
        print(f"{status} | {r['name']}")
        print(f"       Expected: {r['expected']}, Predicted: {r['predicted']}")
    
    # Overall metrics
    print("\n" + "="*70)
    print("OVERALL METRICS")
    print("="*70)
    print(f"Accuracy: {metrics['accuracy']:.1%} ({metrics['correct']}/{metrics['total_tests']})")
    
    # Per-category metrics
    print("\n" + "="*70)
    print("PER-CATEGORY METRICS")
    print("="*70)
    print(f"{'Category':<20} {'Precision':<12} {'Recall':<12} {'F1-Score':<12} {'Support':<10}")
    print("-" * 70)
    
    for category, scores in sorted(metrics['category_metrics'].items()):
        print(f"{category:<20} {scores['precision']:>10.1%}  {scores['recall']:>10.1%}  "
              f"{scores['f1']:>10.1%}  {scores['support']:>8}")
    
    print("="*70)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("ILLNESS CATEGORY CLASSIFICATION TEST")
    print("="*70)
    print(f"Running {len(TEST_CASES)} test cases...")
    
    results = []
    
    for test_case in TEST_CASES:
        try:
            result = run_single_test(test_case)
            results.append(result)
        except Exception as e:
            print(f"\n[ERROR] in test '{test_case['name']}': {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "name": test_case['name'],
                "expected": test_case['expected_category'],
                "predicted": None,
                "correct": False
            })
    
    # Calculate and print metrics
    metrics = calculate_metrics(results)
    print_results(results, metrics)
    
    # Exit with appropriate code
    sys.exit(0 if metrics['accuracy'] >= 0.8 else 1)
