# Phase 176H — Mobile Mission Control Navigation Reconciliation

**Baseline:** `d77aefc07df48f40d774cbf3d2ff4e134000a233` (Phase 176G)
**Branch:** `css-unified-consolidation-2026-07-13`
**Status:** Implemented — **DO NOT COMMIT** until explicitly approved.
**Date:** 2026-07-18

## Exact root cause

Mission Control navigation items are real `<a href="/mission-control/...">`
anchors (not JS-only buttons). Desktop mouse clicks navigate correctly.

On mobile/Android the sidebar CSS kept `overflow-y: auto` from the desktop
sticky sidebar rule even after the stacked (single-column) layout media query
only changed `position` / `height`. Nested overflow scrollports plus a sticky
topbar at `z-index: 5` (sidebar had no competing stacking context) caused
Android Chrome to suppress the synthetic click on nav anchors — so every menu
item appeared inert to touch while remaining mouse-clickable on desktop.

This is a Mission Control shell touch/CSS binding defect, not a Reports defect.

## Fix

1. `theme.py` — at `max-width: 1100px`, set `.mc-sidebar { overflow: visible; z-index: 6; }`;
   raise nav touch targets (`min-height: 44px`), `touch-action: manipulation`.
2. `layout.py` — `MC_NAV_TOUCH_JS` activates `touchend` → `location.assign(href)`
   when the tap is not a scroll gesture, without converting nav to inert buttons.

## Safety

Unchanged: `advisory_only=true`, `execution_allowed=false`,
`live_trading_blocked=true`, `broker_execution_armed=false`.

## Rollback

Revert `theme.py` / `layout.py` Phase 176H edits and this document.
