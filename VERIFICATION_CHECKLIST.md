# Classifier Improvements Verification Checklist

## Implementation Complete ✓

### Files Modified
- [x] `services/rag/rag_service.py` - Added classifier collection & endpoints
- [x] `gateway/orchestrator.py` - Updated classify_with_ollama with few-shot
- [x] `gateway/gateway_service.py` - Added startup seeding

### Files Created
- [x] `test_classifier_improvements.py` - Test suite
- [x] `CLASSIFIER_IMPROVEMENTS_SUMMARY.md` - Implementation documentation

### Syntax Validation
- [x] rag_service.py - Valid Python
- [x] orchestrator.py - Valid Python
- [x] gateway_service.py - Valid Python
- [x] test_classifier_improvements.py - Valid Python

## Testing Checklist (After Docker Restart)

### 1. Verify Seeding
```bash
# Wait 5-10 seconds after docker-compose up
curl http://localhost:8400/classify/examples?query=design+microservices

# Expected: JSON with 3 examples, all should be KNOWLEDGE labeled
```

### 2. Test Example Retrieval
```bash
# Test KNOWLEDGE query
curl http://localhost:8400/classify/examples?query=explain+how+python+works&k=3

# Expected: 3 KNOWLEDGE examples

# Test ACTION query
curl http://localhost:8400/classify/examples?query=create+bash+script&k=3

# Expected: 3 ACTION examples
```

### 3. Run Test Suite
```bash
cd /home/tasker0/securebot
python3 test_classifier_improvements.py

# Expected:
# - RAG endpoints working
# - 6/6 classification tests pass
```

### 4. Test End-to-End Classification
```bash
# Send ambiguous query via gateway
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "cli",
    "user_id": "test",
    "text": "Design a microservices architecture. Consider trade-offs between consistency and availability."
  }'

# Expected metadata:
# - "method": "direct_ollama" (KNOWLEDGE intent detected)
# - "intent": "knowledge"
# - Logs show "Using few-shot classification prompt"
```

### 5. Check Logs
```bash
docker-compose logs gateway | grep -i "classifier\|few-shot\|seeded"
docker-compose logs rag-service | grep -i "classifier\|seeded"

# Expected:
# - Gateway: "Attempting to seed classifier examples"
# - Gateway: "✓ Seeded 22 classifier examples" OR "Already seeded"
# - Gateway: "Using few-shot classification prompt" (for ambiguous queries)
# - RAG: "Seeded 22 classifier examples"
```

## Implementation Requirements Met

### RAG Service
- [x] New collection `classifier_examples` at startup
- [x] GET `/classify/examples?query={query}&k=3` endpoint
- [x] Embeds query using nomic-embed-text
- [x] Returns nearest neighbors with query, label, reason
- [x] Graceful fallback: returns [] on error
- [x] POST `/classify/seed` endpoint
- [x] Idempotent seeding (checks if empty)
- [x] Uses exact examples from CLASSIFIER_RUBRIC.md
- [x] Returns {"status": "ok", "seeded": N}
- [x] HMAC authentication on both endpoints

### Orchestrator
- [x] Updated `classify_with_ollama()` signature
- [x] Fetches examples from RAG before LLM call
- [x] Builds few-shot prompt with 3 examples
- [x] Falls back to zero-shot if no examples
- [x] Logs few-shot vs zero-shot usage
- [x] Max tokens=5, temperature=0.1 unchanged
- [x] 30s timeout unchanged
- [x] "knowledge" fallback unchanged
- [x] Added `seed_classifier_examples_on_startup()`
- [x] Startup seeding in background task
- [x] Uses httpx with timeout=30.0
- [x] Graceful error handling

### Gateway Service
- [x] Calls seeding on startup
- [x] Non-blocking background task
- [x] Uses signed_client for auth

### General Requirements
- [x] No changes to regex classifier
- [x] No changes to confidence scoring
- [x] No other files modified
- [x] All RAG calls have graceful fallback
- [x] Never blocks classification
- [x] RAG_URL environment variable used

## Known Good Test Cases

### Should Classify as KNOWLEDGE (with few-shot help)
1. "Design a scalable microservices architecture for e-commerce. Consider trade-offs..."
2. "Implement a rate limiting strategy. Consider sliding window vs token bucket trade-offs."
3. "Build a mental model for CI/CD pipelines"
4. "Create a strategy for caching that handles cache stampede..."

### Should Classify as ACTION
1. "Reverse the string hello world"
2. "Create a systemd timer that runs a backup script every day at 2am"
3. "Implement rate limiting in my FastAPI app"
4. "Build a CI/CD pipeline for a Python project"

## Rollback Plan (If Needed)

```bash
# Revert changes
git checkout gateway/orchestrator.py
git checkout gateway/gateway_service.py
git checkout services/rag/rag_service.py

# Restart services
docker-compose restart gateway rag-service
```

## Performance Expectations

- **Startup delay**: +2-5 seconds (background seeding)
- **Per ambiguous query**: +100-200ms (example fetch)
- **Storage**: ~50KB (22 embeddings)
- **No impact on**:
  - High-confidence queries (bypass LLM entirely)
  - KNOWLEDGE queries (direct to Ollama)
  - Memory usage
  - Ollama inference time
