# SecureBot — Master Sprint: GLiClass + Skill Registry + RAG Separation + Haiku Skill Creation

Read CLAUDE.md before starting. This sprint completes the core intelligence routing
pipeline. Work through each fix in order — each one builds on the previous.

**Key principle:** Tool routing is deterministic. Memory retrieval is probabilistic.
These two pipelines must never merge.

---

## Architecture Being Built

```
User query
    ↓
[1] GLiClass classification (10ms, GPU)
    │
    ├── search   → vault → web search → llama3.2:3b summarize
    │              ChromaDB: NOT consulted
    │
    ├── task     → memory service direct read → llama3.2:3b
    │              ChromaDB: NOT consulted
    │
    ├── knowledge → RAG context retrieval → llama3.2:3b
    │              ChromaDB: consulted (correct use)
    │
    ├── chat     → RAG context (light) → llama3.2:3b
    │              ChromaDB: consulted (correct use)
    │
    └── action   → [2] Skill Registry (deterministic, exact lookup)
                        ChromaDB: NOT consulted
                        ↓
                   Match found?
                   ├── YES → execute skill locally (free, ~5ms-5s)
                   │         llama3.2:3b wraps output in natural language
                   └── NO  → [3] Haiku generates skill → save → execute
                                                              (~$0.01, one-time)
```

**RAG is consulted ONLY for knowledge and chat intents.**
**Skills directory is NEVER embedded into ChromaDB.**

---

## Pre-Sprint Setup: Sudo User for Script Execution

Before writing any code, create a locked-down execution user on the HOST (not inside
Docker) for running bash skill scripts. Running scripts as root is a full system
compromise vector if a malicious skill is ever generated.

```bash
# On the host VPS
sudo useradd -r -s /bin/bash -m securebot-scripts
sudo passwd -l securebot-scripts          # lock password — no direct login

# Create sudoers rule: gateway container user may sudo as securebot-scripts
# for bash execution only
sudo bash -c 'cat > /etc/sudoers.d/securebot-scripts << EOF
# Allow securebot gateway to execute bash skills as securebot-scripts only
nobody ALL=(securebot-scripts) NOPASSWD: /bin/bash
EOF'
sudo chmod 440 /etc/sudoers.d/securebot-scripts

# Verify
sudo -u securebot-scripts whoami
```

If the gateway container runs as user 1000:1000 (confirmed in docker-compose.yml),
adjust the sudoers `nobody` to match that UID:

```bash
# Find the username for UID 1000 inside the container
docker exec gateway id
# Use that username in the sudoers rule above
```

All bash skill execution must use:
```python
subprocess.run(
    ['sudo', '-u', 'securebot-scripts', 'bash', skill_script_path],
    capture_output=True,
    timeout=10,
    text=True
)
```

---

## Fix 1 — Create Datetime Bash Skill

Datetime queries ("what time is it?") currently take 55.6 seconds because the
orchestrator creates a skill on the fly via LLM inference. The correct fix is a
pre-built bash skill — not a Python fast-path. Skills are the right abstraction.

**Create file:** `~/securebot/skills/datetime-now/SKILL.md`

```markdown
---
name: datetime-now
description: Returns the current system date and time from the host OS
triggers:
  - what time is it
  - what's the time
  - current time
  - what day is it
  - today's date
  - what's today
  - current date
  - date and time
  - what year is it
  - what month is it
execution_mode: bash
timeout: 5
---

# Datetime Now

## Purpose
Returns the current system date, time, and timezone from the host OS.
Executes a bash command and returns the output to the model for natural
language wrapping.

## Script
```bash
#!/bin/bash
date '+%A, %B %d, %Y at %I:%M %p %Z'
```

## Output Format
The script outputs a single line:
  Saturday, February 21, 2026 at 11:45 PM CST

The model wraps this in natural language:
  "It's Saturday, February 21, 2026 at 11:45 PM CST."

## Examples
User: "What time is it?"
Script output: Saturday, February 21, 2026 at 11:45 PM CST
Response: It's Saturday, February 21, 2026 at 11:45 PM CST.

User: "What's today's date?"
Script output: Saturday, February 21, 2026 at 11:45 PM CST
Response: Today is Saturday, February 21, 2026.
```

