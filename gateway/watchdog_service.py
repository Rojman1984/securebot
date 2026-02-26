#!/usr/bin/env python3
"""
ReAct Watchdog Service — monitors SecureBot's scheduled systemd jobs.

Runs as a daemon background thread within the gateway process.

Loop behavior:
  1. Poll systemctl for timer/service status via sandboxed subprocess.
  2. If a unit is in a failed state, grab recent journal logs.
  3. Format a ReAct prompt (Thought/Action) and send to llama3.2:3b (LOCAL ONLY).
  4. Write job health + latest diagnosis to /memory/jobs_status.json.

STRICT CONSTRAINT: This module NEVER sends system logs to any cloud API.
Only llama3.2:3b (local Ollama) is queried for diagnosis.

Author: SecureBot Project
"""

import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

MEMORY_DIR = os.getenv("MEMORY_DIR", "/memory")
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
WATCHDOG_MODEL = "llama3.2:3b"  # local-only — this must NEVER change to a cloud model
POLL_INTERVAL = int(os.getenv("WATCHDOG_POLL_INTERVAL", "60"))
JOBS_STATUS_FILE = Path(MEMORY_DIR) / "jobs_status.json"


# ── Sandboxed subprocess helpers ──────────────────────────────────────────────

def _run_sandboxed(cmd: List[str], timeout: int = 10) -> tuple:
    """
    Execute a command as securebot-scripts via sudo (sandboxed execution model).
    Returns (stdout, stderr, returncode).
    """
    full_cmd = ["sudo", "-u", "securebot-scripts"] + cmd
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "command timed out", 1
    except Exception as e:
        return "", str(e), 1


def _list_timers() -> List[Dict[str, str]]:
    """
    Run 'systemctl list-timers --all --no-pager --plain' via sandboxed subprocess.
    Returns list of dicts with timer fields; empty list if systemctl is unavailable.
    """
    stdout, stderr, rc = _run_sandboxed(
        ["systemctl", "list-timers", "--all", "--no-pager", "--plain"],
        timeout=10,
    )
    if rc != 0:
        logger.debug("systemctl list-timers failed (rc=%d): %s", rc, stderr[:200])
        return []

    timers = []
    lines = stdout.strip().splitlines()
    # Header line format: NEXT LEFT LAST PASSED UNIT ACTIVATES
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 5 and not line.startswith("NEXT"):
            timers.append({
                "next": parts[0],
                "left": parts[1],
                "last": parts[2] if len(parts) > 2 else "n/a",
                "passed": parts[3] if len(parts) > 3 else "n/a",
                "unit": parts[4],
                "activates": parts[5] if len(parts) > 5 else "",
            })
    return timers


def _get_unit_status(unit: str) -> Dict[str, Any]:
    """
    Run 'systemctl status <unit> --no-pager' via sandboxed subprocess.
    Returns {"active": bool, "failed": bool, "raw": str}.
    """
    stdout, stderr, rc = _run_sandboxed(
        ["systemctl", "status", unit, "--no-pager", "--lines=0"],
        timeout=10,
    )
    raw = (stdout + stderr).strip()
    active = "active (running)" in raw or "active (exited)" in raw
    # rc=3 means inactive or failed per systemctl exit codes
    failed = "failed" in raw or rc == 3
    return {"active": active, "failed": failed, "raw": raw[:500]}


def _get_unit_logs(unit: str, n_lines: int = 50) -> str:
    """
    Grab the last n_lines of journal output for a unit via sandboxed subprocess.
    Returns log string or empty string on failure.
    """
    stdout, stderr, rc = _run_sandboxed(
        ["journalctl", "-u", unit, "--no-pager", f"-n{n_lines}", "--output=short"],
        timeout=15,
    )
    return (stdout or stderr).strip()


# ── ReAct diagnosis via local Ollama ─────────────────────────────────────────

