#!/usr/bin/env python3
"""
RAG Service - Retrieval Augmented Generation for SecureBot
Embeds memory files and conversation history into ChromaDB
Retrieves relevant context for queries without loading full memory
"""
import os
import sys
import re
import httpx
import chromadb
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.auth import verify_service_request, create_auth_dependency

app = FastAPI(title="SecureBot RAG Service")

# Environment configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
MEMORY_DIR = Path(os.getenv("MEMORY_DIR", "/memory"))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", "/chroma"))
EMBEDDING_MODEL = "nomic-embed-text"
MAX_CONVERSATIONS = 100

# Auth configuration
ALLOWED_CALLERS = os.getenv("ALLOWED_CALLERS", "gateway,memory-service,heartbeat").split(",")

# Create auth dependency
auth_required = create_auth_dependency(ALLOWED_CALLERS)

# Initialize ChromaDB
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))

# Collections
memory_collection = chroma_client.get_or_create_collection(
    name="memory",
    metadata={"hnsw:space": "cosine"}
)
conversation_collection = chroma_client.get_or_create_collection(
    name="conversations",
    metadata={"hnsw:space": "cosine"}
)
classifier_collection = chroma_client.get_or_create_collection(
    name="classifier_examples",
    metadata={"hnsw:space": "cosine"}
)


# Request models
class ConversationTurn(BaseModel):
    user: str
    assistant: str
    timestamp: str
    user_id: Optional[str] = None  # for tenant isolation in conversations collection


# Helper functions
def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 characters)"""
    return len(text) // 4


async def get_ollama_embedding(text: str) -> List[float]:
    """Get embedding from Ollama"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{OLLAMA_HOST}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": text}
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            print(f"Embedding error: {e}")
            raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")


def chunk_markdown(content: str, source: str, max_tokens: int = 300) -> List[Dict[str, Any]]:
    """
    Chunk markdown by headers with overlap
    Returns list of {text, metadata}
    """
    chunks = []

    # Split by ## headers
    sections = re.split(r'\n##\s+', content)

    for i, section in enumerate(sections):
        if not section.strip():
            continue

        # Extract section title
        lines = section.split('\n', 1)
        title = lines[0].strip('#').strip() if lines else "Intro"
        body = lines[1] if len(lines) > 1 else section

        # Split large sections into smaller chunks
        words = body.split()
        chunk_size = max_tokens * 4  # ~4 chars per token
        overlap = 50 * 4  # 50 token overlap

        start = 0
        chunk_num = 0
        while start < len(' '.join(words)):
            chunk_text = ' '.join(words[start:start + chunk_size])

            if not chunk_text.strip():
                break

            chunks.append({
                "text": f"## {title}\n{chunk_text}",
                "metadata": {
                    "source": source,
                    "section": title,
                    "chunk": chunk_num,
                    "timestamp": datetime.now().isoformat()
                }
            })

            chunk_num += 1
            start += chunk_size - overlap

            if start + overlap >= len(' '.join(words)):
                break

    return chunks


async def embed_memory_files():
    """Embed all memory files into ChromaDB"""
    memory_files = ["soul.md", "user.md", "session.md"]
    total_chunks = 0

    # Clear existing memory collection
    chroma_client.delete_collection("memory")
    global memory_collection
    memory_collection = chroma_client.create_collection(
        name="memory",
        metadata={"hnsw:space": "cosine"}
    )

    for filename in memory_files:
        filepath = MEMORY_DIR / filename
        if not filepath.exists():
            print(f"Skipping {filename} - not found")
            continue

        content = filepath.read_text(encoding="utf-8")
        chunks = chunk_markdown(content, filename, max_tokens=300)

        for chunk in chunks:
            try:
                embedding = await get_ollama_embedding(chunk["text"])

                memory_collection.add(
                    embeddings=[embedding],
                    documents=[chunk["text"]],
                    metadatas=[chunk["metadata"]],
                    ids=[f"{filename}_{chunk['metadata']['chunk']}_{datetime.now().timestamp()}"]
                )
                total_chunks += 1
            except Exception as e:
                print(f"Failed to embed chunk from {filename}: {e}")
                continue

    return total_chunks


