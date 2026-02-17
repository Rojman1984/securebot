# SecureBot Security Model

## Overview

SecureBot implements defense-in-depth security with multiple layers:

1. **Inter-Service Authentication** - HMAC-SHA256 signed requests
2. **Secret Isolation** - Vault service manages all API keys
3. **Network Isolation** - Docker network isolation
4. **Access Control** - Service trust matrix

---

## Inter-Service Authentication

### Security Model

All inter-service communication uses **HMAC-SHA256 signatures** to prevent:

- **Unauthorized access** - Only services with the shared secret can communicate
- **Replay attacks** - 30-second timestamp window + nonce tracking
- **Man-in-the-middle** - Signature tampering is detected
- **Service impersonation** - Each request includes service identity

### Authentication Flow

Every inter-service request must include these headers:

```http
X-Service-ID: gateway
X-Timestamp: 1708167234
X-Nonce: a3f9b2c1
X-Signature: sha256=abc123...
```

**Signature Calculation:**

```python
message = f"{service_id}:{timestamp}:{nonce}:{method}:{path}"
signature = HMAC-SHA256(shared_secret, message)
```

### Validation Rules

Requests are rejected (HTTP 401) if:

1. ❌ Signature doesn't match expected HMAC
2. ❌ Timestamp is outside 30-second window (replay prevention)
3. ❌ Service ID not in allowed_callers list
4. ❌ Nonce has been seen in last 60 seconds (replay prevention)
5. ❌ Any required auth header is missing

All rejections are logged with:
- Timestamp
- Service ID attempting access
- Endpoint requested
- Rejection reason

---

## Service Trust Matrix

### Who Can Call Whom

