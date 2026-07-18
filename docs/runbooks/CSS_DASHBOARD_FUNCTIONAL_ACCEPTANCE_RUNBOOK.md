# CSS Dashboard Functional Acceptance Runbook

**Phase:** 176C / 176D
**Purpose:** Repeatable operator verification that dashboard controls perform intended workflows after deployment.

## Prerequisites

1. Deploy branch `css-unified-consolidation-2026-07-13` including Phase 176C/176D artifacts.
2. Desktop host running web/Mission Control (example: `uvicorn dashboard.web.web_app:app --host 0.0.0.0 --port 8000`).
3. Mobile host running `dashboard.mobile.mobile_app:app` (or unified host mounting both).
4. Valid CLI/runtime session bridged via `artifacts/css_auth_session.json` (e.g. `00000` / `SUPER_USER`) — Phase 176D.
5. Operator account with `ADMIN`/`SUPER_USER` (and a second account without `reports_view` for RBAC checks).
6. Optional: Playwright (`requirements-browser.txt`) for automated browser smoke.

## Fail criteria (any one fails the run)

- Control appears active but does nothing or only changes appearance.
- Control returns HTTP 200 with fabricated/empty “success” without backend evidence.
- Errors swallowed (blank UI / silent catch).
- Secrets/credentials visible in UI or exports.
- Live trading / broker execution armed unexpectedly.
- Print/PDF/generate bypasses `ReportsCenterService`.
- Unauthorized role can mutate via direct route/API.
- **API ALLOW / HTML DENY** (or reverse) for the same identity on Reports.

## Authorization parity (Phase 176D)

| Step | Action | Expected |
|------|--------|----------|
| A1 | Confirm session identity `00000` / `SUPER_USER` (or ADMIN) | Bridged into MC governance |
| A2 | `GET /mission-control/api/reports/home` | `reports_view=true`, matching user_id/role |
| A3 | `GET /mission-control/reports` | Full Reports Center — **not** access denied |
| A4 | Unauthorized role | API 403 **and** HTML access denied |
| A5 | Forged `X-CSS-Role` without trust flag | Denied |

## Report generation (Phase 176E)

| Step | Action | Expected |
|------|--------|----------|
| G1 | Confirm UI host (canonical launcher **8765**) | OpenAPI lists `POST /api/v1/reports/generate` |
| G2 | Click Generate on a safe report (e.g. `safety_lock_report`) | **HTTP 200**, not 404 |
| G3 | Confirm archive | `report_id` / version / hash returned; Library lists report |
| G4 | Detail / print / versions / audit / integrity | All succeed on same host |

## Desktop test sequence

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open `/mission-control/executive-overview` | SSR metrics; READ ONLY badge; no forms |
| 2 | Click each MC nav item | Page changes; `aria-current="page"`; content matches section |
| 3 | Open Reports | Subtabs Categories/Generatable/Create/Library/Detail |
| 4 | Expand All / Collapse All | Category panels open/close; `aria-expanded` toggles |
| 5 | Deep-link `#cat-trading_transactions` | Category opens and scrolls into view |
| 6 | Select generatable report → Check readiness | JSON readiness from MC API |
| 7 | Generate as ADMIN/SUPER_USER | Canonical archive created; report id/version/hash shown |
| 8 | Generate as unauthorized role | Denied / disabled — no archive |
| 9 | Library refresh + open detail | Canonical retrieve; versions/print/pdf/audit/verify work |
| 10 | Open printable HTML | `/api/v1/reports/{id}/print` renders; non-FINAL labelled diagnostic |
| 11 | Web `/dashboard` Refresh | frontend-state bind; no console pageerrors |
| 12 | Web Command Centre | Navigation links are `<a href>` when routes exist; failures visible |
| 13 | Broker / Risk / Users / Config MC pages | Display-only; no writable mutation controls |

## Phone / mobile test sequence

| Step | Action | Expected |
|------|--------|----------|
| 1 | Soft-refresh PWA (`css-mobile-shell-v176d`+) | New shell cached |
| 2 | Top nav each item | Active page shows `aria-current="page"` |
| 3 | Reports menu categories | Disclosures expand; category query filters |
| 4 | Create Report → Generate | POST `/reports/generate` via service; result/error shown |
| 5 | Library `?view=latest` | Heading shows Latest; recent archive only |
| 6 | Detail Print / PDF | `/api/v1/reports/...` resolves on mobile origin (router mounted) |
| 7 | Alerts filters | Client severity filter works; Refresh reloads |
| 8 | Controls/Users (authorized only) | Unauthorized cannot POST |

## Evidence capture

- Screenshot each failed step.
- Save network HAR or note failing URL/method/status/body.
- Capture report_id for generate/print failures.
- Record role used.

## Automated pre-check

```
.\.venv\Scripts\python.exe -m pytest tests\test_phase176c_dashboard_functional_certification.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_phase176b_enterprise_ui_interaction.py tests\test_phase176a_reports_interaction_and_mobile.py tests\test_phase176_institutional_reports_center.py -q
```

Optional live browser:

```
set CSS_LIVE_BROWSER_BASE_URL=http://127.0.0.1:8000
.\.venv\Scripts\python.exe -m pytest -m browser tests\test_phase176c_dashboard_functional_certification.py -q
```

## Rollback

1. Redeploy prior known-good SHA (`0313fe30daf4cf1364bec08d5a97d0c3f9a4fd09` if 176C not accepted).
2. Clear mobile PWA caches / bump service worker if shell stuck.
3. Do not arm live trading during rollback.

## Sign-off checklist

- [ ] Desktop MC navigation complete
- [ ] Reports generate/library/detail/print certified
- [ ] Web refresh APIs return controlled results
- [ ] Mobile Reports print/PDF mounted
- [ ] RBAC denial verified with VIEWER
- [ ] Safety locks unchanged
- [ ] No secrets in UI
- [ ] Failures captured with evidence
- [ ] Operator name / date / environment recorded
