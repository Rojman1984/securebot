#!/usr/bin/env python3
"""
Claude Code Orchestrator
Manages skill creation, validation, and execution.

GLiClass intent classification → SkillRegistry (deterministic) → Haiku skill generation
RAG/ChromaDB consulted ONLY for knowledge and chat intents.

Author: SecureBot Project
License: MIT
"""

import os
import re
import sys
import json
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx
import yaml
from datetime import datetime

# Skill name must start/end with alphanumeric, allow interior hyphens/underscores.
# Min 3 chars, max 50 chars.
_SKILL_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{1,48}[a-zA-Z0-9]$')
_MAX_SKILL_CONTENT = 50_000  # characters

RESPONSE_MODEL = os.getenv('RESPONSE_MODEL', 'llama3.2:3b')
SKILLS_DIR = os.getenv("SKILLS_DIR", "/app/skills")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import get_config
from common.auth import SignedClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_system_prompt() -> str:
    """Load /memory/user.md and return its contents as the base system prompt."""
    user_md = Path(os.getenv("MEMORY_DIR", "/memory")) / "user.md"
    try:
        content = user_md.read_text(encoding="utf-8").strip()
        if content:
            logger.info("Base system prompt loaded from %s (%d chars)", user_md, len(content))
        return content
    except Exception as e:
        logger.debug("Could not load base system prompt from %s: %s", user_md, e)
        return ""


BASE_SYSTEM_PROMPT: str = load_system_prompt()


# ─────────────────────────────────────────────────────────────────────────────
# Skill Registry — deterministic, no vectors, no ChromaDB
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Skill Execution
# ─────────────────────────────────────────────────────────────────────────────

def _extract_bash_script(skill_content: str) -> str:
    """Extract bash script block from SKILL.md content."""
    match = re.search(r'```bash\n(.*?)```', skill_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


async def execute_skill(
    skill: dict,
    user_query: str,
    ollama_url: str,
    user_id: str = "",
    rag_url: str = "",
    signed_client=None,
) -> str:
    """
    Execute a skill and return natural language response.
    Bash skills: run script, capture stdout, optionally enrich with RAG context, wrap with llama3.2:3b.
    Ollama skills: pass instructions + query to llama3.2:3b.
    """
    execution_mode = skill.get("execution_mode", "ollama")
    skill_name = skill.get("name", "unknown")

    if execution_mode == "bash":
        script_content = _extract_bash_script(skill.get("_content", ""))
        if not script_content:
            return "Skill script not found."

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.sh', delete=False
        ) as f:
            f.write(script_content)
            script_path = f.name
        os.chmod(script_path, 0o644)  # allow securebot-scripts to read

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

        # Fetch lightweight RAG context (max_tokens=100) to enrich wrap response
        rag_context = ""
        if rag_url and user_id:
            try:
                async with httpx.AsyncClient(timeout=5.0) as rag_client:
                    params = {"query": user_query, "user_id": user_id, "max_tokens": 100}
                    if signed_client:
                        rag_resp = await signed_client.get(
                            rag_client, f"{rag_url}/context", params=params
                        )
                    else:
                        rag_resp = await rag_client.get(
                            f"{rag_url}/context", params=params
                        )
                    if rag_resp.status_code == 200:
                        rag_context = rag_resp.json().get("context", "")
            except Exception as rag_err:
                logger.debug("RAG context skipped for skill wrap: %s", rag_err)

        wrap_prompt = (
            f"The user asked: '{user_query}'\n"
            + (f"Relevant context: {rag_context}\n" if rag_context else "")
            + f"The system returned: {script_output}\n"
            f"Respond naturally in one sentence using this information."
        )
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{ollama_url}/api/generate",
                    json={"model": RESPONSE_MODEL, "prompt": wrap_prompt, "stream": False}
                )
                return response.json().get("response", script_output)
        except Exception as e:
            logger.error("Ollama wrap failed: %s — returning raw output", e)
            return script_output

    elif execution_mode == "ollama":
        instructions = skill.get("_content", skill.get("instructions", ""))
        # Prompt injection prevention
        _INJECTION_DELIMITERS = ['---', '<s>', '[INST]', '<<SYS>>', '</s>', '[/INST]']
        safe_query = user_query
        for delim in _INJECTION_DELIMITERS:
            safe_query = safe_query.replace(delim, '')
        if len(safe_query) > 2000:
            safe_query = safe_query[:2000]
        safe_arguments = f"[USER INPUT START]\n{safe_query}\n[USER INPUT END]"

        if '$ARGUMENTS' in instructions:
            prompt = instructions.replace('$ARGUMENTS', safe_arguments)
        else:
            prompt = f"{instructions}\n\nUser query: {safe_arguments}"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{ollama_url}/api/generate",
                    json={"model": RESPONSE_MODEL, "prompt": prompt, "stream": False}
                )
                return response.json().get("response", "")
        except Exception as e:
            logger.error("Skill ollama execution failed: %s", e)
            return f"Skill {skill_name} execution failed."

    else:
        logger.warning("Unknown execution_mode: %s for skill %s", execution_mode, skill_name)
        return f"Skill {skill_name} has unsupported execution mode."


