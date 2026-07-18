# Phase 176 — CSS Institutional Reports Center

**Status:** Implemented (catalogue + framework + evidence-backed producers)
**Baseline:** `21620dfb94f04bb0e25dc6a074d23f0b7d28d7f7` (Phase 175)
**Branch:** `css-unified-consolidation-2026-07-13`
**Contract:** `css.institutional_reports_center.v1`

## Mission

Create one first-class **Reports** gateway in Mission Control for every printable,
downloadable, archived, or distributable report CSS can safely support — without
fabricating financial statements or weakening safety / RBAC / audit controls.

## Report capability inventory (summary)

| Class | Meaning | Phase 176 handling |
|---|---|---|
| IMPLEMENTED_AND_RELIABLE | Producer + evidence + validation path exist | `AVAILABLE` / wired |
| IMPLEMENTED_BUT_NOT_REGISTERED | Existing engine/CLI producers | Registered + wrapped where safe |
| PARTIAL | Some evidence, incomplete accounting | `AVAILABLE_WITH_LIMITATIONS` or `COMING_SOON` |
| DATA_AVAILABLE_BUT_NO_REPORT | Evidence exists, no official producer | `COMING_SOON` |
| DATA_INSUFFICIENT | Cannot support official report | `DATA_UNAVAILABLE` / `COMING_SOON` |
| FUTURE_CAPABILITY | Roadmap only | `COMING_SOON` |
| PROHIBITED_OR_NOT_APPLICABLE | e.g. live execution while blocked | `DISABLED` |

Full row-level matrix: `docs/governance/CSS_INSTITUTIONAL_REPORT_CAPABILITY_MATRIX.md`.

## Canonical registry

Package: `backend/reports_center/`

- `definition.py` — `CSSReportDefinition`
- `catalogue.py` — full institutional catalogue (unique `report_code`)
- `registry.py` — catalog/search/category APIs
- `service.py` — home, readiness, generate, library, print, export, audit
- `producers.py` — evidence-backed producers only
- `archive.py` — `artifacts/runtime_reports/reports/<family>/<type>/YYYY/MM/YYYY-MM-DD/vNNN/`
- `audit.py` — unified `report_audit.jsonl`
- `rbac.py` — server-side authorization
- `routes.py` — `/api/v1/reports/...`

Morning Brief archive path is **preserved**:
`artifacts/runtime_reports/morning_briefings/...` (Phases 174/175).

## Navigation

Top-level Mission Control item: **Reports** (`reports_center`).

Logical submenu (category API + home page):

- Report Home / Create Report / Report Library
- Trading & Transactions
- Portfolio & Performance
- Accounts & Cash
- Risk & Exposure
- Broker & Execution
- Treasury
- Compliance & Audit
- Operations & System
- Executive Intelligence
- Distribution & Print Audit

Navigation count updated **15 → 16** (contracts validation).

## Available / limited reports (generatable)

**AVAILABLE**

- Daily Executive Brief (bridge to Phase 174/175)
- Overnight Market Intelligence
- Executive KPI / Actions / Risk / Operational Health extracts
- Daily Brief Distribution Report
- Safety-Lock Report
- Broker Health (sanitized)
- Runtime Health
- Report access / print / email distribution audits
- Archived Report Manifest
- Report Integrity Verification
- Staff Print-Grant Report
- Advisory-Only Compliance
- Report Generation Failures
- Distribution & Print Audit Summary

**AVAILABLE_WITH_LIMITATIONS**

- Transaction Journal / Trade Journal (PnL ledger evidence only)
- Transaction Ticket (supplied evidence or ledger ticket)
- Account Statement (limitation banner; not a complete official ledger statement)
- Portfolio Summary / PnL Report / Risk Summary
- Historical Executive Brief Comparison (KPI/metadata)
- FinCon: AR/AP/GL ageing, governance_summary, supervisory_control_pack

All other catalogue entries are `COMING_SOON`, `DATA_UNAVAILABLE`, or `DISABLED`
(notably `live_execution_activity` while `live_trading_blocked=true`).

## Create-report flow

1. Select `report_code` from catalogue
2. `GET .../readiness/{report_code}`
3. Supply safe filters (dates, account, user, …)
4. `POST /api/v1/reports/generate`
5. Receive report ID / version / hash / blockers / authorized actions