# Endpoints

@app.get("/health")
async def health_check():
    """Service health check with ChromaDB stats"""
    try:
        memory_count = memory_collection.count()
        conversation_count = conversation_collection.count()
        classifier_count = classifier_collection.count()

        return {
            "status": "healthy",
            "embedding_model": EMBEDDING_MODEL,
            "memory_chunks": memory_count,
            "conversations": conversation_count,
            "classifier_examples": classifier_count,
            "chroma_path": str(CHROMA_DIR)
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.post("/embed/memory")
async def embed_memory(
    request: Request
):
    """Re-embed all memory files. Requires HMAC authentication."""
    try:
        chunks_embedded = await embed_memory_files()
        return {
            "status": "ok",
            "chunks_embedded": chunks_embedded,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed/conversation")
async def embed_conversation(
    turn: ConversationTurn,
    request: Request,
    _auth = Depends(auth_required)
):
    """Store a conversation turn. Requires HMAC authentication."""
    try:
        # Truncate long messages
        user_text = turn.user[:500]
        assistant_text = turn.assistant[:500]
        combined = f"User: {user_text}\nAssistant: {assistant_text}"

        # Get embedding
        embedding = await get_ollama_embedding(combined)

        # Store in ChromaDB — include user_id for tenant isolation
        conv_metadata = {"timestamp": turn.timestamp}
        if turn.user_id:
            conv_metadata["user_id"] = turn.user_id
        conversation_collection.add(
            embeddings=[embedding],
            documents=[combined],
            metadatas=[conv_metadata],
            ids=[f"conv_{turn.timestamp}_{datetime.now().timestamp()}"]
        )

        # Maintain rolling window (keep last 100 conversations)
        count = conversation_collection.count()
        if count > MAX_CONVERSATIONS:
            # Get all IDs sorted by timestamp
            results = conversation_collection.get()
            if results and results['ids']:
                ids_to_delete = sorted(results['ids'])[:count - MAX_CONVERSATIONS]
                conversation_collection.delete(ids=ids_to_delete)

        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/context")
async def get_context(
    query: str,
    max_tokens: int = 300,
    user_id: Optional[str] = None,
    request: Request = None,
    _auth = Depends(auth_required)
):
    """
    Get relevant context for a query.
    Searches memory (top 2, shared) and conversations (top 1, filtered by user_id).
    Requires HMAC authentication.
    """
    try:
        # Get query embedding
        query_embedding = await get_ollama_embedding(query)

        # Search memory collection (top 2 results) - shared, no user filter
        memory_results = memory_collection.query(
            query_embeddings=[query_embedding],
            n_results=max(1, min(2, memory_collection.count()))
        )


        # Search conversations - filter by user_id for tenant isolation
        conversation_results = None
        conv_count = conversation_collection.count()
        if conv_count > 0:
            try:
                query_kwargs = dict(
                    query_embeddings=[query_embedding],
                    n_results=max(1, min(1, conv_count))
                )
                if user_id:
                    query_kwargs["where"] = {"user_id": user_id}
                conversation_results = conversation_collection.query(**query_kwargs)
            except Exception as e:
                # Graceful fallback if where-filter fails (older docs without user_id)
                print(f"Conversation filter error (falling back to unfiltered): {e}")
                try:
                    conversation_results = conversation_collection.query(
                        query_embeddings=[query_embedding],
                        n_results=max(1, min(1, conv_count))
                    )
                except Exception:
                    conversation_results = None

        # Build context string
        context_parts = []
        sources = []

        if memory_results and memory_results['documents']:
            for doc, metadata in zip(memory_results['documents'][0], memory_results['metadatas'][0]):
                context_parts.append(f"[From {metadata['source']}]\n{doc}")
                sources.append(metadata['source'])

        if conversation_results and conversation_results['documents']:
            for doc in conversation_results['documents'][0]:
                context_parts.append(f"[Past conversation]\n{doc}")
                sources.append("conversation_history")

        context = "\n\n---\n\n".join(context_parts)

        # Truncate if exceeds max_tokens
        if estimate_tokens(context) > max_tokens:
            # Trim to max_tokens
            char_limit = max_tokens * 4
            context = context[:char_limit] + "..."

        return {
            "context": context,
            "tokens_estimate": estimate_tokens(context),
            "sources": list(set(sources))
        }
    except Exception as e:
        # Graceful fallback - return empty context
        print(f"Context retrieval error: {e}")
        return {
            "context": "",
            "tokens_estimate": 0,
            "sources": [],
            "error": str(e)
        }


@app.get("/classify/examples")
async def get_classifier_examples(
    query: str,
    k: int = 3,
    request: Request = None,
    _auth = Depends(auth_required)
):
    """
    Get k nearest neighbor examples for query classification.
    Requires HMAC authentication.

    Args:
        query: The query to find similar examples for
        k: Number of examples to return (default 3)

    Returns:
        {"examples": [{"query": "...", "label": "ACTION|KNOWLEDGE|SKILL_NEEDED|CURRENT", "reason": "...", "chain_of_thought": "..."}]}
    """
    try:
        # Check if collection is empty
        if classifier_collection.count() == 0:
            print("Classifier examples collection is empty")
            return {"examples": []}

        # Get embedding for query
        query_embedding = await get_ollama_embedding(query)

        # Search for k nearest neighbors
        results = classifier_collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, classifier_collection.count())
        )

        # Format results
        examples = []
        if results and results['metadatas']:
            for metadata in results['metadatas'][0]:
                examples.append({
                    "query": metadata['query'],
                    "label": metadata['label'],
                    "reason": metadata['reason'],
                    "chain_of_thought": metadata.get('chain_of_thought', '')
                })

        return {"examples": examples}

    except Exception as e:
        # Graceful fallback - return empty list
        print(f"Classifier examples retrieval error: {e}")
        return {"examples": []}