# ─────────────────────────────────────────────────────────────────────────────
# Haiku Skill Generation
# ─────────────────────────────────────────────────────────────────────────────

HAIKU_MODEL = "claude-haiku-4-5-20251001"

SKILL_GENERATION_SYSTEM_PROMPT = """You are a skill generator for SecureBot.
Generate a single skill definition. Return ONLY the SKILL.md content, no preamble.

OLLAMA SKILL FORMAT (for reasoning/explanation tasks):
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

BASH SKILL FORMAT (for system commands — MUST include ## Script with a code block):
---
name: skill-name-here
description: one line description
triggers:
  - trigger phrase one
  - trigger phrase two
execution_mode: bash
timeout: 10
---

# Skill Name

## Purpose
What this skill does in 1-2 sentences.

## Script
```bash
#!/bin/bash
# actual commands here — output is captured and returned to user
echo "result"
```

## Output Format
Describe expected output.

## Examples
User: example trigger
Response: example response

RULES:
- name: ^[a-zA-Z0-9][a-zA-Z0-9_-]{1,48}[a-zA-Z0-9]$
- no path separators, dots, or special characters in name
- use execution_mode: bash for OS commands (ports, processes, files, system info)
- use execution_mode: ollama for reasoning, generation, or explanation tasks
- bash skills MUST have a ## Script section with a ```bash ... ``` code block
- keep under 2000 tokens total
- do not include API keys, personal data, or hardcoded system paths
"""