**Also check for and delete any existing LLM-generated datetime skill:**
```bash
ls ~/securebot/skills/ | grep -i date
# If any exist besides datetime-now, delete them:
# rm -rf ~/securebot/skills/get-current-datetime/  (example)
```

**Skill execution result must flow into llama3.2:3b as context:**
```
bash script → stdout captured → passed to llama3.2:3b as:
"The user asked: 'what time is it?'
Script output: Saturday, February 21, 2026 at 11:45 PM CST
Respond naturally using this information."
```

The model wraps script output. It does not dump raw stdout to the user.

---

## Fix 2 — GLiClass Intent Classifier

### 2A — Create `gateway/gliclass_classifier.py` (new file)

```python
"""
GLiClass zero-shot intent classifier.
Singleton — loads ONCE at startup, reused for every request.
NEVER instantiate the model inside classify_intent() — that adds 3-5s per call.

Model: knowledgator/gliclass-small-v1.0 (144M params, ~10ms GPU inference)
Validated results on GTX 1050 Ti:
  search  1.000  |  What are the showtimes for GOAT in McAllen TX today?
  task    1.000  |  what are my pending tasks?
  chat    1.000  |  hello how are you
  search  1.000  |  search for AI news today
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Intent labels — maps to routing branches in orchestrator
INTENT_LABELS = ["search", "action", "task", "memory", "knowledge", "chat"]
CLASSIFICATION_THRESHOLD = 0.3

# Regex pre-filter: zero-cost fast path for obvious search triggers
SEARCH_TRIGGERS = re.compile(
    r'\b(today|tonight|right now|currently|showtimes?|playing near|'
    r'weather|score|news today|price of|stock price|open now|hours today|'
    r'near me|latest|breaking|what.s happening)\b',
    re.IGNORECASE
)

_pipeline = None  # module-level singleton — never reassign per request


def load_classifier(device: str = "cuda:0") -> bool:
    """
    Load GLiClass model into GPU memory.
    Call ONCE at startup from gateway startup event.
    Returns True on success, False on failure.
    """
    global _pipeline
    try:
        from gliclass import GLiClassModel, ZeroShotClassificationPipeline
        from transformers import AutoTokenizer

        logger.info("Loading GLiClass classifier on %s...", device)
        model = GLiClassModel.from_pretrained("knowledgator/gliclass-small-v1.0")
        tokenizer = AutoTokenizer.from_pretrained(
            "knowledgator/gliclass-small-v1.0"
        )
        _pipeline = ZeroShotClassificationPipeline(
            model, tokenizer,
            classification_type='multi-label',
            device=device
        )
        logger.info(
            "GLiClass ready on %s — phi4-mini classifier retired", device
        )
        return True
    except Exception as e:
        logger.warning("GLiClass GPU load failed: %s — trying CPU", e)
        try:
            from gliclass import GLiClassModel, ZeroShotClassificationPipeline
            from transformers import AutoTokenizer
            model = GLiClassModel.from_pretrained(
                "knowledgator/gliclass-small-v1.0"
            )
            tokenizer = AutoTokenizer.from_pretrained(
                "knowledgator/gliclass-small-v1.0"
            )
            _pipeline = ZeroShotClassificationPipeline(
                model, tokenizer,
                classification_type='multi-label',
                device='cpu'
            )
            logger.info("GLiClass on CPU fallback (~50ms per call)")
            return True
        except Exception as e2:
            logger.error("GLiClass failed entirely: %s", e2)
            return False


def classify_intent(text: str) -> tuple[str, float]:
    """
    Classify user query intent. Returns (label, confidence).
    Safe to call from async context — runs synchronously.
    Fast path: regex pre-filter catches obvious search queries in 0ms.
    """
    # Zero-cost fast path
    if SEARCH_TRIGGERS.search(text):
        logger.debug("Regex pre-filter: search | %s", text[:60])
        return "search", 1.0

    if _pipeline is None:
        logger.warning("GLiClass not loaded — defaulting to knowledge")
        return "knowledge", 0.0

    try:
        results = _pipeline(
            text, INTENT_LABELS, threshold=CLASSIFICATION_THRESHOLD
        )[0]
        if not results:
            return "knowledge", 0.5
        top = max(results, key=lambda x: x['score'])
        logger.info(
            "GLiClass: %s (%.3f) | %s", top['label'], top['score'], text[:60]
        )
        return top['label'], top['score']
    except Exception as e:
        logger.error("GLiClass error: %s — defaulting to knowledge", e)
        return "knowledge", 0.0
```

