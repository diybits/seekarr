# Code Review Todo

Branch: `code-review`  
Started: 2026-05-17

---

## 🔴 Critical

- [x] **#1 Add ProxyFix middleware** — done; gated on `TRUST_PROXY=1`; session cookie flags added; README + CLAUDE.md updated

- [ ] **#2 Fix dead `/api/stats/reset_public` JS call** — endpoint was removed server-side (security fix) but `new-main.js:2121` still calls it; stats reset button silently 404s
  - Update call to `/api/stats/reset` (authenticated endpoint)

## 🟠 Important

- [x] **#3 Session cookie security flags** — done alongside #1; `HttpOnly` and `SameSite=Lax` always set, `Secure` when `TRUST_PROXY=1`

- [ ] **#4 Hardcoded absolute JS paths** — all `fetch('/api/...')` calls break under subpath deployments
  - Inject base path via `<meta name="seekarr-base">` in `head.html`
  - Update `utils.js` `fetchWithTimeout` to prefix base path
  - Fix `window.location.href = '/'` (`new-main.js:1318`) and `window.location.href = '/login'` (`new-main.js:2016`)

## 🟡 Polish

- [ ] **#5 Remove unconditional `debug_template_rendering()`** — hooks Jinja loader on every request in production; `web_server.py:95–118`
  - Gate behind `app.debug` or remove entirely (Jinja errors already surface in logs)

- [ ] **#6 Remove `print()` startup statements** — `web_server.py:91–92` raw prints to stdout in production

- [ ] **#7 Fix settings cache wipe on every request** — `auth.py:304–305` clears `settings_cache` on every authenticated request, defeating the 5s TTL and causing a disk read per request
  - Remove the manual cache clear; the TTL is sufficient

## 🟢 Nice to have

- [ ] **#8 Persist sessions across restarts** — `active_sessions` dict in `auth.py` is in-memory only; all users re-authenticate on container restart
  - Write/read sessions to `/config/sessions.json` with expiry cleanup on load

---

## Completed

- **#1** Add ProxyFix middleware (`TRUST_PROXY=1`) — `web_server.py`, `docker-compose.yml`, `README.md`, `CLAUDE.md`
- **#3** Session cookie security flags — `HttpOnly`, `SameSite=Lax` always; `Secure` when `TRUST_PROXY=1`
