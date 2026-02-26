# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

SecureBot is a cost-optimized, self-hosted AI assistant that routes queries intelligently between free local inference (Ollama) and the Claude API. The core value proposition is ~97% cost reduction via skill reuse, zero-shot intent routing, and local-first execution.

## Running the Project

```bash
# Start all services
docker compose up -d --build

# Run the TUI CLI
python securebot-cli.py

# Health check all services
curl [http://127.0.0.1:8080/health](http://127.0.0.1:8080/health)   # Gateway
curl [http://127.0.0.1:8200/health](http://127.0.0.1:8200/health)   # Vault
curl [http://127.0.0.1:8300/health](http://127.0.0.1:8300/health)   # Memory
curl [http://127.0.0.1:8400/health](http://127.0.0.1:8400/health)   # RAG

# View logs
docker compose logs -f gateway
```

## Service Ports

| Service | Port  | Purpose                                 |
| ------- | ----- | --------------------------------------- |
| Gateway | 8080  | Main API entry point & Orchestrator     |
| Vault   | 8200  | Secrets storage & multi-provider search |
| Memory  | 8300  | Persistent user context                 |
| RAG     | 8400  | ChromaDB vector embeddings              |
| CodeBot | 8500  | Skill generation agent                  |
| Ollama  | 11434 | Local LLM (on host, not Docker)         |

Only the Gateway is exposed externally. All inter-service traffic is on the `securebot` Docker bridge network.

## Architecture & Request Flow

```text
User Query
    ↓
[1] GLiClass Classification (144M params, <50ms)
    │
    ├── search    → Vault Web Search → llama3.2:3b summary (No RAG)
    ├── task      → Memory Service Direct Read → llama3.2:3b (No RAG)
    ├── knowledge → RAG Context Retrieval → llama3.2:3b (Uses ChromaDB)
    ├── chat      → RAG Context Retrieval → llama3.2:3b (Uses ChromaDB)
    └── action    → [2] Skill Registry (Deterministic exact match)
                        ↓
                    Match found?
                    ├── YES → Execute Bash/Ollama locally (Free)
                    └── NO  → [3] CodeBot (Pi + Haiku) → Save → Execute (~$0.01)
                                   ↓ (CodeBot unavailable?)
                               [4] Haiku API direct (fallback only)
```

**Key Principle:** Tool routing is deterministic. Memory retrieval is probabilistic. **These two pipelines must never merge.** RAG is consulted ONLY for knowledge and chat intents. Legacy LLM-based classifiers (`phi4-mini`) have been retired.

## Key Files

- `gateway/orchestrator.py` — The core routing pipeline. Contains the master pre-router, strict pipeline separation, and `_sanitize_for_cloud` privacy layer.
- `gateway/gliclass_classifier.py` — Zero-shot intent classifier. Loaded once into GPU/RAM at startup.
- `gateway/gateway_service.py` — FastAPI endpoints.
- `gateway/watchdog_service.py` — ReAct daemon — polls systemctl for failed units, fetches journalctl logs, diagnoses via llama3.2:3b, writes /memory/jobs_status.json.
- `vault/vault_service.py` — Secret isolation + SearchOrchestrator with provider fallback.
- `services/memory/memory_service.py` — Manages `soul.md`, `user.md`, `session.md`, `tasks.json`.
- `services/rag/rag_service.py` — ChromaDB integration.
- `securebot-cli.py` — Curses TUI. Connects to `127.0.0.1` explicitly. Type `/jobs` to toggle the System Dashboard (job health, watchdog diagnoses, pending approval queue with inline resolve input).
- `codebot/tools/tool_request_approval.py` — HMAC-signed HITL tool — POSTs to `/approvals/request`, polls `/approvals/status/{id}` every 5s up to 5min.

## Skills System

Skills live in `skills/<skill-name>/SKILL.md` with YAML frontmatter.

```yaml
---
name: datetime-now
description: Returns the current system date and time
triggers:
  - what time is it
  - today's date
execution_mode: bash
timeout: 5
---
```

* **Matching:** Exact substring match based on `triggers` array in the frontmatter. (The legacy +5/+3 scoring system is retired).
* **Execution (Bash):** Scripts are written to a temp file and executed via `subprocess.run` on the host OS as a locked-down user (`sudo -u securebot-scripts`). The `stdout` is then passed to Ollama to be wrapped in natural language.
* **Execution (Ollama):** Pure prompt manipulation using `$ARGUMENTS`.
* **Execution (Python):** Script block extracted from SKILL.md, written to temp file, executed via `sudo -u securebot-scripts python3`. stdout captured and returned directly (no Ollama wrap). Used for structured data tasks like cost reporting.

## Inter-Service Authentication & Security

* **HMAC-SHA256:** All requests between services use `X-Service-ID`, `X-Timestamp`, `X-Nonce`, `X-Signature`.
* **Endpoint Protection:** `Depends(verify_service_request)` is wired to all protected endpoints in vault, memory, and rag via the `APIRouter` pattern. `/health` endpoints remain public for Docker healthchecks. All three services (vault :8200, memory :8300, rag :8400) return 401 on unsigned requests. `/internal/test-skill` on gateway accepts codebot service ID only.
* **Approval Queue Endpoints (gateway :8080):**

  | Endpoint | Auth |
  |----------|------|
  | `POST /approvals/request` | HMAC-SHA256 (codebot only) |
  | `GET  /approvals/pending` | API key (X-API-Key) |
  | `POST /approvals/resolve/{id}` | API key (X-API-Key) |
  | `GET  /approvals/status/{id}` | HMAC-SHA256 (codebot only) |
* **Bash Sandboxing:** The `gateway` container executes bash scripts using `sudo -u securebot-scripts` configured via host-side sudoers, preventing root container escapes.
* **Anonymization Layer:** Before sending requests to Anthropic's Haiku API for skill creation, `orchestrator.py` runs `_sanitize_for_cloud`. This regex engine redacts emails, IPs, MAC addresses, SSH keys, and explicit keywords defined in the `.env` via `REDACT_WORDS`.

## Configuration

* `vault/secrets/secrets.json` — API keys. Injected by Vault at runtime. Never passed to AI models.
* `.env` — Holds `GATEWAY_API_KEY`, `SERVICE_SECRET`, and `REDACT_WORDS` (for the anonymization layer).

## Do Not Touch

- `vault/secrets/secrets.json` — never overwrite programmatically.
- `memory/soul.md` — chmod 444, read-only identity file.
- **Skills Collection:** Do not embed `SKILL.md` files into ChromaDB. Skills are loaded directly into RAM by the `SkillRegistry` object.
- `codebot/tools/` — Pi CLI tool definitions. Modifying these breaks the CodeBot skill generation pipeline.

## Active Development Direction

**Current phase:** Sprint 3 complete. All three sprints delivered. Next phase: Specialist Agent Fleet (SearchBot, MemoryBot, ReasonBot as isolated containers). SecureBot orchestrates; specialists receive sanitized payloads only (need-to-know context isolation).

**Hardware:**
Ryzen 5 8600G + GTX 1050 Ti · 16GB RAM · SecureBot-P2 · Mission, TX
