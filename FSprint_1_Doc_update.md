Update SecureBot documentation to reflect completed Phase 1 auth wiring and Sprint 1 CodeBot implementation.

READ THESE FILES FIRST before making any changes:
  - CLAUDE.md
  - README.md
  - docs/ARCHITECTURE.md (if exists)
  - docs/SECURITY.md (if exists)
  - Project_Guidance.md (if exists)

CHANGES TO MAKE:

1. CLAUDE.md
   - Update security section to confirm Depends(verify_service_request) is now
     wired to all protected endpoints in vault, memory, and rag via APIRouter pattern
   - Add CodeBot to the service ports table: codebot | 8500 | Skill generation agent
   - Update architecture diagram to include codebot container
   - Update request flow to show: action → SkillRegistry → match? YES=local,
     NO=CodeBot (pi+Haiku) → save → execute. Haiku direct is fallback only if
     CodeBot unavailable.
   - Add to "Do Not Touch": codebot/tools/ — Pi CLI tool definitions
   - Update "Active Development Direction" to: Sprint 2 — ReAct Watchdog +
     Cost Accounting

2. README.md
   - Security section: mark inter-service auth as fully implemented and verified.
     All three services (vault 8200, memory 8300, rag 8400) return 401 on
     unsigned requests. /health endpoints remain public for Docker healthchecks.
   - Architecture diagram: add codebot service
   - Project structure: add codebot/ directory entry with description
   - Hardware/model table: confirm Holy Trinity — GLiClass(144M) CPU in gateway
     container, nomic-embed-text(137M) + llama3.2:3b via Ollama on host GPU

3. docs/SECURITY.md (create if missing, update if exists)
   Add verified endpoint protection table:
   | Service | Protected endpoints | Auth method | Unprotected |
   |---------|--------------------|-|-------------|
   | vault (8200) | /execute, /search, /secrets/* | HMAC-SHA256 | /health |
   | memory (8300) | /memory/*, /tasks/* | HMAC-SHA256 | /health |
   | rag (8400) | /embed/*, /classify/*, /context | HMAC-SHA256 | /health |
   | gateway (8080) | /message, /internal/test-skill | API key + HMAC | /health |
   Note: /internal/test-skill accepts codebot service ID only

4. docs/CODEBOT.md (create new)
   Document the CodeBot specialist container:
   - Purpose: isolated skill generation agent replacing direct Haiku calls
   - Port: 8500
   - Stack: Python 3.11 + Node.js 20 + @mariozechner/pi-coding-agent
   - User: codebot-worker (non-root)
   - Key files: codebot_service.py, skill_router.py, pi_config.json, tools/
   - GLiClass coding gatekeeper: classifies intent as system_bash or
     python_api_or_data before drafting
   - Pi tool workflow: classify → draft → lint → sandbox test → validate
     YAML → commit. Never commits on failures.
   - Sandbox: all execution routed through gateway /internal/test-skill,
     runs as securebot-scripts user
   - Privacy: _sanitize_for_cloud() runs on user context before any Haiku call
   - Fallback: if CodeBot unavailable, orchestrator falls back to haiku_generate_skill

5. Project_Guidance.md (if present)
   - Phase 1 Core Stability: mark all items complete including auth endpoint
     protection. Add completion date 2026-02-26.
   - Update current phase to Phase 2 + Sprint 2 in parallel
   - Add Sprint 1 CodeBot as completed under a new "Specialist Agent Fleet" section

CONSTRAINTS:
  - Do not modify vault/secrets/secrets.json
  - Do not modify memory/soul.md
  - Preserve all existing content — append/update, do not replace wholesale
  - If a doc section conflicts with current architecture, update it to match
    CLAUDE.md as the source of truth

VERIFY when done:
  - grep -r "codebot" docs/ | wc -l   # should be > 0
  - grep "8500" CLAUDE.md             # should appear in ports table
  - grep "Phase 1.*complete\|100%" Project_Guidance.md  # should appear
