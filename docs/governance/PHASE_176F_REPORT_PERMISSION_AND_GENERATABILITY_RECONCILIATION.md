# Phase 176F — Report Permission Metadata and Generatability Reconciliation

**Baseline:** `782523584dfb1c91034490f687c5e4578d462cd7` (Phase 176E)
**Branch:** `css-unified-consolidation-2026-07-13`
**Status:** Implemented — **DO NOT COMMIT** until explicitly approved.
**Date:** 2026-07-18

## Exact root cause

Frequently Used cards and the Create Report selector consumed
`generatable_selector_options()`, which returned a **reduced DTO** containing only:

- `report_code`, `title`, `status`, `supported_scopes`, `supported_formats`,
  `limitations`, `filter_fields`

It **omitted**:

- `required_view_permission`
- `required_generate_permission`
- `required_print_permission`
- `generatable` (and later effective `can_generate`)

Mission Control `_report_card()` reads those keys via `.get()`, so missing keys
rendered as `None` and `bool(report.get("generatable"))` was `False` →
**Not generatable** for every Frequently Used card — even when page-level
`reports_view` / `reports_generate` were true and the registry definition was
AVAILABLE with a real producer.

Secondary defect: `CSSReportDefinition.as_dict()` did not include the
`generatable` property (dataclass `asdict` skips `@property`), so catalog /
home API payloads lacked the flag.

Category sections already carried permission names; the visible top-of-page
Frequently Used grid was the primary live false-negative surface.

## Field mismatch / serialization defect

| Layer | Defect |
|-------|--------|
| `generatable_selector_options()` | Reduced DTO omitted permission + generatable fields |
| `CSSReportDefinition.as_dict()` | Omitted `generatable` property |
| UI card | Correct key names (`required_*_permission`); `.get()` → `None` on reduced DTO |
| Capability calc | Missing `generatable` treated as denial |

Not a rename mismatch (`view_permission` vs `required_view_permission`) and not
a Phase 176D RBAC denial.

## Canonical UI report-definition contract

`backend/reports_center/capabilities.py`:

- `evaluate_report_capabilities(definition, role=…)`
- `ui_report_definition(definition, role=…)`

Preserved registry field names (never renamed between layers):

`report_type`, `report_code`, `title`, `category`, `status`, `inventory_class`,
`supported_scopes`, `supported_formats`, `producer`, `validator`, `limitations`,
`official_report`, `advisory_only`, `printable`, `downloadable`, `emailable`,
`required_view_permission`, `required_generate_permission`,
`required_print_permission`, `required_email_permission`, `required_admin_action`,
plus effective: `generatable`, `can_view`, `can_generate`, `can_print`, `can_email`,
`generate_label`, `generate_blocked_reason`, `configuration_error`.

## Capability evaluation

1. **Status:** generate only for `AVAILABLE` / `AVAILABLE_WITH_LIMITATIONS`;
   blocked for `COMING_SOON`, `DATA_UNAVAILABLE`, `DISABLED`, `DEPRECATED`.
2. **Producer:** non-empty producer string **and** code in
   `registered_producer_codes()`.
3. **Evidence contract:** supported when producer is registered (per-request
   evidence such as transaction ticket enforced at `produce()` time).
4. **Permissions:** user must pass `ReportsAccessControl` for required generate
   (and view) permissions.
5. **Fail closed:** empty/missing `required_generate_permission` (or view) on a
   status-eligible report → `configuration_error`, never silent
   `reports_generate` grant.

UI may hide controls from `can_generate`; server routes remain authoritative.

## Desktop / mobile parity

Both surfaces call `category_sections(role=…)` /
`generatable_selector_options(role=…)` built from the same
`ui_report_definition` + `evaluate_report_capabilities`.

PWA cache remains **`css-mobile-shell-v176d`** (no static mobile asset change).

## Safety

Unchanged: `advisory_only=true`, `execution_allowed=false`,
`live_trading_blocked=true`, `broker_execution_armed=false`.

## Tests

`tests/test_phase176f_report_permission_and_generatability.py`

## Rollback

Revert Phase 176F files (`capabilities.py`, `ui_contract.py`, `definition.py`
`as_dict`, producers registration helpers, MC/mobile card rendering, service
readiness/home, tests, this doc). Phase 176E route mount on 8765 remains.

## Live evidence

Against Desktop launcher `http://127.0.0.1:8765` after reload:

- HTML: `view=None` count **0**; `View permission: reports_view` present on cards
- `daily_executive_brief` / `safety_lock_report`: `data-generatable="true"`
- Create selector includes generatable codes; Generate preselect works
- `POST /api/v1/reports/generate` `safety_lock_report` → HTTP **200** (e.g. v020/v021)
- Playwright acceptance: `artifacts/tmp/phase176f_reports_acceptance.png` (local evidence; not required in commit)
- SUPER_USER counts: AVAILABLE generatable **19**, AVAILABLE_WITH_LIMITATIONS **13**, total **32**
- Status inventory: COMING_SOON **145**, DATA_UNAVAILABLE **13**, DISABLED **1**
