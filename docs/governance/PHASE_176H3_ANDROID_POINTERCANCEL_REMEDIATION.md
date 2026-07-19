# Phase 176H.3 — Android pointercancel remediation

**Branch:** `css-unified-consolidation-2026-07-13`  
**Depends on:** Phase 176H.1 native-anchor navigation (`native-anchor-176h1`)

## Verified defect

Live DOM hit-testing showed nav `<a href>` correctly received touches (no overlay,
no `location.assign` interceptor). On mobile, sidebar + huge `.mc-main` stacked
into one document owned by `HTML` (`scrollHeight` ≫ viewport). Finger taps with
slight vertical movement caused Chromium `pointercancel` on the anchor and
suppressed native navigation. Playwright zero-slop taps still succeeded.

## Remediation (CSS only)

Mobile `@media (max-width: 1100px)`:

- `html, body.mc-body`: `height: 100%`; `max-height: 100dvh`; `overflow: hidden`
- `.mc-shell`: flex column; `height: 100dvh`; overflow hidden
- `.mc-sidebar`: `flex: 0 0 auto`; `overflow: auto` (capped max-height)
- `.mc-main`: `flex: 1`; `min-height: 0`; `overflow: auto`

Desktop grid + sticky sidebar unchanged. Native `<a href>` only — no
`preventDefault` / `location.assign` navigation helpers.

## Safety

Unchanged advisory / execution locks.
