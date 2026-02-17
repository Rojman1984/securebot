"""
HMAC-based inter-service authentication for SecureBot.

Security model:
- HMAC-SHA256 signed requests between services
- Shared secret via environment variables
- 30-second timestamp window (replay prevention)
- Nonce tracking (60-second window)
- Service identity verification
"""

import hmac
import hashlib
import time
import os
import secrets
import logging
from typing import List
from fastapi import Request, HTTPException, Depends
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Configuration
SERVICE_SECRET = os.getenv("SERVICE_SECRET", "")
SERVICE_ID = os.getenv("SERVICE_ID", "")
TIMESTAMP_WINDOW = 30  # seconds
NONCE_CACHE = {}  # {nonce: timestamp}
NONCE_EXPIRY = 60  # seconds


def sign_request(method: str, path: str, service_id: str = None, secret: str = None) -> dict:
    """
    Generate auth headers for outgoing request.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: URL path
        service_id: Override SERVICE_ID (optional)
        secret: Override SERVICE_SECRET (optional)

    Returns:
        dict: Headers to include in request
    """
    sid = service_id or SERVICE_ID
    sec = secret or SERVICE_SECRET

    if not sid or not sec:
        raise ValueError("SERVICE_ID and SERVICE_SECRET must be set")

    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(8)
    message = f"{sid}:{timestamp}:{nonce}:{method.upper()}:{path}"
    signature = hmac.new(
        sec.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return {
        "X-Service-ID": sid,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": f"sha256={signature}"
    }


def verify_request(
    service_id: str,
    timestamp: str,
    nonce: str,
    signature: str,
    method: str,
    path: str,
    allowed_callers: List[str]
) -> bool:
    """
    Verify incoming request signature.

    Validates:
    1. Service is in allowed_callers list
    2. Timestamp is within TIMESTAMP_WINDOW
    3. Nonce has not been used before (replay prevention)
    4. Signature matches expected HMAC

    Args:
        service_id: Calling service identifier
        timestamp: Unix timestamp string
        nonce: Random nonce for replay prevention
        signature: HMAC signature to verify
        method: HTTP method
        path: URL path
        allowed_callers: List of service IDs allowed to call this endpoint

    Returns:
        bool: True if valid

    Raises:
        HTTPException: 401 if validation fails
    """

    # 1. Check service is allowed
    if service_id not in allowed_callers:
        logger.warning(
            f"AUTH REJECTED: Service '{service_id}' not in allowed_callers "
            f"for {method} {path}. Allowed: {allowed_callers}"
        )
        raise HTTPException(
            status_code=401,
            detail="Service not authorized"
        )

    # 2. Check timestamp window
    try:
        request_time = int(timestamp)
    except ValueError:
        logger.warning(f"AUTH REJECTED: Invalid timestamp format from {service_id}")
        raise HTTPException(
            status_code=401,
            detail="Invalid timestamp format"
        )

    current_time = time.time()
    time_diff = abs(current_time - request_time)

    if time_diff > TIMESTAMP_WINDOW:
        logger.warning(
            f"AUTH REJECTED: Timestamp expired from {service_id}. "
            f"Diff: {time_diff}s (max {TIMESTAMP_WINDOW}s)"
        )
        raise HTTPException(
            status_code=401,
            detail="Request timestamp expired"
        )

    # 3. Check nonce not reused (replay attack prevention)
    _cleanup_nonces()
    if nonce in NONCE_CACHE:
        logger.warning(
            f"AUTH REJECTED: Nonce reuse detected from {service_id}. "
            f"Possible replay attack for {method} {path}"
        )
        raise HTTPException(
            status_code=401,
            detail="Nonce already used"
        )
    NONCE_CACHE[nonce] = current_time

    # 4. Verify signature using constant-time comparison
    message = f"{service_id}:{timestamp}:{nonce}:{method.upper()}:{path}"
    expected = "sha256=" + hmac.new(
        SERVICE_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    # Use hmac.compare_digest to prevent timing attacks
    if not hmac.compare_digest(expected, signature):
        logger.warning(
            f"AUTH REJECTED: Invalid signature from {service_id} "
            f"for {method} {path}"
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid signature"
        )

    logger.info(f"AUTH SUCCESS: {service_id} → {method} {path}")
    return True


def _cleanup_nonces():
    """Remove expired nonces from cache to prevent memory leak."""
    cutoff = time.time() - NONCE_EXPIRY
    expired = [n for n, t in NONCE_CACHE.items() if t < cutoff]
    for n in expired:
        del NONCE_CACHE[n]


async def verify_service_request(
    request: Request,
    allowed_callers: List[str]
):
    """
    FastAPI dependency to verify incoming request.

    Usage:
        @app.post("/endpoint")
        async def endpoint(
            request: Request,
            _auth = Depends(lambda r: verify_service_request(r, ["gateway", "rag-service"]))
        ):
            ...

    Args:
        request: FastAPI Request object
        allowed_callers: List of service IDs allowed to call this endpoint

    Raises:
        HTTPException: 401 if auth fails
    """
    service_id = request.headers.get("X-Service-ID")
    timestamp = request.headers.get("X-Timestamp")
    nonce = request.headers.get("X-Nonce")
    signature = request.headers.get("X-Signature")

    if not all([service_id, timestamp, nonce, signature]):
        logger.warning(
            f"AUTH REJECTED: Missing auth headers for {request.method} {request.url.path}. "
            f"Headers: service_id={bool(service_id)}, timestamp={bool(timestamp)}, "
            f"nonce={bool(nonce)}, signature={bool(signature)}"
        )
        raise HTTPException(
            status_code=401,
            detail="Missing authentication headers"
        )

    verify_request(
        service_id, timestamp, nonce, signature,
        request.method, request.url.path,
        allowed_callers
    )


class SignedClient:
    """
    HTTP client wrapper that automatically signs all requests.

    Usage:
        signed = SignedClient(
            service_id=os.getenv("SERVICE_ID", "gateway"),
            secret=os.getenv("SERVICE_SECRET", "")
        )

        async with httpx.AsyncClient() as client:
            response = await signed.post(client, "http://vault:8200/search", json={...})
            response = await signed.get(client, "http://memory:8300/retrieve")
    """

    def __init__(self, service_id: str, secret: str):
        """
        Initialize signed client.

        Args:
            service_id: This service's identifier
            secret: Shared HMAC secret
        """
        self.service_id = service_id
        self.secret = secret

        if not service_id or not secret:
            raise ValueError("service_id and secret are required")

    def _get_headers(self, method: str, path: str) -> dict:
        """Generate authentication headers for a request."""
        return sign_request(method, path, self.service_id, self.secret)

    async def post(self, client, url: str, **kwargs):
        """
        Send signed POST request.

        Args:
            client: httpx.AsyncClient instance
            url: Full URL to request
            **kwargs: Additional arguments to pass to client.post()

        Returns:
            httpx.Response
        """
        path = urlparse(url).path
        headers = kwargs.get("headers", {})
        headers.update(self._get_headers("POST", path))
        kwargs["headers"] = headers
        return await client.post(url, **kwargs)

    async def get(self, client, url: str, **kwargs):
        """
        Send signed GET request.

        Args:
            client: httpx.AsyncClient instance
            url: Full URL to request
            **kwargs: Additional arguments to pass to client.get()

        Returns:
            httpx.Response
        """
        path = urlparse(url).path
        headers = kwargs.get("headers", {})
        headers.update(self._get_headers("GET", path))
        kwargs["headers"] = headers
        return await client.get(url, **kwargs)

    async def put(self, client, url: str, **kwargs):
        """Send signed PUT request."""
        path = urlparse(url).path
        headers = kwargs.get("headers", {})
        headers.update(self._get_headers("PUT", path))
        kwargs["headers"] = headers
        return await client.put(url, **kwargs)

    async def delete(self, client, url: str, **kwargs):
        """Send signed DELETE request."""
        path = urlparse(url).path
        headers = kwargs.get("headers", {})
        headers.update(self._get_headers("DELETE", path))
        kwargs["headers"] = headers
        return await client.delete(url, **kwargs)


def create_auth_dependency(allowed_callers: List[str]):
    """
    Create a reusable FastAPI dependency for auth.

    Usage:
        ALLOWED_CALLERS = ["gateway", "rag-service"]
        auth_dep = create_auth_dependency(ALLOWED_CALLERS)

        @app.post("/endpoint")
        async def endpoint(request: Request, _auth = Depends(auth_dep)):
            ...
    """
    async def dependency(request: Request):
        await verify_service_request(request, allowed_callers)
    return dependency
