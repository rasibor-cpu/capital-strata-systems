# Phase 176C — Complete Dashboard Functional Certification

**Baseline:** `0313fe30daf4cf1364bec08d5a97d0c3f9a4fd09` (Phase 176B)
**Branch:** `css-unified-consolidation-2026-07-13`
**Status:** Complete.

## Objective

Certify that visible desktop/mobile controls perform their **intended workflows**, not merely that elements exist, are clickable, open, or return HTTP 200.

## Canonical registry

Package: `dashboard/ui_function/`

- `models.CSSUIFunctionDefinition` — required schema fields
- `registry_mc.py` / `registry_web.py` / `registry_mobile.py` — inventories
- `registry.py` — assembly + completeness asserts (no `UNVERIFIED`, no `BROKEN`)
- `certify.py` — ASGI functional workflows (nav, APIs, Reports generate→archive→print_info)
- `browser_harness.py` — optional Playwright live browser smoke
- `matrix.py` — exports `docs/governance/CSS_UI_FUNCTION_CAPABILITY_MATRIX.md`

## Root causes repaired in this phase

| Defect | Root cause | Repair |
|--------|------------|--------|
| Mobile Print/PDF 404 | `mobile_app` did not mount `create_reports_center_router` | Mount `/api/v1/reports/*` on mobile app |
| Latest Reports no-op | `?view=latest` ignored | Honour `view=latest` in library route + `list_library` |
| Web SCC “Navigation Links” inert | Rendered as `<span>` | Render `<a href>` when route present; visible disabled span otherwise; surface fetch errors |
| Reports category deep-links | `#cat-*` vs panel ids / no open handler | Carried from prior sub-tab work: wrapper `id=cat-*` + `CSSUIInteraction.openDisclosureForTarget` |
| Mobile active nav missing | Current page link omitted | Always render active link with `aria-current` |
| Reports Create selector empty / JS pageerror | `html.escape` on `application/json` script left literal `&quot;` so `JSON.parse` failed | Embed JSON with `\u003c`/`\u003e`/`\u0026` sanitization only |

## Honest non-functional surfaces (not marked FUNCTIONAL)

- Mission Control pages other than Reports: SSR read-only → `FUNCTIONAL_WITH_LIMITATIONS` + mutation controls `FAIL_CLOSED`
- Documentation index: paths not hyperlinked (absolute path exposure policy) → limitations documented
- Micro-pilot arm/configure APIs: no visible UI → `DISABLED` / `NO_VISIBLE_CONTROL`
- Live trading: remains blocked; trade ticket `FUNCTIONAL_WITH_LIMITATIONS`

## Live browser testing

Optional dependency: `requirements-browser.txt` (Playwright).

```
pip install -r requirements-browser.txt
playwright install chromium
# start host, then:
set CSS_LIVE_BROWSER_BASE_URL=http://127.0.0.1:8000
pytest -m browser tests/test_phase176c_dashboard_functional_certification.py
```

Mandatory CI path uses ASGI `TestClient` + BeautifulSoup + canonical `ReportsCenterService` workflows (HTTP 200 alone is never a pass criterion).

## Safety

Unchanged:

- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`

## Operator runbook

`docs/runbooks/CSS_DASHBOARD_FUNCTIONAL_ACCEPTANCE_RUNBOOK.md`
