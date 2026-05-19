# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Seekarr is a Python/Flask service that continuously searches *Arr applications (Sonarr, Radarr, Lidarr, Readarr, Whisparr, Eros) for missing media and quality upgrades. It exposes a web UI on port 9705. Intended to run via Docker with `/config` as a persistent volume.

## Commands

**Run locally:**
```bash
pip install -r requirements.txt
python3 main.py
# Debug mode (Flask dev server + verbose logs):
DEBUG=true python3 main.py
# Behind a reverse proxy (enables ProxyFix + Secure cookie):
TRUST_PROXY=1 python3 main.py
```

**Lint (must use a venv — system Python is externally managed):**
```bash
python3 -m venv .venv && .venv/bin/pip install flake8
.venv/bin/flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

**Docker:**
```bash
docker build -t seekarr .
docker run -p 9705:9705 -v /your-path/seekarr:/config seekarr
```

**Docker release** (manual only — no auto-push on CI):
Trigger `docker-release.yml` via GitHub Actions → Run workflow, providing a tag (e.g. `7.0.0`).

## Architecture

### Startup flow
`main.py` starts two threads: a Waitress web server (main thread) and a background processing loop (daemon thread). The shared `stop_event` from `background.py` coordinates graceful shutdown.

### Web layer (`src/primary/web_server.py`)
Flask app that registers all blueprints and owns authentication middleware. Blueprint layout:
- `src/primary/apps/{app}_routes.py` — per-app settings API and connection testing
- `src/primary/apps/blueprints.py` — single import point for all app blueprints
- `src/primary/routes/` — common routes, history, scheduler UI routes
- `src/primary/stateful_routes.py` — stateful item management endpoints

### Background processing (`src/primary/background.py`)
`start_seekarr()` launches one thread per enabled app (`app_specific_loop`). Each thread calls `process_missing` and `process_upgrades` from the corresponding `src/primary/apps/{app}.py`, then sleeps for `sleep_duration` seconds.

### Per-app modules
Each supported app has two files:
- `src/primary/apps/{app}.py` — processing logic (process_missing, process_upgrades, check_connection)
- `src/primary/apps/{app}_routes.py` — Flask blueprint for the app's settings/test-connection endpoints

**API layer contract**: All HTTP calls to external apps must go through each module's `arr_request()` function. It is the single place that applies SSL verification (`get_ssl_verify_setting()`), session reuse, User-Agent, and consistent error handling. Do not call `requests.get/post()` or `session.get/post()` directly — route everything through `arr_request()`. The function signature includes a `params` kwarg for query string parameters.

### Settings (`src/primary/settings_manager.py`)
All settings live at `/config/{app}.json`. `load_settings(app_name)` and `get_setting(app_name, key, default)` are the primary access patterns. A 5-second TTL cache sits in front of disk reads. Default templates are in `src/primary/default_configs/`.

### State tracking (`src/primary/state.py`)
Already-processed item IDs are persisted under `/config/state/{app}/` so restarts don't re-hunt the same items. `check_state_reset()` clears state after the configured interval (default 168 hours).

### Auth (`src/primary/auth.py`)
Single-user login backed by `/config/user/credentials.json`. Passwords hashed with bcrypt. TOTP 2FA via pyotp/qrcode. Session cookie name: `seekarr_session`. The `authenticate_request()` decorator is applied in `web_server.py` to protect routes.

### Supporting services
- `scheduler_engine.py` — cron-style action scheduler, reads `/config/scheduler/schedule.json`
- `hourly_cap_scheduler.py` — enforces per-app hourly API rate caps
- `stats_manager.py` — hunt/upgrade counters (reset via `/api/stats/reset`, auth required)

## Config persistence layout

```
/config/
  {app}.json          # per-app settings
  general.json        # global settings (debug mode, timeouts)
  user/credentials.json
  state/{app}/        # processed item ID tracking
  stateful/           # extended stateful management
  scheduler/schedule.json
  logs/
  secret_key          # auto-generated Flask session key
```

## Import path quirk

`main.py` inserts `src/` into `sys.path`, so modules may import as either `from primary.X import Y` or `from src.primary.X import Y`. Both forms appear in the codebase — new code should prefer `from src.primary.X import Y` for clarity.

## Adding a new app

1. `src/primary/apps/{app}.py` — implement `process_missing`, `process_upgrades`, `check_connection`, `get_queue_size`
2. `src/primary/apps/{app}_routes.py` — Flask blueprint with `/test-connection` and settings endpoints
3. Register the blueprint in `src/primary/apps/blueprints.py` and `web_server.py`
4. Add a default config JSON to `src/primary/default_configs/{app}.json`
5. Add the app name to `KNOWN_APP_TYPES` in `settings_manager.py` and `state.py`

## CI

- `ci.yml` — lint then test, runs on push/PR to `main`. No Docker push.
- `docker-release.yml` — manual `workflow_dispatch` only; prompts for tag and push toggle.
- `security.yml` — dependency/SAST scanning.
- `seekarr-docs.yml` — deploys `docs/` to GitHub Pages.
