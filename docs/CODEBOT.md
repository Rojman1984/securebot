# CodeBot — Skill Generation Specialist

## Purpose

CodeBot is an isolated specialist container responsible for generating new skills when the SkillRegistry has no match for a user's action intent. It replaces the previous pattern of calling the Haiku API directly from the orchestrator, providing better sandboxing, auditability, and a zero-cost primary path via the Pi coding agent.

The orchestrator calls CodeBot first (`codebot_generate_skill()`). Haiku direct (`haiku_generate_skill()`) is the fallback only if CodeBot is unavailable.

---

## Service Details

| Property | Value |
|----------|-------|
| Port | 8500 |
| Container user | `codebot-worker` (non-root) |
| Base image | `python:3.11-slim` + Node.js 20 |
| Primary tool | `@mariozechner/pi-coding-agent` |
| GLiClass mode | CPU-only (no GPU required) |
| Skill mount | `./skills:/workspace/skills:rw` |

---

## Stack

- **Python 3.11** — FastAPI service (`codebot_service.py`)
- **Node.js 20** — Runs the Pi coding agent CLI
- **`@mariozechner/pi-coding-agent`** — Zero-cost local skill drafting
- **GLiClass `gliclass-small-v1.0`** (CPU) — Coding intent gatekeeper

---

## Key Files

| File | Purpose |
|------|---------|
| `codebot/codebot_service.py` | FastAPI :8500 endpoints |
| `codebot/skill_router.py` | Classifies intent as `system_bash` or `python_api_or_data` |
| `codebot/pi_config.json` | Pi coding agent configuration |
| `codebot/tools/` | Pi CLI tool definitions (do not modify) |
| `codebot/tools/tool_request_approval.py` | HITL approval tool — see Model Fallback section above |

---

## GLiClass Coding Gatekeeper

Before drafting, `skill_router.py` classifies the skill request using GLiClass (CPU) with labels:

- `system_bash` — System administration, file ops, date/time, OS commands
- `python_api_or_data` — API calls, data processing, web requests

A regex fast path catches common patterns before falling back to GLiClass. This ensures the correct execution mode (`bash` vs `ollama`) is selected before the Pi agent begins drafting.

---

## Pi Tool Workflow

Every new skill passes through all five tools in sequence. The skill is committed only if all steps succeed.

```
classify (skill_router.py)
    ↓
draft (Pi coding agent)
    ↓
lint (tool_lint_bash.sh / tool_lint_python.sh)
    ↓
sandbox test (tool_run_sandbox_test.py → gateway /internal/test-skill)
    ↓ (needs secret or critical change?)
request_approval → poll status (5s interval, 5min max)
    ↓ (resolved by operator)
resume workflow
    ↓
validate YAML (tool_validate_yaml.py — 5-field check)
    ↓
commit (tool_commit_skill.sh — path-traversal-safe)
```

**Never commits on failures.** Any step failure aborts the pipeline and returns an error to the orchestrator.

Pi must STOP and call `request_approval` when it lacks credentials or is about to make a system-critical change. Execution does not continue until the operator resolves the request via the CLI dashboard or API.

### Tool Descriptions

| Tool | Language | Purpose |
|------|----------|---------|
| `tool_lint_bash.sh` | Bash | `shellcheck` static analysis for bash skills |
| `tool_lint_python.sh` | Bash | `flake8` linting for python skills |
| `tool_run_sandbox_test.py` | Python | HMAC-signed POST to gateway `/internal/test-skill` |
| `tool_validate_yaml.py` | Python | Validates SKILL.md frontmatter has all 5 required fields |
| `tool_commit_skill.sh` | Bash | Writes SKILL.md to `skills/` with path-traversal protection |
| `tool_request_approval.py` | Python | HMAC-signed POST to `/approvals/request`; polls `/approvals/status/{id}` every 5s, up to 5 minutes |

---

## Sandbox Execution

All test execution is routed through the gateway's `/internal/test-skill` endpoint:

- CodeBot sends HMAC-signed request to `gateway:8080/internal/test-skill`
- Gateway runs the skill as `sudo -u securebot-scripts` (locked-down host user)
- stdout is returned to CodeBot for pass/fail evaluation
- `/internal/*` endpoints bypass the `GATEWAY_API_KEY` middleware but require HMAC auth

---

## Privacy

`_sanitize_for_cloud()` in `orchestrator.py` runs on the user context before any payload is sent to CodeBot or the Haiku fallback. This redacts:

- Email addresses
- IP addresses
- MAC addresses
- SSH keys
- Explicit keywords from `.env` `REDACT_WORDS`

CodeBot itself also calls `_sanitize_for_cloud()` before invoking Haiku for any complex skill logic.

---

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

---

## Fallback Behavior

If CodeBot is unavailable (container down, timeout, or HTTP error), the orchestrator automatically falls back to `haiku_generate_skill()`, which calls the Haiku API directly. This ensures skill generation is never blocked by CodeBot availability.

---

## Authentication

CodeBot is in the `ALLOWED_CALLERS` list for vault and gateway. The gateway's `/internal/test-skill` endpoint accepts only the `codebot` service ID.

See [SECURITY.md](SECURITY.md) for the full trust matrix.
