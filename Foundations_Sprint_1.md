[SYSTEM CONTEXT & DIRECTIVE]
You are an expert AI software architect working on "SecureBot", a highly secure, local-first AI assistant. You are executing Sprint 1 of the CodeBot expansion.
Review the `CLAUDE.md` in the root directory to understand the "Holy Trinity" VRAM architecture, the strict deterministic routing pipeline, and the Bash/OS sandboxing rules.

[SPRINT 1 OBJECTIVE]
Create the CodeBot container. CodeBot is an isolated Docker service powered by the Pi CLI (pi-coding-agent) framework. It will receive sanitized intents from the Gateway, use GLiClass to determine the programming language (Bash vs. Python), author the skill, securely test it via the Gateway, and commit it to the shared `skills/` volume.

Please implement this step-by-step, explaining your changes as you go:

### STEP 1: CodeBot Docker Architecture
1. Create a `codebot/` directory in the project root.
2. Create `codebot/Dockerfile`. It must:
   - Use a lightweight base image supporting Node.js (for Pi CLI) and Python 3.10+ (for GLiClass, Flake8).
   - Install OS dependencies: `npm install -g pi-coding-agent`, `pip install flake8 gliclass`, and `apt-get install shellcheck jq curl`.
   - Create a non-root user `codebot-worker`. CodeBot MUST NOT run as root.
   - Set the working directory to `/workspace`.
3. Update the root `docker-compose.yml`:
   - Add the `codebot` service.
   - Mount `./skills:/workspace/skills:rw` so CodeBot can write SKILL.md files.
   - Attach it to the `securebot` internal bridge network.

### STEP 2: The Gateway Test Sandbox
CodeBot cannot execute code directly. It must ask the Gateway to run it.
1. In `gateway/gateway_service.py`, add a new internal-only FastAPI endpoint: `POST /internal/test-skill`.
2. This endpoint must accept a JSON payload: `{"code": "...", "execution_mode": "bash|python"}`.
3. It must write the code to a secure temporary file and execute it strictly using `subprocess.run(["sudo", "-u", "securebot-scripts", ...])`.
4. Return a JSON response containing `stdout`, `stderr`, and the `exit_code`.

### STEP 3: The GLiClass Coding Gatekeeper (Inside CodeBot)
1. Create `codebot/skill_router.py`.
2. Implement a lightweight Python script that loads the GLiClass model (using the same 144M model logic as the Gateway).
3. Define the labels: `["system_bash", "python_api_or_data"]`.
4. This script accepts the user's intent as an argument and prints the classification, allowing Pi CLI to decide which template to use before writing code.

### STEP 4: Pi CLI Configuration & Safe Extensions
1. Create the Pi CLI configuration file inside `codebot/`.
2. Build the following strictly scoped custom tools/extensions for Pi:
   - `tool_lint_bash`: Runs `shellcheck` against generated `.sh` payloads.
   - `tool_lint_python`: Runs `flake8` against generated `.py` payloads.
   - `tool_run_sandbox_test`: Sends the drafted script to `http://gateway:8080/internal/test-skill` and returns the result. Instruct Pi to ALWAYS use this and fix non-zero exit codes before committing.
   - `tool_validate_yaml`: Parses the drafted `SKILL.md` to ensure it contains exactly: `name`, `description`, `triggers` (array), `execution_mode` (bash/python), and `timeout`.
   - `tool_commit_skill`: Saves the vetted `SKILL.md` to `/workspace/skills/<skill-name>/` and outputs a success signal.

### STEP 5: Update the Gateway Handoff
1. Modify `gateway/orchestrator.py`. Locate the fallback logic where `haiku_generate_skill` is currently called.
2. Instead of calling the Anthropic API directly, update the fallback to forward the `_sanitize_for_cloud` payload to the new CodeBot container via a secure HTTP POST request on the internal Docker network.
3. Ensure the Gateway orchestration pipeline remains completely intact. Do not merge the deterministic and probabilistic routing paths.

### STRICT CONSTRAINTS:
- Do NOT alter `vault/secrets/secrets.json`.
- Do NOT alter `memory/soul.md`.
- Ensure `execution_mode: python` uses the exact same `sudo -u securebot-scripts` paradigm as Bash.