### 2B — Load at gateway startup

**File:** `gateway/gateway_service.py`

```python
from gliclass_classifier import load_classifier

@app.on_event("startup")
async def startup_event():
    # ... existing startup code ...
    load_classifier(device="cuda:0")
```

### 2C — Replace LLM classifier in orchestrator

**File:** `gateway/orchestrator.py`

Find the current intent classification call (phi4-mini LLM call or keyword match).
Replace it with:

```python
from gliclass_classifier import classify_intent

# In route_query():
intent, confidence = classify_intent(query_text)
logger.info("Intent: %s (confidence: %.3f)", intent, confidence)
```

### 2D — Retire phi4-mini classifier

1. Remove `CLASSIFIER_MODEL` from `.env`
2. Remove `CLASSIFIER_MODEL` from `docker-compose.yml` gateway environment
3. Remove all code calling phi4-mini for classification in `orchestrator.py`
4. Keep `phi4-mini:3.8b` in ollama list — do not `ollama rm` it (future specialist use)

### 2E — Docker and requirements

Add to `gateway/requirements.txt`:
```
gliclass==0.1.16
```

Add to `gateway/Dockerfile` BEFORE other pip installs:
```dockerfile
RUN pip install torch --index-url https://download.pytorch.org/whl/cu121 --timeout 300
```

Add to `docker-compose.yml` under gateway volumes:
```yaml
volumes:
  - ~/.cache/huggingface:/root/.cache/huggingface
```
This persists the 574MB model weights across container rebuilds — without this,
every `docker-compose up --build` re-downloads the model.

---

## Fix 3 — Skill Registry (Deterministic, No RAG)

**File:** `gateway/orchestrator.py`

### 3A — SkillRegistry class

Add at module level. Skills load once at startup. No vector search. No ChromaDB.

