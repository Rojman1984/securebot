#!/usr/bin/env python3
"""
Test script to verify few-shot classifier improvements.
Tests both the RAG service endpoints and the orchestrator integration.
"""
import asyncio
import httpx
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from gateway.orchestrator import classify_with_ollama, IntentClassifier

# Service URLs
RAG_URL = os.getenv("RAG_URL", "http://localhost:8400")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


async def test_rag_endpoints():
    """Test RAG service classifier endpoints"""
    print("=" * 80)
    print("TESTING RAG SERVICE ENDPOINTS")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test 1: Seed the classifier examples
        print("\n[1/3] Testing POST /classify/seed...")
        try:
            response = await client.post(f"{RAG_URL}/classify/seed", json={})
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Seeding successful: {data}")
            else:
                print(f"✗ Seeding failed: HTTP {response.status_code}")
                print(f"  Response: {response.text}")
        except Exception as e:
            print(f"✗ Seeding error: {e}")

        # Test 2: Verify collection has examples
        print("\n[2/3] Testing GET /classify/examples (empty query)...")
        try:
            response = await client.get(
                f"{RAG_URL}/classify/examples",
                params={"query": "test query", "k": 3}
            )
            if response.status_code == 200:
                data = response.json()
                examples = data.get("examples", [])
                print(f"✓ Retrieved {len(examples)} examples")
                if examples:
                    print(f"  First example: {examples[0]['query'][:60]}...")
                    print(f"  Label: {examples[0]['label']}")
            else:
                print(f"✗ Example retrieval failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"✗ Example retrieval error: {e}")

        # Test 3: Test with ambiguous query (should return KNOWLEDGE examples)
        print("\n[3/3] Testing GET /classify/examples (ambiguous query)...")
        test_query = "Design a microservices architecture. Consider trade-offs..."
        try:
            response = await client.get(
                f"{RAG_URL}/classify/examples",
                params={"query": test_query, "k": 3}
            )
            if response.status_code == 200:
                data = response.json()
                examples = data.get("examples", [])
                print(f"✓ Retrieved {len(examples)} examples for ambiguous query")
                for i, ex in enumerate(examples, 1):
                    print(f"  [{i}] {ex['label']}: {ex['query'][:60]}...")
            else:
                print(f"✗ Example retrieval failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"✗ Example retrieval error: {e}")


async def test_orchestrator_classification():
    """Test orchestrator classification with few-shot examples"""
    print("\n" + "=" * 80)
    print("TESTING ORCHESTRATOR CLASSIFICATION")
    print("=" * 80)

    # Test queries from rubric
    test_cases = [
        {
            "query": "Design a scalable microservices architecture for e-commerce. Consider trade-offs between consistency and availability.",
            "expected": "knowledge",
            "description": "Architectural trade-off analysis (ambiguous)"
        },
        {
            "query": "Reverse the string hello world",
            "expected": "action",
            "description": "Specific transformation (high-confidence ACTION)"
        },
        {
            "query": "What are the pros and cons of using Redis vs Memcached for session storage?",
            "expected": "knowledge",
            "description": "Technology comparison (high-confidence KNOWLEDGE)"
        },
        {
            "query": "Implement rate limiting in my FastAPI app",
            "expected": "action",
            "description": "Specific implementation (high-confidence ACTION)"
        },
        {
            "query": "Build a mental model for CI/CD pipelines",
            "expected": "knowledge",
            "description": "Mental model request (ambiguous - should be KNOWLEDGE)"
        },
        {
            "query": "Create a systemd timer that runs a backup script every day at 2am",
            "expected": "action",
            "description": "Specific artifact creation (high-confidence ACTION)"
        }
    ]

    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] {test_case['description']}")
        print(f"  Query: {test_case['query'][:70]}...")

        # First check regex classifier
        intent, confidence = IntentClassifier.classify_intent(test_case['query'])
        print(f"  Regex classification: {intent} (confidence: {confidence})")

        # If ambiguous, test LLM classifier
        if confidence == "ambiguous":
            try:
                llm_intent = await classify_with_ollama(
                    test_case['query'],
                    OLLAMA_URL,
                    RAG_URL,
                    signed_client=None
                )
                print(f"  LLM classification: {llm_intent}")
                final_intent = llm_intent
            except Exception as e:
                print(f"  ✗ LLM classification error: {e}")
                final_intent = intent
        else:
            final_intent = intent

        # Check result
        if final_intent == test_case['expected']:
            print(f"  ✓ PASS: Classified as {final_intent}")
            results.append(True)
        else:
            print(f"  ✗ FAIL: Expected {test_case['expected']}, got {final_intent}")
            results.append(False)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total} ({100 * passed / total:.1f}%)")

    if passed == total:
        print("✓ All tests passed!")
    else:
        print(f"✗ {total - passed} test(s) failed")


async def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("SECUREBOT CLASSIFIER IMPROVEMENTS TEST SUITE")
    print("=" * 80)
    print(f"RAG_URL: {RAG_URL}")
    print(f"OLLAMA_URL: {OLLAMA_URL}")

    try:
        # Test RAG endpoints first
        await test_rag_endpoints()

        # Then test orchestrator classification
        await test_orchestrator_classification()

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest suite error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
