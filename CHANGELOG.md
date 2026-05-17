# Changelog

All notable changes to Seekarr are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [7.0.0] — 2026-05-17

### ⚠️ Breaking Changes

- **Session cookie renamed** (`huntarr_session` → `seekarr_session`) — all users must log in again after upgrading.
- **Docker volume renamed** (`huntarr-config` → `seekarr-config`) — migrate data before upgrading:
  ```bash
  docker volume create seekarr-config
  docker run --rm -v huntarr-config:/from -v seekarr-config:/to alpine sh -c "cp -av /from/. /to/"
  docker volume rm huntarr-config
  ```
- **`/api/stats/reset_public` removed** — use the authenticated `/api/stats/reset` endpoint instead.
- **Environment variable renamed** (`HUNTARR_RUN_MIGRATION` → `SEEKARR_RUN_MIGRATION`).

### Changed (Rebrand: Huntarr → Seekarr)

- **Breaking** — Session cookie renamed from `huntarr_session` to `seekarr_session`. All existing sessions are invalidated; users must log in again after upgrading. (`src/primary/auth.py`)
- Logger names updated: `HuntarrRoot` → `SeekarrRoot`, `HuntarrBackground` → `SeekarrBackground`. (`main.py`, `src/primary/background.py`)
- Windows service class renamed `HuntarrService` → `SeekarrService`; service name and display name updated to "Seekarr" / "Seekarr Service". (`src/primary/windows_service.py`)
- Background entry point renamed `start_huntarr()` → `start_seekarr()`; migration env var renamed `HUNTARR_RUN_MIGRATION` → `SEEKARR_RUN_MIGRATION`. (`src/primary/background.py`)
- TOTP 2FA provisioning issuer updated from `"Huntarr"` to `"Seekarr"`. Existing enrolled authenticators are unaffected. (`src/primary/auth.py`)
- HTTP `User-Agent` header updated from `Huntarr/1.0 (https://github.com/plexguide/Huntarr.io)` to `Seekarr/7.0.0 (https://github.com/diybits/seekarr)` across all six Arr app API modules.
- All HTML templates and documentation pages rebranded: titles, headings, footers, GitHub links, Docker image references, and version badges updated to Seekarr/7.0.0.
- Sidebar "Become A Sponsor" link updated to `github.com/sponsors/diybits`; original developer's personal Unraid link replaced with Seekarr GitHub link.
- `localStorage` key prefix changed from `huntarr-*` to `seekarr-*`; CSS class `.huntarr-logo` renamed to `.seekarr-logo`.
- All JavaScript files rebranded: `HuntarrUtils` → `SeekarrUtils`, `huntarrUI` → `seekarrUI`, `window.huntarrSchedules` → `window.seekarrSchedules`.
- GitHub API calls in `new-main.js` updated to `api.github.com/repos/diybits/seekarr`; sponsors link updated to `github.com/sponsors/diybits`.
- `github-sponsors.js`: `sponsorsUsername` updated to `'diybits'`.
- 50 in-app help links updated from `huntarr.io/threads/*` to `seekarr.io/threads/*` (placeholders until seekarr.io is live).
- `Dockerfile`: added OCI image labels (title, description, url, source, authors, license).
- **Breaking** — Docker named volume renamed from `huntarr-config` to `seekarr-config`. Migrate existing data before upgrading:
  ```bash
  docker volume create seekarr-config
  docker run --rm -v huntarr-config:/from -v seekarr-config:/to alpine sh -c "cp -av /from/. /to/"
  docker volume rm huntarr-config
  ```
- `docker-compose.yml`: service name, container name, and volume updated to `seekarr`; image set to `ghcr.io/diybits/seekarr:latest`.
- GitHub Actions workflows replaced and added:
  - `huntarr-docs.yml` renamed to `seekarr-docs.yml` (GitHub Pages deploy).
  - Old `docker-build-push.yml` and `docker-image.yml` (pushed to Docker Hub) removed.
  - New `ci.yml`: gated pipeline — lint → test → Docker build & push to GHCR (`ghcr.io/diybits/seekarr`). Docker stage skipped on pull requests.
  - New `security.yml`: weekly pip-audit of `requirements.txt` + Trivy image scan with SARIF upload to GitHub Security tab.
- Static asset files renamed: `huntarr-logo.png` → `seekarr-logo.png`, `Huntarr.svg` → `Seekarr.svg`, `huntarr.ico` → `seekarr.ico`. PNG artwork (16–864px) retains existing images pending new Seekarr artwork.

### Security

- **Fixed (HIGH)** — Removed hardcoded fallback Flask secret key `'dev_key_for_sessions'`. A cryptographically random 64-hex-character key is now generated on first start and persisted to `/config/secret_key` (mode `0o600`). Set the `SECRET_KEY` environment variable to supply your own key; it takes precedence over the auto-generated file. (`src/primary/web_server.py`)

- **Fixed (HIGH)** — Removed trust in the `X-Forwarded-For` request header for Local Bypass Mode authentication decisions. The local-network check now uses only `request.remote_addr` (the OS-level TCP peer address, which cannot be spoofed by a remote client). Previously, any client could send `X-Forwarded-For: 127.0.0.1` to bypass authentication when Local Bypass Mode was enabled. (`src/primary/auth.py`)

- **Fixed (MEDIUM)** — Removed the unauthenticated `/api/stats/reset_public` endpoint. This endpoint allowed any client that could reach the server to wipe all media statistics without authentication. The authenticated `/api/stats/reset` endpoint continues to provide this functionality. **Breaking change**: anything calling `/api/stats/reset_public` directly must switch to `/api/stats/reset` with a valid session. (`src/primary/web_server.py`)

- **Fixed (MEDIUM)** — Replaced SHA-256 password hashing with bcrypt. SHA-256 is a general-purpose hash optimised for speed and is vulnerable to GPU-accelerated brute-force attacks if the credential file is stolen. bcrypt is purpose-built for passwords and includes a cost factor that makes brute-force computationally expensive. **Existing accounts are migrated automatically** — on next successful login the stored hash is transparently upgraded to bcrypt with no action required from the user. The credentials file permissions have also been tightened from `0o644` to `0o600`. (`src/primary/auth.py`)

---

## [6.6.3] — upstream baseline

Last upstream Huntarr release before the Seekarr fork. See the [upstream release history](https://github.com/plexguide/Huntarr.io/releases) for changes prior to 7.0.0.
