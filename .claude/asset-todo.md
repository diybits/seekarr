# Asset Todo

## Critical — broken references

- [ ] `frontend/static/arrs/48-eros.png` — 48×48 PNG, transparent background
  - Eros stats card (`home_section.html:353`) currently uses the Whisparr logo as a placeholder

## Important — quality/spec gaps

- [x] ~~Regenerate `seekarr.ico`~~ — already contains 16, 32, 48, 64, 128, 256px frames; no action needed
- [x] `frontend/static/logo/apple-touch-icon.png` — created 180×180, `head.html` updated
- [x] `frontend/static/logo/192.png` — created 192×192
- [x] `frontend/static/site.webmanifest` — created; `<link rel="manifest">` added to `head.html`
- [x] ~~Fix `40.png`~~ — confirmed true 40×40; no action needed

## Nice to have

- [ ] `frontend/static/images/og-preview.png` — 1200×630 PNG for social link previews
  - No `og:image` tag exists; add OG + Twitter card meta tags to `head.html` after creating
- [ ] `frontend/static/arrs/48-swaparr.png` — 48×48 PNG, transparent background
  - Swaparr is a supported app but has no icon in `arrs/`
- [ ] Replace README screenshots with Seekarr-branded ones (~1280×800 PNG each)
  - `README.md` still references upstream Huntarr screenshots (GitHub user-attachments URLs)
  - Needed: homepage/stats dashboard, log viewer, settings page