@app.post("/classify/seed")
async def seed_classifier_examples(
    request: Request
):
    """
    Seed the classifier_examples collection with hardcoded examples.
    Idempotent - only seeds if collection is empty.
    Requires HMAC authentication.

    Returns:
        {"status": "ok", "seeded": N}
    """
    try:
        # Check if already seeded
        if classifier_collection.count() > 0:
            print("Classifier examples already seeded")
            return {"status": "ok", "seeded": 0, "message": "Already seeded"}

        # Define seed examples - 6 per class (24 total), with chain_of_thought
        seed_examples = [
            # KNOWLEDGE examples (6)
            {
                "query": "Design a scalable microservices architecture for e-commerce. Consider trade-offs between consistency and availability.",
                "label": "KNOWLEDGE",
                "reason": "Asks for architectural guidance and trade-off analysis, not a deliverable artifact.",
                "chain_of_thought": "The user asks to 'design' with 'consider trade-offs' — this is analytical guidance, not a deliverable. No code or file is requested. → KNOWLEDGE"
            },
            {
                "query": "What are the pros and cons of using Redis vs Memcached for session storage?",
                "label": "KNOWLEDGE",
                "reason": "Comparison of technologies, no artifact requested.",
                "chain_of_thought": "'Pros and cons' signals comparative analysis. No action verb requesting a specific artifact. → KNOWLEDGE"
            },
            {
                "query": "Explain how Python list comprehensions work with nested loops.",
                "label": "KNOWLEDGE",
                "reason": "Explanation of a concept.",
                "chain_of_thought": "'Explain how' is a canonical knowledge signal. User wants understanding, not code. → KNOWLEDGE"
            },
            {
                "query": "How does consistent hashing work and when should I use it?",
                "label": "KNOWLEDGE",
                "reason": "Conceptual explanation with usage guidance.",
                "chain_of_thought": "'How does X work' + 'when should I use it' — both request explanation and guidance. No artifact. → KNOWLEDGE"
            },
            {
                "query": "What are best practices for securing a FastAPI application?",
                "label": "KNOWLEDGE",
                "reason": "Best practices discussion, no code artifact requested.",
                "chain_of_thought": "'Best practices' is a knowledge signal. User wants a list of recommendations, not code. → KNOWLEDGE"
            },
            {
                "query": "What are the trade-offs between monolith and microservices for a startup?",
                "label": "KNOWLEDGE",
                "reason": "Architectural trade-off analysis.",
                "chain_of_thought": "'Trade-offs between' is a strong analytical signal. No implementation artifact requested. → KNOWLEDGE"
            },

            # ACTION examples (6)
            {
                "query": "Reverse the string hello world",
                "label": "ACTION",
                "reason": "Specific transformation of specific input requested.",
                "chain_of_thought": "Direct imperative verb 'reverse' on a specific input. An executable result is expected immediately. No skill gap. → ACTION"
            },
            {
                "query": "Write a bash script to monitor disk usage and alert when above 90%",
                "label": "ACTION",
                "reason": "Specific script artifact requested.",
                "chain_of_thought": "'Write a bash script' is an unambiguous artifact request. The output is a specific file. Existing bash skill available. → ACTION"
            },
            {
                "query": "Build a Python function that parses a CSV and returns a dict",
                "label": "ACTION",
                "reason": "Specific code artifact to produce.",
                "chain_of_thought": "'Build a Python function' requests a concrete code artifact. Standard capability, no new skill needed. → ACTION"
            },
            {
                "query": "Generate an Ansible playbook to install nginx on Ubuntu",
                "label": "ACTION",
                "reason": "Specific playbook artifact to produce.",
                "chain_of_thought": "'Generate an Ansible playbook' — clear artifact request. Standard devops task within existing capabilities. → ACTION"
            },
            {
                "query": "Convert this JSON to YAML: {name: roland, role: admin}",
                "label": "ACTION",
                "reason": "Specific data transformation with given input.",
                "chain_of_thought": "Imperative 'convert' with specific input provided. Immediate transformation, no new skill required. → ACTION"
            },
            {
                "query": "Implement a binary search function in Python",
                "label": "ACTION",
                "reason": "Specific code artifact, not a conceptual explanation.",
                "chain_of_thought": "'Implement' signals code production. 'Binary search in Python' is a standard algorithm — within existing capabilities. → ACTION"
            },

            # SKILL_NEEDED examples (6)
            {
                "query": "Generate a PDF report from this CSV data",
                "label": "SKILL_NEEDED",
                "reason": "No PDF generation skill exists.",
                "chain_of_thought": "User wants a PDF artifact from CSV. Checking skills index: no pdf-generation skill found. A new skill must be created before execution. → SKILL_NEEDED"
            },
            {
                "query": "Send me a Telegram message when disk usage exceeds 90%",
                "label": "SKILL_NEEDED",
                "reason": "No Telegram skill exists.",
                "chain_of_thought": "Requires Telegram bot integration. Checking skills index: no telegram-notify skill found. This is a new capability that needs a skill. → SKILL_NEEDED"
            },
            {
                "query": "Create a Docker Compose file for a Python app with PostgreSQL and Redis",
                "label": "SKILL_NEEDED",
                "reason": "No docker-compose skill exists.",
                "chain_of_thought": "Artifact request for a multi-service Docker Compose. Skills index: no docker-compose-generator skill found. Queuing skill creation. → SKILL_NEEDED"
            },
            {
                "query": "Monitor my SecureBot services and send a daily email summary",
                "label": "SKILL_NEEDED",
                "reason": "No email skill exists.",
                "chain_of_thought": "Requires email integration and service monitoring. Skills index: no email-sender or service-monitor skill found. → SKILL_NEEDED"
            },
            {
                "query": "Convert this markdown file to a Word document",
                "label": "SKILL_NEEDED",
                "reason": "No markdown-to-docx skill exists.",
                "chain_of_thought": "markdown→docx conversion requires pandoc or python-docx integration. Skills index: no markdown-to-docx skill. → SKILL_NEEDED"
            },
            {
                "query": "Set up a Python virtual environment and install dependencies from requirements.txt",
                "label": "SKILL_NEEDED",
                "reason": "No python-env-setup skill exists.",
                "chain_of_thought": "Shell automation for venv + pip install. Skills index: no python-env-setup skill found. Queuing for creation. → SKILL_NEEDED"
            },

            # CURRENT examples (6)
            {
                "query": "What are the latest AI developments in 2026?",
                "label": "CURRENT",
                "reason": "Latest and 2026 signal recency beyond 2023 training.",
                "chain_of_thought": "'Latest' + '2026' both signal real-time information beyond training cutoff. Cannot answer from static knowledge. → CURRENT"
            },
            {
                "query": "What is the current price of Bitcoin?",
                "label": "CURRENT",
                "reason": "Prices change in real-time.",
                "chain_of_thought": "'Current price' is inherently real-time data. Bitcoin price changes every second. Static training data is useless here. → CURRENT"
            },
            {
                "query": "Who won the Super Bowl this year?",
                "label": "CURRENT",
                "reason": "Sports results are time-sensitive.",
                "chain_of_thought": "'This year' signals recency. Sports results are not in training data for current season. Web search required. → CURRENT"
            },
            {
                "query": "What are the latest Ubuntu 24.04 security updates?",
                "label": "CURRENT",
                "reason": "Security updates released continuously.",
                "chain_of_thought": "'Latest' + 'security updates' — CVEs and patches are released daily. Training data is stale for this. → CURRENT"
            },
            {
                "query": "Is there a new version of phi4-mini available?",
                "label": "CURRENT",
                "reason": "Model releases happen after training cutoff.",
                "chain_of_thought": "'New version' of a model released post-cutoff. Model release information requires web search. → CURRENT"
            },
            {
                "query": "What is the current status of the Anthropic API rate limits?",
                "label": "CURRENT",
                "reason": "API policies change frequently.",
                "chain_of_thought": "'Current status' of API policies — these change frequently. Must query live documentation or search. → CURRENT"
            },
        ]

        # Embed and store each example
        seeded_count = 0
        for example in seed_examples:
            try:
                # Get embedding for query
                embedding = await get_ollama_embedding(example["query"])

                # Store in collection with chain_of_thought in metadata
                classifier_collection.add(
                    embeddings=[embedding],
                    documents=[example["query"]],
                    metadatas=[{
                        "query": example["query"],
                        "label": example["label"],
                        "reason": example["reason"],
                        "chain_of_thought": example["chain_of_thought"]
                    }],
                    ids=[f"example_{seeded_count}_{datetime.now().timestamp()}"]
                )
                seeded_count += 1
            except Exception as e:
                print(f"Failed to seed example: {example['query'][:50]}... Error: {e}")
                continue

        print(f"Seeded {seeded_count} classifier examples")
        return {"status": "ok", "seeded": seeded_count}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/summarize/session")
