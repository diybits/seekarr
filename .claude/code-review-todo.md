# Code Review Todo

Branch: `code-review`  
Started: 2026-05-17

---

## 🔴 Critical

- [x] **#1 Trusted proxy middleware** — `TrustedProxyMiddleware` in `utils/proxy.py`; validates `REMOTE_ADDR` against `TRUSTED_PROXIES` (IPs, CIDRs, or `*`) before trusting forwarded headers; strips headers from untrusted connections; `SESSION_COOKIE_SECURE` when `TRUSTED_PROXIES` is set; `docker-compose.yml` + `README.md` updated

- [x] **#2 Fix dead `/api/stats/reset_public` JS call** — updated `new-main.js:2121` to call `/api/stats/reset` (authenticated endpoint)

## 🟠 Important

- [x] **#3 Session cookie security flags** — done alongside #1; `HttpOnly` and `SameSite=Lax` always set, `Secure` when `TRUST_PROXY=1`

- [x] **#4 Hardcoded absolute JS paths** — injected `<meta name="seekarr-base" content="{{ request.script_root }}">` in `head.html`; `utils.js` `fetchWithTimeout` now prepends base path to all `/`-relative URLs; fixed two `window.location.href` redirects in `new-main.js`

## 🟡 Polish

- [x] **#5 Remove unconditional `debug_template_rendering()`** — removed function and call from `web_server.py`

- [x] **#6 Remove `print()` startup statements** — removed all debug `print()` calls from `web_server.py` startup

- [x] **#7 Fix settings cache wipe on every request** — removed manual `settings_cache = {}` clear in `auth.py`; TTL handles freshness

## 🟢 Nice to have

- [x] **#8 Persist sessions across restarts** — sessions saved to `/config/sessions.json` (atomic write, 0o600); loaded on startup with expired entries pruned; `threading.Lock` guards all mutations

---

## Completed

- **#1** Add ProxyFix middleware (`TRUST_PROXY=1`) — `web_server.py`, `docker-compose.yml`, `README.md`, `CLAUDE.md`
- **#3** Session cookie security flags — `HttpOnly`, `SameSite=Lax` always; `Secure` when `TRUST_PROXY=1`
