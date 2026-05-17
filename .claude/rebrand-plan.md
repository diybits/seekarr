# Seekarr Project — Master Task List

Repository: https://github.com/diybits/seekarr
Domain: seekarr.io (owned, site setup pending)

## Decisions — All Locked In

| # | Decision | Answer |
|---|----------|--------|
| 1 | Docker registry | GHCR only — `ghcr.io/diybits/seekarr` |
| 2 | huntarr.io help links (52 in settings_forms.js) | Replace with `seekarr.io` placeholders |
| 3 | Donation/sponsor section in README | Remove |
| 4 | Logo artwork | Rename files now; replace image content when artwork is ready |
| 5 | Version number | **7.0.0** — major bump for breaking changes |
| 6 | GitHub org | **diybits** — confirmed |

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

## Security Tasks (all complete ✅)

| # | Task | Commit |
|---|------|--------|
| 1 | Fix hardcoded fallback Flask secret key | ec57262 |
| 2 | Fix X-Forwarded-For spoofing bypass in local network auth | 7d0938a |
| 3 | Remove unauthenticated /api/stats/reset_public endpoint | 23e6914 |
| 4 | Replace SHA-256 password hashing with bcrypt | 1c81fc5 |

---

## Rebrand Task List

### Task #5 — Python core rebrand ⏳
Files: `main.py`, `src/primary/windows_service.py`, `src/primary/auth.py`, `src/primary/background.py`
- Logger names: HuntarrRoot → SeekarrRoot, HuntarrBackground → SeekarrBackground
- Class: HuntarrService → SeekarrService
- Windows service: _svc_name_ = "Seekarr", _svc_display_name_ = "Seekarr Service"
- Function: start_huntarr() → start_seekarr()
- **Session cookie**: "huntarr_session" → "seekarr_session"
  ⚠️ Breaking change — all users must log in again after upgrade

### Task #6 — API User-Agent strings ⏳
Files: `src/primary/apps/{sonarr,radarr,lidarr,readarr,whisparr,eros}/api.py`
- "Huntarr/1.0 (https://github.com/plexguide/Huntarr.io)"
- → "Seekarr/7.0.0 (https://github.com/diybits/seekarr)"

### Task #7 — HTML templates ⏳
Files: `frontend/templates/**/*.html`, `docs/**/*.html`
- Titles, headings, display text, footers: Huntarr → Seekarr
- GitHub links → https://github.com/diybits/seekarr
- Git clone URL → https://github.com/diybits/seekarr.git
- Docker image refs → ghcr.io/diybits/seekarr:latest
- Logo image refs: huntarr-logo.png → seekarr-logo.png

### Task #8 — JavaScript files ⏳
Files: `frontend/static/js/**/*.js`
- "Huntarr" → "Seekarr" in comments and string literals
- GitHub API calls in new-main.js → api.github.com/repos/diybits/seekarr/*
- github-sponsors.js: sponsorsUsername → 'diybits'
- 52 huntarr.io links → https://seekarr.io/threads/* (placeholders)

### Task #9 — Docker files ⏳
Files: `Dockerfile`, `docker-compose.yml`
- OCI labels: title="Seekarr", url/source=https://github.com/diybits/seekarr, authors="diybits"
- docker-compose: service/container/volume names huntarr → seekarr
- Image: ghcr.io/diybits/seekarr
- ⚠️ Volume rename — document migration in CHANGELOG

### Task #10 — GitHub Actions workflows ⏳
Files: `.github/workflows/*.yml`
- huntarr-docs.yml → seekarr-docs.yml
- All image refs → ghcr.io/diybits/seekarr:*
- Remove Docker Hub push steps
- New: ci.yml (gated lint → test → docker-build/push)
- New: security.yml (pip-audit + Trivy)
- GHCR push target: ghcr.io/diybits/seekarr (GITHUB_TOKEN auto-scoped to repo)

### Task #11 — Markdown documentation ⏳
Files: `README.md`, `CHANGELOG.md`, `docs/README.md`, `.claude/security-findings.md`
- "Huntarr" → "Seekarr" throughout
- All plexguide/Huntarr.io links → https://github.com/diybits/seekarr
- Docker image → ghcr.io/diybits/seekarr:latest
- Volume paths: huntarr → seekarr
- Remove PayPal donation section
- Remove/update Cleanuperr partnership section
- Version → 7.0.0
- CHANGELOG: add [7.0.0] section with breaking changes + volume migration command
- GitHub Pages: diybits.github.io/seekarr

### Task #12 — Static assets (rename now; artwork later) ✅
- docs/images/huntarr-logo.png → seekarr-logo.png ✅
- frontend/static/logo/Huntarr.svg → Seekarr.svg ✅
- frontend/static/logo/huntarr.ico → seekarr.ico ✅
- All HTML/JS references updated in Tasks #7 and #8 ✅
- PNG set (16–864px) awaiting new artwork

### Task #13 — 2FA issuer name ⏳
File: `src/primary/auth.py`
- issuer_name="Huntarr" → issuer_name="Seekarr"
- Cosmetic only; existing 2FA codes unaffected

---

## Breaking Changes to Document in CHANGELOG under [7.0.0]

- **Session cookie renamed** (`huntarr_session` → `seekarr_session`) — all users must log in again
- **Docker volume renamed** (`huntarr-config` → `seekarr-config`) — migration command:
  ```bash
  docker volume create seekarr-config
  docker run --rm -v huntarr-config:/from -v seekarr-config:/to alpine sh -c "cp -av /from/. /to/"
  docker volume rm huntarr-config
  ```
- **`/api/stats/reset_public` removed** — use authenticated `/api/stats/reset`

---

## Logo / Asset Files

| File | Status |
|---|---|
| `docs/images/seekarr-logo.png` | ✅ Renamed — artwork pending |
| `frontend/static/logo/Seekarr.svg` | ✅ Renamed — artwork pending |
| `frontend/static/logo/seekarr.ico` | ✅ Renamed — artwork pending |
| `frontend/static/logo/*.png` (16–864px) | ⏳ Awaiting new artwork (keep existing Huntarr images for now) |
