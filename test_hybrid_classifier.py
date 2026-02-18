#!/usr/bin/env python3
"""
Test script for hybrid intent classifier

Tests the confidence scoring and demonstrates when LLM classification would be invoked.
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from gateway.orchestrator import IntentClassifier

# Test cases
test_cases = [
    {
        "query": "Design a scalable microservices architecture for e-commerce with high availability. Consider trade-offs between consistency and availability.",
        "expected_intent": "knowledge",
        "expected_confidence": "ambiguous",
        "reason": "Has 'design' (ambiguous verb) + 'trade-offs', 'consider' (analytical signals)"
    },
    {
        "query": "What are the pros and cons of using Redis vs Memcached?",
        "expected_intent": "knowledge",
        "expected_confidence": "high",
        "reason": "Starts with 'what are' (high-confidence knowledge pattern)"
    },
    {
        "query": "Explain Python list comprehensions",
        "expected_intent": "knowledge",
        "expected_confidence": "high",
        "reason": "Starts with 'explain' (high-confidence knowledge pattern)"
    },
    {
        "query": "Reverse the string hello world",
        "expected_intent": "action",
        "expected_confidence": "high",
        "reason": "Starts with 'reverse' (high-confidence action pattern)"
    },
    {
        "query": "Create a systemd timer that runs every hour",
        "expected_intent": "action",
        "expected_confidence": "high",
        "reason": "Has 'create' (ambiguous) but no analytical signals = action"
    },
    {
        "query": "Write a bash script to monitor disk usage",
        "expected_intent": "action",
        "expected_confidence": "high",
        "reason": "Has 'write a script' (high-confidence action pattern)"
    },
    {
        "query": "Build a REST API with authentication. Explain the architecture and security considerations.",
        "expected_intent": "knowledge",
        "expected_confidence": "ambiguous",
        "reason": "Has 'build' (ambiguous) + 'explain', 'architecture' (analytical signals)"
    },
    {
        "query": "Implement a cache layer for the database. What are the best practices?",
        "expected_intent": "knowledge",
        "expected_confidence": "ambiguous",
        "reason": "Has 'implement' (ambiguous) + 'what are', 'best practices' (analytical signals)"
    },
    {
        "query": "Develop a testing strategy for microservices. Compare integration vs unit testing approaches.",
        "expected_intent": "knowledge",
        "expected_confidence": "ambiguous",
        "reason": "Has 'develop' (ambiguous) + 'strategy', 'compare' (analytical signals)"
    },
    {
        "query": "Install Docker and set up a container",
        "expected_intent": "action",
        "expected_confidence": "high",
        "reason": "Starts with 'install' (high-confidence action pattern)"
    }
]

def test_classifier():
    print("=" * 80)
    print("HYBRID INTENT CLASSIFIER TEST")
    print("=" * 80)
    print()

    passed = 0
    failed = 0
    llm_needed = 0

    for i, test in enumerate(test_cases, 1):
        query = test["query"]
        expected_intent = test["expected_intent"]
        expected_confidence = test["expected_confidence"]
        reason = test["reason"]

        intent, confidence = IntentClassifier.classify_intent(query)

        # Check if test passed
        intent_match = intent == expected_intent
        confidence_match = confidence == expected_confidence
        test_passed = intent_match and confidence_match

        if test_passed:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1

        if confidence == "ambiguous":
            llm_needed += 1
            llm_marker = "🔍 LLM NEEDED"
        else:
            llm_marker = "⚡ FAST PATH"

        print(f"Test {i}: {status} {llm_marker}")
        print(f"Query: {query[:70]}...")
        print(f"Expected: {expected_intent} ({expected_confidence})")
        print(f"Got:      {intent} ({confidence})")
        print(f"Reason:   {reason}")

        if not test_passed:
            if not intent_match:
                print(f"  ERROR: Intent mismatch! Expected '{expected_intent}', got '{intent}'")
            if not confidence_match:
                print(f"  ERROR: Confidence mismatch! Expected '{expected_confidence}', got '{confidence}'")

        print()

    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print(f"LLM disambiguation needed: {llm_needed}/{len(test_cases)} queries")
    print(f"Fast path efficiency: {len(test_cases) - llm_needed}/{len(test_cases)} queries")
    print("=" * 80)

    return failed == 0

if __name__ == "__main__":
    success = test_classifier()
    sys.exit(0 if success else 1)
