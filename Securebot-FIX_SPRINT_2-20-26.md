# SecureBot — Security Hardening + CLI Bug Fix Sprint (v2)

You are working on SecureBot, a self-hosted AI assistant running on a public Oracle Cloud VPS.
Read `CLAUDE.md` first for full architecture context before making any changes.

This session addresses confirmed vulnerabilities from a formal security review plus known CLI bugs.
**This system is internet-facing. Work through Priority 1 fixes before anything else.**

Work through each fix in order. After each fix: state what file you changed, what you changed, and why.

---

## PRIORITY 1 — CRITICAL (Internet-Facing, Fix Before Restarting Services)

### Fix 1A: Unauthenticated Public Gateway (Open Relay)

**Confirmed risk:** Port 8080 is open to `0.0.0.0/0` on Oracle Cloud. Anyone who finds the IP can
use `/message` as a free relay to burn Anthropic API credits or trigger internal skills.

**File:** `gateway/gateway_service.py`

**Fix:**
1. Add API key middleware. Read `GATEWAY_API_KEY` from environment (`.env` file).
2. All requests to non-`/health` endpoints must include header `X-API-Key: <key>`.
3. Return `HTTP 401 {"detail": "Unauthorized"}` on missing or incorrect key.
4. Use `hmac.compare_digest()` for the comparison — never `==` (timing attack prevention).
5. `/health` stays public — Docker healthcheck requires it.
6. Generate the key and add to `.env`:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
7. Update `securebot-cli.py` to send `X-API-Key` header on all gateway requests.

**Do not** modify the existing `X-Service-ID` HMAC inter-service auth — that's separate.

---

### Fix 1B: Unsanitized Skill File Writing (Path Traversal / RCE)

**Confirmed risk:** `create_skill()` writes raw LLM output to disk using the skill name as a path
component. A crafted prompt like `"Create a skill named '../../../../../etc/cron.d/malicious'"` can
overwrite host system files. A malicious skill containing a reverse shell will be saved and executed.

**File:** `gateway/orchestrator.py`

**Fix:**
1. After extracting `skill_name` from LLM response frontmatter, validate against:
   `^[a-zA-Z0-9][a-zA-Z0-9_-]{1,48}[a-zA-Z0-9]$`
