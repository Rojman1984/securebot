#!/bin/bash
# Re-embed all memory files into ChromaDB
# Run this after manually editing memory files

set -e

echo "🔄 Re-embedding memory files into ChromaDB..."

# Trigger RAG service to re-embed
response=$(curl -s -X POST http://localhost:8400/embed/memory)

if echo "$response" | grep -q '"status":"ok"'; then
    chunks=$(echo "$response" | grep -o '"chunks_embedded":[0-9]*' | cut -d: -f2)
    echo "✅ Memory re-embedded successfully: $chunks chunks"
else
    echo "❌ Re-embedding failed"
    echo "$response"
    exit 1
fi
