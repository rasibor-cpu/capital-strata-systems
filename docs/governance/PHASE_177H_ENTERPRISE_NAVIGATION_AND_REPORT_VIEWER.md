# PHASE 177H — Enterprise Navigation Shell, Reports Hub & Paginated Viewer

**Status:** Source complete (uncommitted). Controlled restart of `:8090` and `:8765` required to activate live UI.
**Date:** 2026-07-20
**Baseline:** `07df51b75fbe18aab1a9575fd5c00408a8d4dad7`
**Branch:** `css-unified-consolidation-2026-07-13`

---

## Route architecture

| Surface | Canonical landing | Reports hub | Viewer |
|---------|-------------------|-------------|--------|
| Mobile `:8090` | `/dashboard` | `/reports` | `/reports/viewer`, `/api/reports/{id}/view` |
| Mission Control `:8765` | `/mission-control/executive-overview` | `/mission-control/reports` | `/mission-control/reports/viewer`, `/api/options-income/report.viewer` |

Cross-surface Home / Mission Control links use `dashboard/enterprise_shell/routes.py` with optional:

- `CSS_MOBILE_DASHBOARD_BASE_URL` / `CSS_MOBILE_PUBLIC_URL`
- `CSS_MISSION_CONTROL_BASE_URL` / `CSS_LAUNCHER_PUBLIC_URL`

Non-http(s) bases are rejected (no open redirects).

---

## Platform-wide navigation standard

**No CSS module may strand the user inside a subsystem without direct Home and global navigation access.**

Every major page provides:

1. Home in the global / primary navigation
2. CSS brand / logo control returning to the Mobile Dashboard landing (`/dashboard`)

---

## Enterprise shell

Shared package: `dashboard/enterprise_shell/`

- `routes.py` — canonical destinations + cross-surface helpers
- `shell.py` — brand Home, breadcrumbs, mobile primary/More nav, phone footer
- `reports_hub.py` — read-only hub catalogue (available vs coming-soon)

Mission Control `layout.py` consumes the shared brand, Home sidebar item, and navigable breadcrumbs.

Mobile `_top_nav` / `_header` consume the shared shell (no isolated overcrowded button strip).

---

## Mobile navigation model

Primary (phone-safe): **Home · Mission Control · Trade (if permitted) · Reports · More**

More disclosure retains Positions, Execution, Risk, Alerts, Broker Management, Runtime Diagnostics, Certification, Settings, Administration, Options Income deep link, and related modules.

Sticky footer mirrors the primary set on narrow viewports with safe-area padding and 44px touch targets.

---

## Breadcrumb rules

- Landing page: no trail
- Deeper pages: `Home › … › Current`
- Intermediate crumbs are links; current page is `aria-current="page"` without href
- Mobile collapses via flex-wrap

---

## Reports hub

Categories: Executive, Financial, Risk and Operations, Governance.

Entries from the existing Reports Center registry plus honest `COMING_SOON` placeholders. Options Income is a special available card linking to the paginated viewer on the Mission Control surface.

No fabricated financial report bodies.

---

## Report discovery API (GET-only)

- `GET /api/reports`
- `GET /api/reports/categories`
- `GET /api/reports/{report_id}`
- `GET /api/reports/{report_id}/metadata`
- `GET /api/reports/{report_id}/view`

Mounted on mobile and launcher. No delete/modify/execution endpoints.

---

## Paginated viewer

`dashboard/reports_viewer/paginated_viewer.py`

- A4-sized page sheets with shadow/boundary
- Default **one page at a time** (`continuous_scroll_default=false`)
- Previous / Next / page selector / TOC / Print / optional PDF / Home / Back to Reports
- Swipe + keyboard arrows
- Fit-width and readable-text modes for phones
- Print CSS reveals all pages for paper output

Reuses `EnterpriseReportDocument` / Options Income `viewer_hints` — does not create a second reporting framework.

---

## Long-table behavior

Inherited from `backend/broker_reporting/page_layout.py` (line budget, continuation titles, presentation `repeating_table_headers`). Viewer displays pre-paginated pages; it does not hide material columns.

---

## Accessibility