2. Explicitly reject any name containing: `/`, `\`, `..`, `.`, spaces, or special characters.
3. Resolve and assert the final path:
   ```python
   resolved = Path(SKILLS_DIR / skill_name).resolve()
   assert str(resolved).startswith(str(SKILLS_DIR.resolve())), "Path traversal attempt"
   ```
4. Reject skill content over 50,000 characters.
5. Log all rejected attempts with the attempted name at WARNING level.

---

### Fix 1C: Prompt Injection via $ARGUMENTS

**Confirmed risk:** `skill_content.replace('$ARGUMENTS', arguments)` is a raw substitution.
A crafted query can break out of the arguments boundary and rewrite the Ollama system prompt,
bypassing skill safety constraints entirely.

**File:** `gateway/orchestrator.py`

**Fix:**
1. Bracket the arguments before substitution:
   ```python
   safe_arguments = f"[USER INPUT START]\n{arguments}\n[USER INPUT END]"
   skill_content = skill_content.replace('$ARGUMENTS', safe_arguments)
   ```
2. Truncate `arguments` to 2000 characters before substitution (log a warning if truncated).
3. Strip common prompt injection delimiters from arguments:
   `---`, `<s>`, `[INST]`, `<<SYS>>`, `</s>`, `[/INST]`

---

## PRIORITY 2 — MEDIUM (Fix This Session)

### Fix 2A: In-Memory Nonce Cache (Multi-Worker Replay Risk)

**Confirmed risk:** `NONCE_CACHE = {}` is not shared across Uvicorn workers. Simultaneous requests
to two workers can both pass nonce validation. Container restart wipes the cache, allowing replays.

**File:** `common/auth.py`

**Fix:**
1. Add a docblock above `NONCE_CACHE` documenting the limitation and that Redis is the production fix.
2. Add a startup warning log: if `WEB_CONCURRENCY` > 1 or unset, log:
   `WARNING: Nonce replay protection unreliable with multiple workers. Set WEB_CONCURRENCY=1.`
3. In `docker-compose.yml`, explicitly set `--workers 1` on all four services (gateway, vault,
   memory-service, rag-service) if not already enforced. This is the mitigation until Redis is added.

### Fix 2B: RAG Tenant Isolation (Privacy — User Data Bleed)

**Confirmed risk:** `_store_conversation` pushes all user messages into ChromaDB with no `user_id`
tag. `get_relevant_context` retrieves based purely on semantic similarity. User A's private data
(personal keys, private documents) can bleed into User B's prompt context.

**Files:** `services/rag/rag_service.py`, `gateway/gateway_service.py`

**Fix:**
1. In `rag_service.py`: when embedding a conversation via `/embed/conversation`, store `user_id`
   in ChromaDB document metadata.
2. When retrieving via `/context`, accept `user_id` as a query param and add:
   `where={"user_id": user_id}` to the ChromaDB query on the `conversations` collection.
3. **Important:** The `memory` collection (soul.md, user.md, session) is shared — do NOT add user
   filtering there. Only the `conversations` collection gets filtered.
4. Update `gateway/gateway_service.py` to pass `user_id` when calling `/embed/conversation`
   and `/context`.

---

## PRIORITY 3 — CLI BUG FIXES

### Fix 3A: Search Returns Empty Response

**Symptom:**
```json
{"status": "success", "response": "", "method": "web_search_needed", "search_used": false, "processing_time": 0.0001s}
```
Response time is ~0.1s — the search is being detected but never executed. The orchestrator
sets the method flag then returns without calling the vault.

**Files:** `gateway/orchestrator.py`, `gateway/gateway_service.py`

**Fix:**
1. Search for `web_search_needed` in `orchestrator.py` and trace the full code path.
2. Find the short-circuit — likely one of:
   - Missing `await` on an async vault call
   - An early `return` before the vault is called
   - Search results fetched but not assembled into the `response` field
3. Fix so that `web_search_needed` causes:
   - Vault `/execute` called with `{"tool": "web_search", "params": {"query": ...}}`
   - Results returned to Ollama summarizer
   - Summarized text placed in the `response` field
4. Smoke test (response time must be 5–30s, not 0.1s):
   ```bash
   curl -X POST http://localhost:8080/message \
     -H "Content-Type: application/json" \
     -H "X-API-Key: <key>" \
     -d '{"channel":"cli","user_id":"tasker0","text":"what movies are playing in McAllen TX today"}'
   ```

### Fix 3B: Tasks Show Count But Not Content

**Symptom:** "You have 3 pending tasks" with priority levels shown but task names/descriptions blank.

**Files:** `memory/tasks.json`, `services/memory/memory_service.py`, `gateway/orchestrator.py`

**Fix:**
1. Inspect the file first:
   ```bash
   cat ~/securebot/memory/tasks.json | python3 -m json.tool
   ```
2. If fields are empty, populate with actual pending work:
   ```json
   {
     "todo": [
       {
         "id": "task-001",
         "title": "Fix /status CLI command",
         "description": "Vault X error in _cmd_status — debug and repair the URL",
         "priority": "high",
         "created": "2026-02-20T00:00:00"
       },
       {
         "id": "task-002",
         "title": "Fix /memory CLI command",
         "description": "Clears screen but displays no content — trace memory service response handling in CLI",
         "priority": "high",
         "created": "2026-02-20T00:00:00"
       },
       {
         "id": "task-003",
         "title": "Anonymized memory layer for Haiku router",
         "description": "Design and implement anonymization layer so raw memory files are not sent to Anthropic API",
         "priority": "medium",
         "created": "2026-02-20T00:00:00"
       },
       {
         "id": "task-004",
         "title": "Build SearchBot specialist agent",
         "description": "Containerized search/scrape specialist: Playwright + Trafilatura + phi4-mini",
         "priority": "medium",
         "created": "2026-02-20T00:00:00"
       }
     ],
     "completed": []
   }
   ```
3. If data looks good but display is wrong, trace how task data flows into the Ollama prompt
   in `orchestrator.py` — check for truncation or missing field references.
4. After any changes: `curl -X POST http://localhost:8400/embed/memory`

### Fix 3C: /status Command — Vault X Error

**File:** `securebot-cli.py`

**Fix:**
1. Find `_cmd_status` function.
2. Locate the malformed vault URL — correct endpoint is `http://localhost:8200/health`.
3. Fix and verify all five service health checks display: gateway, vault, memory, RAG, Ollama.

### Fix 3D: /memory Command — Blank Screen

**File:** `securebot-cli.py`

**Fix:**
1. Find `_cmd_memory` function.
2. Confirm it calls `http://localhost:8300/memory/context` correctly.
3. Check for missing `stdscr.addstr()` or `stdscr.refresh()` after response is received.
4. Fix and verify: `/memory` displays soul/user/session context summary in the TUI.

---

## Completion Checklist

After all fixes:

1. Restart services: `docker-compose down && docker-compose up -d`
2. Verify all containers start clean: `docker-compose ps` — all should show `healthy`
3. Run classifier tests: `python test_intent_classifier.py && python test_classifier_simple.py`
4. Smoke test sequence in CLI:
   - `hello` → personal greeting (memory working)
   - `what are my pending tasks` → lists all 4 tasks with titles and descriptions
   - `search for AI news today` → 5–30s response time, real results returned
   - `/status` → all five services green
   - `/memory` → displays context summary
5. Report: files changed, what changed, anything that couldn't be fully resolved.

---

## Hard Constraints — Do Not Touch

- `vault/secrets/secrets.json` — never read, write, or log contents
- `memory/soul.md` — read-only (chmod 444), never modify
- `chroma/` directory — never delete
- Existing `X-Service-ID` HMAC logic in `common/auth.py` — extend only, never replace
- Docker non-root user `1000:1000` in compose — confirm it's still set, do not change