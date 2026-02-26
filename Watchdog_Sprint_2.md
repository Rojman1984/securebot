[SYSTEM CONTEXT & DIRECTIVE]
You are an expert AI software architect working on "SecureBot". You are executing Sprint 2 of the CodeBot expansion. 
Assume Sprint 1 (CodeBot container, Gateway test sandbox, and GLiClass gatekeeper) is complete and functional. 
Review `CLAUDE.md` for architectural rules. Do NOT break the strict deterministic vs. probabilistic pipeline separation.

[SPRINT 2 OBJECTIVE]
Implement the ReAct Watchdog loop to monitor scheduled tasks and build the Cost Accounting system to track Anthropic API usage. CodeBot must track its own tokens, and SecureBot must autonomously diagnose failing background jobs using the local `llama3.2:3b` model.

### STEP 1: The ReAct Watchdog Service (Gateway)
1. In `gateway/`, create a new background thread/service called `watchdog_service.py`.
2. The Watchdog must periodically poll the host OS for the status of SecureBot's scheduled jobs (e.g., `systemctl list-timers` and `systemctl status` for specific services). 
3. It MUST use the sandboxed execution model: `subprocess.run(["sudo", "-u", "securebot-scripts", ...])` to fetch these logs.
4. Implement the ReAct Loop : If a monitored job returns a failed state, the Watchdog grabs the tail of the error logs.
5. It formats a strict prompt wrapping the error logs and sends it to the local `llama3.2:3b` model (via Ollama API) to output a structured diagnosis:
   - **Thought:** (Why did this fail?)
   - **Action:** (What needs to be done?)
6. Save the current health status and latest diagnosis of all jobs into `memory/jobs_status.json`.

### STEP 2: Frontier Model Cost Tracking (CodeBot)
CodeBot uses Anthropic (Haiku) and must track its own costs.
1. Update CodeBot's Pi CLI initialization/wrapper script to intercept API responses.
2. Extract `prompt_tokens` and `completion_tokens` from every Anthropic API call.
3. Calculate cost (e.g., Haiku 3.5 rates: $1.00/1M input, $5.00/1M output).
4. Append this data to `/workspace/memory/cost_logs.json`. Structure must include: `timestamp`, `session_id`, `task_name`, `input_tokens`, `output_tokens`, and `total_cost`.

### STEP 3: The Cost Report Skill
1. Create a new deterministic skill in `/workspace/skills/report-costs/SKILL.md`.
2. Set frontmatter: `name: report-costs`, `description: Summarize API spending`, `triggers: ["show me my api costs", "cost report", "how much have i spent"]`, `execution_mode: python`.
3. The Python payload must read `memory/cost_logs.json`, aggregate the costs by day/session, and print a clean, plaintext summary to `stdout` for the Gateway's synthesizer model to read.

### STRICT CONSTRAINTS:
- Do NOT alter `vault/secrets/secrets.json`.
- The Watchdog must ONLY query `llama3.2:3b` locally. It must NEVER send system logs to the cloud API.