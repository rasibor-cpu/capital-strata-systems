# CSS Issue Log (Operational + Dev)

Purpose:
- Maintain a repo-native record of issues, root causes, fixes, and prevention controls.
- Supports auditability, onboarding, and faster troubleshooting.
- This is NOT a changelog. It is an issue register.

Conventions:
- Status: OPEN | MITIGATED | CLOSED
- Severity: P0 (blocking) | P1 (high) | P2 (medium) | P3 (low)
- Category: DATA | RUNNER | GOVERNANCE | REPORTING | UX | ENV | CI
- Every issue must include: Symptom, Trigger, Root cause, Fix, Prevention.

---

## Index
- 2026-02: Phase 1 replay runner issues, output overload, long-run stalls
- 2026-02: Reporting/printing requirements expansion + governance controls
- 2026-02: Posting calendar/date-control + overrides not yet implemented

---

## Issues

### CSS-ISSUE-0001 — Runner output overload (“too many lines / too many rows”)
- Date first seen: 2026-02 (multiple sessions)
- Status: MITIGATED
- Severity: P1
- Category: RUNNER / UX
- Symptom:
  - CLI runners printed excessive tables/rows; difficult to read; slowed terminal.
- Trigger:
  - Diagnostics returning full trade lists / full bar-by-bar prints.
- Root cause:
  - Lack of paging/summary-first output policy.
- Fix:
  - Prefer summary blocks: counts, min/avg/max, top-N samples, write full detail to CSV/JSON.
- Prevention:
  - Standard runner output contract:
    1) summary header
    2) top-N samples (N<=20)
    3) save full artifacts to audit/ or reports/
    4) print artifact paths

---

### CSS-ISSUE-0002 — Runner appeared to “freeze” / PowerShell no response
- Date first seen: 2026-02
- Status: MITIGATED
- Severity: P1
- Category: RUNNER / ENV
- Symptom:
  - Long waits; perceived hang; required stopping other run; no prompt return.
- Trigger:
  - Long backtests + large CSV parsing + verbose logging.
- Root cause:
  - Heavy compute + no progress indicator; sometimes blocked by large IO.
- Fix:
  - Add progress heartbeat: every X bars print “processed n / total”.
  - Add timing checkpoints and guardrails.
- Prevention:
  - All long runners must show:
    - start time
    - total bars
    - progress every 5–10%
    - end time + runtime

---

### CSS-ISSUE-0003 — Confusing gate semantics (ok=True vs final=="ALLOW")
- Date first seen: 2026-02
- Status: CLOSED
- Severity: P0
- Category: GOVERNANCE
- Symptom:
  - Diagnostics incorrectly interpreted ExecutionGate decisions; miscounted blocks/approvals.
- Trigger:
  - Some decisions used `decision.final == "ALLOW"` and/or status strings rather than `ok=True`.
- Root cause:
  - Gate output contract not normalized across runners.
- Fix:
  - Updated diagnostic harness to treat `final=="ALLOW"` as canonical, and only count gate_blocks when actually blocked.
- Prevention:
  - GateDecision contract baseline:
    - decision.final in {ALLOW, BLOCK}
    - decision.reason required
    - runner must use decision.final only

---

### CSS-ISSUE-0004 — Path/root confusion (scripts saving relative to CWD)
- Date first seen: 2026-02
- Status: CLOSED
- Severity: P1
- Category: DATA / ENV
- Symptom:
  - Data outputs written to unexpected folders depending on where script launched.
- Trigger:
  - Running scripts from tools/ vs repo root.
- Root cause:
  - Using relative paths from current working directory rather than repo root.
- Fix:
  - Standardized “REPO_ROOT = Path(__file__).resolve().parents[n]” pattern.
- Prevention:
  - New scripts must:
    - derive repo root
    - create output dirs
    - print output paths

---

### CSS-ISSUE-0005 — Data volume too large for first-pass diagnostics
- Date first seen: 2026-02
- Status: MITIGATED
- Severity: P2
- Category: DATA / RUNNER
- Symptom:
  - “Option A produced too many results” and similar; diagnostic unusable without slicing.
- Trigger:
  - Running full-year or multi-instrument diagnostics without sampling.
- Root cause:
  - No default slicing policy.
- Fix:
  - Introduced “1-week slice” and “top-N” reporting.
- Prevention:
  - Default diagnostics = (time slice) + (top-N) + artifacts saved.

---

### CSS-ISSUE-0006 — Missing override logging framework (audit weakness)
- Date first seen: 2026-02
- Status: OPEN
- Severity: P0
- Category: GOVERNANCE / REPORTING
- Symptom:
  - Overrides (e.g., back-dated cheque posting) lack immutable audit log.
- Trigger:
  - Requirements expansion: authority gating + override evidence.
- Root cause:
  - Override model not yet implemented in posting pipeline.
- Fix (planned):
  - Append-only override log:
    - timestamp_utc, user_id, override_type, target, old_value, new_value, reason, approver_id, approval_level, hash_prev, hash_this
- Prevention:
  - Fail closed: posting requiring override must not proceed without a valid override record.

---

### CSS-ISSUE-0007 — Posting calendar accepts invalid dates / uncontrolled backdating
- Date first seen: 2026-02
- Status: OPEN
- Severity: P0
- Category: GOVERNANCE
- Symptom:
  - Risk of unauthorized back-valued entries; audit/reconciliation issues.
- Trigger:
  - Cheques and postings can be backdated without proper authority.
- Root cause:
  - Missing “PostingDatePolicy” gate and override enforcement.
- Fix (planned):
  - Add PostingDatePolicy:
    - reject invalid dates
    - backdating beyond threshold requires override + approval
- Prevention:
  - Every posting stores:
    - input_date, effective_date, policy_result, override_id (optional)

---

### CSS-ISSUE-0008 — Need structured end-of-day / month-end / year-end snapshots
- Date first seen: 2026-02
- Status: OPEN
- Severity: P1
- Category: REPORTING
- Symptom:
  - Auditors require frozen snapshots; current system is real-time but not “period-closed”.
- Trigger:
  - New requirement: daily pages per user; month-end GL snapshots; year-end consolidated BS/IS.
- Root cause:
  - Snapshot engine not yet implemented.
- Fix (planned):
  - EOD snapshot: journal digest + GL balances freeze
  - Month-end: GL snapshot with integrity hash
  - Year-end: consolidated BS/IS; auto rollover to new FY
- Prevention:
  - Period close produces:
    - snapshot.json
    - printable report
    - integrity hash + version

---

### CSS-ISSUE-0009 — Need “Print from any screen” review capability
- Date first seen: 2026-02
- Status: OPEN
- Severity: P2
- Category: UX / REPORTING
- Symptom:
  - Review workflows require ad-hoc print/export anywhere.
- Trigger:
  - Auditor/end-of-day batch review requirement.
- Root cause:
  - Reporting not yet wired into UI workflows.
- Fix (planned):
  - Standard ReportRegistry + ExportService (PDF/HTML later; start with text/CSV).
- Prevention:
  - Every UI module registers its reports and can generate print artifacts by date range.

---

## Template for New Issues

### CSS-ISSUE-XXXX — <Title>
- Date first seen:
- Status:
- Severity:
- Category:
- Symptom:
- Trigger:
- Root cause:
- Fix:
- Prevention:
- Notes/Links: