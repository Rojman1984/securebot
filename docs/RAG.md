# RAG (Retrieval Augmented Generation) System

## Overview

SecureBot uses a RAG system to solve the **context window problem** on budget hardware:

**Problem**: Prepending full memory files (soul.md, user.md, session.md) to every prompt caused:
- httpx.ReadTimeout (120+ seconds on Ryzen 5 3500U)
- Wasted context window on irrelevant memory
- Poor performance with phi4-mini:3.8b

**Solution**: RAG with ChromaDB
- Embed memory chunks into vector database
- Retrieve only TOP 3 most relevant chunks per query (~300 tokens max)
- Store conversation history (rolling window of 100 turns)
- Summarize sessions at end of day

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Query                           │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    v
            ┌───────────────┐
            │   Gateway     │
            │   Service     │
            └───────┬───────┘
                    │
        ┌───────────┴──────────────┐
        │                          │
        v                          v
┌───────────────┐          ┌──────────────┐
│  RAG Service  │          │ Orchestrator │
│ (port 8400)   │◄─────────│              │
└───────┬───────┘          └──────────────┘
        │
        v
┌─────────────────────────────────────────┐
│           ChromaDB Collections          │
│                                         │
│  1. memory (soul, user, session chunks)│
│  2. conversations (last 100 turns)     │
└─────────────────────────────────────────┘
```

## ChromaDB Collections

### 1. Memory Collection
Stores semantic chunks from memory files:
- **soul.md**: Bot identity and purpose (read-only)
- **user.md**: User profile, preferences, hardware
- **session.md**: Current session context

**Chunking Strategy**:
- Split by `## headers` (semantic sections)
- Max 300 tokens per chunk
- 50 token overlap between chunks
- Metadata: `{source: "user.md", section: "Goals", chunk: 0, timestamp: "..."}`

### 2. Conversations Collection
Stores recent conversation turns:
- Rolling window of **100 conversations max**
- Stores: user message + assistant response
- Truncates long messages to 500 chars each
- Enables learning from past interactions

## Embedding Model

**nomic-embed-text** via Ollama
- Free, runs locally
- Optimized for semantic search
- 768-dimensional embeddings
- Fast on CPU (even on budget hardware)

Install:
```bash
ollama pull nomic-embed-text
```

### Alternative Models
If nomic-embed-text is too slow:
```bash
# Faster but less accurate
ollama pull all-minilm

# More accurate but slower
ollama pull mxbai-embed-large
```

Update `services/rag/rag_service.py`:
```python
EMBEDDING_MODEL = "all-minilm"  # Change this
```

## Context Retrieval Flow

```python
# 1. User sends query: "What are my GitHub projects?"

# 2. RAG service embeds query with nomic-embed-text

# 3. ChromaDB searches both collections:
#    - memory collection: top 2 results
#    - conversations collection: top 1 result

# 4. Returns combined context (~200 tokens):
"""
[From user.md]
## GitHub Username
tasker0

## Active Projects
- SecureBot v2.0
- homelab automation

[Past conversation]
User: What's my GitHub username?
Assistant: Your GitHub username is tasker0.
"""

# 5. Orchestrator prepends context to prompt:
"""
Context:
[From user.md]
## GitHub Username
tasker0
...

---

User query: What are my GitHub projects?
"""
```

## API Endpoints

### GET /health
Health check with ChromaDB stats
```json
{
  "status": "healthy",
  "embedding_model": "nomic-embed-text",
  "memory_chunks": 42,
  "conversations": 87
}
```

### POST /embed/memory
Re-embed all memory files (soul.md, user.md, session.md)
```bash
curl -X POST http://localhost:8400/embed/memory
```

Response:
```json
{
  "status": "ok",
  "chunks_embedded": 42,
  "timestamp": "2025-01-15T10:30:00"
}
```

### POST /embed/conversation
Store a conversation turn
```bash
curl -X POST http://localhost:8400/embed/conversation \
  -H "Content-Type: application/json" \
  -d '{
    "user": "What is my name?",
    "assistant": "Your name is Roland.",
    "timestamp": "2025-01-15T10:30:00"
  }'
```

### GET /context?query=...&max_tokens=300
Retrieve relevant context for a query
```bash
curl "http://localhost:8400/context?query=What%20are%20my%20goals&max_tokens=300"
```

Response:
```json
{
  "context": "[From user.md]\n## Goals\n- Build SecureBot...",
  "tokens_estimate": 150,
  "sources": ["user.md", "conversation_history"]
}
```

### POST /summarize/session
Summarize current session.md to 200 tokens
- Uses phi4-mini to summarize
- Saves to `memory/summaries/session_2025-01-15.md`
- Updates session.md with summary
- Re-embeds memory automatically

```bash
curl -X POST http://localhost:8400/summarize/session
```

## Maintenance

### Re-embed After Memory Edits
After manually editing memory files:
```bash
bash services/scripts/embed_memory.sh
```

Or via API:
```bash
curl -X POST http://localhost:8400/embed/memory
```

### Automatic Re-embedding
Memory service automatically triggers re-embedding after:
- POST to `/memory/session` (session updates)
- Any memory file modification via API

### Session Summarization
Automatic at end of day via systemd timer:
```bash
# Runs daily at 11:59 PM
systemctl status securebot-daily.timer
```

Manual trigger:
```bash
curl -X POST http://localhost:8400/summarize/session
```

### Check ChromaDB Stats
```bash
curl http://localhost:8400/health | jq
```

### Clear ChromaDB (Reset)
```bash
# Stop docker
docker-compose down

# Delete ChromaDB data
rm -rf chroma/

# Restart and re-embed
docker-compose up -d
sleep 10
curl -X POST http://localhost:8400/embed/memory
```

## Performance Benefits

### Before RAG (Full Memory Context)
```
Prompt size: ~8000 tokens (full soul.md + user.md + session.md)
Response time: 120-180 seconds
Timeout rate: ~30% (httpx.ReadTimeout)
Context waste: ~90% of memory irrelevant to query
```

### After RAG (Relevant Chunks Only)
```
Prompt size: ~300 tokens (top 3 relevant chunks)
Response time: 15-30 seconds
Timeout rate: <1%
Context precision: ~95% relevance
```

**Result**: 4-6x faster responses, 95%+ timeout elimination

## Hardware Requirements

**Minimum** (Ryzen 5 3500U, 8GB RAM):
- nomic-embed-text: ~2s per embedding
- ChromaDB: ~50MB disk usage
- RAG overhead: +2-3s per query

**Recommended** (Modern CPU, 16GB RAM):
- nomic-embed-text: <1s per embedding
- ChromaDB: ~100MB disk usage
- RAG overhead: +1s per query

## Troubleshooting

### RAG service won't start
```bash
# Check logs
docker logs rag-service

# Common issues:
# 1. Ollama not running
ollama serve

# 2. nomic-embed-text not installed
ollama pull nomic-embed-text

# 3. Port 8400 in use
lsof -i :8400
```

### Context not relevant to query
```bash
# Check what's embedded
curl http://localhost:8400/health

# If memory_chunks = 0, embed memory:
curl -X POST http://localhost:8400/embed/memory

# Test retrieval
curl "http://localhost:8400/context?query=test"
```

### ChromaDB permission errors
```bash
# Fix ownership (user 1000:1000)
sudo chown -R 1000:1000 chroma/
```

### Slow embedding performance
```bash
# Switch to faster model
# Edit services/rag/rag_service.py:
EMBEDDING_MODEL = "all-minilm"

# Rebuild
docker-compose build rag-service
docker-compose up -d rag-service
```

## Configuration

### Adjust context size
Edit retrieval parameters in `services/rag/rag_service.py`:
```python
@app.get("/context")
async def get_context(query: str, max_tokens: int = 300):  # Change default
    # Search memory collection (top 2 results)
    memory_results = memory_collection.query(
        query_embeddings=[query_embedding],
        n_results=min(2, memory_collection.count())  # Change top N
    )
```

### Change conversation window size
```python
MAX_CONVERSATIONS = 100  # Change this in rag_service.py
```

### Adjust chunking strategy
```python
def chunk_markdown(content: str, source: str, max_tokens: int = 300):
    # Change max_tokens for larger/smaller chunks
    chunk_size = max_tokens * 4  # ~4 chars per token
    overlap = 50 * 4  # 50 token overlap (change this)
```

## Security Notes

- ChromaDB data stored in `./chroma/` (gitignored)
- No external API calls - all local
- Memory chunks include user profile data - keep chroma/ private
- Conversation history stored locally only
- No telemetry or usage tracking

## Future Enhancements

1. **Multi-modal embeddings**: Image/PDF context
2. **Skill embedding**: Search skills by semantic similarity
3. **Time-weighted retrieval**: Prefer recent context
4. **User feedback loop**: Learn from query relevance
5. **Hybrid search**: Combine vector + keyword search

## See Also

- [MEMORY.md](MEMORY.md) - Memory system overview
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [docker-compose.yml](../docker-compose.yml) - RAG service config