def _diagnose_failure(unit: str, logs: str) -> str:
    """
    Send error logs to llama3.2:3b (LOCAL ONLY — NEVER to cloud API) with a
    ReAct-structured prompt. Returns the model's structured diagnosis.
    """
    prompt = (
        f"A SecureBot systemd unit has entered a failed state.\n"
        f"Unit: {unit}\n\n"
        f"Recent logs (last 50 lines):\n{logs[:2000]}\n\n"
        f"Analyze this failure and respond using ONLY this exact format:\n\n"
        f"Thought: <Why did this fail? What is the root cause? 2-3 sentences.>\n"
        f"Action: <What specific corrective steps should be taken? 2-3 sentences.>\n\n"
        f"Do not add any other text outside of Thought and Action."
    )
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": WATCHDOG_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 350},
                },
            )
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
            logger.warning("Watchdog Ollama returned HTTP %d", resp.status_code)
    except Exception as e:
        logger.error("Watchdog Ollama diagnosis failed: %s", e)
    return "Diagnosis unavailable (Ollama unreachable)."


# ── Status persistence ────────────────────────────────────────────────────────

def _load_jobs_status() -> Dict[str, Any]:
    try:
        if JOBS_STATUS_FILE.exists():
            return json.loads(JOBS_STATUS_FILE.read_text())
    except Exception as e:
        logger.warning("Could not load jobs_status.json: %s", e)
    return {"jobs": {}, "updated": None}


def _save_jobs_status(data: Dict[str, Any]) -> None:
    try:
        JOBS_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        JOBS_STATUS_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.error("Failed to write jobs_status.json: %s", e)


# ── Main watchdog cycle ───────────────────────────────────────────────────────

def _run_one_cycle() -> None:
    """Execute one monitoring cycle: list timers, check status, diagnose failures."""
    now = datetime.now().isoformat()
    jobs_data = _load_jobs_status()
    jobs = jobs_data.setdefault("jobs", {})

    timers = _list_timers()

    if not timers:
        # systemctl unavailable inside Docker without /run/systemd socket mount
        logger.debug(
            "Watchdog: no timers found — systemctl may be unavailable in this environment. "
            "Mount /run/systemd/private and /var/run/dbus/system_bus_socket for host access."
        )
        jobs_data["updated"] = now
        jobs_data["watchdog_note"] = (
            "systemctl returned no data. "
            "Ensure /run/systemd/private is mounted to enable host systemd access."
        )
        _save_jobs_status(jobs_data)
        return

    failed_count = 0
    for timer in timers:
        unit = timer.get("unit", "").strip()
        if not unit:
            continue

        status = _get_unit_status(unit)
        job_entry: Dict[str, Any] = {
            "unit": unit,
            "last_check": now,
            "active": status["active"],
            "failed": status["failed"],
            "status_raw": status["raw"],
        }

        if status["failed"]:
            failed_count += 1
            logger.warning("Watchdog: FAILED unit detected: %s", unit)
            logs = _get_unit_logs(unit)
            diagnosis = _diagnose_failure(unit, logs) if logs else "No logs available."
            job_entry["diagnosis"] = {
                "timestamp": now,
                "logs_tail": logs[-1000:] if logs else "",
                "react_diagnosis": diagnosis,
            }
            logger.info("Watchdog diagnosis for %s:\n%s", unit, diagnosis[:200])
        else:
            # Preserve prior diagnosis (unit may have recovered — keep history)
            prior = jobs.get(unit, {})
            job_entry["diagnosis"] = prior.get("diagnosis")

        jobs[unit] = job_entry

    jobs_data["updated"] = now
    jobs_data.pop("watchdog_note", None)  # clear stale note if timers are now visible
    _save_jobs_status(jobs_data)
    logger.debug(
        "Watchdog cycle complete: %d timers checked, %d failed", len(timers), failed_count
    )


def _watchdog_loop() -> None:
    """Main polling loop. Runs in a daemon thread indefinitely."""
    logger.info(
        "ReAct Watchdog loop started (interval=%ds, diagnosis_model=%s)",
        POLL_INTERVAL, WATCHDOG_MODEL,
    )
    while True:
        try:
            _run_one_cycle()
        except Exception as e:
            logger.error("Watchdog cycle error: %s", e)
        time.sleep(POLL_INTERVAL)


# ── Public API ────────────────────────────────────────────────────────────────

def start_watchdog() -> threading.Thread:
    """
    Start the ReAct Watchdog in a daemon background thread.
    Call from gateway_service.py startup_event().
    """
    thread = threading.Thread(target=_watchdog_loop, name="watchdog", daemon=True)
    thread.start()
    logger.info("ReAct Watchdog daemon thread started")
    return thread