async def haiku_generate_skill(
    user_request: str,
    vault_url: str,
    skills_dir: Path
) -> dict:
    """
    Generate a new skill via Haiku when no local match exists.
    Privacy: request AND user profile are sanitized before leaving the system.
    Haiku receives sanitized system context (OS, hardware, paths) to tailor
    bash scripts to the user's actual environment. It never sees soul.md,
    raw memory files, or any personal identifiers.
    Cost: ~$0.01 per skill (one-time — future executions are free).
    """
    sanitized = _sanitize_for_cloud(user_request)
    logger.info("Haiku skill generation request: %s", sanitized[:80])

    # Load user profile for architecture context; sanitize before sending
    user_md_path = Path(os.getenv("MEMORY_DIR", "/memory")) / "user.md"
    sanitized_profile = ""
    try:
        raw_profile = user_md_path.read_text(encoding="utf-8").strip()
        if raw_profile:
            sanitized_profile = _sanitize_for_cloud(raw_profile)
            logger.info("User profile loaded and sanitized for Haiku (%d chars)", len(sanitized_profile))
    except Exception as e:
        logger.debug("Could not load user.md for skill context: %s", e)

    try:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            # Retrieve from vault via authenticated POST /secret
            service_id = os.getenv("SERVICE_ID", "gateway")
            service_secret = os.getenv("SERVICE_SECRET", "")
            _sc = SignedClient(service_id, service_secret) if service_secret else None
            async with httpx.AsyncClient(timeout=10.0) as client:
                if _sc:
                    resp = await _sc.post(client, f"{vault_url}/secret",
                                          json={"name": "anthropic_api_key"})
                else:
                    resp = await client.post(f"{vault_url}/secret",
                                             json={"name": "anthropic_api_key"})
                if resp.status_code == 200:
                    api_key = resp.json().get("value", "")
        if not api_key:
            raise ValueError("No Anthropic API key available (vault or env)")
    except Exception as e:
        logger.error("API key retrieval failed: %s", e)
        return {"success": False, "error": str(e), "cost": 0.0}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Build user message — inject sanitized profile so Haiku can tailor
        # bash scripts to the user's actual OS, hardware, and path layout.
        if sanitized_profile:
            enhanced_prompt = (
                f"Generate a skill for: {sanitized}\n\n"
                f"---\n"
                f"User system context (sanitized — use to tailor bash scripts to "
                f"this environment, e.g. correct paths, package manager, OS):\n"
                f"{sanitized_profile}"
            )
        else:
            enhanced_prompt = f"Generate a skill for: {sanitized}"

        message = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=1024,
            system=SKILL_GENERATION_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": enhanced_prompt
            }]
        )
        skill_content = message.content[0].text

        # Cost tracking (Haiku: $0.80/M input, $4.00/M output)
        cost = (message.usage.input_tokens * 0.0000008) + \
               (message.usage.output_tokens * 0.000004)
        logger.info(
            "COST_EVENT: skill_creation | model=%s | tokens=%d/%d | cost=$%.4f",
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

    Redacts:
    - Email addresses
    - Phone numbers (US format)
    - IPv4 addresses
    - MAC addresses (colon or hyphen separated)
    - SSH/PEM private key blocks
    - Keywords from REDACT_WORDS env var (comma-separated, case-insensitive)
    """
    sanitized = text

    # Email addresses
    sanitized = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        '[EMAIL]', sanitized
    )

    # US phone numbers
    sanitized = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', sanitized)

    # IPv4 addresses
    sanitized = re.sub(
        r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]', sanitized
    )

    # MAC addresses (xx:xx:xx:xx:xx:xx or xx-xx-xx-xx-xx-xx)
    sanitized = re.sub(
        r'\b([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}\b',
        '[MAC]', sanitized
    )

    # SSH / PEM private key blocks (multi-line)
    sanitized = re.sub(
        r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----',
        '[SSH_KEY]', sanitized, flags=re.DOTALL
    )

    # Explicit REDACT_WORDS from environment (comma-separated, case-insensitive)
    redact_words_env = os.getenv("REDACT_WORDS", "Roland,Rolando,Mac")
    for word in redact_words_env.split(","):
        word = word.strip()
        if word:
            sanitized = re.sub(re.escape(word), '[REDACTED]', sanitized, flags=re.IGNORECASE)

    return sanitized.strip()


def _validate_and_save_skill(skill_content: str, skills_dir: Path) -> dict:
    """Validate and save Haiku-generated skill. Reuses Fix 1B security checks."""
    if len(skill_content) > _MAX_SKILL_CONTENT:
        logger.warning("Skill too large (%d chars) — rejected", len(skill_content))
        return {"success": False, "error": "Skill content too large"}

    name_match = re.search(r'^name:\s*(.+)$', skill_content, re.MULTILINE)
    if not name_match:
        return {"success": False, "error": "No skill name in generated content"}

    skill_name = name_match.group(1).strip()
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


# ─────────────────────────────────────────────────────────────────────────────
# Legacy SkillMatcher — kept for gateway /skills and /stats endpoints
# ─────────────────────────────────────────────────────────────────────────────

class SkillMatcher:
    """Match queries to existing skills (legacy — used by gateway for listing)."""

    def __init__(self, skills_dir: str = "/app/skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.config = get_config()
        self.skills = self._load_skills()

    def _load_skills(self) -> Dict[str, Any]:
        skills = {}
        if not self.skills_dir.exists():
            return skills
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            try:
                skill = self._parse_skill_file(skill_file)
                if self.config.is_skill_enabled(skill['name']):
                    skills[skill['name']] = skill
            except Exception as e:
                logger.error("Failed to load skill %s: %s", skill_file, e)
        return skills

    def _parse_skill_file(self, skill_file: Path) -> Dict[str, Any]:
        content = skill_file.read_text()
        if content.startswith('---\n'):
            parts = content.split('---\n', 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                markdown_content = parts[2].strip()
            else:
                frontmatter = {}
                markdown_content = content
        else:
            frontmatter = {}
            markdown_content = content
        return {
            'name': frontmatter.get('name', skill_file.parent.name),
            'description': frontmatter.get('description', ''),
            'category': frontmatter.get('category', 'general'),
            'priority': frontmatter.get('priority', 999),
            'content': markdown_content,
            'frontmatter': frontmatter,
            'path': skill_file,
            'triggers': []
        }


# ─────────────────────────────────────────────────────────────────────────────
# Route Query — strict pipeline separation
# ─────────────────────────────────────────────────────────────────────────────

def _format_tasks(tasks: Any) -> str:
    """Format tasks list for Ollama prompt context."""
    if not tasks:
        return "No tasks found."
    if isinstance(tasks, list):
        lines = []
        for t in tasks:
            if isinstance(t, dict):
                status = t.get("status", "unknown")
                title = t.get("title") or t.get("query") or t.get("id", "untitled")
                lines.append(f"- [{status}] {title}")
            else:
                lines.append(f"- {t}")
        return "\n".join(lines) if lines else "No tasks found."
    return str(tasks)

def determine_routing_path(query: str) -> tuple[str, float, dict | None]:
    """
    Acts as the master pre-router.
    1. Uses GLiClass to determine the true intent.
    2. If it's an action, performs the deterministic skill lookup.
    3. Pipes both the intent and the matched skill down the line.
    """
    from gliclass_classifier import classify_intent

    # 1. Ask GLiClass for the intent
    intent, confidence = classify_intent(query)
    matched_skill = None

    # 2. ONLY do a skill lookup if GLiClass confirms the user wants an action
    if intent in ("action", "task_action"):
        matched_skill = skill_registry.find_by_trigger(query)

        if matched_skill:
            logger.info("Pre-router mapped ACTION to specific skill: %s", matched_skill.get('name'))
        else:
            logger.info("Pre-router detected ACTION, but no existing skill matched (Will escalate to Haiku).")

    return intent, confidence, matched_skill

async def route_query(
    query: str,
    user_id: str,
    vault_url: str = "http://vault:8200",
    ollama_url: str = "http://host.docker.internal:11434",
    has_search_results: bool = False,
    memory_service_url: Optional[str] = None,
    system_prompt: Optional[str] = None,
    rag_url: Optional[str] = None,
    session_id: str = "default",
) -> Dict[str, Any]:
    """
    Route user query to the correct pipeline.

    TWO PARALLEL PIPELINES — NEVER MERGE:
    A) Deterministic: search, action, task → no ChromaDB
    B) Probabilistic: knowledge, chat → ChromaDB for memory context
    """
    from gliclass_classifier import classify_intent

    _memory_url = memory_service_url or os.getenv("MEMORY_SERVICE_URL", "http://memory-service:8300")
    _rag_url = rag_url or os.getenv("RAG_URL", "http://rag-service:8400")

    # Service secret for signed inter-service calls
    service_id = os.getenv("SERVICE_ID", "gateway")
    service_secret = os.getenv("SERVICE_SECRET", "")
    signed_client = SignedClient(service_id, service_secret) if service_secret else None

    # If query already has search results injected by the gateway pre-check,
    # skip classification and summarize directly (backward compat path).
    if has_search_results:
        logger.info("Summarizing pre-fetched search results with Ollama")
        try:
            context = await _get_rag_context(query, user_id, _rag_url, signed_client)
            enhanced = f"Context:\n{context}\n\n---\n\n{query}" if context else query
        except Exception:
            enhanced = query
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": RESPONSE_MODEL, "prompt": enhanced,
                      "system": system_prompt or BASE_SYSTEM_PROMPT, "stream": False}
            )
            result = resp.json().get("response", "")
        return {"result": result, "response": result, "method": "direct_ollama",
                "intent": "search", "cost": 0.0, "engine": "ollama"}

    # ─────────────────────────────────────────────
    # THE MASTER PRE-ROUTER
    # GLiClass acts as the gatekeeper.
    # ─────────────────────────────────────────────
    intent, confidence, matched_skill = determine_routing_path(query)
    logger.info("Intent: %s (%.3f) | %s", intent, confidence, query[:60])

    # ─────────────────────────────────────────────
    # PIPELINE A — Deterministic (no RAG/ChromaDB)
    # ─────────────────────────────────────────────

    if intent == "search":
        try:
            search_results = await _search_via_vault(query, vault_url, signed_client)
            augmented = _build_search_context(query, search_results)
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{ollama_url}/api/generate",
                    json={"model": RESPONSE_MODEL, "prompt": augmented,
                          "system": system_prompt or BASE_SYSTEM_PROMPT, "stream": False}
                )
                response = resp.json().get("response", "")
            return {
                "result": response, "response": response,
                "method": "search", "intent": intent, "cost": 0.0, "engine": "ollama"
            }
        except Exception as e:
            logger.error("Search failed: %s — falling back to knowledge", e)
            intent = "knowledge"

    elif intent in ("action", "task_action"):
        # We ALREADY have the skill if one existed, thanks to the pre-router!
        if matched_skill:
            logger.info("Skill match: %s — executing locally", matched_skill.get("name"))
            response = await execute_skill(matched_skill, query, ollama_url, user_id, _rag_url, signed_client)
            return {
                "result": response, "response": response,
                "method": "skill_execution",
                "skill_used": matched_skill.get("name"),
                "skill_created": None,
                "cost": 0.0, "engine": "ollama"
            }
        else:
            logger.info("No skill match — escalating to Haiku")
            skills_path = Path(SKILLS_DIR)
            result = await haiku_generate_skill(query, vault_url, skills_path)
            if result["success"]:
                skill_registry.reload()
                new_skill = skill_registry.get(result["skill_name"])
                if new_skill:
                    response = await execute_skill(new_skill, query, ollama_url, user_id, _rag_url, signed_client)
                    return {
                        "result": response, "response": response,
                        "method": "skill_execution",
                        "skill_used": result["skill_name"],
                        "skill_created": result["skill_name"],
                        "cost": result["cost"], "engine": "claude+ollama"
                    }
            logger.warning("Skill generation failed — falling back to knowledge")
            intent = "knowledge"
    # ... (Keep everything from here down exactly as you have it!) ...
    elif intent == "task":
        try:
            tasks = await _get_tasks_from_memory(_memory_url, signed_client)
            task_context = _format_tasks(tasks)
            prompt = (
                f"User asked: {query}\n\n"
                f"Current tasks:\n{task_context}\n"
                f"Respond with the relevant task information."
            )
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{ollama_url}/api/generate",
                    json={"model": RESPONSE_MODEL, "prompt": prompt,
                          "system": system_prompt or BASE_SYSTEM_PROMPT, "stream": False}
                )
                response = resp.json().get("response", "")
            return {
                "result": response, "response": response,
                "method": "task_lookup", "intent": intent,
                "cost": 0.0, "engine": "ollama"
            }
        except Exception as e:
            logger.error("Task retrieval failed: %s", e)
            intent = "knowledge"

    # ─────────────────────────────────────────────
    # PIPELINE B — Probabilistic (RAG/ChromaDB)
    # Only knowledge and chat reach here
    # ─────────────────────────────────────────────

    try:
        memory_context = await _get_rag_context(query, user_id, _rag_url, signed_client)
    except Exception as e:
        logger.warning("RAG context failed: %s — continuing without", e)
        memory_context = ""

    if memory_context:
        prompt = f"Context:\n{memory_context}\n\n---\n\nUser query: {query}"
    else:
        prompt = query

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": RESPONSE_MODEL, "prompt": prompt,
                      "system": system_prompt or BASE_SYSTEM_PROMPT, "stream": False}
            )
            response = resp.json().get("response", "")
    except Exception as e:
        logger.error("Ollama generation failed: %s", e)
        response = "I encountered an error generating a response."

    return {
        "result": response, "response": response,
        "method": f"ollama_{intent}",
        "intent": intent, "cost": 0.0, "engine": "ollama"
    }


# ─────────────────────────────────────────────────────────────────────────────
# Internal HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _search_via_vault(query: str, vault_url: str, signed_client) -> List[Dict]:
    """Execute web search via Vault service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{vault_url}/execute"
        payload = {
            "tool": "web_search",
            "params": {"query": query, "max_results": 3},
            "session_id": "orchestrator"
        }
        if signed_client:
            resp = await signed_client.post(client, url, json=payload)
        else:
            resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            return resp.json().get("results", [])
        raise Exception(f"Vault search returned HTTP {resp.status_code}")


