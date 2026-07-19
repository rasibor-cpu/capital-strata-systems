# Phase 176H.1 — Physical Android Mission Control Navigation Remediation

**Baseline context:** Phase 176H (`2d2e8f3`) failed physical Android acceptance.
**Branch tip at implementation:** includes Phase 176I (`0facf91`).
**Status:** Implemented — **DO NOT COMMIT** until explicitly approved.
**Date:** 2026-07-19

## Why Phase 176H passed emulation but failed physical Android

Phase 176H added `touchend` → `preventDefault()` → `location.assign(href)`.

Playwright `has_touch` / `tap()` does **not** exercise the same Android Chrome
touch → synthetic-click pipeline. Emulation could navigate while real Android
Chrome left anchors inert after `preventDefault` cancelled the native click.

Served-build verification on `:8765` confirmed 176H CSS/JS **was** live
(`overflow: visible`, `location.assign`, `Cache-Control: no-store`, identical
LAN/localhost body hash). Stale service-worker HTML on `:8765` was **not** a
factor (`/service-worker.js` → 404). Cache was therefore not the primary cause.

## Exact verified root cause

1. **Primary:** Mission Control shipped a touch interceptor that called
   `preventDefault()` on `touchend`, suppressing native `<a href>` navigation.
2. **Contributing:** Nested icon/label `<span>` elements inside anchors as
   exclusive touch targets; sticky sidebar/topbar stacking retained risk on
   some viewports.

Proof: with JavaScript **disabled**, Playwright navigation via plain anchors
succeeded; production requirement is native-anchor navigation without JS.

## Fix (176H.1)

- Remove production `MC_NAV_TOUCH_JS` interceptor entirely.
- Keep real `<a href="/mission-control/...">` as the only navigation mechanism.
- Mobile CSS: `position: static` + `overflow: visible` on sidebar/topbar;
  `pointer-events: none` on `.mc-nav a > *`.
- Optional `?touch_debug=1` overlay (dev-only; not required for navigation).
- Build marker `native-anchor-176h1` in HTML meta/data attributes.
- PWA SW (`css-mobile-shell-v176h1`): never cache `/mission-control*` HTML.

## Operator refresh

Hard-refresh Android Chrome on `http://192.168.86.217:8765/mission-control`
(or open with `?touch_debug=1` once). No app reinstall required.

## Safety

Unchanged advisory / execution locks.
