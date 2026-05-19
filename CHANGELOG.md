# Changelog

All notable changes to Seekarr are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Fixed

- **2FA timing edge case** — `pyotp.TOTP.verify()` defaulted to `valid_window=0`, rejecting codes generated at a 30-second window boundary if `verify()` ran milliseconds later. All three `totp.verify()` calls in `auth.py` now use `valid_window=1` (the adjacent-window tolerance recommended by RFC 6238), eliminating intermittent 2FA failures for users with slight clock skew. (`src/primary/auth.py`)

### Removed

- **Windows service module** — `src/primary/windows_service.py` and the corresponding argv-handling block in `main.py` removed. The project is Docker-first (`linux/amd64` + `linux/arm64`); the module imported win32 packages at the top level (unimportable on Linux), was untestable in CI, and had no documented installation path. (`src/primary/windows_service.py`, `main.py`)

### Added

- **Test suite expanded to 697 tests** — new coverage for eros API layer (38 tests, PR #55), all six apps' `missing.py` and `upgrade.py` modules (148 tests, PR #56), and `background.py` orchestration loop (18 tests, PR #57).
- **pytest-cov coverage reporting in CI** — `ci.yml` now runs with `--cov=src/primary` and enforces a ≥50% coverage gate; coverage summary printed on every run. (`requirements.txt`, `.github/workflows/ci.yml`)
- **GitHub issue templates** — structured YAML forms for bug reports and feature requests; blank free-form issues disabled; docs link added to chooser. (`.github/ISSUE_TEMPLATE/`)
- **Multi-arch Docker image documented** — README now notes the image supports `linux/amd64` and `linux/arm64`. (`README.md`)

### Changed

- **Replaced flake8 with ruff** — CI lint stage now runs `ruff check src/` via `ruff.toml`. Enforces E722, F401, F541, F841, and W292. Auto-fixed 235 violations across 14 source files; manually fixed 2 bare excepts, dead variable assignments, and a duplicate log line. (`ruff.toml`, `.github/workflows/ci.yml`)

### Maintenance

- Dead code removed: orphaned stub files (PR #49), `FUNDING.yml` (PR #50), unused routes and config cleanup (PR #53).
- Trivy SARIF upload `continue-on-error` removed from `security.yml` (PR #52).
- `SECURITY.md` added; branch/PR workflow and squash-merge strategy documented in `CLAUDE.md` (PR #51).
- Local Docker build convention documented: tag as `yyyy.dayofyear.buildofday` and pass `--build-arg VERSION=<tag>` so the UI displays the local version instead of `dev`. (`CLAUDE.md`)

---

## [7.1.0] — 2026-05-19

### Fixed

- **SSL verification bypass (all apps)** — Direct `requests.get/post()` calls in sonarr, radarr, lidarr, readarr, whisparr, eros, and swaparr bypassed `arr_request()`, meaning `get_ssl_verify_setting()` was never consulted. Users with SSL verification disabled still received certificate errors on the majority of API calls. All HTTP calls now route through `arr_request()`. (`src/primary/apps/*/api.py`, `src/primary/apps/swaparr/handler.py`)
- **Whisparr v2 wrong base URL** — `arr_request()` in `whisparr/api.py` was using `/api/v3/` as its primary URL path instead of `/api/`. This caused all Whisparr v2 API calls to fail before falling back. (`src/primary/apps/whisparr/api.py`)
- **Swaparr query string construction** — Queue and delete requests had query parameters embedded directly in the URL string instead of passed via `params` dict, which could produce malformed URLs. (`src/primary/apps/swaparr/handler.py`)

### Added

- **Test suite — 491 tests** covering the full codebase: scheduler engine, history manager, stateful manager, hourly cap scheduler, web server routes, sonarr/radarr/lidarr/readarr/whisparr/eros API layers, swaparr routes, auth (including 2FA and credential changes), proxy middleware, config, keys manager, migrate_settings, history utils, stateful routes, and scheduler routes.
- **CI: auto-create GitHub Release on Docker push** — `docker-release.yml` now runs `gh release create` with `--generate-notes` when the push toggle is enabled, eliminating the manual release-notes step. (`/.github/workflows/docker-release.yml`)
- **CI: CodeQL SARIF upload fixed for private repos** — `upload-sarif` upgraded to v4 (v3 deprecated December 2026); `continue-on-error: true` added so the step silently skips while the repo is private and activates automatically on publication. (`/.github/workflows/security.yml`)

### Changed

- `arr_request()` in `radarr/api.py` gained a `params` kwarg for query string parameters — consistent with the other app modules.
- Sonarr's three paginated fetch functions extracted into a shared `_fetch_paginated()` helper, eliminating duplicated retry logic.
- Test-connection handlers across all apps consolidated into a shared utility, removing per-app duplication.
- Dead code removed: unused stub functions (`refresh_author`, `book_search`, `refresh_item`), orphaned files, and unused imports across readarr, eros, sonarr, and whisparr.

### Maintenance

- `pytest` bumped `8.4.2 → 9.0.3`.
- `data/` added to `.gitignore` (runtime tally fallback written by `stats_manager.py`).

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
- 76 in-app help icon links replaced with real per-app GitHub Pages docs URLs (`https://diybits.github.io/seekarr/apps/{app}.html`). Previously pointed to non-existent `huntarr.io/threads/*` and `seekarr.io/threads/*` paths. (`frontend/static/js/settings_forms.js`)
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
  - New `ci.yml`: gated pipeline — lint (flake8, errors and undefined names only) → test (pytest, skipped if no `tests/` directory). No Docker push — image publishing is handled exclusively by `docker-release.yml`.
  - New `security.yml`: weekly pip-audit of `requirements.txt` + Trivy image scan with SARIF upload to GitHub Security tab.
- Static asset files renamed: `huntarr-logo.png` → `seekarr-logo.png`, `Huntarr.svg` → `Seekarr.svg`, `huntarr.ico` → `seekarr.ico`. PNG artwork (16–864px) retains existing images pending new Seekarr artwork.

### Documentation

- Built full GitHub Pages docs site deployed from `docs/` via `seekarr-docs.yml`.
- App integration pages (Sonarr, Radarr, Lidarr, Readarr, Whisparr) redesigned with three-group settings layout matching the Seekarr UI: Instances / Search Settings / Additional Options.
- Official app logos added throughout docs (SVG for Lidarr/Readarr/Whisparr; PNG for Sonarr/Radarr where SVG fills were invisible on dark theme).
- Per-app accent colour theming applied to integration settings pages.
- Integrations index and Settings index card headers made clickable links.
- Getting Started section added to all page sidebars.
- Fork attribution notice added to home page: credits Huntarr (v6.6.3) / PlexGuide team as the upstream foundation.
- Dead GitHub wiki link in `README.md` replaced with live docs URL (`https://diybits.github.io/seekarr/`).

### Security

- **Fixed (HIGH)** — Removed hardcoded fallback Flask secret key `'dev_key_for_sessions'`. A cryptographically random 64-hex-character key is now generated on first start and persisted to `/config/secret_key` (mode `0o600`). Set the `SECRET_KEY` environment variable to supply your own key; it takes precedence over the auto-generated file. (`src/primary/web_server.py`)

- **Fixed (HIGH)** — Removed trust in the `X-Forwarded-For` request header for Local Bypass Mode authentication decisions. The local-network check now uses only `request.remote_addr` (the OS-level TCP peer address, which cannot be spoofed by a remote client). Previously, any client could send `X-Forwarded-For: 127.0.0.1` to bypass authentication when Local Bypass Mode was enabled. (`src/primary/auth.py`)

- **Fixed (MEDIUM)** — Removed the unauthenticated `/api/stats/reset_public` endpoint. This endpoint allowed any client that could reach the server to wipe all media statistics without authentication. The authenticated `/api/stats/reset` endpoint continues to provide this functionality. **Breaking change**: anything calling `/api/stats/reset_public` directly must switch to `/api/stats/reset` with a valid session. (`src/primary/web_server.py`)

- **Fixed (MEDIUM)** — Replaced SHA-256 password hashing with bcrypt. SHA-256 is a general-purpose hash optimised for speed and is vulnerable to GPU-accelerated brute-force attacks if the credential file is stolen. bcrypt is purpose-built for passwords and includes a cost factor that makes brute-force computationally expensive. **Existing accounts are migrated automatically** — on next successful login the stored hash is transparently upgraded to bcrypt with no action required from the user. The credentials file permissions have also been tightened from `0o644` to `0o600`. (`src/primary/auth.py`)

---

## [6.6.3] — upstream baseline

Last upstream Huntarr release before the Seekarr fork. See the [upstream release history](https://github.com/plexguide/Huntarr.io/releases) for changes prior to 7.0.0.
