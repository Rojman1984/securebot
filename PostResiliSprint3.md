Update SecureBot documentation to reflect Sprint 3 (Resilience) completion.

READ THESE FILES FIRST before making any changes:
  - CLAUDE.md (source of truth)
  - docs/SECURITY.md (needs endpoint table update)
  - docs/CODEBOT.md (needs HITL + fallback sections)
  - docs/ARCHITECTURE.md (needs approval queue + dashboard sections)

═══════════════════════════════════════════════
FILE 1: CLAUDE.md
═══════════════════════════════════════════════

CHANGE 1 — Add approval queue endpoints to gateway endpoints table:
  | POST /approvals/request    | CodeBot requests credentials or permission (HMAC, codebot only) |
  | GET  /approvals/pending    | CLI polls for unresolved requests (API key) |
  | POST /approvals/resolve/{id} | CLI submits resolution value; secrets routed via Vault (API key) |
  | GET  /approvals/status/{id}  | CodeBot polls for resolution (HMAC, codebot only) |

CHANGE 2 — Add tool_request_approval.py to Key Files table:
  | codebot/tools/tool_request_approval.py | HMAC-signed HITL tool — POSTs to /approvals/request, polls /approvals/status/{id} every 5s up to 5min |

CHANGE 3 — Update Active Development Direction:
  "Sprint 3 complete. All three sprints delivered. Next phase: Specialist Agent Fleet
  (SearchBot, CodeBot, MemoryBot, ReasonBot as isolated containers)."

CHANGE 4 — Add /jobs to CLI usage note or TUI section if one exists.
  Add: "Type /jobs in the TUI to toggle the System Dashboard (job health,
  watchdog diagnoses, pending approval queue with inline resolve input)."

═══════════════════════════════════════════════
FILE 2: docs/SECURITY.md
═══════════════════════════════════════════════

CHANGE 1 — Update the Verified Endpoint Protection table.
  Add four rows for the approval queue endpoints:

  | gateway (8080) | POST /approvals/request   | HMAC-SHA256 (codebot only) | — |
  | gateway (8080) | GET /approvals/pending    | API key (X-API-Key)         | — |
  | gateway (8080) | POST /approvals/resolve/{id} | API key (X-API-Key)      | — |
  | gateway (8080) | GET /approvals/status/{id}   | HMAC-SHA256 (codebot only) | — |

CHANGE 2 — Update the Service Trust Matrix "Who Can Call Whom" table.
  Update the codebot row:
    BEFORE: codebot | gateway (/internal/test-skill only)
    AFTER:  codebot | gateway (/internal/test-skill, /approvals/request, /approvals/status/{id})

  Add a note below the table:
  > **Approval secret routing:** When a resolution includes a `key_name`, the gateway
  > routes the secret value through the Vault `/secret` endpoint. Secrets are never
  > stored in the approval queue itself and never written to secrets.json via this path.

CHANGE 3 — Add a new "Approval Queue Security" subsection under Security Layers:

  ### Approval Queue

  The in-memory approval store (`_APPROVAL_STORE`) has these security properties:
  - Requests created only by HMAC-authenticated codebot service
  - Resolved only by API-key-authenticated CLI operator
  - Resolution values containing secrets are forwarded to Vault, not stored in the queue
  - **Important:** Store is in-memory only — pending approvals are lost on gateway restart
  - Resolved status and values are available to codebot polling via HMAC-authenticated
    `/approvals/status/{id}` only after resolution

═══════════════════════════════════════════════
FILE 3: docs/CODEBOT.md
═══════════════════════════════════════════════

CHANGE 1 — Add tool_request_approval to the Tool Descriptions table:
  | tool_request_approval.py | Python | HMAC-signed POST to /approvals/request; polls /approvals/status/{id} every 5s, up to 5 minutes |

CHANGE 2 — Update Pi Tool Workflow diagram to include the HITL branch:

  classify → draft → lint → sandbox test → validate YAML → commit
                                ↓ (needs secret or critical change?)
                        request_approval → poll status (5s interval, 5min max)
                                ↓ (resolved by operator)
                           resume workflow

  Add text: "Pi must STOP and call request_approval when it lacks credentials
  or is about to make a system-critical change. Execution does not continue
  until the operator resolves the request via the CLI dashboard or API."

