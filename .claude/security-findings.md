# Security Findings — Huntarr

Review date: 2026-05-17

## Summary

| # | Severity | File | Line | Issue | Status |
|---|----------|------|------|-------|--------|
| 1 | HIGH | src/primary/web_server.py | 120 | Hardcoded fallback Flask secret key | ✅ Fixed 2026-05-17 |
| 2 | HIGH | src/primary/auth.py | 343–355 | X-Forwarded-For spoofing bypasses local auth | ⏳ Pending |
| 3 | MEDIUM | src/primary/web_server.py | 828–856 | Unauthenticated stats-reset public endpoint | ⏳ Pending |
| 4 | MEDIUM | src/primary/auth.py | 75–80 | Weak SHA-256 password hashing | ⏳ Pending |

---

## Finding 1 — Hardcoded Fallback Flask Secret Key ✅ FIXED 2026-05-17
**Severity**: High | **File**: `src/primary/web_server.py:120`

```python
# Before (vulnerable)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_sessions')
```

Flask uses the secret key to sign session cookies with HMAC. The fallback `'dev_key_for_sessions'` is committed to source, so anyone who reads the code can forge valid session cookies and bypass authentication in deployments where `SECRET_KEY` is not explicitly set.

**Resolution**: If `SECRET_KEY` env var is set it is used directly (no behaviour change for existing deployments). Otherwise a 32-byte random hex key is generated once at startup, persisted to `/config/secret_key` with mode `0o600`, and reloaded on every subsequent start. The hardcoded fallback has been removed.

---

## Finding 2 — X-Forwarded-For Spoofing Bypasses Local Network Auth
**Severity**: High | **File**: `src/primary/auth.py:343–355`

When "Local Bypass" mode is enabled, `authenticate_request()` reads the attacker-controlled `X-Forwarded-For` header and grants unauthenticated access if the first IP looks local. Any external client can send `X-Forwarded-For: 127.0.0.1` to bypass authentication.

**Fix**: Remove the `X-Forwarded-For` block entirely. Check only `request.remote_addr` (OS-level TCP peer, cannot be spoofed) for the local-network bypass decision.

---

## Finding 3 — Unauthenticated Stats-Reset Public Endpoint
**Severity**: Medium | **File**: `src/primary/web_server.py:828–856`

`/api/stats/reset_public` has no authentication check (labelled "public endpoint without auth" in a comment). Anyone who can reach the server can wipe all media statistics.

**Fix**: Delete the route. The authenticated `/api/stats/reset` in `src/primary/routes/common.py` already covers this.

---

## Finding 4 — Weak SHA-256 Password Hashing
**Severity**: Medium | **File**: `src/primary/auth.py:75–80`

Passwords are hashed with SHA-256 + salt. SHA-256 is designed for speed; GPUs can compute billions of hashes/second, making the credential file trivially brute-forceable if stolen. The file is also world-readable at mode `0o644`.

**Fix**: Replace with `bcrypt` (add to `requirements.txt`):

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(stored: str, provided: str) -> bool:
    return bcrypt.checkpw(provided.encode(), stored.encode())
```

Also tighten `credentials.json` permissions to `0o600`.