async def summarize_session(
    request: Request,
    _auth = Depends(auth_required)
):
    """
    Summarize current session.md to 200 tokens max
    Requires HMAC authentication.
    Save summary and re-embed memory
    """
    try:
        session_file = MEMORY_DIR / "session.md"
        if not session_file.exists():
            raise HTTPException(status_code=404, detail="session.md not found")

        content = session_file.read_text(encoding="utf-8")

        # Use Ollama to summarize
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": "phi4-mini:3.8b",
                    "prompt": f"Summarize this session log concisely in 200 tokens or less. Focus on key tasks, decisions, and outcomes:\n\n{content}",
                    "stream": False
                }
            )
            response.raise_for_status()
            summary = response.json()["response"]

        # Save summary to archive
        summaries_dir = MEMORY_DIR / "summaries"
        summaries_dir.mkdir(exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        summary_file = summaries_dir / f"session_{date_str}.md"
        summary_file.write_text(summary, encoding="utf-8")

        # Update session.md with summary
        new_session = f"# Session Log\n\n## Summary (as of {date_str})\n{summary}\n\n## Current Session\n"
        session_file.write_text(new_session, encoding="utf-8")

        # Re-embed memory
        await embed_memory_files()

        return {
            "status": "ok",
            "summary": summary,
            "summary_file": str(summary_file)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print(f"Starting RAG Service on port 8400")
    print(f"Ollama host: {OLLAMA_HOST}")
    print(f"Memory dir: {MEMORY_DIR}")
    print(f"ChromaDB dir: {CHROMA_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=8400)
