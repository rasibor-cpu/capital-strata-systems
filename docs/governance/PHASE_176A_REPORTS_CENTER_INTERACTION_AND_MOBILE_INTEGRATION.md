# Phase 176A — Reports Center Interaction and Mobile Integration

**Baseline:** `51891e91495e54697468b2a63c50ccc16567d438` (Phase 176)  
**Branch:** `css-unified-consolidation-2026-07-13`

## Verified root causes

### Desktop
`dashboard/mission_control/pages/reports_center.py` rendered **static** `detail_table` markup only (category counts and text). There were **no** `<details>`/`<summary>`, buttons, forms, or client scripts. Categories could not expand; report names were not actionable; Create Report was documentation text only.

### Mobile
`dashboard/mobile/mobile_app.py` `_top_nav` and Command Center hard-coded menu links **without** a Reports entry. No `/reports*` routes existed. The phone therefore could not surface the Phase 176 catalogue regardless of API availability.

### API / cache
Canonical APIs already existed under `/mission-control/api/reports/*` (GET) and `/api/v1/reports/*` (writes). Mobile simply never called them. Service worker cache was still `css-mobile-shell-v1`, so shell assets could remain stale after deploy.

## What changed (no registry/RBAC/producer changes)

- Interactive Mission Control Reports page (accordions, cards, Create Report, library/detail JS)
- Shared `backend/reports_center/ui_contract.py` for desktop/mobile nav + safe filter fields
- Mobile Reports home/create/library/detail + form POST generate via `ReportsCenterService`
- Reports nav item (permission-gated) + Command Center card
- PWA cache bump to `css-mobile-shell-v176a` + manifest marker

## Refresh procedure (phone)

1. Redeploy / restart mobile app host.
2. Open the app online once so the new service worker (`v176a`) activates and drops `v1` caches.
3. Soft refresh the dashboard (no reinstall required).
4. Confirm top nav shows **Reports** for roles with `reports_view` / `view_reports`.

## Safety

Unchanged: `advisory_only=true`, `execution_allowed=false`, `live_trading_blocked=true`, `broker_execution_armed=false`.  
Email remains EMAIL_DISABLED by default; executive brief policy still Phase 175.
