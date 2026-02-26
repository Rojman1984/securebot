#!/usr/bin/env python3
"""
CodeBot Service — Isolated skill generation using the Pi CLI agent framework.

Receives sanitized skill-generation requests from the Gateway, classifies them
as bash or python using GLiClass, then invokes Pi CLI with the five custom tools
(lint_bash, lint_python, run_sandbox_test, validate_yaml, commit_skill) to
draft, lint, sandbox-test, and commit a new SKILL.md file.

All inter-service calls use HMAC-SHA256 auth (SERVICE_SECRET shared secret).
CodeBot never contacts Anthropic — Pi CLI handles code generation locally.

Author: SecureBot Project
"""

import hashlib
import hmac as hmac_lib
import json
import logging
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
SERVICE_ID = os.getenv("SERVICE_ID", "codebot")
SERVICE_SECRET = os.getenv("SERVICE_SECRET", "")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8080")
SKILLS_DIR = os.getenv("SKILLS_DIR", "/workspace/skills")
WORKSPACE = Path("/workspace")
PI_CONFIG = str(WORKSPACE / "pi_config.json")

_SKILL_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{1,48}[a-zA-Z0-9]$')

app = FastAPI(title="CodeBot Service", version="1.0.0")


# ── HMAC Auth ────────────────────────────────────────────────────────────────

