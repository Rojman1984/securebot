#!/usr/bin/env python3
"""
tool_request_approval.py — Request human administrator approval via the Gateway approval queue.

Usage:
    python3 tool_request_approval.py --rationale "Need Stripe API key" --needs "stripe_api_key"
    python3 tool_request_approval.py --rationale "Permission to modify /etc/hosts" \
        --needs "approval" --type permission

Blocks until the administrator resolves the request via /approvals/resolve/{id}.
Prints the resolution value to stdout on success.
Exits non-zero on timeout or error.

Timeout: 5 minutes by default. The admin should respond in the CLI dashboard.
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

POLL_INTERVAL = 5   # seconds between status polls
TIMEOUT = 300       # 5 minutes max wait


def _sign_headers(method: str, path: str) -> dict:
    """Generate HMAC-SHA256 auth headers matching common/auth.py sign_request()."""
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


def request_approval(rationale: str, needs: str, request_type: str = "credential") -> dict:
    """POST an approval request to the Gateway. Returns {"id": ..., "status": "pending"}."""
    path = "/approvals/request"
    url = f"{GATEWAY_URL}{path}"
    headers = _sign_headers("POST", path)
    headers["Content-Type"] = "application/json"
    payload = {"rationale": rationale, "needs": needs, "request_type": request_type}
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to create approval request: HTTP {resp.status_code}: {resp.text}"
        )
    return resp.json()


def poll_status(request_id: str) -> dict:
    """HMAC-signed poll of the approval status. Returns the status record."""
    path = f"/approvals/status/{request_id}"
    url = f"{GATEWAY_URL}{path}"
    headers = _sign_headers("GET", path)
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to poll approval status: HTTP {resp.status_code}: {resp.text}"
        )
    return resp.json()


def main():
    parser = argparse.ArgumentParser(
        description="Request admin approval and block until resolved."
    )
    parser.add_argument("--rationale", required=True, help="Why this approval is needed")
    parser.add_argument(
        "--needs", required=True,
        help="What is being requested (e.g. 'stripe_api_key', 'approval')"
    )
    parser.add_argument(
        "--type", default="credential",
        choices=["credential", "permission", "notification"],
        help="Request type",
    )
    parser.add_argument(
        "--timeout", type=int, default=TIMEOUT,
        help="Max seconds to wait for resolution"
    )
    args = parser.parse_args()

    # Step 1: Create the approval request
    try:
        result = request_approval(args.rationale, args.needs, args.type)
    except Exception as e:
        print(json.dumps({"error": str(e), "resolution": None}), file=sys.stderr)
        sys.exit(1)

    request_id = result["id"]
    print(
        f"[approval-pending] id={request_id} needs={args.needs} "
        f"rationale={args.rationale[:60]}",
        file=sys.stderr,
    )

    # Step 2: Poll until resolved or timed out
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        try:
            status = poll_status(request_id)
        except Exception as e:
            print(f"[approval-poll-error] {e}", file=sys.stderr)
            continue

        if status["status"] == "resolved":
            resolution = status.get("resolution") or ""
            print(resolution)   # stdout — Pi CLI reads this as the tool result
            sys.exit(0)

    print(
        json.dumps({
            "error": f"Approval request {request_id} timed out after {args.timeout}s",
            "resolution": None,
        }),
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
