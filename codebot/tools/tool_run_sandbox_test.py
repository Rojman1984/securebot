#!/usr/bin/env python3
"""
tool_run_sandbox_test.py — Send a generated script to the Gateway sandbox.

Usage:
    python3 tool_run_sandbox_test.py --code <script_text> --mode bash
    python3 tool_run_sandbox_test.py --code <script_text> --mode python
    # OR pass code via stdin:
    echo "#!/bin/bash\necho hello" | python3 tool_run_sandbox_test.py --mode bash

Returns a JSON object: {"stdout": "...", "stderr": "...", "exit_code": 0}
Exits with the script's exit_code so Pi CLI can detect failures.
"""

import argparse
import hashlib
import hmac as hmac_lib
import json
import os
import secrets
import sys
import time

import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8080")
SERVICE_ID = os.getenv("SERVICE_ID", "codebot")
SERVICE_SECRET = os.getenv("SERVICE_SECRET", "")


def _sign_headers(method: str, path: str) -> dict:
    """Generate HMAC-SHA256 auth headers for the request."""
    if not SERVICE_SECRET:
        return {}
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(8)
    message = f"{SERVICE_ID}:{timestamp}:{nonce}:{method.upper()}:{path}"
    signature = "sha256=" + hmac_lib.new(
        SERVICE_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "X-Service-ID": SERVICE_ID,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }


def run_sandbox_test(code: str, execution_mode: str) -> dict:
    """POST to /internal/test-skill and return the result dict."""
    path = "/internal/test-skill"
    url = f"{GATEWAY_URL}{path}"
    headers = _sign_headers("POST", path)
    headers["Content-Type"] = "application/json"

    payload = {"code": code, "execution_mode": execution_mode}

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        return {
            "stdout": "",
            "stderr": f"Gateway returned HTTP {resp.status_code}: {resp.text}",
            "exit_code": 1,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Connection to gateway failed: {e}",
            "exit_code": 1,
        }


def main():
    parser = argparse.ArgumentParser(description="Run a script in the Gateway sandbox")
    parser.add_argument("--code", help="Script source code (or omit to read from stdin)")
    parser.add_argument("--mode", default="bash", choices=["bash", "python"],
                        help="execution_mode: bash or python")
    args = parser.parse_args()

    code = args.code if args.code else sys.stdin.read()
    if not code.strip():
        print(json.dumps({"stdout": "", "stderr": "No code provided", "exit_code": 1}))
        sys.exit(1)

    result = run_sandbox_test(code, args.mode)
    print(json.dumps(result, indent=2))
    sys.exit(result.get("exit_code", 0))


if __name__ == "__main__":
    main()
