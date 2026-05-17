# Asset Todo

## Critical — broken references

- [ ] `frontend/static/arrs/48-eros.png` — 48×48 PNG, transparent background
  - Eros stats card (`home_section.html:353`) currently uses the Whisparr logo as a placeholder

## Important — quality/spec gaps

- [ ] Regenerate `frontend/static/logo/seekarr.ico` to include 16, 32, and 48px frames (current file only has 16 and 32)
  - Source: `frontend/static/logo/Seekarr.svg`
- [ ] `frontend/static/logo/apple-touch-icon.png` — 180×180 PNG, solid background, no rounded corners
  - Current `<apple-touch-icon>` points at 128px; Apple spec is 180px
  - Update `head.html:31` to reference the new file after creating
- [ ] `frontend/static/logo/192.png` — 192×192 PNG
- [ ] `frontend/static/site.webmanifest` — references 192×192 and 512×512 icons
  - No manifest exists; add `<link rel="manifest" href="/static/site.webmanifest">` to `head.html`
- [ ] Fix `frontend/static/logo/40.png` — filename says 40px but actual dimensions are 48×48 (duplicate of `48.png`)
  - Verify no references (`grep -r "40\.png" frontend/`) then delete or regenerate at true 40×40

## Nice to have

- [ ] `frontend/static/images/og-preview.png` — 1200×630 PNG for social link previews
  - No `og:image` tag exists; add OG + Twitter card meta tags to `head.html` after creating
- [ ] `frontend/static/arrs/48-swaparr.png` — 48×48 PNG, transparent background
  - Swaparr is a supported app but has no icon in `arrs/`
- [ ] Replace README screenshots with Seekarr-branded ones (~1280×800 PNG each)
  - `README.md` still references upstream Huntarr screenshots (GitHub user-attachments URLs)
  - Needed: homepage/stats dashboard, log viewer, settings page