CHANGE 3 — Add a new "Model Fallback" section:

  ## Model Fallback (Error Interceptor)

  `codebot_service.py` watches for Anthropic API quota errors:
  - HTTP 429 (rate limit)
  - HTTP 402 (payment required)
  - "overloaded" error patterns

  On quota error:
  1. Builds a temporary Pi config pointing to `FALLBACK_MODEL` env var
  2. Posts a notification to the gateway approval queue
  3. Retries the skill generation once with the fallback model
  4. Cleans up temp config in a `finally` block

  Set `FALLBACK_MODEL` in `.env` to a local Ollama model or OpenRouter endpoint.
  If unset, fallback silently degrades to the Haiku direct path.

CHANGE 4 — Update the Key Files table:
  | codebot/tools/tool_request_approval.py | HITL approval tool — see HITL section above |

═══════════════════════════════════════════════
FILE 4: docs/ARCHITECTURE.md
═══════════════════════════════════════════════

CHANGE 1 — Add Approval Queue to Gateway Service endpoints list:
  POST /approvals/request     → CodeBot HITL credential/permission request
  GET  /approvals/pending     → CLI polls unresolved requests
  POST /approvals/resolve/{id} → CLI operator submits resolution (secrets via Vault)
  GET  /approvals/status/{id}  → CodeBot polls for resolution

CHANGE 2 — Add a new Flow 6 to the Data Flow section:

  ### Flow 6: CodeBot Needs a Secret (HITL Approval)

  CodeBot: "I need a Stripe API key to generate this skill"
      ↓ tool_request_approval.py
      ↓ HMAC-signed POST /approvals/request {rationale, needs, type: "credential"}
      ↓ Gateway stores in _APPROVAL_STORE (in-memory)
      ↓ CLI header shows: [!1 APPROVALS /jobs]
      ↓ Operator types /jobs → dashboard shows pending request
      ↓ Operator types: 0 sk_live_...
      ↓ Gateway routes secret through Vault /secret endpoint
      ↓ PATCH /approvals/resolve/id → status: resolved
      ↓ CodeBot poll (every 5s) detects resolved → reads resolution value
      ↓ Pi CLI resumes workflow with provided secret
      Cost: $0.00 (no additional API calls)

CHANGE 3 — Add CLI Dashboard note to the Presentation Layer box:
  Add: "• /jobs dashboard (job health, watchdog diagnoses, approval queue)"

═══════════════════════════════════════════════
FILE 5: docs/QUICKSTART.md
═══════════════════════════════════════════════

CHANGE — Add a new "System Dashboard" section under Common Commands:

  ### System Dashboard (/jobs)

  The TUI includes a live System Dashboard. Type /jobs in the chat input
  to toggle it.

  **Dashboard shows:**
  - All scheduled background jobs with health status and last-check timestamp
  - Watchdog ReAct diagnosis for any failed units
  - Pending CodeBot approval requests (credential requests, permission requests)

  **Resolving an approval request:**
  1. Type /jobs to open the dashboard
  2. Note the index number of the pending request (e.g., 0)
  3. Type: 0 <value>  (e.g., 0 sk_live_abc123)
  4. Press Enter — credential-type resolutions are routed through Vault automatically
  5. Ctrl-C or /jobs to return to chat

  **Alert in chat view:**
  When approvals are pending, the header bar shows: [!N APPROVALS /jobs]
  The dashboard polls every 10 seconds automatically.

  **Via API (non-TUI):**
  # Check pending approvals
  curl http://localhost:8080/approvals/pending \
    -H "X-API-Key: <GATEWAY_API_KEY>"

  # Resolve an approval
  curl -X POST http://localhost:8080/approvals/resolve/<id> \
    -H "X-API-Key: <GATEWAY_API_KEY>" \
    -H "Content-Type: application/json" \
    -d '{"value": "sk_live_...", "key_name": "stripe_api_key"}'

CHANGE 2 — Add important caveat near the approval queue docs:
  > ⚠️ The approval store is in-memory. Pending approvals are lost if the
  > gateway container restarts. If CodeBot is blocked waiting for approval
  > and the gateway restarts, CodeBot will time out (5 min) and the skill
  > generation will fail. Re-trigger the original query to start again.

═══════════════════════════════════════════════
CONSTRAINTS
═══════════════════════════════════════════════
- Do not modify vault/secrets/secrets.json
- Do not modify memory/soul.md
- Preserve all existing content except specific additions above

VERIFY when done:
  grep "approvals" docs/SECURITY.md | wc -l     # Should be > 5
  grep "request_approval" docs/CODEBOT.md       # Should appear in table + workflow
  grep "APPROVAL_STORE" docs/ARCHITECTURE.md    # Should appear with in-memory note
  grep "jobs" docs/QUICKSTART.md                # Should appear in dashboard section
  grep "in-memory" docs/SECURITY.md             # Should appear in approval section
  grep "Fallback" docs/CODEBOT.md               # Should appear in new section