```python
import os
import yaml
from pathlib import Path

SKILLS_DIR = os.getenv("SKILLS_DIR", "/app/skills")

class SkillRegistry:
    """
    Deterministic skill lookup. Exact match only. No vectors. No RAG.
    Skills are complete YAML objects — never chunked, never embedded.
    Loaded once at startup, reloaded via /skills/reload endpoint.
    """
    def __init__(self, skills_dir: str):
        self.skills_dir = Path(skills_dir)
        self._registry: dict = {}
        self._load_all()

    def _load_all(self):
        if not self.skills_dir.exists():
            logger.warning("Skills dir not found: %s", self.skills_dir)
            return
        count = 0
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            # Support both SKILL.md (existing) and skill.yaml (new)
            skill_md = skill_dir / "SKILL.md"
            skill_yaml = skill_dir / "skill.yaml"

            if skill_md.exists():
                try:
                    content = skill_md.read_text()
                    meta = self._parse_frontmatter(content)
                    meta["_content"] = content
                    meta["_path"] = str(skill_md)
                    meta["_execution_format"] = "markdown"
                    self._registry[skill_dir.name] = meta
                    # Index triggers for fast lookup
                    for trigger in meta.get("triggers", []):
                        self._registry[f"__trigger__{trigger.lower()}"] = skill_dir.name
                    count += 1
                except Exception as e:
                    logger.warning("Failed to load skill %s: %s", skill_dir.name, e)

            elif skill_yaml.exists():
                try:
                    with open(skill_yaml) as f:
                        skill_def = yaml.safe_load(f)
                    skill_def["_path"] = str(skill_yaml)
                    skill_def["_execution_format"] = "yaml"
                    self._registry[skill_dir.name] = skill_def
                    for trigger in skill_def.get("triggers", []):
                        self._registry[f"__trigger__{trigger.lower()}"] = skill_dir.name
                    count += 1
                except Exception as e:
                    logger.warning("Failed to load skill %s: %s", skill_dir.name, e)

        logger.info("Skill registry: %d skills loaded", count)

    def _parse_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter from SKILL.md files."""
        import re
        match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if match:
            return yaml.safe_load(match.group(1)) or {}
        return {}

    def get(self, skill_name: str) -> dict | None:
        """Exact name lookup."""
        return self._registry.get(skill_name)

    def find_by_trigger(self, user_message: str) -> dict | None:
        """
        Deterministic trigger matching. String containment only.
        No vectors. No similarity scoring.
        Returns the skill definition or None.
        """
        user_lower = user_message.lower()
        for key, value in self._registry.items():
            if key.startswith("__trigger__"):
                trigger = key[len("__trigger__"):]
                if trigger in user_lower:
                    skill_name = value
                    return self._registry.get(skill_name)
        return None

    def list_all(self) -> list:
        return [
            {
                "name": k,
                "description": v.get("description", ""),
                "triggers": v.get("triggers", []),
                "execution_mode": v.get("execution_mode", "ollama")
            }
            for k, v in self._registry.items()
            if not k.startswith("__trigger__")
        ]

    def reload(self):
        self._registry.clear()
        self._load_all()
        logger.info("Skill registry reloaded")


# Module-level singleton — initialized at import time
skill_registry = SkillRegistry(SKILLS_DIR)
```

### 3B — Skill execution with model wrapping

Add skill execution function. Bash skills capture stdout and pass to llama3.2:3b
for natural language wrapping — raw script output is never returned directly.

```python
async def execute_skill(
    skill: dict,
    user_query: str,
    ollama_client
) -> str:
    """
    Execute a skill and return natural language response.
    Bash skills: run script, capture stdout, wrap with llama3.2:3b.
    Ollama skills: pass instructions + query to llama3.2:3b.
    RAG context: NEVER passed here. Skills are self-contained.
    """
    execution_mode = skill.get("execution_mode", "ollama")
    skill_name = skill.get("name", "unknown")

    if execution_mode == "bash":
        # Extract and run the bash script
        script_content = _extract_bash_script(skill.get("_content", ""))
        if not script_content:
            return "Skill script not found."

        # Write to temp file and execute as securebot-scripts user
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.sh', delete=False
        ) as f:
            f.write(script_content)
            script_path = f.name

        try:
            result = subprocess.run(
                ['sudo', '-u', 'securebot-scripts', 'bash', script_path],
                capture_output=True,
                timeout=skill.get("timeout", 10),
                text=True
            )
            script_output = result.stdout.strip()
            if not script_output:
                script_output = result.stderr.strip() or "No output."
        except subprocess.TimeoutExpired:
            script_output = "Script timed out."
        finally:
            os.unlink(script_path)

        # Wrap output with llama3.2:3b for natural language response
        wrap_prompt = (
            f"The user asked: '{user_query}'\n"
            f"The system returned: {script_output}\n"
            f"Respond naturally in one sentence using this information."
        )
        return await ollama_client.generate(wrap_prompt)

    elif execution_mode == "ollama":
        # Pass skill instructions + user query to llama3.2:3b
        instructions = skill.get("_content", skill.get("instructions", ""))
        prompt = instructions.replace("$ARGUMENTS", user_query)
        return await ollama_client.generate(prompt)

    else:
        logger.warning("Unknown execution_mode: %s for skill %s",
                       execution_mode, skill_name)
        return f"Skill {skill_name} has unsupported execution mode."


def _extract_bash_script(skill_content: str) -> str:
    """Extract bash script block from SKILL.md content."""
    import re
    match = re.search(r'```bash\n(.*?)```', skill_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""
```

