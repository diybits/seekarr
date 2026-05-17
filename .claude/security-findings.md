# Security Findings — Seekarr

Review date: 2026-05-17

## Summary

| # | Severity | File | Line | Issue | Status |
|---|----------|------|------|-------|--------|
| 1 | HIGH | src/primary/web_server.py | 120 | Hardcoded fallback Flask secret key | ✅ Fixed 2026-05-17 |
| 2 | HIGH | src/primary/auth.py | 343–355 | X-Forwarded-For spoofing bypasses local auth | ✅ Fixed 2026-05-17 |
| 3 | MEDIUM | src/primary/web_server.py | 828–856 | Unauthenticated stats-reset public endpoint | ✅ Fixed 2026-05-17 |
| 4 | MEDIUM | src/primary/auth.py | 75–80 | Weak SHA-256 password hashing | ✅ Fixed 2026-05-17 |

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

## Finding 2 — X-Forwarded-For Spoofing Bypasses Local Network Auth ✅ FIXED 2026-05-17
**Severity**: High | **File**: `src/primary/auth.py:343–355`

When "Local Bypass" mode is enabled, `authenticate_request()` read the attacker-controlled `X-Forwarded-For` header and granted unauthenticated access if the first IP looked local. Any external client could send `X-Forwarded-For: 127.0.0.1` to bypass authentication.

**Resolution**: Removed the entire `X-Forwarded-For` block (lines 342–355). The local-bypass decision now checks only `request.remote_addr`, the OS-level TCP peer address which cannot be forged by a remote client.

---

## Finding 3 — Unauthenticated Stats-Reset Public Endpoint ✅ FIXED 2026-05-17
**Severity**: Medium | **File**: `src/primary/web_server.py:828–856`

`/api/stats/reset_public` had no authentication check (labelled "public endpoint without auth" in a comment). Anyone who could reach the server could wipe all media statistics.

**Resolution**: Route deleted entirely. The authenticated `/api/stats/reset` endpoint in `src/primary/routes/common.py` already provides this functionality with proper session verification.

---

## Finding 4 — Weak SHA-256 Password Hashing ✅ FIXED 2026-05-17
**Severity**: Medium | **File**: `src/primary/auth.py:75–80`

Passwords were hashed with SHA-256 + salt. SHA-256 is designed for speed; GPUs can compute billions of hashes/second, making the credential file trivially brute-forceable if stolen. The credentials file was also world-readable at mode `0o644`.

**Resolution**: Replaced `hash_password()` with bcrypt (`bcrypt` was already present in `requirements.txt`). `verify_password()` now detects the hash format by prefix — bcrypt hashes start with `$2b$` and are verified with `bcrypt.checkpw()`; legacy `salt:hash` pairs fall through to the original SHA-256 path so existing accounts keep working. On the first successful login after the upgrade, `verify_user()` silently re-hashes the stored password to bcrypt and saves it — no user action required. Credentials file permissions tightened to `0o600` in both `save_user_data()` and `create_user()`.
