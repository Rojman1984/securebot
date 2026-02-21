# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

SecureBot is a cost-optimized, self-hosted AI assistant that routes queries intelligently between free local inference (Ollama) and the Claude API. The core value proposition is ~97% cost reduction via skill reuse and local-first routing.

## Running the Project

```bash
# Start all services
docker-compose up -d

# Run the TUI CLI
python securebot-cli.py

# Health check all services
curl http://localhost:8080/health   # Gateway
curl http://localhost:8200/health   # Vault
curl http://localhost:8300/health   # Memory
curl http://localhost:8400/health   # RAG

# View logs
docker logs gateway
docker logs vault
# CLI debug logs: /tmp/securebot-cli.log
```

## Running Tests

```bash
python test_intent_classifier.py
python test_classifier_simple.py
python test_hybrid_classifier.py
python test_classifier_improvements.py
```

Tests run against a live Ollama instance and focus on classification accuracy. There is no central test runner or mocking framework.

## Service Ports

| Service  | Port | Purpose                           |
|----------|------|-----------------------------------|
| Gateway  | 8080 | Main API entry point              |
| Vault    | 8200 | Secrets storage & multi-provider search |
| Memory   | 8300 | Persistent user context           |
| RAG      | 8400 | ChromaDB vector embeddings        |
| Ollama   | 11434 | Local LLM (on host, not Docker)  |

Only the Gateway is exposed externally. All inter-service traffic is on the `securebot` Docker bridge network.

## Architecture & Request Flow

```
User → Gateway (8080) → Orchestrator
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
         Ollama (free)   Claude API ($0.006)  Skill Exec (free)
              │                               ▲
              └──── Skill Creation ($0.10) ───┘
```

The orchestrator in `gateway/orchestrator.py` makes routing decisions:
1. **SearchDetector** — keyword scan to detect web search intent
2. **SkillMatcher** — scans `skills/` for a SKILL.md that matches the query
3. **ComplexityClassifier** — routes to `simple_ollama | skill_execution | skill_creation | direct_claude`
4. **IntentClassifier** — KNOWLEDGE vs ACTION classification for further routing

The Vault service handles all external API calls (Google, Tavily, DuckDuckGo) so API keys are never passed to or visible by AI models.

## Key Files

- `gateway/orchestrator.py` — All routing intelligence; the most complex file (~41KB)
- `gateway/gateway_service.py` — FastAPI `/message` and `/health` endpoints
- `vault/vault_service.py` — Secret isolation + SearchOrchestrator with provider fallback
- `services/memory/memory_service.py` — Manages `soul.md`, `user.md`, `session.md`, `tasks.json`
- `services/rag/rag_service.py` — ChromaDB integration; three collections: memory, conversations, classifier_examples
- `common/auth.py` — HMAC-SHA256 inter-service auth with replay prevention (30s window + nonce)
- `common/config.py` — ConfigManager loading `~/.securebot/config.yml` with fallback defaults
- `securebot-cli.py` — Curses TUI; reads `~/securebot/.env` for `SERVICE_SECRET`

## Skills System

Skills live in `skills/<skill-name>/SKILL.md` with YAML frontmatter:

```yaml
---
name: skill-name
description: "trigger keywords used for matching"
category: search|code|stt|tts|general
priority: 1        # lower = higher priority
requires_api_key: true
execution: vault-tool|ollama|claude-code
tool_name: optional_tool_name
---
```

Matching scores: exact name match (+5), trigger word match (+3 each), description overlap (+0.5/word). A skill is selected if score ≥ 5. Skills execute free via Ollama after initial creation via Claude API.

## Inter-Service Authentication

All requests between services use HMAC-SHA256. Required headers:
- `X-Service-ID`, `X-Timestamp`, `X-Nonce`, `X-Signature`

Use `common/auth.py`'s `SignedClient` for authenticated calls and `verify_request()` as a FastAPI dependency on protected routes. Each service has an `ALLOWED_CALLERS` list.

## Configuration

User config at `~/.securebot/config.yml` (see `config/config.example.yml`). Key options:
- `skills.disabled_skills` — list of skills to skip
- `skills.search_priority` — override search provider order
- `gateway.search_detection` — `strict | normal | relaxed`
- `orchestrator.ollama_model` — default local model (e.g. `phi4-mini:3.8b`)
- `orchestrator.claude_model` — model for skill creation

## Secrets

API keys live in `vault/secrets/secrets.json` (gitignored). The Vault service injects them into tool calls at runtime. Access via `vault.get_secret("search.google_api_key")`. Never pass secrets directly to AI model context.

## CLI Commands

`/status`, `/vault`, `/memory`, `/edit`, `/clear`, `/tone [1-3]`, `/verbosity [1-5]`, `/help`

Default model for responses: `llama3:8b` (override with `RESPONSE_MODEL` env var).

## Do Not Touch

- `vault/secrets/secrets.json` — never overwrite programmatically
- `memory/soul.md` — chmod 444, read-only identity file; do not modify
- `chroma/` — do not delete without re-embedding all documents
- `.env` — `ANTHROPIC_API_KEY` is project-scoped only, never export to global shell

## Active Development Direction

**Next phase:** Distributed specialist agent fleet — SearchBot, CodeBot, MemoryBot, ReasonBot as isolated containers. SecureBot orchestrates; specialists receive sanitized payloads only (need-to-know context isolation).

**Pending:** Anonymized memory layer before implementing the Haiku router — memory files currently sent verbatim to the Anthropic API; this is a privacy concern that must be resolved first.

## Hardware

Ryzen 5 8600G + GTX 1050 Ti · 16GB RAM · SecureBot-P2 · McAllen TX