---

## Fix 4 — Clean Route Query (RAG Separation)

**File:** `gateway/orchestrator.py`

Replace the current `route_query()` routing logic with strict pipeline separation.
This is the core of the fix — RAG is called ONLY for knowledge and chat intents.

```python
async def route_query(
    query_text: str,
    user_id: str,
    session_id: str,
    vault_client,
    memory_client,
    rag_client,
    ollama_client
) -> dict:
    """
    Route user query to the correct pipeline.

    TWO PARALLEL PIPELINES — NEVER MERGE:
    A) Deterministic: search, action, task → no ChromaDB
    B) Probabilistic: knowledge, chat → ChromaDB for memory context
    """
    from gliclass_classifier import classify_intent

    intent, confidence = classify_intent(query_text)
    logger.info("Intent: %s (%.3f) | %s", intent, confidence, query_text[:60])

    # ─────────────────────────────────────────────
    # PIPELINE A — Deterministic (no RAG/ChromaDB)
    # ─────────────────────────────────────────────

    if intent == "search":
        # Web search via vault — ChromaDB NOT consulted
        try:
            search_results = await vault_client.search(query_text)
            response = await ollama_client.summarize(query_text, search_results)
            return {
                "response": response,
                "method": "search",
                "intent": intent,
                "cost": 0.0
            }
        except Exception as e:
            logger.error("Search failed: %s — falling back to knowledge", e)
            intent = "knowledge"  # fall through to Pipeline B

    elif intent in ("action", "task_action"):
        # Skill registry lookup — ChromaDB NOT consulted
        skill = skill_registry.get(intent) or \
                skill_registry.find_by_trigger(query_text)

        if skill:
            # Skill found — execute locally for free
            logger.info("Skill match: %s — executing locally", skill.get("name"))
            response = await execute_skill(skill, query_text, ollama_client)
            return {
                "response": response,
                "method": "skill_execution",
                "skill_used": skill.get("name"),
                "skill_created": None,
                "cost": 0.0
            }
        else:
            # No match — escalate to Haiku for skill generation
            logger.info("No skill match — escalating to Haiku")
            result = await haiku_generate_skill(
                query_text, vault_client, Path(SKILLS_DIR)
            )
            if result["success"]:
                skill_registry.reload()  # register the new skill
                new_skill = skill_registry.get(result["skill_name"])
                if new_skill:
                    response = await execute_skill(
                        new_skill, query_text, ollama_client
                    )
                    return {
                        "response": response,
                        "method": "skill_execution",
                        "skill_used": result["skill_name"],
                        "skill_created": result["skill_name"],
                        "cost": result["cost"]
                    }
            # Haiku failed — fall through to knowledge path
            logger.warning("Skill generation failed — falling back to knowledge")
            intent = "knowledge"

    elif intent == "task":
        # Memory service direct read — ChromaDB NOT consulted
        try:
            tasks = await memory_client.get_tasks()
            task_context = _format_tasks(tasks)
            response = await ollama_client.generate(
                f"User asked: {query_text}\n\nCurrent tasks:\n{task_context}\n"
                f"Respond with the relevant task information."
            )
            return {
                "response": response,
                "method": "task_lookup",
                "intent": intent,
                "cost": 0.0
            }
        except Exception as e:
            logger.error("Task retrieval failed: %s", e)
            intent = "knowledge"  # fall through

    # ─────────────────────────────────────────────
    # PIPELINE B — Probabilistic (RAG/ChromaDB)
    # Only knowledge and chat reach here
    # ─────────────────────────────────────────────

    # RAG memory context — ONLY consulted here
    try:
        memory_context = await rag_client.get_context(
            query=query_text,
            user_id=user_id,
            max_tokens=300
        )
    except Exception as e:
        logger.warning("RAG context failed: %s — continuing without", e)
        memory_context = ""

    response = await ollama_client.generate_with_context(
        query_text, memory_context
    )
    return {
        "response": response,
        "method": f"ollama_{intent}",
        "intent": intent,
        "cost": 0.0
    }
```

