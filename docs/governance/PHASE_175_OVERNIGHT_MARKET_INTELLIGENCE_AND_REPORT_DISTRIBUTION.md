# PHASE 175 — Overnight Market Intelligence, Daily Executive Brief Distribution, and Controlled Printing

**Repository:** `C:\rasib\source\capital-strata-systems`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Baseline:** `a380cc33910af5b3410713faa6626722347cf904`  
**Status:** IMPLEMENTATION COMPLETE — awaiting explicit commit/push approval  
**Date:** 2026-07-18  

---

## 1. Root Cause of the First FAILED Brief

Phase 174 correctly fail-closed with `market_panel_unavailable` because:

1. `evidence._load_market` set `overnight_market_summary: None` and only returned a market block when regime artifacts existed.
2. On environments without regime/advisory artifacts, the market panel was empty → validator blocked FINAL.
3. Freeze v1.0 requires Market panel availability for FINAL; Phase 174 did **not** weaken that gate.

Phase 175 supplies the missing **Overnight Market Intelligence Producer** so real CSS evidence can populate the market panel without fabricating data.

---

## 2. Implementation Plan (executed)

1. Pre-flight verify baseline HEAD.  
2. Map print/email/RBAC infrastructure.  
3. Resolve Mission Control POST vs Freeze GET-only conflict (see §3).  
4. Implement overnight producer + Phase 174 integration.  
5. Implement printable HTML/PDF, RBAC grants, email distribution (mocked).  
6. Wire APIs, tests, documentation.  
7. **Stop before commit/push.**

---

## 3. Architecture Freeze Conflict and Resolution

| Conflict | Freeze / host rule | Phase 175 prompt | Resolution (no freeze change) |
|---|---|---|---|
| POST under `/mission-control/...` | MC router rejects POST/PUT/PATCH/DELETE at registration; Freeze APIs are GET-only | Suggested POST email/print-audit under MC | **Controlled writes live under `/api/v1/executive-brief/...`**. MC exposes GET status/info only. |

This follows the prompt’s “adjusted to existing route conventions” clause and does **not** alter `host_registration` or Freeze v1.0.

---

## 4. Overnight Market Intelligence Producer

**Module:** `backend/executive_intelligence/overnight_market.py`  
**Contract:** `css.overnight_market_intelligence.v1`

### Evidence inputs (existing CSS artifacts)

- `artifacts/runtime_advisory_snapshot.json`  
- `artifacts/portfolio_decision.json`  
- `artifacts/portfolio_snapshot.json` / `runtime_portfolio_state.json`  
- `artifacts/css_session_state_pcnrass.json`  
- Optional injected test bundles  

### Outputs

- reporting window, provenance, source hashes, freshness, validation_status, market_data_status  
- asset-class coverage (FX/Crypto/Futures/Options/Equities/Fixed Income/Commodities) — UNAVAILABLE when absent  
- overnight summary (instruments, movers, vol/liquidity, regime transitions, warnings)  
- market regime (executive ontology mapped from engine labels; gate enums untouched)  
- market confidence (coverage × regime confidence × agreement × freshness)  
- advisory trading implications (MONITOR/OBSERVE/PREPARE/HEDGE/AVOID/REVIEW)  
- opportunity_input seeds for Phase 174 ranking (does not replace it)  

### Integration

- `evidence._load_market` calls producer  
- Assembler Market panel consumes overnight summary + market_confidence  
- Scoring uses market_confidence.value  
- Validator unchanged — still blocks FINAL on market UNAVAILABLE  

---

## 5. Printable Report Architecture

### Reused framework

- Sign-off conventions from `engine/reporting/report_printer.py` (`Printed by`, generated timestamp)  
- Sanitizer from Phase 174  
- No second ticket subsystem; transaction tickets untouched  

### Formats

1. Printer-friendly HTML — `print_report.render_printable_html`  
2. PDF — pure-Python minimal PDF writer (no new dependency; reserved archive filename)  
3. Existing JSON + Markdown archive  

### Rules

- Official print/PDF **FINAL only**  
- Secrets redacted  
- Advisory banner + safety locks always present  
- PDF archived beside FINAL version; hash in version `manifest.json`  
- PDF failure → `printable_status=PARTIAL`; JSON/MD FINAL preserved  

---

## 6. RBAC Permissions and Admin Designation

| Permission | Who |
|---|---|
| `executive_brief_print` | ADMIN, SUPER_USER; or staff with active **print-only** grant |
| `executive_brief_email` | **ADMIN and SUPER_USER only** — intrinsically role-gated, **not delegable** |
| `manage_executive_brief_grants` | ADMIN, SUPER_USER (print grants only) |

