[SYSTEM CONTEXT & DIRECTIVE]
You are an expert AI software architect working on "SecureBot". You are executing Sprint 3, the final phase of the CodeBot expansion.
Assume Sprints 1 and 2 are fully integrated. Your goal is to add safety nets: an approval queue for critical actions, automated model fallback for API limits, and a CLI dashboard.

[SPRINT 3 OBJECTIVE]
Connect the agent's edge cases to the human administrator. Implement an HTTP 429/402 error interceptor for model fallback, an approval queue API for CodeBot to ask permission/keys, and a live dashboard in the Curses TUI.

### STEP 1: The Approval Queue API (Gateway)
1. Update `gateway/gateway_service.py` with new endpoints:
   - `POST /approvals/request`: CodeBot posts a rationale and what it needs (e.g., "Need Stripe API key").
   - `GET /approvals/pending`: Returns a list of unresolved requests.
   - `POST /approvals/resolve/{id}`: Accepts human input/approval to resolve the block.

### STEP 2: CodeBot HITL & Model Fallback Tools
1. Inside CodeBot, create a new Pi CLI tool: `tool_request_approval`. Instruct Pi CLI to use this, pause its execution, and wait for Gateway resolution if it realizes it lacks credentials or needs to make a system-critical change.
2. Implement an Error Interceptor in CodeBot's wrapper script.
   - Watch for Anthropic API errors (HTTP 429 Rate Limit, HTTP 402 Payment Required).
   - If hit, programmatically reconfigure Pi CLI to a fallback model (e.g., a local model or an alternative provider via OpenRouter).
   - Fetch necessary fallback keys via the Gateway and resume the context tree.
   - POST a notification to the Gateway that a fallback occurred.

### STEP 3: The CLI Dashboard (`securebot-cli.py`)
1. Update `securebot-cli.py` (the Curses TUI).
2. Add a background polling thread that checks `GET /approvals/pending` and reads `memory/jobs_status.json` every 10 seconds.
3. Add an "Approvals" alert to the main chat view if requests are pending.
4. Create a dedicated "System Dashboard" view (toggled via a slash command like `/jobs` or a hotkey).
5. The Dashboard must render:
   - A live table of all scheduled background jobs and their health status.
   - The Watchdog's latest ReAct diagnosis for any failed jobs.
   - An interface to review CodeBot's pending approval requests, input the requested text (like an API key), and submit it to `/approvals/resolve/{id}`.

### STRICT CONSTRAINTS:
- Do NOT alter `vault/secrets/secrets.json` directly. New API keys provided via the CLI approval queue should be routed through the Vault service safely.
- Ensure the Curses TUI layout remains stable and doesn't crash on smaller terminal windows when rendering the new tables.