---

## Fix 5 — Haiku Skill Generation

**File:** `gateway/orchestrator.py` (add these functions)

```python
HAIKU_MODEL = "claude-haiku-4-5-20251001"

SKILL_GENERATION_SYSTEM_PROMPT = """You are a skill generator for SecureBot.
Generate a single skill definition. Return ONLY the SKILL.md content, no preamble.

FORMAT:
---
name: skill-name-here
description: one line description
triggers:
  - trigger phrase one
  - trigger phrase two
execution_mode: ollama
model: llama3.2:3b
---

# Skill Name

## Purpose
What this skill does in 1-2 sentences.

## Instructions
Step by step instructions. Use $ARGUMENTS where the user input goes.

## Output Format
Describe expected output.

## Examples
User: example trigger
Response: example response

RULES:
- name: ^[a-zA-Z0-9][a-zA-Z0-9_-]{1,48}[a-zA-Z0-9]$
- no path separators, dots, or special characters in name
- execution_mode: ollama (unless explicitly a bash system command)
- keep under 2000 tokens total
- do not include API keys, personal data, or system paths
"""

async def haiku_generate_skill(
    user_request: str,
    vault_client,
    skills_dir: Path
) -> dict:
    """
    Generate a new skill via Haiku when no local match exists.
    Privacy: request is sanitized before leaving the system.
    Haiku never sees memory context, soul.md, or personal identifiers.
    Cost: ~$0.01 per skill (one-time — future executions are free).
    """
    sanitized = _sanitize_for_cloud(user_request)
    logger.info(
        "Haiku skill generation request: %s", sanitized[:80]
    )

    try:
        api_key_resp = await vault_client.get("/secrets/anthropic_api_key")
        api_key = api_key_resp.get("value")
        if not api_key:
            raise ValueError("No Anthropic API key in vault")
    except Exception as e:
        logger.error("Vault API key retrieval failed: %s", e)
        return {"success": False, "error": str(e), "cost": 0.0}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=1024,
            system=SKILL_GENERATION_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Generate a skill for: {sanitized}"
            }]
        )
        skill_content = message.content[0].text

        # Cost tracking (Haiku: $0.80/M input, $4.00/M output)
        cost = (message.usage.input_tokens * 0.0000008) + \
               (message.usage.output_tokens * 0.000004)
        logger.info(
            "COST_EVENT: skill_creation | model=%s | "
            "tokens=%d/%d | cost=$%.4f",
            HAIKU_MODEL,
            message.usage.input_tokens,
            message.usage.output_tokens,
            cost
        )

        result = _validate_and_save_skill(skill_content, skills_dir)
        result["cost"] = cost
        return result

    except Exception as e:
        logger.error("Haiku skill generation failed: %s", e)
        return {"success": False, "error": str(e), "cost": 0.0}


def _sanitize_for_cloud(text: str) -> str:
    """
    Strip personal identifiers before sending to cloud API.
    This is the anonymization gate — Haiku sees request type, not personal data.
    """
    sanitized = text
    sanitized = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        '[EMAIL]', sanitized
    )
    sanitized = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', sanitized)
    sanitized = re.sub(
        r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]', sanitized
    )
    return sanitized.strip()


def _validate_and_save_skill(skill_content: str, skills_dir: Path) -> dict:
    """Validate and save Haiku-generated skill. Reuses Fix 1B security checks."""
    if len(skill_content) > 50_000:
        logger.warning("Skill too large (%d chars) — rejected", len(skill_content))
        return {"success": False, "error": "Skill content too large"}

    name_match = re.search(r'^name:\s*(.+)$', skill_content, re.MULTILINE)
    if not name_match:
        return {"success": False, "error": "No skill name in generated content"}

    skill_name = name_match.group(1).strip()
    _SKILL_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{1,48}[a-zA-Z0-9]$')
    if not _SKILL_NAME_RE.match(skill_name):
        logger.warning("Invalid skill name from Haiku: %s — rejected", skill_name)
        return {"success": False, "error": f"Invalid skill name: {skill_name}"}

    skill_path = (skills_dir / skill_name).resolve()
    if not str(skill_path).startswith(str(skills_dir.resolve())):
        logger.warning("Path traversal attempt: %s", skill_name)
        return {"success": False, "error": "Path traversal detected"}

    skill_path.mkdir(parents=True, exist_ok=True)
    skill_file = skill_path / "SKILL.md"
    skill_file.write_text(skill_content)
    logger.info("New skill saved: %s", skill_name)
    return {"success": True, "skill_name": skill_name, "skill_path": str(skill_file)}
```

