Update SecureBot documentation to reflect Sprint 2 (Watchdog + Cost Accounting) completion and Watchdog mounts.

READ THESE FILES FIRST before making any changes:
  - CLAUDE.md (source of truth)
  - docs/ARCHITECTURE.md
  - docs/SECURITY.md
  - docs/CODEBOT.md

═══════════════════════════════════════════════
FILE 1: CLAUDE.md
═══════════════════════════════════════════════

CHANGE 1 — Add watchdog_service.py to the Key Files table:
  | gateway/watchdog_service.py | ReAct daemon — polls systemctl for failed units, fetches journalctl logs, diagnoses via llama3.2:3b, writes /memory/jobs_status.json |

CHANGE 2 — Update Active Development Direction:
  Replace current Sprint 2 reference with:
  "Sprint 3 — Approval Queue API, model fallback interceptor, CLI System Dashboard"

CHANGE 3 — Add python execution mode to the Skills System section.
  After the existing bash/ollama execution mode descriptions add:
  - **Execution (Python):** Script block extracted from SKILL.md, written to temp file,
    executed via `sudo -u securebot-scripts python3`. stdout captured and returned directly
    (no Ollama wrap). Used for structured data tasks like cost reporting.

═══════════════════════════════════════════════
FILE 2: docs/ARCHITECTURE.md
═══════════════════════════════════════════════

CHANGE 1 — Add Watchdog to Component Architecture section.
  After the "### 1. Gateway Service" subsection, insert a new subsection:

  ### 1b. Watchdog Service (Background Daemon)

  **Purpose:** Passive monitoring daemon. Runs as a background thread inside the
  gateway container. No external port.

  **Responsibilities:**
  - Poll `systemctl list-timers --all` via `sudo -u securebot-scripts` (sandboxed)
  - Detect failed systemd units
  - Fetch `journalctl` logs for failed units (sandboxed)
  - Send ReAct-structured prompt to `llama3.2:3b` for root-cause diagnosis
  - Write job health + diagnoses to `/memory/jobs_status.json`

  **Constraints:**
  - Model hardcoded to `llama3.2:3b` — no cloud API calls
  - Requires host's `/run/systemd/private` and `/var/run/dbus/system_bus_socket` mounted
    to function; degrades gracefully without them

  **Key File:** `gateway/watchdog_service.py`

CHANGE 2 — Add cost accounting to the Orchestrator section (2.x).
  After the existing pipeline sections add:

  #### 2.4 Cost Accounting

  After every successful Haiku API call (skill creation fallback), `_append_cost_log()`
  appends a JSON entry to `/memory/cost_logs.json`:
```json
  {
    "timestamp": "ISO-8601",
    "session_id": "string",
    "task_name": "string",
    "model": "claude-haiku-4-5-20251001",
    "input_tokens": 0,
    "output_tokens": 0,
    "total_cost": 0.00
  }
```

  **Haiku 4.5 rates:** $1.00/M input tokens, $5.00/M output tokens

CHANGE 3 — Update Skill Execution Modes section.
  Add python as a third execution mode:

  **Python mode:**
  1. Extract ` ```python ` code block from SKILL.md
  2. Write to `tempfile.NamedTemporaryFile(suffix='.py')`; `chmod 644`
  3. `subprocess.run(['sudo', '-u', 'securebot-scripts', 'python3', script_path], ...)`
  4. Capture `stdout`; delete temp file
  5. Return stdout directly — no Ollama wrap (used for structured data output)

CHANGE 4 — Update STORAGE LAYER in Architecture Layers diagram.
  Add two new entries to the storage layer box:
  • /memory/jobs_status.json  (watchdog job health + ReAct diagnoses)
  • /memory/cost_logs.json    (Haiku API cost audit trail)

═══════════════════════════════════════════════
FILE 3: docs/COST_ANALYSIS.md
═══════════════════════════════════════════════

CHANGE 1 — Correct Haiku pricing throughout the file.
  Find any references to Haiku API costs for skill creation and add a note:
  "Haiku 4.5 rates: $1.00/M input, $5.00/M output
   Skill creation (~5K in + 5K out tokens): ~$0.03 per skill"

CHANGE 2 — Add a Cost Monitoring section near the bottom (before See Also):

  ### Cost Monitoring

  SecureBot automatically tracks all Haiku API usage in `/memory/cost_logs.json`.
  View aggregated cost reports using the built-in skill:

  Trigger phrases:
  - "show me my api costs"
  - "cost report"
  - "how much have i spent"

  The report aggregates by day and session, showing model used, token counts,
  and running totals. Local Ollama usage is always $0.00 and is not logged.

═══════════════════════════════════════════════
FILE 4: docs/MEMORY.md
═══════════════════════════════════════════════

CHANGE — Add two new files to the memory files table.
  In the "Files managed" or similar section, add:

  | File | Purpose | Permissions |
  | jobs_status.json | Watchdog job health + ReAct diagnoses (written by watchdog daemon) | Read/write |
  | cost_logs.json   | Haiku API cost audit trail (append-only, written by orchestrator) | Read/write |

═══════════════════════════════════════════════
FILE 5: docs/SKILLS.md
═══════════════════════════════════════════════

CHANGE — Add python to the Execution Modes section.

  ### 4. python (Structured Data Tasks)

  Executes a Python script block for tasks requiring structured output,
  data processing, or file reading where Ollama wrapping is undesirable.
```yaml
  execution_mode: python
