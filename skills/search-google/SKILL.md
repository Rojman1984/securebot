---
name: search-google
description: Search the web using Google Custom Search API for general queries, coding questions, nutrition information, and planning
category: search
priority: 1
requires_api_key: true
execution: vault-tool
tool_name: google_search
---

# Google Custom Search

Perform web searches using Google Custom Search API.

## Provider Details

- **Provider**: Google Custom Search API
- **Free Tier**: 100 queries/day (3,000/month)
- **Best For**: General queries, coding, nutrition, planning
- **Requires API Key**: Yes

## Usage

This skill is automatically invoked when:
1. A search is needed (detected by gateway)
2. Google is the highest priority available provider
3. Rate limits have not been exceeded

## Configuration

Requires the following secrets in `/vault/secrets.json`:
```json
{
  "search": {
    "google_api_key": "your-api-key",
    "google_cx": "your-search-engine-id"
  }
}
```

## Priority

Priority 1 (highest) - Tried first when available.