---

## Fix 6 — ChromaDB Audit (Skills Must Not Be Embedded)

```bash
# Search for skill content being embedded into ChromaDB
grep -rn "embed.*skill\|skill.*embed" ~/securebot/gateway/
grep -rn "embed.*skill\|skill.*embed" ~/securebot/services/

# Must return nothing — if any hits, remove those embed calls

# Check what ChromaDB collections exist
curl http://localhost:8400/collections | python3 -m json.tool

# Approved collections:
#   memory       (soul/user/session markdown) — OK
#   conversations (exchange history)           — OK
#   skills       — MUST NOT EXIST, delete if present
```

If a `skills` collection exists in ChromaDB, purge it:
```python
# Run once to clean up
import chromadb
client = chromadb.PersistentClient(path="/chroma")
try:
    client.delete_collection("skills")
    print("Skills collection removed from ChromaDB")
except:
    print("No skills collection found — clean")
```

---

## Fix 7 — Skills Reload Endpoint

**File:** `gateway/gateway_service.py`

```python
@app.post("/skills/reload")
async def reload_skills(_auth=Depends(api_key_middleware)):
    """Hot-reload skill registry without container restart."""
    skill_registry.reload()
    skills = skill_registry.list_all()
    return {
        "status": "ok",
        "skills_loaded": len(skills),
        "skills": [s["name"] for s in skills]
    }
```

---

## Files Modified This Sprint

- `~/securebot/skills/datetime-now/SKILL.md` — NEW bash skill
- `~/securebot/gateway/gliclass_classifier.py` — NEW
- `~/securebot/gateway/orchestrator.py` — classifier, registry, routing, Haiku
- `~/securebot/gateway/gateway_service.py` — startup load, reload endpoint
- `~/securebot/gateway/requirements.txt` — add gliclass
- `~/securebot/gateway/Dockerfile` — torch install order
- `~/securebot/docker-compose.yml` — HuggingFace volume, remove CLASSIFIER_MODEL
- `~/securebot/.env` — remove CLASSIFIER_MODEL
- `/etc/sudoers.d/securebot-scripts` — NEW (host, not container)

---

## Smoke Tests (Run in Order — All Must Pass)

**Test 1 — Syntax check before rebuild:**
```bash
python3 -m py_compile ~/securebot/gateway/orchestrator.py && echo "PASS"
python3 -m py_compile ~/securebot/gateway/gliclass_classifier.py && echo "PASS"
```

**Test 2 — Rebuild gateway:**
```bash
cd ~/securebot && docker compose up -d --build gateway
docker compose ps  # gateway must show healthy
```

