# Phase 176E — Report Generation Route Reconciliation

**Baseline:** `796ec8368c4ec359e087ab8a699423b23f1a55fa` (Phase 176D)
**Branch:** `css-unified-consolidation-2026-07-13`
**Status:** Implemented — **DO NOT COMMIT** until explicitly approved.
**Date:** 2026-07-18

## Exact root cause

The operator UI (Mission Control Reports) is served from the **canonical launcher** on **port 8765**.

The Generate button uses a **same-origin relative** fetch:

```js
fetch('/api/v1/reports/generate', { method: 'POST', ... })
```

Phase 176 mounted `create_reports_center_router()` on:

- `dashboard.web.web_app` (port **8000**)
- `dashboard.mobile.mobile_app` (port **8090**)

but **not** on `launcher.css_mobile_launcher` (port **8765**).

The launcher registered Mission Control GET routes (`/mission-control/api/reports/*`) only.
Therefore:

| Call | Host | Result |
|------|------|--------|
| Readiness / catalog (MC GET) | 8765 | 200 |
| `POST /api/v1/reports/generate` | 8765 | **404 Not Found** |
| Same POST | 8000 / 8090 | 200 (router mounted) |

This was a **route registration / host ownership** defect, not RBAC.

## Old route topology

```
Browser → http://host:8765/mission-control/reports
        → POST /api/v1/reports/generate   (relative)
        → launcher FastAPI
        → NO create_reports_center_router
        → 404

web_app:8000 and mobile:8090 already had /api/v1/reports/* mounted (unused by this UI).
```

## Canonical route topology after fix

```
Browser → http://host:8765/mission-control/reports
        → POST /api/v1/reports/generate
        → launcher FastAPI
        → create_reports_center_router()
        → Phase 176D CSSAuthorizationContext / session bridge
        → ReportsCenterService.generate()
        → immutable archive
        → 200 + report_id/version/hash
```

Mission Control remains GET-only under `/mission-control/api/reports/*`.
Controlled writes remain under `/api/v1/reports/*`.

## Application / port ownership

| Port | Application | Reports GET (MC) | Reports write `/api/v1/reports` |
|------|-------------|------------------|--------------------------------|
| **8765** | `launcher.css_mobile_launcher` | Yes | **Yes (Phase 176E)** |
| **8000** | `dashboard.web.web_app` | Yes | Yes |
| **8090** | `dashboard.mobile.mobile_app` | N/A (mobile HTML) | Yes + `/reports/generate` form |

Port 8765 ownership by `launcher.css_mobile_launcher` is intentional (not an orphan).

## Fix applied

In `launcher/css_mobile_launcher.py`:

- `app.include_router(create_reports_center_router())`
- `app.include_router(create_executive_brief_distribution_router())` (parity with web_app for DEB PDF/email APIs)

No duplicate generation logic. Frontend path unchanged (canonical relative URL is correct once mounted).

## Desktop / mobile parity

- Desktop MC JS: `POST /api/v1/reports/generate` (unchanged; now reachable on 8765)
- Mobile: `POST /reports/generate` HTML form → `ReportsCenterService` + mounted `/api/v1/reports/*` on 8090
- PWA cache: **unchanged** (`css-mobile-shell-v176d`) — no mobile static/JS change

## Live evidence (post-restart)

- Original failing URL: `POST http://127.0.0.1:8765/api/v1/reports/generate` → **404**
- Final working URL: same → **200**
- Example report: `cssrpt_risk_exposure_safety_lock_report_2026-07-18_v009` / `v009` / hash `d5231809…`
- Playwright click Generate → POST generate **200**
- Library / detail / print / versions / audit / integrity → **200**

## Authorization

Phase 176D session bridge + `CSSAuthorizationContext` enforced on the mounted router. No ADMIN/TRADER/VIEWER silent fallback.

## Operational restart

```text
# Restart canonical launcher so route table reloads
python -m launcher.css_mobile_launcher
# default: 0.0.0.0:8765
```

## Rollback

```text
git checkout 796ec8368c4ec359e087ab8a699423b23f1a55fa
# restart launcher
```

## Safety

Preserved: `advisory_only=true`, `execution_allowed=false`, `live_trading_blocked=true`, `broker_execution_armed=false`.
