#!/usr/bin/env python3
"""
Test Intent Classifier

Demonstrates the intent classification for KNOWLEDGE vs ACTION queries
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from gateway.orchestrator import IntentClassifier

# Test cases
test_queries = {
    "KNOWLEDGE": [
        "explain list comprehensions",
        "what are Python decorators",
        "why does async work this way",
        "how does list slicing work",
        "describe the differences between lists and tuples",
        "tell me about generators",
        "what do you know about exceptions",
        "what is a closure",
        "can you explain lambda functions",
        "help me understand recursion",
        "summarize object-oriented programming",
        "difference between == and is"
    ],
    "ACTION": [
        "reverse this string: hello",
        "create a function to parse JSON",
        "write a script to automate backups",
        "generate a REST API endpoint",
        "fix the bug in this code",
        "search for Python decorators documentation",
        "make a calculator app",
        "build a web scraper",
        "configure nginx for production",
        "run the test suite",
        "automate deployment process",
        "convert CSV to JSON"
    ]
}

def test_intent_classifier():
    """Test the intent classifier with various queries"""

    print("=" * 70)
    print("INTENT CLASSIFIER TEST")
    print("=" * 70)

    for expected_category, queries in test_queries.items():
        print(f"\n{expected_category} QUERIES (should detect as 'knowledge' or 'action'):")
        print("-" * 70)

        correct = 0
        total = len(queries)

        for query in queries:
            intent = IntentClassifier.classify_intent(query)

            # Check if classification matches expected category
            is_correct = (
                (expected_category == "KNOWLEDGE" and intent == "knowledge") or
                (expected_category == "ACTION" and intent == "action")
            )

            status = "✓" if is_correct else "✗"
            if is_correct:
                correct += 1

            print(f"  {status} [{intent:9}] {query}")

        accuracy = (correct / total) * 100
        print(f"\n  Accuracy: {correct}/{total} ({accuracy:.1f}%)")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_intent_classifier()
