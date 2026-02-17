---
name: search-duckduckgo
description: Search using DuckDuckGo for privacy-focused searches with no API key required
category: search
priority: 3
requires_api_key: false
execution: vault-tool
tool_name: duckduckgo_search
---

# DuckDuckGo Search

Perform web searches using DuckDuckGo (no API key required).

## Provider Details

- **Provider**: DuckDuckGo Search
- **Free Tier**: No API key needed (rate limited)
- **Best For**: Fallback provider, privacy-focused searches
- **Requires API Key**: No

## Usage

This skill is automatically invoked when:
1. A search is needed (detected by gateway)
2. Other providers are unavailable or rate-limited
3. Always available as fallback

## Configuration

No configuration required. This provider is always available.

## Priority

Priority 3 (lowest) - Used as fallback when other providers are unavailable or rate-limited.

## Notes

- No API key required
- Always enabled
- Rate limits may apply from DuckDuckGo's side
