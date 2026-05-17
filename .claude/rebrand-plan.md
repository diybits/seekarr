# Rebrand Plan: Huntarr → Seekarr

New repository: `jeblankenship/seekarr` (possibly moving to `diybits/seekarr` — TBD)
New domain: seekarr.io

## Decisions Locked In

| # | Decision | Answer |
|---|----------|--------|
| 1 | Docker registry | GHCR only — `ghcr.io/<org>/seekarr` (org TBD: jeblankenship or diybits) |
| 2 | huntarr.io help links (52 in settings_forms.js) | Replace with `seekarr.io` placeholders |
| 3 | Donation/sponsor section in README | Remove |
| 4 | Logo artwork | Identify files needing replacement; wait for new assets |
| 5 | Version number | **7.0.0** — major bump for breaking changes |
| 6 | GitHub org | **TBD** — jeblankenship or diybits; use placeholder `<org>` in workflow files until confirmed |

---

## Scope Summary (from initial audit)

| Category | File count | Occurrences |
|----------|-----------|-------------|
| Python source files | 10+ | ~60 |
| HTML templates & docs | 10 | ~80 |
| JavaScript files | 8 | ~80 (incl. 52 huntarr.io help links) |
| Docker files | 2 | 6 |
| GitHub Actions workflows | 3 | 20+ |
| Markdown docs | 4 | 40+ |
| Static assets (filenames) | 3 | — |

---

## Task List (Task IDs reference the session task tracker)

### Task #5 — Python core rebrand
Files: `main.py`, `src/primary/windows_service.py`, `src/primary/auth.py`, `src/primary/background.py`
- Logger names: HuntarrRoot → SeekarrRoot, HuntarrBackground → SeekarrBackground
- Class: HuntarrService → SeekarrService
- Windows service metadata: _svc_name_ = "Seekarr", _svc_display_name_ = "Seekarr Service"
- Function: start_huntarr() → start_seekarr()
- **Session cookie**: SESSION_COOKIE_NAME = "huntarr_session" → "seekarr_session"
  ⚠️ Breaking change — all users must log in again after upgrade

### Task #6 — API User-Agent strings
Files: `src/primary/apps/{sonarr,radarr,lidarr,readarr,whisparr,eros}/api.py`
- "Huntarr/1.0 (https://github.com/plexguide/Huntarr.io)"
- → "Seekarr/7.0.0 (https://github.com/<org>/seekarr)"  ← org TBD

### Task #7 — HTML templates
Files: `frontend/templates/**/*.html`, `docs/**/*.html`
- Page titles, headings, display text, footers: Huntarr → Seekarr
- All plexguide GitHub links → https://github.com/<org>/seekarr
- Git clone URL: plexguide/Huntarr.io.git → <org>/seekarr.git
- Docker image refs in docs → ghcr.io/<org>/seekarr:latest

### Task #8 — JavaScript files
Files: `frontend/static/js/**/*.js`
- Module comments and error strings: "Huntarr" → "Seekarr"
- GitHub API calls in new-main.js: plexguide/Huntarr.io → <org>/seekarr (3 URLs)
- github-sponsors.js: sponsorsUsername 'plexguide' → owner of new org
- **52 huntarr.io forum links**: replace https://huntarr.io/threads/* → https://seekarr.io/threads/*

### Task #9 — Docker files
Files: `Dockerfile`, `docker-compose.yml`
- Add OCI image labels: title="Seekarr", url/source=https://github.com/<org>/seekarr
- docker-compose: service/container/volume names huntarr → seekarr
- Image: ghcr.io/<org>/seekarr
- ⚠️ Volume rename breaks existing deployments — document migration in CHANGELOG

### Task #10 — GitHub Actions workflows
Files: `.github/workflows/*.yml`
- Rename huntarr-docs.yml → seekarr-docs.yml; update workflow name inside
- Update all image refs to ghcr.io/<org>/seekarr:*
- Remove Docker Hub push steps (GHCR only)
- **New: .github/workflows/ci.yml** — gated lint → test → docker-build/push
- **New: .github/workflows/security.yml** — pip-audit + Trivy scan
- Note: org placeholder must be resolved before workflows will function correctly

### Task #11 — Markdown documentation
Files: `README.md`, `CHANGELOG.md`, `docs/README.md`, `.claude/security-findings.md`
- All "Huntarr" → "Seekarr"
- All plexguide/Huntarr.io links → <org>/seekarr
- Docker image examples → ghcr.io/<org>/seekarr:latest
- Volume paths: /your-path/huntarr → /your-path/seekarr
- Remove PayPal donation section
- Remove or update "Perfect Pair: Huntarr & Cleanuperr" section
- Version references → 7.0.0
- CHANGELOG: add [7.0.0] section with all breaking changes + volume migration command

### Task #12 — Static assets (identify; wait for artwork)
Files needing new artwork / rename:
- `docs/images/huntarr-logo.png` → `seekarr-logo.png`
- `frontend/static/logo/Huntarr.svg` → `Seekarr.svg`
- `frontend/static/logo/huntarr.ico` → `seekarr.ico`
Action now: rename files and update all references.
Action later: replace image content with Seekarr logo artwork when available.

### Task #13 — 2FA issuer name
File: `src/primary/auth.py`
- issuer_name="Huntarr" → issuer_name="Seekarr"
- Cosmetic only; existing enrolled 2FA codes continue to work

---

## Org Placeholder — Items Blocked Until Confirmed

The following cannot be finalised until `jeblankenship` vs `diybits` is decided:

| Item | Current placeholder | Affects |
|------|-------------------|---------|
| GHCR image name | `ghcr.io/<org>/seekarr` | Tasks 9, 10, 11 |
| GitHub repo URL | `https://github.com/<org>/seekarr` | Tasks 5–11 |
| GitHub API calls | `api.github.com/repos/<org>/seekarr` | Task 8 |
| Sponsors username | `<org>` or remove widget | Task 8 |
| Workflow GITHUB_TOKEN push target | `<org>` | Task 10 |

Recommendation: use `jeblankenship` now and do a single search-and-replace to `diybits` if the org moves. All references are in text/config files so the swap takes under 5 minutes.

---

## Breaking Changes to Document in CHANGELOG under 7.0.0

- **Session cookie renamed** (`huntarr_session` → `seekarr_session`) — all users must log in again after upgrade
- **Docker volume renamed** (`huntarr-config` → `seekarr-config`) — existing deployments must migrate:
  ```bash
  docker volume create seekarr-config
  docker run --rm -v huntarr-config:/from -v seekarr-config:/to alpine sh -c "cp -av /from/. /to/"
  docker volume rm huntarr-config
  ```
- **`/api/stats/reset_public` endpoint removed** — use authenticated `/api/stats/reset` instead

---

## Logo / Asset Files Awaiting New Artwork

| Current file | New filename | Status |
|---|---|---|
| `docs/images/huntarr-logo.png` | `seekarr-logo.png` | ⏳ Awaiting artwork |
| `frontend/static/logo/Huntarr.svg` | `Seekarr.svg` | ⏳ Awaiting artwork |
| `frontend/static/logo/huntarr.ico` | `seekarr.ico` | ⏳ Awaiting artwork |
| `frontend/static/logo/*.png` (16–864px) | same names | ⏳ Awaiting artwork |