```

  **Use Cases:**
  - Cost reporting (reads cost_logs.json, prints table)
  - Log analysis
  - Any task where stdout should be returned verbatim

  **Execution:**
  1. Extract ```python block from SKILL.md
  2. Write to temp file, chmod 644
  3. Run via `sudo -u securebot-scripts python3`
  4. stdout returned directly (no Ollama wrap)

  **Security:** Same sandboxing as bash — runs as `securebot-scripts` user.

═══════════════════════════════════════════════
FILE 6: docs/QUICKSTART.md
═══════════════════════════════════════════════

CHANGE — Add watchdog and cost monitoring to the "Check Service Health" section.

  After existing health check commands add:
  # Watchdog job health
  cat memory/jobs_status.json | python3 -m json.tool

  # API cost log
  cat memory/cost_logs.json | python3 -m json.tool

  Also add "cost report" to the Usage Examples section:
  ### Cost Report (Free - Python skill)
  curl -X POST http://localhost:8080/message \
    -H "Content-Type: application/json" \
    -H "X-API-Key: <GATEWAY_API_KEY>" \
    -d '{"channel":"api","user_id":"user1","text":"show me my api costs"}'

═══════════════════════════════════════════════
ADDITIONAL: docker-compose.yml — Watchdog mounts
═══════════════════════════════════════════════

Update the gateway service in docker-compose.yml to mount the host
systemd sockets so the watchdog can poll systemctl:

Find the gateway service volumes block and add:
  - /run/systemd/private:/run/systemd/private:ro
  - /var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket:ro

These are read-only mounts. The watchdog already degrades gracefully
if they are absent, but without them it monitors nothing.

Also verify that the gateway service sudoers rule covers systemctl
and journalctl — check gateway/Dockerfile for the sudoers line and
ensure it includes:
  securebot-scripts) NOPASSWD: /bin/bash, /usr/local/bin/python3,
  /bin/systemctl, /usr/bin/journalctl

If systemctl or journalctl are missing from the sudoers rule, add them.
Verify actual binary paths first:
  which systemctl
  which journalctl

Use the actual paths found, not assumed paths.

═══════════════════════════════════════════════
CONSTRAINTS
═══════════════════════════════════════════════
- Do not modify vault/secrets/secrets.json
- Do not modify memory/soul.md
- Do not alter docs/SECURITY.md or docs/CODEBOT.md — already correct
- Preserve all existing content except specific additions above

VERIFY when done:
  grep "watchdog" docs/ARCHITECTURE.md | wc -l   # Should be > 3
  grep "cost_logs" docs/ARCHITECTURE.md           # Should appear
  grep "python" docs/SKILLS.md | grep "mode"      # Should appear
  grep "1.00" docs/COST_ANALYSIS.md               # Haiku rate should appear
  grep "jobs_status" docs/MEMORY.md               # Should appear

VERIFY when done:
  grep "systemd/private" docker-compose.yml    # Should appear
  grep "dbus" docker-compose.yml               # Should appear
  grep "systemctl" gateway/Dockerfile          # Should appear in sudoers line
