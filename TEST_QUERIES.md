# Test Queries for Hybrid Intent Classifier

Use these queries to test the hybrid classifier behavior in production.

---

## ✅ KNOWLEDGE Queries (Should route to Ollama directly)

### High-confidence (Fast Path ⚡)
These should complete in <1ms classification time.

```
Explain Python list comprehensions
What are the pros and cons of using Redis vs Memcached?
Why does Docker use cgroups for isolation?
How does a hash table work internally?
What is the difference between TCP and UDP?
Describe the CAP theorem and its implications
```

### Ambiguous (LLM Path 🔍)
These should invoke LLM classifier (~3-5s additional latency).

```
Design a scalable microservices architecture for e-commerce with high availability. Consider trade-offs between consistency and availability.

Develop a testing strategy for microservices. Compare integration vs unit testing approaches.

Implement a monitoring solution for Kubernetes. What are the best practices and trade-offs?

Build a CI/CD pipeline. Explain the architecture and compare different approaches like GitLab CI vs Jenkins.

Create a backup strategy for PostgreSQL. Consider recovery time objectives and storage costs.
```

---

## ✅ ACTION Queries (Should route to skill matching)

### High-confidence (Fast Path ⚡)

```
Reverse the string hello world

Encrypt this message using AES-256: "secret data"

Parse the following JSON and extract the user IDs

Convert 100 USD to EUR using current exchange rates

Install Docker and set up a development container

Write a bash script to monitor disk usage and alert when >80%

Generate a random 32-character password

Schedule a cron job to run backups daily at 2am
```

### Ambiguous verbs without analytical signals (Fast Path ⚡)

```
Create a systemd timer that runs every hour

Build a REST API endpoint for user authentication

Implement rate limiting for the API gateway

Develop a Python script to scrape product prices

Design a database schema for an e-commerce platform
```

---

## 🔍 Expected Logging for Each Type

### Fast Path Knowledge
```
INFO - Intent classification: knowledge (confidence: high)
INFO - KNOWLEDGE intent detected - bypassing skill matching, using Ollama directly
INFO - Query: 'Explain Python list comprehensions'
```

### LLM Path Knowledge
```
INFO - Intent classification: knowledge (confidence: ambiguous)
INFO - ⚠️  Ambiguous query detected, invoking LLM classifier
INFO - 🔍 Using LLM for ambiguous query classification
INFO - ✓ LLM classified as: KNOWLEDGE
INFO - LLM resolved intent: knowledge
INFO - KNOWLEDGE intent detected - bypassing skill matching, using Ollama directly
```

### Fast Path Action
```
INFO - Intent classification: action (confidence: high)
INFO - Classification: skill_execution
INFO - Matched skill: string-reversal
```

---

## 🧪 Production Testing Checklist

- [ ] Test at least 3 high-confidence knowledge queries (fast path)
- [ ] Test at least 2 ambiguous knowledge queries (LLM path)
- [ ] Test at least 3 high-confidence action queries (fast path)
- [ ] Verify LLM timeout handling (set Ollama offline temporarily)
- [ ] Check logs show correct intent classification
- [ ] Verify no skill matching triggered for knowledge queries
- [ ] Confirm response quality for ambiguous queries

---

## 📊 Metrics to Monitor

### Classification Performance
- **Fast path ratio**: Should be ~80% (8/10 queries)
- **LLM path ratio**: Should be ~20% (2/10 queries)
- **LLM timeout rate**: Should be <1%

### Response Quality
- **Knowledge queries**: Should get direct Ollama responses (no skill errors)
- **Action queries**: Should match appropriate skills or create new ones
- **Ambiguous queries**: Should correctly disambiguate intent

### Latency
- **Fast path**: <1ms classification overhead
- **LLM path**: ~3-5s additional latency for classification only
- **Total response time**: Classification + generation time

---

## 🐛 Troubleshooting

### Issue: All queries marked as "ambiguous"
**Check:** Review ANALYTICAL_SIGNALS list - may be too broad
**Fix:** Refine analytical signal patterns in `IntentClassifier`

### Issue: LLM always returns "KNOWLEDGE"
**Check:** LLM prompt may need adjustment
**Fix:** Review `classify_with_ollama()` system prompt

### Issue: LLM timeouts frequently
**Check:** Ollama service health, system load
**Fix:** Increase timeout from 30s or check Ollama logs

### Issue: Fast path not triggering
**Check:** Query patterns may not match exactly
**Fix:** Review pattern matching logic, add debug logging

---

## 📝 Notes

- **Case sensitivity**: All patterns are case-insensitive (`.lower()`)
- **Partial matches**: Patterns can appear anywhere in query (except ACTION_PATTERNS_HIGH which must start the query)
- **Priority**: Knowledge patterns checked before action patterns
- **Fallback**: Default is always "knowledge" (safer/cheaper)
