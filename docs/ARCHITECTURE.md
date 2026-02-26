# SecureBot Architecture

Technical deep dive into SecureBot's cost-optimized hybrid architecture.

---

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Routing Strategy](#routing-strategy)
- [Skill System Design](#skill-system-design)
- [Security Model](#security-model)
- [Cost Optimization](#cost-optimization)
- [API Reference](#api-reference)

---

## System Overview

SecureBot uses a **hybrid architecture** combining local and cloud inference for maximum cost efficiency:

### Design Principles

1. **Local First** — Run simple tasks on YOUR hardware (zero marginal cost)
2. **Cloud When Needed** — Use Claude Haiku API only for new skill creation (~$0.01/skill)
3. **Secrets Isolation** — API keys never exposed to AI models (vault pattern)
4. **Skill Reuse** — Create reusable capabilities once, execute forever FREE
5. **Zero-Shot Routing** — GLiClass (144M params, <50ms) replaces all heuristic classifiers
6. **Strict Pipeline Separation** — Deterministic (Tool) and Probabilistic (RAG) paths never merge
7. **Graceful Fallback** — Multi-provider search with automatic failover

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                           │
│  • REST API endpoints (Gateway port 8080)                       │
│  • TUI CLI (securebot-cli.py)                                   │
│  • Request validation, API key enforcement                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      ROUTING LAYER                              │
│  • GLiClass zero-shot intent classification (<50ms)             │
│  • SkillRegistry deterministic trigger matching (action only)   │
│  • Strict Pipeline A / Pipeline B separation                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     EXECUTION LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │    Ollama    │  │  Haiku API   │  │  Bash Runner │         │
│  │ (Local/Free) │  │ (Skill gen)  │  │  (Sandboxed) │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      STORAGE LAYER                              │
│  • Skills directory (RAM-loaded SkillRegistry)                  │
│  • Vault secrets (secrets.json, volume-mounted)                 │
│  • Memory service (soul.md, user.md, session.md, tasks.json)    │
│  • RAG / ChromaDB (knowledge + chat context only)               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Gateway Service (Port 8080)

**Purpose:** API entry point, GATEWAY_API_KEY enforcement, and orchestration trigger.

**Responsibilities:**
- Accept messages from any channel (API, TUI, etc.)
- Enforce `X-API-Key` header on all non-health endpoints
- Detect `web_search_needed` flag from orchestrator and execute vault search
- Pass `user_id` to both RAG (for context filtering) and Memory services

**Tech Stack:**
- FastAPI (async Python web framework)
- httpx (async HTTP client)
- Pydantic (request validation)

**Key Files:**
- `gateway/gateway_service.py` — FastAPI service
- `gateway/orchestrator.py` — Routing logic and privacy layer

**Endpoints:**
```
POST /message          → Send message to SecureBot
GET  /health           → Health check (all 5 services)
GET  /skills           → List loaded skills
POST /skills/reload    → Hot-reload SkillRegistry from disk
```

---

### 2. Orchestrator (Routing Intelligence)

**Purpose:** Zero-shot intent routing with strict pipeline separation. All heuristic classifiers have been retired.

**Key Principle:** Tool routing is deterministic. Memory retrieval is probabilistic. **These two pipelines must never merge.**

#### 2.1 GLiClass Master Pre-Router

```
GLiClass (knowledgator/gliclass-small-v1.0)
  • 144M parameters — loaded once into GPU/RAM at startup
  • <50ms classification latency
  • Zero-shot: no fine-tuning required
  • Output: one of (search, task, knowledge, chat, action)
```

The `determine_routing_path()` function calls `classify_intent()` from `gliclass_classifier.py`. GLiClass is the single gatekeeper — it evaluates intent first, and only if it returns `action` does the orchestrator consult the SkillRegistry.

**Retired components (do not reference):**
- `ComplexityClassifier` — removed
- `SkillMatcher` scoring algorithm (+5 name, +3 trigger, +0.5 description) — removed
- `phi4-mini` as classifier — removed
- `SearchDetector` keyword heuristics — removed (search is now a GLiClass intent)

#### 2.2 SkillRegistry (Deterministic)

```python
class SkillRegistry:
    """
    Deterministic skill lookup. Exact substring match on trigger phrases.
    No vectors. No similarity scoring. No ChromaDB.
    Skills loaded into RAM at startup. Hot-reloadable via /skills/reload.
    """
```

**Matching Algorithm (exact, no scoring):**
1. Load all `SKILL.md` files from `/app/skills/` at startup
2. Parse YAML frontmatter; extract `triggers` list
3. On query: check if any trigger phrase is a substring of the lowercased user message
4. Return first match, or `None` (→ escalate to Haiku)

**SkillRegistry is consulted ONLY if GLiClass returns `action` intent.**

The legacy `SkillMatcher` class remains in `orchestrator.py` but is used only by the `/skills` listing endpoint — it plays no role in routing.

#### 2.3 Route Query — Two Strict Pipelines

```
User Query
    ↓
[1] GLiClass Classification (144M params, <50ms)
    │
    ├── search    → Pipeline A: Vault Web Search → llama3.2:3b summary (NO RAG)
    ├── task      → Pipeline A: Memory Service Direct Read → llama3.2:3b (NO RAG)
    ├── action    → Pipeline A: SkillRegistry lookup
    │                   ├── Match → Execute Bash/Ollama locally (FREE)
    │                   └── No match → Haiku API creates skill → Save → Execute (~$0.01)
    ├── knowledge → Pipeline B: RAG Context Retrieval → llama3.2:3b (ChromaDB)
    └── chat      → Pipeline B: RAG Context Retrieval → llama3.2:3b (ChromaDB)
```

**Pipeline A — Deterministic (no RAG/ChromaDB):**
- `search` → `_search_via_vault()` → vault SearchOrchestrator → Ollama summary
- `task` → `_get_tasks_from_memory()` → memory service `tasks.json` → Ollama summary
- `action` → SkillRegistry → execute locally, or Haiku generates new skill

**Pipeline B — Probabilistic (RAG/ChromaDB):**
- `knowledge` / `chat` → `_get_rag_context()` → ChromaDB retrieval → Ollama with context

RAG is **never** consulted for search, task, or action intents.

---

### 3. Vault Service (Port 8200)

**Purpose:** Secrets isolation and multi-provider web search.

**Security Model:**
```
WITHOUT VAULT:
  User query with sensitive context → AI sees raw secrets → potential leak

WITH VAULT:
  AI sends tool request {tool: "web_search", params: {...}}
  Vault injects API key at execution time → AI NEVER sees it
```

**SearchOrchestrator — Multi-Provider Strategy:**
```
Priority 1: Google Custom Search  (100/day free)
    ↓ (rate limit or error)
Priority 2: Tavily                (1000/month free, AI-optimized)
    ↓ (rate limit or error)
Priority 3: DuckDuckGo            (unlimited, no key needed)
```

**Vault /secret POST endpoint:**
- HMAC-authenticated endpoint added for inter-service API key retrieval
- `haiku_generate_skill()` calls this to get the Anthropic API key at skill creation time

---

### 4. Memory Service (Port 8300)

**Purpose:** Persistent user context across sessions.

**Files managed:**
| File | Purpose | Permissions |
|------|---------|-------------|
| `soul.md` | Identity and persona (immutable) | chmod 444 — read-only |
| `user.md` | Hardware profile, OS, preferences | Read/write |
| `session.md` | Current session context | Read/write |
| `tasks.json` | Task queue (dict format) | Read/write |

`user.md` is loaded at gateway startup into `BASE_SYSTEM_PROMPT` for all Ollama calls. It is also loaded by `haiku_generate_skill()` to provide architecture context for bash skill generation (sanitized before sending).

---

### 5. RAG Service (Port 8400)

**Purpose:** ChromaDB vector embeddings for knowledge and chat context retrieval.

**Collections:**
| Collection | Contents | Used by |
|-----------|---------|---------|
| `memory` | user/soul/session memory chunks | Pipeline B only |
| `conversations` | Conversation history (per user_id) | Pipeline B only |
| `classifier_examples` | Seed examples for classifier (legacy) | Not active |

**Critical constraint:** Skills are never embedded into ChromaDB. The `SkillRegistry` loads SKILL.md files directly into RAM.

**User isolation:** `/context` endpoint accepts `user_id` parameter; conversation context is filtered per user.

---

### 6. Ollama (Port 11434)

**Purpose:** Local LLM inference — runs on HOST machine, not in Docker.

**Active model:** `llama3.2:3b-instruct-q4_K_M` (set via `RESPONSE_MODEL` env var)

Accessed from Docker containers via `http://host.docker.internal:11434`.

---

## Data Flow

### Flow 1: Search Query

```
User: "latest AI news"
    ↓ Gateway validates API key
    ↓ GLiClass → intent: "search"
    ↓ Pipeline A: _search_via_vault()
    ↓ Vault SearchOrchestrator (Google → Tavily → DDG)
    ↓ _build_search_context() injects results
    ↓ Ollama llama3.2:3b summarizes (FREE)
    → Response  (cost: $0.00, engine: ollama, method: search)
```

### Flow 2: Action — Existing Skill

```
User: "what time is it"
    ↓ Gateway validates API key
    ↓ GLiClass → intent: "action"
    ↓ SkillRegistry.find_by_trigger("what time is it") → datetime-now
    ↓ execute_skill() → bash script → sudo -u securebot-scripts bash /tmp/xxx.sh
    ↓ stdout captured → Ollama wraps in natural language (FREE)
    → Response  (cost: $0.00, engine: ollama, method: skill_execution)
```

### Flow 3: Action — No Existing Skill (Haiku Creates It)

```
User: "check if port 443 is open"
    ↓ Gateway validates API key
    ↓ GLiClass → intent: "action"
    ↓ SkillRegistry → no match
    ↓ haiku_generate_skill():
        1. _sanitize_for_cloud(user_request)
        2. Load user.md → _sanitize_for_cloud(profile) → sanitized_profile
        3. POST Anthropic Haiku API with enhanced_prompt (request + sanitized context)
        4. Validate skill name regex, path traversal check
        5. Save SKILL.md → skill_registry.reload()
    ↓ execute_skill() new skill → bash → Ollama wrap
    → Response  (cost: ~$0.01 one-time, engine: claude+ollama, method: skill_execution)
```

### Flow 4: Knowledge / Chat Query

```
User: "how does the memory system work?"
    ↓ Gateway validates API key
    ↓ GLiClass → intent: "knowledge"
    ↓ Pipeline B: _get_rag_context() → ChromaDB similarity search
    ↓ Ollama llama3.2:3b with context (FREE)
    → Response  (cost: $0.00, engine: ollama, method: ollama_knowledge)
```

### Flow 5: Task Query

```
User: "what are my pending tasks?"
    ↓ Gateway validates API key
    ↓ GLiClass → intent: "task"
    ↓ Pipeline A: _get_tasks_from_memory() → memory:8300/tasks
    ↓ _format_tasks() → Ollama summary (FREE)
    → Response  (cost: $0.00, engine: ollama, method: task_lookup)
```

---

## Routing Strategy

### Decision Tree

```
                        ┌─────────────┐
                        │ User Query  │
                        └─────────────┘
                              │
                              ↓
               ┌──────────────────────────┐
               │  [1] GLiClass Classifier  │
               │  144M params · <50ms      │
               └──────────────────────────┘
                              │
          ┌───────┬───────┬───┴────┬────────┐
          ↓       ↓       ↓        ↓        ↓
       search   task   action  knowledge  chat
          │       │       │        │        │
          │       │       │        └────────┘
          │       │       │             ↓
          │       │       │        [Pipeline B]
          │       │       │        ChromaDB RAG
          │       │       │        Ollama ($0)
          │       │       │
          │       │    ┌──┴──────────────────┐
          │       │    ↓ [2] SkillRegistry   │
          │       │    Deterministic trigger  │
          │       │    substring match        │
          │       │    ┌──────────┬──────────┘
          │       │    ↓          ↓
          │       │  Match      No match
          │       │    │          │
          │       │    ↓          ↓
          │       │ Execute   [3] Haiku API
          │       │ Bash/     generates skill
          │       │ Ollama    → Save → Execute
          │       │  ($0)     (~$0.01 one-time)
          │       │
          ↓       ↓
     [Pipeline A — No RAG]
     Vault Search / Memory Tasks
     Ollama summary ($0)
```

---

## Skill System Design

### SKILL.md Format

```yaml
---
name: skill-name-kebab-case
description: one line description
triggers:
  - exact trigger phrase one
  - trigger phrase two
execution_mode: bash | ollama
timeout: 10          # bash only
model: llama3.2:3b   # ollama only
---

# Skill Title

## Purpose
What this skill does in 1-2 sentences.

## Script         ← bash skills MUST have this section
```bash
#!/bin/bash
# commands here — stdout is captured and wrapped by Ollama
echo "result"
```

## Instructions   ← ollama skills use this instead
Step by step. Use $ARGUMENTS where user input goes.

## Output Format
Describe expected output.
```

### Skill Execution Modes

**Bash mode:**
1. Extract `## Script` code block from SKILL.md
2. Write to `tempfile.NamedTemporaryFile(suffix='.sh')`; `chmod 644`
3. `subprocess.run(['sudo', '-u', 'securebot-scripts', 'bash', script_path], ...)`
4. Capture `stdout`; delete temp file
5. Optionally fetch lightweight RAG context (max 100 tokens) for wrap enrichment
6. Ollama `llama3.2:3b` wraps raw output in natural language

**Ollama mode:**
1. Load SKILL.md content
2. Sanitize user input (strip injection delimiters, truncate to 2000 chars)
3. Replace `$ARGUMENTS` with bracketed user input: `[USER INPUT START]...[USER INPUT END]`
4. POST to Ollama `/api/generate`

### Skill Lifecycle

```
1. TRIGGER CHECK (every query with action intent)
   GLiClass → action → SkillRegistry.find_by_trigger() → match?

2. CREATION (only when no match, ~$0.01 one-time)
   haiku_generate_skill() → sanitize request + user profile → Haiku API
   → validate name regex + path traversal → save SKILL.md → reload registry

3. EXECUTION (infinite times, $0.00)
   execute_skill() → bash or ollama → Ollama natural-language wrap

4. HOT RELOAD
   POST /skills/reload → SkillRegistry clears + re-reads disk
```

---

## Security Model

### Threat Model — Threats Mitigated

1. **Prompt Injection / Credential Theft** — Vault pattern: AI never sees API keys in context
2. **Replay Attacks** — HMAC nonce cache + 30-second timestamp window
3. **Unauthorized Inter-Service Access** — GATEWAY_API_KEY on all external endpoints; HMAC-SHA256 on all internal service calls
4. **Container Escape via Bash Skills** — Bash sandboxing (see below)
5. **PII Leakage to Cloud API** — Anonymization layer (see below)
6. **Skill Path Traversal** — Skill name validated by regex; `resolve()` checked against SKILLS_DIR prefix
7. **Prompt Injection via Skill Arguments** — `$ARGUMENTS` wrapped in `[USER INPUT START/END]`; injection delimiters stripped; truncated to 2000 chars

### Security Layers

```
LAYER 1: Network Isolation
  Docker bridge network 'securebot' — only Gateway :8080 exposed externally
  All inter-service traffic on private network

LAYER 2: API Key Enforcement
  GATEWAY_API_KEY middleware on gateway_service.py
  All /message, /skills endpoints require X-API-Key header
  /health endpoints remain open for Docker healthchecks

LAYER 3: HMAC-SHA256 Inter-Service Auth
  X-Service-ID, X-Timestamp, X-Nonce, X-Signature on all service calls
  WEB_CONCURRENCY=1 on all 4 services (prevents nonce cache split-brain)

LAYER 4: Secrets Isolation (Vault)
  secrets.json volume-mounted, never in Docker image
  Never logged, never passed to AI models
  Injected only at tool execution time

LAYER 5: File Permissions
  vault/secrets/secrets.json — chmod 600
  memory/soul.md — chmod 444 (read-only identity file)
```

### Bash Sandboxing

All bash skills are executed via a locked-down OS user, preventing container root escapes:

```python
subprocess.run(
    ['sudo', '-u', 'securebot-scripts', 'bash', script_path],
    capture_output=True,
    timeout=skill.get("timeout", 10),
    text=True
)
```

**Setup:** Host-side sudoers rule required:
```
tasker0 ALL=(securebot-scripts) NOPASSWD: /bin/bash
```

**Script lifecycle:** Written to `tempfile`, `chmod 644` (so `securebot-scripts` can read), executed, then immediately deleted with `os.unlink()`.

### Anonymization Layer (`_sanitize_for_cloud`)

Before any data is sent to Anthropic's Haiku API (for skill creation), it passes through the `_sanitize_for_cloud()` privacy gate. This applies to both the user's request and the loaded `user.md` profile.

**Regex patterns applied:**

| Pattern | Replacement | Example |
|---------|-------------|---------|
| Email address | `[EMAIL]` | `user@domain.com` → `[EMAIL]` |
| US phone number | `[PHONE]` | `555-123-4567` → `[PHONE]` |
| IPv4 address | `[IP]` | `192.168.1.100` → `[IP]` |
| MAC address (`:` or `-`) | `[MAC]` | `aa:bb:cc:dd:ee:ff` → `[MAC]` |
| SSH/PEM private key block | `[SSH_KEY]` | `-----BEGIN RSA PRIVATE KEY-----...` → `[SSH_KEY]` |
| `REDACT_WORDS` env keywords | `[REDACTED]` | comma-separated, case-insensitive |

**Environment variable:**
```
REDACT_WORDS=Roland,Rolando,Mac   # default fallback
```

**Why user.md is sent (sanitized):** Haiku needs OS/hardware/path context to generate accurate bash skills (correct package manager, paths, architecture). The sanitization ensures the architecture context reaches Haiku while personal identifiers are stripped.

---

## Cost Optimization

### Cost Breakdown by Route

| Route | Cost | When Used |
|-------|------|-----------|
| Ollama (search, task, knowledge, chat) | $0.00 | All non-action queries |
| Skill execution (bash or ollama) | $0.00 | Action with existing skill |
| Haiku skill creation | ~$0.01 | Action with no existing skill (one-time) |

**Monthly example (500 queries):**
```
450 queries (search/task/knowledge/chat) → Ollama → $0.00
45 skill executions                       → Ollama → $0.00
5 new skills created                      → Haiku  → $0.05
Total: ~$0.05/month
```

Note: Previous ARCHITECTURE.md referenced `direct_claude` at $0.006/query — this route no longer exists. All cloud API usage is exclusively for one-time skill creation via Haiku.

---

## API Reference

### Gateway API (Port 8080)

#### POST /message

**Request:**
```json
{
  "channel": "api",
  "user_id": "user123",
  "text": "Your query here"
}
```
Headers: `X-API-Key: <GATEWAY_API_KEY>`

**Response:**
```json
{
  "status": "success",
  "result": "AI response here",
  "method": "search|task_lookup|skill_execution|ollama_knowledge|ollama_chat",
  "intent": "search|task|action|knowledge|chat",
  "cost": 0.0,
  "engine": "ollama|claude+ollama",
  "skill_used": "skill-name",
  "skill_created": "skill-name"
}
```

#### GET /health

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "gateway": "ok",
    "vault": "ok",
    "memory": "ok",
    "rag": "ok",
    "ollama": "ok"
  },
  "skills_loaded": 8
}
```

#### POST /skills/reload

Hot-reload the SkillRegistry from disk without restarting the container.

**Response:**
```json
{"status": "reloaded", "skills_loaded": 9}
```

---

### Vault API (Port 8200)

#### POST /execute

Execute web search with injected secrets.

**Request:**
```json
{
  "tool": "web_search",
  "params": {"query": "search query", "max_results": 3},
  "session_id": "orchestrator"
}
```

**Response:**
```json
{
  "status": "success",
  "provider": "google",
  "results": [
    {"title": "...", "url": "...", "snippet": "..."}
  ]
}
```

#### POST /secret (HMAC-authenticated)

Retrieve a named secret. Used by `haiku_generate_skill()` to get the Anthropic API key.

**Request:**
```json
{"name": "anthropic_api_key"}
```

---

### Memory API (Port 8300)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/tasks` | GET | Read tasks.json |
| `/memory/user` | GET | Read user.md |
| `/memory/session` | GET | Read session.md |

---

### RAG API (Port 8400)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/context` | GET | Retrieve relevant context (accepts `user_id`, `query`, `max_tokens`) |
| `/embed/conversation` | POST | Store conversation turn (stores `user_id` in metadata) |

---

## Summary

SecureBot's architecture achieves extreme cost efficiency through:

1. **Zero-Shot Routing** — GLiClass replaces all heuristic classifiers; <50ms intent detection
2. **Strict Pipeline Separation** — Tool execution (deterministic) never touches RAG (probabilistic)
3. **Bash Sandboxing** — Skills run as locked-down OS user; no container escape possible
4. **Skill Reuse** — Pay ~$0.01 once with Haiku, execute forever free with Ollama
5. **Anonymization Gate** — `_sanitize_for_cloud()` strips all PII before any cloud API call
6. **Secrets Isolation** — Vault pattern; API keys injected only at execution time
7. **Multi-Provider Search** — Maximize free tiers (Google → Tavily → DuckDuckGo)

**Result:** ~97% cost savings vs Claude Pro

---

**For more details, see:**
- [SKILLS.md](SKILLS.md) — Creating and managing reusable skills
- [SECURITY.md](SECURITY.md) — Full security model and trust matrix
- [CONFIGURATION.md](CONFIGURATION.md) — Advanced configuration
- [HARDWARE.md](HARDWARE.md) — Hardware optimization
