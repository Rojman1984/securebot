Update SecureBot documentation to fix stale references identified after Sprint 1 completion.

READ THESE FILES FIRST before making any changes:
  - CLAUDE.md (source of truth for architecture)
  - docs/CODEBOT.md (reference for CodeBot details)
  - docs/SECURITY.md (reference for endpoint table)

═══════════════════════════════════════════════
FILE 1: docs/ARCHITECTURE.md
═══════════════════════════════════════════════

CHANGE 1 — Add CodeBot to Architecture Layers diagram.
Find the EXECUTION LAYER box:
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
  │  │    Ollama    │  │  Haiku API   │  │  Bash Runner │         │
  │  │ (Local/Free) │  │ (Skill gen)  │  │  (Sandboxed) │         │
  │  └──────────────┘  └──────────────┘  └──────────────┘         │

Replace with:
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
  │  │    Ollama    │  │   CodeBot    │  │  Haiku API   │  │  Bash Runner │  │
  │  │ (Local/Free) │  │ (Port 8500)  │  │ (Fallback)   │  │  (Sandboxed) │  │
  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │

CHANGE 2 — Update Flow 3 (Action — No Existing Skill).
Find "Flow 3: Action — No Existing Skill (Haiku Creates It)" and replace the
haiku_generate_skill() step block with:

    ↓ codebot_generate_skill():
        1. _sanitize_for_cloud(user_request + user profile)
        2. POST to CodeBot :8500 (Pi CLI + GLiClass gatekeeper)
        3. Pi workflow: classify → draft → lint → sandbox test → validate → commit
        4. Sandbox runs via gateway /internal/test-skill as securebot-scripts
        5. If CodeBot unavailable → fallback to haiku_generate_skill()
    ↓ execute_skill() new skill → bash → Ollama wrap
    → Response  (cost: ~$0.01 one-time, engine: codebot+ollama, method: skill_execution)

CHANGE 3 — Fix sudoers example in Bash Sandboxing section.
Find:
  tasker0 ALL=(securebot-scripts) NOPASSWD: /bin/bash

Replace with:
  tasker0 ALL=(securebot-scripts) NOPASSWD: /bin/bash, /usr/local/bin/python3

Add a note beneath:
  Note: Python path must match the actual binary location in the gateway container.
  Verify with: docker exec securebot-gateway-1 which python3

CHANGE 4 — Update the routing decision tree action branch.
Find the No match branch in the decision tree:
  └── No match → [3] Haiku API generates skill → Save → Execute

Replace with:
  └── No match → [3] CodeBot (:8500) generates skill
                      ↓ (CodeBot unavailable?)
                  ├── NO  → Pi workflow → validate → commit → Execute
                  └── YES → Haiku API fallback → Save → Execute

═══════════════════════════════════════════════
FILE 2: docs/SKILLS.md
═══════════════════════════════════════════════

CHANGE — Clarify the Skill Matching System section.
The current section describes the legacy SkillMatcher scoring algorithm as if it
controls routing. Add this NOTE block immediately after the "## Skill Matching System"
heading and BEFORE the "Matching Algorithm" subsection:

> **Important (Architecture Note):** The scoring algorithm described below applies
> to the `/skills` listing endpoint only. **Query routing does NOT use this
> algorithm.** Live routing uses:
> 1. GLiClass zero-shot classifier (determines intent: search/task/knowledge/chat/action)
> 2. For `action` intent only: `SkillRegistry.find_by_trigger()` — exact substring
>    match against the `triggers` array in SKILL.md frontmatter
>
> If no trigger matches, the query escalates to CodeBot for skill generation.
> The legacy SkillMatcher class remains in orchestrator.py for skill browsing only.

═══════════════════════════════════════════════
FILE 3: docs/CONFIGURATION.md
═══════════════════════════════════════════════

CHANGE 1 — Replace all occurrences of phi4-mini:3.8b with llama3.2:3b
  Find all: phi4-mini:3.8b
  Replace with: llama3.2:3b

CHANGE 2 — Fix claude_model reference for skill creation.
Find:
  claude_model: "claude-sonnet-4-20250514"

Replace with:
  claude_model: "claude-haiku-4-5-20251001"

Add comment: # Used only as fallback when CodeBot (:8500) is unavailable

CHANGE 3 — Update DEFAULT_CONFIG block at bottom of file to match above changes.

═══════════════════════════════════════════════
FILE 4: docs/INSTALL.md
═══════════════════════════════════════════════

CHANGE 1 — Replace all occurrences of phi4-mini:3.8b with llama3.2:3b throughout
  the entire file.

CHANGE 2 — In the Step-by-Step table or model selection section, update:
  Budget tier model: phi4-mini:3.8b → llama3.2:3b
  Keep budget tier label but correct the model name

CHANGE 3 — Add CodeBot to the service health checks section.
Find the verification block with curl commands for each service port.
Add after the existing health checks:
  # CodeBot health
  curl http://localhost:8500/health

═══════════════════════════════════════════════
FILE 5: docs/QUICKSTART.md
═══════════════════════════════════════════════

CHANGE — Replace all occurrences of phi4-mini:3.8b with llama3.2:3b throughout.

Also update the cost section. Find:
  - Skill creation = ~$0.10

Replace with:
  - Skill creation = ~$0.01 (CodeBot local path, no API cost)
  - Skill creation via Haiku fallback = ~$0.01 (if CodeBot unavailable)

═══════════════════════════════════════════════
FILE 6: docs/RAG.md
═══════════════════════════════════════════════

CHANGE — Replace all occurrences of phi4-mini:3.8b with llama3.2:3b throughout.
  Also replace phi4-mini with llama3.2:3b in the session summarization section.

═══════════════════════════════════════════════
FILE 7: docs/MEMORY.md
═══════════════════════════════════════════════

CHANGE — Replace all occurrences of phi4-mini:3.8b with llama3.2:3b throughout,
  including the architecture diagram at the bottom of the file.

═══════════════════════════════════════════════
CONSTRAINTS
═══════════════════════════════════════════════
- Do not modify vault/secrets/secrets.json
- Do not modify memory/soul.md
- Preserve all existing content except the specific changes above
- Do not alter SECURITY.md or CODEBOT.md — they are already correct

VERIFY when done:
  grep -r "phi4-mini" docs/         # Should return 0 results
  grep "CodeBot" docs/ARCHITECTURE.md   # Should appear in diagrams
  grep "codebot_generate_skill" docs/ARCHITECTURE.md  # Should appear in Flow 3
  grep "python3" docs/ARCHITECTURE.md  # Should appear in sudoers section
  grep "Architecture Note" docs/SKILLS.md  # Should appear