def _build_search_context(query: str, search_results: List[Dict]) -> str:
    """Build search context prompt."""
    if not search_results:
        return query
    parts = ["Search results:\n"]
    for i, r in enumerate(search_results[:3], 1):
        parts.append(f"[{i}] {r.get('title', 'No title')}")
        parts.append(f"    {r.get('snippet', '')[:100]}...\n")
    parts.append(f"\nQuestion: {query}\n")
    return "".join(parts)


async def _get_tasks_from_memory(memory_url: str, signed_client) -> Any:
    """Fetch tasks from memory service."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"{memory_url}/tasks"
        if signed_client:
            resp = await signed_client.get(client, url)
        else:
            resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tasks", data)
        raise Exception(f"Memory tasks returned HTTP {resp.status_code}")


async def _get_rag_context(
    query: str, user_id: str, rag_url: str, signed_client
) -> str:
    """Get relevant memory context from RAG service."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"{rag_url}/context"
        params = {"query": query, "user_id": user_id, "max_tokens": 300}
        if signed_client:
            resp = await signed_client.get(client, url, params=params)
        else:
            resp = await client.get(url, params=params)
        if resp.status_code == 200:
            return resp.json().get("context", "")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Legacy helpers kept for backward compatibility
# ─────────────────────────────────────────────────────────────────────────────

