# Code Review Todo

Branch: `code-review`  
Started: 2026-05-17

---

## 🔴 Critical

- [x] **#1 Trusted proxy middleware** — `TrustedProxyMiddleware` in `utils/proxy.py`; validates `REMOTE_ADDR` against `TRUSTED_PROXIES` (IPs, CIDRs, or `*`) before trusting forwarded headers; strips headers from untrusted connections; `SESSION_COOKIE_SECURE` when `TRUSTED_PROXIES` is set; `docker-compose.yml` + `README.md` updated

- [x] **#2 Fix dead `/api/stats/reset_public` JS call** — updated `new-main.js:2121` to call `/api/stats/reset` (authenticated endpoint)

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
