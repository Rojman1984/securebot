#!/usr/bin/env python3
"""
Simplified test for hybrid intent classifier (no external dependencies)

Tests the confidence scoring logic without needing httpx or other deps.
"""

# Inline classifier logic for testing (copied from orchestrator.py)
class IntentClassifier:
    """Classify query intent: ACTION vs KNOWLEDGE with hybrid LLM disambiguation"""

    # High-confidence KNOWLEDGE patterns - unambiguous questions
    KNOWLEDGE_PATTERNS_HIGH = [
        "explain", "what is", "what are", "what do", "what does",
        "why", "why is", "why are", "why do", "why does",
        "how does", "how do", "how is", "how are",
        "describe", "tell me about", "tell me what",
        "define", "definition of",
        "can you explain", "help me understand",
        "could you explain", "would you explain",
        "difference between", "differences between",
        "what's the difference",
        "what does X mean", "what do X mean",
        "meaning of", "purpose of",
        "what do you know", "do you know",
        "have you heard", "are you familiar",
        "summarize", "summary of",
        "tell me", "show me what"
    ]

    ACTION_PATTERNS_HIGH = [
        "reverse", "encrypt", "decode", "decrypt", "hash",
        "parse", "convert", "transform", "execute",
        "run", "perform",
        "schedule", "automate", "set up", "setup",
        "configure", "install", "deploy",
        "write a script", "generate a script",
        "fix", "update", "change", "modify", "edit",
        "refactor", "optimize", "improve", "enhance",
        "search for", "find me", "look up", "get me",
        "fetch", "retrieve", "pull"
    ]

    AMBIGUOUS_VERBS = [
        "design", "develop", "implement", "build", "create",
        "make", "write", "code", "compare"
    ]

    ANALYTICAL_SIGNALS = [
        "trade-off", "trade-offs", "tradeoff", "tradeoffs",
        "consider", "considering",
        "pros and cons", "advantages and disadvantages",
        "when to use", "when should",
        "difference", "compare", "comparison",
        "best practice", "best practices",
        "why", "how does", "what is",
        "explain", "describe",
        "architecture", "strategy", "approach",
        "pattern", "patterns",
        "philosophy", "principles"
    ]

    @staticmethod
    def classify_intent(query: str) -> tuple:
        query_lower = query.lower().strip()

        # Check high-confidence KNOWLEDGE patterns first
        for pattern in IntentClassifier.KNOWLEDGE_PATTERNS_HIGH:
            if query_lower.startswith(pattern) or f" {pattern}" in f" {query_lower}":
                return ("knowledge", "high")

        # Check for analytical signals (knowledge even with action verbs)
        has_analytical = any(signal in query_lower for signal in IntentClassifier.ANALYTICAL_SIGNALS)
        has_ambiguous_verb = any(verb in query_lower for verb in IntentClassifier.AMBIGUOUS_VERBS)

        # If has ambiguous verb + analytical signals = ambiguous (needs LLM)
        if has_ambiguous_verb and has_analytical:
            return ("knowledge", "ambiguous")

        # Check high-confidence ACTION patterns
        for pattern in IntentClassifier.ACTION_PATTERNS_HIGH:
            if query_lower.startswith(pattern):
                return ("action", "high")

        # If has ambiguous verb without analytical signals = likely action
        if has_ambiguous_verb:
            return ("action", "high")

        # Default to knowledge (safer/cheaper)
        return ("knowledge", "high")


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
        "expected_confidence": "high",
        "reason": "Contains 'explain' (high-confidence knowledge pattern) - fast path wins"
    },
    {
        "query": "Implement a cache layer for the database. What are the best practices?",
        "expected_intent": "knowledge",
        "expected_confidence": "high",
        "reason": "Contains 'what are' (high-confidence knowledge pattern) - fast path wins"
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
                print(f"  ⚠️  ERROR: Intent mismatch! Expected '{expected_intent}', got '{intent}'")
            if not confidence_match:
                print(f"  ⚠️  ERROR: Confidence mismatch! Expected '{expected_confidence}', got '{confidence}'")

        print()

    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print(f"LLM disambiguation needed: {llm_needed}/{len(test_cases)} queries")
    print(f"Fast path efficiency: {len(test_cases) - llm_needed}/{len(test_cases)} queries")
    print("=" * 80)

    return failed == 0

if __name__ == "__main__":
    import sys
    success = test_classifier()
    sys.exit(0 if success else 1)