**Staff grants:** print designation only under  
`artifacts/runtime_reports/executive_intelligence_archive/rbac/staff_grants.json`  

- Attempting to grant `executive_brief_email` to STAFF returns `EMAIL_GRANT_NOT_DELEGABLE`  
- Legacy email entries in grant files are ignored for authorization  
- Print grant never implies email send or email receive eligibility  

### Email sender policy (corrected)

Manual send: **SUPER_USER** and **ADMIN** only. STAFF cannot send.

### Email recipient policy (corrected)

Official DEB email recipients must resolve to **active CSS users** whose role is
**SUPER_USER** or **ADMIN** only.

- No STAFF recipients  
- No arbitrary external addresses  
- No mixed eligible/ineligible lists (reject entire list)  
- Server-side revalidation at send time even if a list was previously approved  
- Failure reason: `RECIPIENT_ROLE_NOT_AUTHORIZED`  
- Audit records store eligible/rejected counts without exposing full addresses  

---

## 7. Email Distribution

- Transport disabled by default → `NOT_CONFIGURED`  
- `CSS_EXEC_BRIEF_EMAIL_TRANSPORT=mock` enables mock (tests)  
- Recipient lists: **ADMIN/SUPER_USER CSS user IDs only** (validated at upsert and send)  
- Direct recipient payload fields rejected (`RECIPIENT_ROLE_NOT_AUTHORIZED`)  
- FINAL-only; PDF attachment hash recorded  
- No real SMTP during development/tests  
- Reuses dry-run philosophy of `EmailNotificationProvider`  

---

## 8. Mission Control / API Surface

### MC (GET-only)

- `.../distribution-status`  
- `.../print` and `.../pdf` return **pointers** to controlled `/api/v1` endpoints  

### Controlled writes (`/api/v1/executive-brief`)

- GET authorization, print HTML, PDF, histories  
- POST email, print-audit, grants designate/revoke, recipient-lists  

Registered in `dashboard/web/web_app.py`.

---

## 9. Archive Changes

FINAL version directory may now include:

- `executive_morning_brief.json`  
- `executive_morning_brief.md`  
- `executive_morning_brief.pdf` (when generation succeeds)  
- `manifest.json` (includes `pdf.sha256`, `printable_status`)  
- `validation.json`  

---

## 10. Tests

`tests/test_phase175_overnight_market_and_distribution.py` plus Phase 174/159A regressions.

---

## 11. Operational Instructions

1. Ensure regime/advisory/portfolio artifacts exist for overnight producer coverage.  
2. Generate brief via `ExecutiveIntelligenceEngine.generate(...)`.  
3. Print/PDF: call `/api/v1/executive-brief/{date}/print|pdf` with headers `X-CSS-Role` and `X-CSS-User-Id`.  
4. Email: configure recipient list as ADMIN; set transport env only when intentionally enabling mock/provider; default remains NOT_CONFIGURED.  
5. Designate staff: `POST /api/v1/executive-brief/grants/designate`.  

---

## 12. Security Controls

- FINAL-only official printables  
- Secret sanitization on brief + printables  
- RBAC server-side  
- Recipient list governance  
- Audit JSONL for print/email  
- No credentials in reports/emails  
- MC write surface unchanged  

---

## 13. Failure Behavior

| Failure | Behavior |
|---|---|
| Missing/stale market | Producer FAIL; brief market panel UNAVAILABLE; FINAL blocked |
| PDF generation error | FINAL JSON/MD kept; printable PARTIAL |
| Unauthorized print/email | DENIED + audit |
| Email not configured | NOT_CONFIGURED (non-fatal to brief generation) |

---

## 14. Limitations

1. PDF is a minimal text PDF (not full CSS visual design).  
2. Scheduled daily email cron not implemented (API + service ready).  
3. Header-based role identity is explicit test/ops convention; integrate with live auth session next.  
4. Mobile launcher may need the same `/api/v1/executive-brief` router registration if used as sole host.  

---

## 15. Rollback

Revert Phase 175 modules and route registrations; Phase 174 validator/archive behavior remains intact. Grant/distribution artifacts under `artifacts/` are gitignored.

---

## 16. Safety Statement

All Phase 175 outputs remain:

- `advisory_only=true`  
- `execution_allowed=false`  
- `live_trading_blocked=true`  
- `broker_execution_armed=false`  

No live trading, order routing, credential changes, or real external email during implementation/tests.