Unsafe filters (path traversal, SQL metacharacters, oversized values) are rejected.

## Printing / PDF / export

- Printable HTML: `GET /api/v1/reports/{report_id}/print` (RBAC + audit)
- FAILED/DRAFT: diagnostic preview banner only
- Executive Brief PDF remains on `/api/v1/executive-brief/{date}/pdf`
- Structured export: JSON (and CSV where producer supplies it — transaction/trade journals only)
- XLSX: **not claimed** (not implemented)
- PDF: claimed only for Daily Executive Brief (Phase 175 native PDF). Other reports use HTML print; `/pdf` endpoints do not claim native PDF for non-brief reports.

## Email policies

| Family | Policy |
|---|---|
| Default | `EMAIL_DISABLED` |
| Daily Executive Brief | Phase 175 unchanged: ADMIN/SUPER_USER send & receive only; STAFF cannot send/receive; no external recipients |
| Other families | Explicit future policy required before enablement |

`POST /api/v1/reports/{id}/email` returns `EMAIL_DISABLED`.

## RBAC

Permissions (ADMIN/SUPER_USER):

- `reports_view`, `reports_generate`, `reports_admin`, `reports_print_all`, `reports_export`, `reports_audit_view`
- Family print: `executive_brief_print`, `transaction_ticket_print`, `trade_journal_print`, `account_statement_print`, `portfolio_report_print`, `risk_report_print`

Legacy `view_reports` still satisfies view checks. STAFF receives only explicit grants. Menu visibility never grants authority.

## Archive / versioning

- No silent overwrite of FINAL versions
- FAILED stored under `.../FAILED/vNNN/`
- `manifest.json`, `validation.json`, `provenance.json`, content files
- Hash integrity verification API

## APIs

**Mission Control (GET-only)**

- `/mission-control/api/reports/catalog`
- `/mission-control/api/reports/home`
- `/mission-control/api/reports/categories`
- `/mission-control/api/reports/definitions/{code}`
- `/mission-control/api/reports/readiness/{code}`
- `/mission-control/api/reports`
- `/mission-control/api/reports/{id}` (+ versions, print info, pdf info, audit)

**Controlled writes**

- `POST /api/v1/reports/generate`
- `POST /api/v1/reports/{id}/print-audit`
- `POST /api/v1/reports/{id}/verify-integrity`
- `POST /api/v1/reports/{id}/email` → disabled

## Security / safety

Preserved locks:

- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`

No credentials in broker reports; no arbitrary filesystem access; no fabricated statements.

## FinCon printer fix

Restored `engine/reporting/treasury_instrument_aggregate.py` as a **fail-closed stub** so
`engine.reporting.report_printer` imports again. Treasury aggregate remains
`DATA_UNAVAILABLE` / not official.

## Operational instructions

1. Open Mission Control → **Reports**
2. Inspect catalogue / readiness
3. Generate via `/api/v1/reports/generate` with `X-CSS-Role` / `X-CSS-User-Id`
4. Print via `/api/v1/reports/{id}/print` when permitted
5. Executive brief email continues via `/api/v1/executive-brief`

## Limitations

- Many portfolio/risk/treasury/compliance reports are registered but not generatable
- Account Statement is explicitly limited (incomplete ledger)
- PDF for non-brief reports uses HTML print fallback in this phase
- Favorites/pinned UI deferred (API/home placeholders only)

## Rollback

Revert Phase 176 commit; remove `backend/reports_center`, Reports nav entry, and
permissions additions. Morning brief archive unaffected.

## Tests

`tests/test_phase176_institutional_reports_center.py` plus regression of 174/175,
Mission Control, RBAC, and printer import.

## Future roadmap

Wire additional producers only when evidence, validation, permissions, and
identity/versioning are complete. Enable email per family only with explicit policy.

## Phase 176A — Interaction and mobile integration

See `docs/governance/PHASE_176A_REPORTS_CENTER_INTERACTION_AND_MOBILE_INTEGRATION.md`.

**Desktop root cause:** Reports page was static tables only (no accordions/buttons/forms/JS).

**Mobile root cause:** `_top_nav` / Command Center omitted Reports; no `/reports*` routes.

**Remediation:** Interactive MC Reports UI; shared `ui_contract`; mobile Reports home/create/library/detail; SW cache `css-mobile-shell-v176a`. Registry/producers/RBAC/safety unchanged.