| Service | Can Call | Cannot Call |
|---------|----------|-------------|
| **gateway** | vault, memory-service, rag-service | (none - gateway is orchestrator) |
| **vault** | (none - receives only) | All services (vault doesn't make outbound calls) |
| **memory-service** | rag-service | vault, gateway |
| **rag-service** | memory-service | vault, gateway |
| **heartbeat** | gateway, memory-service, rag-service | vault |
| **EXTERNAL** | (none) | ALL - external requests are rejected |

### Service Configurations

**Vault** (`ALLOWED_CALLERS`):
```bash
gateway,rag-service,memory-service,heartbeat
```

**Gateway** (accepts external, signs outgoing):
```bash
# No ALLOWED_CALLERS - gateway is the entry point
# Signs all outgoing requests to other services
```

**Memory Service** (`ALLOWED_CALLERS`):
```bash
gateway,rag-service,heartbeat
```

**RAG Service** (`ALLOWED_CALLERS`):
```bash
gateway,memory-service,heartbeat
```

---

## Setup

### 1. Generate Shared Secret

Run the setup script:

```bash
bash services/scripts/setup_auth.sh
```

Or manually:

```bash
# Generate 256-bit secret
python3 -c "import secrets; print(secrets.token_hex(32))"

# Add to .env
echo "SERVICE_SECRET=<your-generated-secret>" >> .env
```

### 2. Environment Variables

All services automatically receive these variables via docker-compose:

```yaml
environment:
  - SERVICE_SECRET=${SERVICE_SECRET}        # Shared HMAC secret
  - SERVICE_ID=vault                        # This service's identity
  - ALLOWED_CALLERS=gateway,rag-service     # Who can call this service
```

### 3. Start Services

```bash
docker compose up -d
```

Authentication is enabled automatically when `SERVICE_SECRET` is set.

---

## Implementation Details

### Common Auth Module

Located in `common/auth.py`:

**Core Functions:**
- `sign_request()` - Generate auth headers for outgoing requests
- `verify_request()` - Validate incoming request signatures
- `verify_service_request()` - FastAPI dependency for auth
- `SignedClient` - HTTP client wrapper with automatic signing

**Usage in Services:**

```python
from common.auth import verify_service_request, SignedClient

# Protect endpoints (all services except gateway)
ALLOWED_CALLERS = os.getenv("ALLOWED_CALLERS", "").split(",")

@app.post("/endpoint")
async def endpoint(
    request: Request,
    _auth = Depends(lambda r: verify_service_request(r, ALLOWED_CALLERS))
):
    # ... endpoint logic
    pass

# Sign outgoing requests (gateway only)
signed_client = SignedClient(
    service_id=os.getenv("SERVICE_ID"),
    secret=os.getenv("SERVICE_SECRET")
)

async with httpx.AsyncClient() as client:
    response = await signed_client.post(
        client,
        "http://vault:8200/execute",
        json={...}
    )
```

### Health Endpoints

**Health endpoints (`/health`) remain PUBLIC** for Docker healthchecks:

```python
@app.get("/health")
async def health():
    # No auth required - Docker needs this
    return {"status": "healthy"}
```

### Nonce Management

Nonces are cached for 60 seconds to prevent replay attacks:

```python
NONCE_CACHE = {}  # {nonce: timestamp}

# Cleanup expired nonces automatically
def _cleanup_nonces():
    cutoff = time.time() - 60
    expired = [n for n, t in NONCE_CACHE.items() if t < cutoff]
    for n in expired:
        del NONCE_CACHE[n]
```

---

## Security Properties

### ✅ What This Protects Against

1. **Unauthorized Access**
   - External attackers cannot call internal services
   - Services cannot exceed their trust matrix permissions

2. **Replay Attacks**
   - Timestamp window (30 seconds) prevents old requests
   - Nonce tracking prevents duplicate requests

3. **Man-in-the-Middle**
   - Signature tampering is immediately detected
   - HMAC ensures message integrity

4. **Service Impersonation**
   - Only services with the shared secret can sign requests
   - Service identity is cryptographically verified

5. **Credential Theft**
   - Shared secret never appears in logs
   - Secrets stored in `.env` (gitignored)

### ⚠️ Limitations

This implementation does **NOT** protect against:

1. **Compromised Container**
   - If a container is owned, the secret is exposed
   - Mitigation: Use mTLS (see Advanced Security below)

2. **Docker Host Compromise**
   - Host-level access bypasses all container security
   - Mitigation: Harden Docker host, use SELinux/AppArmor

3. **Timing Attacks**
   - Uses `hmac.compare_digest()` for constant-time comparison
   - Still vulnerable if attacker can measure network timing

4. **Cryptanalysis**
   - HMAC-SHA256 is secure but not quantum-resistant
   - Mitigation: Use 256-bit keys (already implemented)

---

## Advanced Security (Optional)

### Mutual TLS (mTLS)

For production deployments requiring higher security:

1. Generate certificates for each service
2. Configure Docker networks with TLS
3. Enforce client certificate validation
4. Rotate certificates regularly

See `docs/MTLS.md` (coming soon) for implementation guide.

### Secret Rotation

To rotate the shared secret:

```bash
# 1. Generate new secret
python3 -c "import secrets; print(secrets.token_hex(32))"

# 2. Update .env
vim .env  # Update SERVICE_SECRET

# 3. Restart services
docker compose restart
```

**Note:** All services must be restarted simultaneously to avoid auth failures.

### Monitoring

All authentication failures are logged:

```bash
# View auth failures
docker compose logs | grep "AUTH REJECTED"

# View successful authentications
docker compose logs | grep "AUTH SUCCESS"
```

Example log entry:

```
2026-02-17 12:34:56 - AUTH REJECTED: Service 'external' not in allowed_callers for POST /execute. Allowed: ['gateway', 'rag-service']
```

---

## Troubleshooting

### "Missing authentication headers"

**Cause:** Request missing `X-Service-ID`, `X-Timestamp`, `X-Nonce`, or `X-Signature`

**Fix:** Ensure outgoing requests use `SignedClient` wrapper

### "Request timestamp expired"

**Cause:** Clock skew between containers > 30 seconds

**Fix:**
```bash
# Sync Docker host clock
sudo ntpdate -s time.nist.gov

# Restart containers
docker compose restart
```

### "Invalid signature"

**Cause:** `SERVICE_SECRET` mismatch between services

**Fix:** Ensure all services have the same `SERVICE_SECRET` in `.env`

### "Service not authorized"

**Cause:** Service ID not in `ALLOWED_CALLERS` list

**Fix:** Update `ALLOWED_CALLERS` in `docker-compose.yml` for target service

---

## References

- [HMAC-SHA256 Specification (RFC 2104)](https://www.rfc-editor.org/rfc/rfc2104)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)

---

## Contact

For security vulnerabilities, please report to: [your-security-email@example.com]

Do **NOT** create public GitHub issues for security vulnerabilities.