def _verify_hmac(request: Request) -> bool:
    """Verify that the incoming request is signed by an allowed caller (gateway)."""
    sid = request.headers.get("X-Service-ID", "")
    ts = request.headers.get("X-Timestamp", "")
    nonce = request.headers.get("X-Nonce", "")
    sig = request.headers.get("X-Signature", "")

    if not all([sid, ts, nonce, sig]):
        raise HTTPException(status_code=401, detail="Missing HMAC auth headers")

    if sid not in ("gateway",):
        raise HTTPException(status_code=401, detail=f"Service '{sid}' not authorized")

    # Timestamp window: ±30s
    try:
        req_time = int(ts)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")
    if abs(time.time() - req_time) > 30:
        raise HTTPException(status_code=401, detail="Timestamp expired")

    if not SERVICE_SECRET:
        logger.warning("SERVICE_SECRET not set — HMAC auth bypassed")
        return True

    message = f"{sid}:{ts}:{nonce}:{request.method.upper()}:{request.url.path}"
    expected = "sha256=" + hmac_lib.new(
        SERVICE_SECRET.encode(), message.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac_lib.compare_digest(expected, sig):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    return True


async def hmac_auth(request: Request):
    _verify_hmac(request)


# ── Models ───────────────────────────────────────────────────────────────────

class SkillRequest(BaseModel):
    """Payload from Gateway requesting a new skill to be generated."""
    intent: str                          # sanitized user intent (PII already stripped)
    user_id: Optional[str] = "system"


class SkillResult(BaseModel):
    success: bool
    skill_name: Optional[str] = None
    skill_path: Optional[str] = None
    execution_mode: Optional[str] = None
    error: Optional[str] = None
    cost: float = 0.0                    # CodeBot is free — no API calls


# ── Skill classification ─────────────────────────────────────────────────────

def _classify_coding_mode(intent: str) -> str:
    """
    Invoke skill_router.py as a subprocess and return 'system_bash' or
    'python_api_or_data'.  Falls back to 'system_bash' on any error.
    """
    try:
        result = subprocess.run(
            [sys.executable, str(WORKSPACE / "skill_router.py"), intent],
            capture_output=True, text=True, timeout=30,
        )
        line = result.stdout.strip().split("\n")[0]
        label = line.split()[0] if line else "system_bash"
        if label not in ("system_bash", "python_api_or_data"):
            label = "system_bash"
        logger.info("skill_router: %s for intent: %s", label, intent[:60])
        return label
    except Exception as e:
        logger.warning("skill_router failed: %s — defaulting to system_bash", e)
        return "system_bash"


# ── Pi CLI invocation ─────────────────────────────────────────────────────────

def _build_pi_task(intent: str, execution_mode: str) -> str:
    """Build the Pi CLI task description for skill generation."""
    mode_label = "bash" if execution_mode == "system_bash" else "python"
    return (
        f"Generate a SecureBot SKILL.md for the following user intent: \"{intent}\"\n\n"
        f"Classification result: execution_mode={mode_label}\n\n"
        f"Follow the workflow:\n"
        f"1. Draft SKILL.md using execution_mode: {mode_label}\n"
        f"2. {'Call lint_bash on the script block' if mode_label == 'bash' else 'Call lint_python on the script block'}\n"
        f"3. Call run_sandbox_test with the script and mode '{mode_label}'\n"
        f"4. Call validate_yaml on the complete SKILL.md\n"
        f"5. Call commit_skill with the skill name and SKILL.md path\n"
        f"Return only the committed skill name."
    )


def _invoke_pi_cli(task: str, timeout: int = 120) -> dict:
    """
    Run Pi CLI non-interactively with the given task string.
    Returns {"success": bool, "output": str, "skill_name": str|None}.
    """
    try:
        result = subprocess.run(
            ["pi", "--config", PI_CONFIG, "--task", task],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(WORKSPACE),
            env={**os.environ, "SKILLS_DIR": SKILLS_DIR, "GATEWAY_URL": GATEWAY_URL},
        )
        output = result.stdout.strip()
        err = result.stderr.strip()

        if result.returncode != 0:
            logger.error("Pi CLI exited %d: %s", result.returncode, err[:200])
            return {"success": False, "output": err or output, "skill_name": None}

        # Extract skill name from the output — Pi is instructed to print only it
        skill_name = _extract_skill_name_from_output(output)
        logger.info("Pi CLI completed. skill_name=%s", skill_name)
        return {"success": True, "output": output, "skill_name": skill_name}

    except subprocess.TimeoutExpired:
        logger.error("Pi CLI timed out after %ds", timeout)
        return {"success": False, "output": "Pi CLI timed out", "skill_name": None}
    except FileNotFoundError:
        logger.error("Pi CLI not found — is pi-coding-agent installed?")
        return {"success": False, "output": "pi command not found", "skill_name": None}
    except Exception as e:
        logger.error("Pi CLI error: %s", e)
        return {"success": False, "output": str(e), "skill_name": None}


def _extract_skill_name_from_output(output: str) -> Optional[str]:
    """
    Parse Pi CLI output for a valid committed skill name.
    Pi is prompted to output just the skill name on its last line.
    Also handles "committed: /workspace/skills/<name>/SKILL.md" format
    from tool_commit_skill.sh.
    """
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    if not lines:
        return None

    # Look for "committed: ..." from tool_commit_skill.sh
    for line in reversed(lines):
        if line.startswith("committed:"):
            path_part = line.split("committed:")[-1].strip()
            # Extract skill name from path: /workspace/skills/<name>/SKILL.md
            parts = Path(path_part).parts
            skills_idx = next((i for i, p in enumerate(parts) if p == "skills"), None)
            if skills_idx is not None and skills_idx + 1 < len(parts):
                candidate = parts[skills_idx + 1]
                if _SKILL_NAME_RE.match(candidate):
                    return candidate

    # Fall back: last line that looks like a valid skill name
    for line in reversed(lines):
        candidate = line.strip().split()[-1] if line.strip() else ""
        if _SKILL_NAME_RE.match(candidate):
            return candidate

    return None


# ── FastAPI endpoints ────────────────────────────────────────────────────────

@app.post("/generate-skill", response_model=SkillResult)
async def generate_skill(
    payload: SkillRequest,
    _auth=Depends(hmac_auth),
) -> SkillResult:
    """
    Receive a sanitized skill-generation request from the Gateway.
    Classify, invoke Pi CLI, lint, sandbox-test, validate, and commit the skill.
    Returns cost=0.0 — CodeBot is entirely free (no Anthropic API calls).
    """
    logger.info("Skill generation request: %s", payload.intent[:80])

    # 1. Classify bash vs python
    execution_mode = _classify_coding_mode(payload.intent)
    mode_label = "bash" if execution_mode == "system_bash" else "python"

    # 2. Build and run Pi CLI task
    task = _build_pi_task(payload.intent, execution_mode)
    pi_result = _invoke_pi_cli(task, timeout=120)

    if not pi_result["success"] or not pi_result.get("skill_name"):
        logger.warning("Pi CLI failed to generate skill: %s", pi_result["output"][:200])
        return SkillResult(
            success=False,
            error=pi_result.get("output", "Pi CLI returned no skill"),
            cost=0.0,
        )

    skill_name = pi_result["skill_name"]
    skill_path = str(Path(SKILLS_DIR) / skill_name / "SKILL.md")

    # Verify the skill file was actually written to disk
    if not Path(skill_path).exists():
        logger.error("Pi CLI claimed success but skill file missing: %s", skill_path)
        return SkillResult(
            success=False,
            error=f"Skill file not found after commit: {skill_path}",
            cost=0.0,
        )

    logger.info("Skill committed: %s at %s", skill_name, skill_path)
    return SkillResult(
        success=True,
        skill_name=skill_name,
        skill_path=skill_path,
        execution_mode=mode_label,
        cost=0.0,
    )


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check — verifies Pi CLI is installed."""
    pi_ok = False
    pi_version = "unknown"
    try:
        result = subprocess.run(
            ["pi", "--version"], capture_output=True, text=True, timeout=5
        )
        pi_ok = result.returncode == 0
        pi_version = result.stdout.strip() or result.stderr.strip()
    except Exception:
        pass

    return {
        "status": "healthy" if pi_ok else "degraded",
        "version": "1.0.0",
        "dependencies": {
            "pi_cli": "healthy" if pi_ok else "unavailable",
            "pi_cli_version": pi_version,
        },
        "skills_dir": SKILLS_DIR,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500, log_level="info")