- Landmark header/nav/main/aside
- Visible focus styles on viewer controls
- `aria-live` page indicator
- Labels on icon-adjacent Home / brand controls
- Status badges retain text labels (not color alone)

---

## Runtime status in shell

Shell badges consume existing platform/runtime fields (`runtime_mode`, `execution_state`, broker). No new status calculation in the navigation layer.

Expected live values remain: Runtime `DISABLED`, Execution `BLOCKED`, Mobile access `READ_ONLY`, Broker `NONE`, Options Income `ADVISORY_ONLY`.

---

## Safety confirmation

- Runtime Mode Resolver unchanged
- Platform status / telemetry authority unchanged
- Tier-1 brokers unchanged (no IBKR)
- Options Income remains advisory-only
- Execution remains blocked
- No credentials, operator intent, or ledger changes
- No process restart in this phase

---

## Known limitations

- Reports Center archived instance viewer still opens via existing `/api/v1/reports/{id}/print|pdf`; catalogue codes without instances are not silently fabricated into viewer pages
- Full continuous-to-paginated migration of every historical HTML report is incremental
- Cross-port Home from MC / launcher SPA requires `CSS_MOBILE_DASHBOARD_BASE_URL` when the Mobile Dashboard is on a different host/port than `:8765`
- Launcher SPA Trade primary item opens the local `#trade` screen (paper ticket UI remains blocked by authority); it does not grant execution

---

## Phase 177H.1 — Launcher SPA unification

**Status:** Source complete (uncommitted), bundled with Phase 177H workset.

### Integration

The launcher SPA at `/mobile` consumes `enterprise_nav` from `build_enterprise_navigation_contract(surface="launcher_spa")` injected by `build_mobile_dashboard_context()`.

Read-only API: `GET /api/navigation/enterprise`.

### Canonical navigation contract

`dashboard/enterprise_shell/nav_contract.py` is the source of truth for:

- primary: Home · Mission Control · Trade · Reports · More
- More: Positions, Execution, Risk, Alerts, Runtime (SPA panels), Broker Management, Runtime Diagnostics, Options Income, OI paginated report, Certification, Settings, Administration
- platform status badges (no local calculation)
- Reports hub + paginated viewer hrefs
- PWA start URL metadata and shell cache id `css-launcher-spa-shell-v177h1`

### SPA Home behavior

Brand + Home navigate to `mobile_home_href(for_surface="mission_control")` → `/dashboard` (or configured `CSS_MOBILE_DASHBOARD_BASE_URL`). This is **not** browser Back and **not** the SPA `#home` runtime panel (that panel remains under More → Runtime (Mobile SPA)).

### Reports integration

Primary Reports → `/mission-control/reports`. More → Options Income Report → `/api/options-income/report.viewer` (paginated, continuous_scroll_default false). Discovery via `/api/reports`.

### Cross-surface routes

Same helpers as Phase 177H. Unsafe schemes rejected. No hard-coded localhost/IP in SPA nav contract.

### PWA start and restore

- Manifest `start_url`: `/mobile-launcher` (launcher landing — not Mission Control, not a stale SPA hash)
- SPA may restore last `#screen` via sessionStorage/hash; Home remains available in the enterprise footer
- Shell cache version: `css-launcher-spa-shell-v177h1` (manifest `css_shell_cache`)

### Active-state rules

Exact path or exact spa_screen match via `match_active_destination` / SPA JS. Broad substring matching forbidden.

### Accessibility

Primary nav landmark, More dialog with aria-expanded/aria-controls, Escape closes More, brand aria-label, aria-current on active trade screen, text+icon labels.

### Remaining SPA limitations

- Quick-nav row (Runtime/Trade/Portfolio/Alerts) remains as local shortcuts inside the page body
- Paper trade forms remain in the SPA; badges continue to show execution BLOCKED
- No service worker on the launcher SPA template (manifest-only PWA metadata)

---

## Future enhancements

- Thumbnail strip / search / zoom levels
- Landscape mode for wide tables
- Retire residual SPA quick-nav in favor of More-only secondary access
- Bind Reports Center instance IDs directly into the paginated viewer
