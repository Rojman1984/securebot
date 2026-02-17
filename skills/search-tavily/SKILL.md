---
name: search-tavily
description: Search using Tavily AI-optimized API for research, fact-finding, and getting direct answers
category: search
priority: 2
requires_api_key: true
execution: vault-tool
tool_name: tavily_search
---

# Tavily Search

Perform AI-optimized web searches using Tavily API.

## Provider Details

- **Provider**: Tavily API
- **Free Tier**: 1,000 queries/month
- **Best For**: AI-optimized research, fact-finding, direct answers
- **Requires API Key**: Yes
- **Special Feature**: Provides direct answers when available

## Usage

This skill is automatically invoked when:
1. A search is needed (detected by gateway)
2. Tavily is the highest priority available provider
3. Rate limits have not been exceeded

## Configuration

Requires the following secret in `/vault/secrets.json`:
```json
{
  "search": {
    "tavily_api_key": "your-api-key"
  }
}
```

## Priority

Priority 2 - Tried after Google (if configured) or first if Google not available.
