# Changelog

All notable changes to Huntarr are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Security

- **Fixed (HIGH)** — Removed hardcoded fallback Flask secret key `'dev_key_for_sessions'`. A cryptographically random 64-hex-character key is now generated on first start and persisted to `/config/secret_key` (mode `0o600`). Set the `SECRET_KEY` environment variable to supply your own key; it takes precedence over the auto-generated file. (`src/primary/web_server.py`)

- **Fixed (HIGH)** — Removed trust in the `X-Forwarded-For` request header for Local Bypass Mode authentication decisions. The local-network check now uses only `request.remote_addr` (the OS-level TCP peer address, which cannot be spoofed by a remote client). Previously, any client could send `X-Forwarded-For: 127.0.0.1` to bypass authentication when Local Bypass Mode was enabled. (`src/primary/auth.py`)

- **Fixed (MEDIUM)** — Removed the unauthenticated `/api/stats/reset_public` endpoint. This endpoint allowed any client that could reach the server to wipe all media statistics without authentication. The authenticated `/api/stats/reset` endpoint continues to provide this functionality. **Breaking change**: anything calling `/api/stats/reset_public` directly must switch to `/api/stats/reset` with a valid session. (`src/primary/web_server.py`)

---

## [6.6.3] — previous release

See [GitHub Releases](https://github.com/plexguide/Huntarr.io/releases) for earlier version history.