**Test 3 — GLiClass loaded (check startup logs):**
```bash
docker compose logs gateway | grep -i "gliclass\|classifier"
# Expected: "GLiClass ready on cuda:0 — phi4-mini classifier retired"
# Must NOT see: "phi4-mini" in any classification call
```

**Test 4 — Datetime via bash skill (<5 seconds):**
```bash
curl -s -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(grep GATEWAY_API_KEY ~/securebot/.env | cut -d= -f2)" \
  -d '{"channel":"api","user_id":"roland","text":"what time is it?"}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin);
    print('method:', r.get('metadata',{}).get('method'));
    print('response:', r.get('response','')[:100])"
# Expected method: skill_execution
# Expected: natural language time response
# Must NOT take 55 seconds
```

**Test 5 — RAG used for knowledge, NOT for action:**
```bash
# Knowledge query — RAG should fire
curl -s -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(grep GATEWAY_API_KEY ~/securebot/.env | cut -d= -f2)" \
  -d '{"channel":"api","user_id":"roland","text":"what have we been working on?"}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin);
    print('method:', r.get('metadata',{}).get('method'));
    print('response:', r.get('response','')[:200])"
# Check logs — should see RAG context retrieval
docker compose logs gateway --tail 20 | grep -i "rag\|context"
```

**Test 6 — Search routing (no hallucinated results):**
```bash
curl -s -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(grep GATEWAY_API_KEY ~/securebot/.env | cut -d= -f2)" \
  -d '{"channel":"api","user_id":"roland","text":"what movies are playing in McAllen TX today?"}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin);
    print('method:', r.get('metadata',{}).get('method'));
    print('response:', r.get('response','')[:200])"
# Expected method: search
# Response time: 5-30s (actual web search)
# Must NOT contain fabricated showtimes
```

**Test 7 — Haiku skill creation (new skill):**
```bash
# Use a request that won't match any existing skill
curl -s -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(grep GATEWAY_API_KEY ~/securebot/.env | cut -d= -f2)" \
  -d '{"channel":"api","user_id":"roland","text":"create a daily backup cron job for my documents folder"}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin);
    print('method:', r.get('metadata',{}).get('method'));
    print('skill_created:', r.get('metadata',{}).get('skill_created'));
    print('cost:', r.get('metadata',{}).get('cost'))"
# Expected: skill_created shows a skill name, cost > 0
ls ~/securebot/skills/ | grep backup  # new skill must exist
```

**Test 8 — Skill reuse (same request, free):**
```bash
# Repeat a similar backup request — must reuse skill, not call Haiku again
curl -s -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(grep GATEWAY_API_KEY ~/securebot/.env | cut -d= -f2)" \
  -d '{"channel":"api","user_id":"roland","text":"set up a weekly backup cron job for downloads"}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin);
    print('method:', r.get('metadata',{}).get('method'));
    print('skill_created:', r.get('metadata',{}).get('skill_created'));
    print('cost:', r.get('metadata',{}).get('cost'))"
# Expected: skill_created = null, cost = 0.0 — Haiku NOT called
```

**Test 9 — ChromaDB clean (no skills embedded):**
```bash
grep -rn "embed.*skill\|skill.*embed" ~/securebot/gateway/
grep -rn "embed.*skill\|skill.*embed" ~/securebot/services/
# Both must return nothing
```

**Test 10 — phi4-mini retired:**
```bash
docker compose logs gateway --tail 200 | grep -i "phi4\|classifier_model"
# Must return nothing
```

Only report DONE when all 10 tests pass.

---

## Do Not Touch

- `vault/secrets/secrets.json`
- `memory/soul.md` (chmod 444)
- `chroma/` directory (except removing skills collection if it exists)
- Existing HMAC inter-service auth in `common/auth.py`
- `SKILL_MATCH_THRESHOLD` — do not adjust without testing
- Existing skill execution logic for Ollama-mode skills — only add bash mode