async def queue_skill_creation(query: str) -> None:
    """Queue a skill creation request by appending a task to tasks.json."""
    memory_dir = Path(os.getenv("MEMORY_DIR", "/memory"))
    tasks_path = memory_dir / "tasks.json"

    tasks = []
    if tasks_path.exists():
        try:
            tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
            if not isinstance(tasks, list):
                tasks = []
        except Exception as e:
            logger.warning("Could not read tasks.json: %s, starting fresh", e)
            tasks = []

    now = datetime.now()
    task = {
        "id": f"task_{int(now.timestamp())}",
        "type": "skill_creation",
        "query": query,
        "status": "pending",
        "created": now.isoformat()
    }
    tasks.append(task)

    try:
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text(json.dumps(tasks, indent=2), encoding="utf-8")
        logger.info("Skill creation queued for: %s", query[:50])
    except Exception as e:
        logger.error("Failed to write tasks.json: %s", e)


async def seed_classifier_examples_on_startup(
    rag_url: str, signed_client: Optional[Any] = None
):
    """Seed classifier examples collection on gateway startup."""
    try:
        logger.info("Attempting to seed classifier examples...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{rag_url}/classify/seed"
            if signed_client:
                response = await signed_client.post(client, url, json={})
            else:
                response = await client.post(url, json={})
            if response.status_code == 200:
                data = response.json()
                seeded = data.get("seeded", 0)
                if seeded > 0:
                    logger.info("Seeded %d classifier examples", seeded)
                else:
                    logger.info("Classifier examples already seeded")
            else:
                logger.warning("Failed to seed classifier examples: HTTP %d",
                               response.status_code)
    except Exception as e:
        logger.warning("Failed to seed classifier examples: %s", e)


if __name__ == "__main__":
    import asyncio

    async def test():
        result = await route_query(
            "Write a function to calculate fibonacci numbers",
            "test_user"
        )
        print(json.dumps(result, indent=2))

    asyncio.run(test())
