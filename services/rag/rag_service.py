#!/usr/bin/env python3
"""
RAG Service - Retrieval Augmented Generation for SecureBot
Embeds memory files and conversation history into ChromaDB
Retrieves relevant context for queries without loading full memory
"""
import os
import re
import httpx
import chromadb
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="SecureBot RAG Service")

# Environment configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
MEMORY_DIR = Path(os.getenv("MEMORY_DIR", "/memory"))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", "/chroma"))
EMBEDDING_MODEL = "nomic-embed-text"
MAX_CONVERSATIONS = 100

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


# Request models
class ConversationTurn(BaseModel):
    user: str
    assistant: str
    timestamp: str


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

        return {
            "status": "healthy",
            "embedding_model": EMBEDDING_MODEL,
            "memory_chunks": memory_count,
            "conversations": conversation_count,
            "chroma_path": str(CHROMA_DIR)
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.post("/embed/memory")
async def embed_memory():
    """Re-embed all memory files"""
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
async def embed_conversation(turn: ConversationTurn):
    """Store a conversation turn"""
    try:
        # Truncate long messages
        user_text = turn.user[:500]
        assistant_text = turn.assistant[:500]
        combined = f"User: {user_text}\nAssistant: {assistant_text}"

        # Get embedding
        embedding = await get_ollama_embedding(combined)

        # Store in ChromaDB
        conversation_collection.add(
            embeddings=[embedding],
            documents=[combined],
            metadatas=[{"timestamp": turn.timestamp}],
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
async def get_context(query: str, max_tokens: int = 300):
    """
    Get relevant context for a query
    Searches memory (top 2) and conversations (top 1)
    """
    try:
        # Get query embedding
        query_embedding = await get_ollama_embedding(query)

        # Search memory collection (top 2 results)
        memory_results = memory_collection.query(
            query_embeddings=[query_embedding],
            n_results=max(1, min(2, memory_collection.count()))
        )





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


@app.post("/summarize/session")
async def summarize_session():
    """
    Summarize current session.md to 200 tokens max
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
