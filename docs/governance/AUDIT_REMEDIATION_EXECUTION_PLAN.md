# Audit Remediation Execution Plan

## Purpose

This plan defines recommended remediation sequencing based on ARP-001 verification. It is documentation-only and does not implement any code, tests, runtime behavior, dashboard behavior, broker behavior, execution behavior, risk-control behavior, margin behavior, security behavior, authentication, authorization, credential, or trading logic changes.

## Execution Principles

* Remediate verified safety and security gaps before cleanup work.
* Preserve existing CSS authority boundaries.
* Do not introduce new trade authority while wiring controls.
* Add tests before or with any future code remediation.
* Keep each remediation phase small enough for Robert review.
* Treat non-canonical files separately from canonical runtime paths.

## Recommended Sequence

### ARP-002 - Live Authorization and Two-Key Arming

**Findings:** B-02, B-09

**Objective:** Replace hardcoded live identity with RBAC/SUPER_USER authorization and integrate `live_arm` into the same canonical live boundary.

**Estimated Effort:** Medium

**Risk:** High if done incorrectly, because this controls LIVE execution authorization.

**Dependencies:**

* Confirm canonical live entrypoint.
* Confirm RBAC/SUPER_USER role source.
* Confirm audit context requirements.

**Recommended Implementation:**

* Update `backend/app/security/live_toggle.py` to require approved role/permission.
* Call `backend.app.ops.live_arm.assert_live_armed_or_block()` inside the live boundary.
* Add tests for TEST mode blocked, LIVE unauthorized blocked, LIVE authorized but unarmed blocked, LIVE authorized and armed allowed.

### ARP-003 - Margin Gate Enforcement Design and Integration

**Findings:** B-04

**Objective:** Wire MarginTradeGate into the approved trade permission path without bypassing CSSUnifiedTradeGate, broker controls, or capital governor.

**Estimated Effort:** Medium to High

**Risk:** High because this changes trade permission behavior.

**Dependencies:**

* Declare canonical trade permission path.
* Decide whether margin enforcement belongs inside CSSUnifiedTradeGate or a unified decision envelope before CSSUnifiedTradeGate approval.
* Confirm broker mode and margin snapshot source.

**Recommended Implementation:**

* Add margin gate input to the canonical trade decision flow.
* Ensure LIVE UNKNOWN margin state fails closed.
* Keep dashboard display-only behavior separate.
* Add tests for all margin state bands.

### ARP-004 - AntiBleedGuard Integration Decision

**Findings:** B-01

**Objective:** Either integrate AntiBleedGuard into the canonical trade decision path or formally retire it as non-authoritative.

**Estimated Effort:** Medium

**Risk:** Medium to High because cost-aware rejection can change trade eligibility.

**Dependencies:**

* Define required candidate fields for expected move, fee, spread, slippage, trade size, and side.
* Decide whether AntiBleedGuard output blocks trades or feeds a broader risk decision envelope.

**Recommended Implementation:**

* If integrated, insert after candidate validation and before final trade approval.
* Add tests for insufficient edge, expected move below cost, too-small trade, cooldown, and approved cases.
* Add audit/log evidence for rejected trades.

### ARP-005 - Runtime Parse and Clean-Clone Reproducibility

**Findings:** B-06, B-10

**Objective:** Fix current canonical syntax failure and resolve ignored/untracked dashboard import dependency.

**Estimated Effort:** Low to Medium

**Risk:** Medium because import path changes can affect dashboard/runtime data loading.

**Dependencies:**

* Decide whether `backend/data/coinbase_historical_downloader.py` is source code or generated/local data.
* Confirm whether `css_live_dashboard_v5.py` remains runnable/canonical.

**Recommended Implementation:**

* Fix `engine/reports/ticket_formatter.py` syntax.
* Normalize BOM-prefixed canonical files in a mechanical cleanup phase.
* Track/move `coinbase_historical_downloader.py` if source code, or remove the import from non-canonical dashboard file.
* Add compile checks for affected files.

### ARP-006 - Dashboard Canonicalization

**Findings:** B-03, B-10

**Objective:** Decide and document whether root `css_live_dashboard_v5.py` is legacy or supported. Remove shadowed duplicate functions if supported.

**Estimated Effort:** Medium

**Risk:** Medium because dashboard files have historically accumulated runtime logic.

**Dependencies:**

* Confirm canonical dashboard entrypoint.
* Confirm supported dashboard files.

**Recommended Implementation:**

* If legacy, move to archive or mark clearly non-canonical.
* If supported, consolidate `display_dashboard` and `execute_trade`.
* Add compile/import checks for supported dashboard entrypoints.

### ARP-007 - CSSUnifiedTradeGate Authority Consolidation

**Findings:** B-07

**Objective:** Declare and enforce a single canonical CSSUnifiedTradeGate authority.

**Estimated Effort:** Medium

**Risk:** Medium because dashboard-local gate logic may differ from backend gate logic.

**Dependencies:**

* Decide canonical owner, likely `backend/governance/css_unified_trade_gate.py`.
* Confirm whether dashboard should consume canonical decisions or only display externally produced decisions.

**Recommended Implementation:**

* Replace local dashboard gate definitions with imports or display-only adapters.
* Retire build scripts or mark them non-runtime.
* Add tests checking backend and dashboard import boundaries.

### ARP-008 - RiskGovernor Authority Consolidation

**Findings:** B-08

**Objective:** Declare a single canonical RiskGovernor and deprecate or wrap alternate definitions.

**Estimated Effort:** Medium to High

**Risk:** Medium because risk governor behavior differs between definitions.

**Dependencies:**

* Confirm canonical execution path and risk test coverage.
* Identify any legacy consumers of backend variants.

**Recommended Implementation:**

* Declare `engine/risk/risk_governor.py` canonical if confirmed by Robert.
* Convert alternate definitions to wrappers, compatibility shims, or deprecated modules.
* Add import-boundary tests.

### ARP-009 - Compliance Package Boundary Review

**Findings:** B-05

**Objective:** Review package exports and repository dependencies after more urgent safety work.

**Estimated Effort:** Low

**Risk:** Low based on current verification because import failure did not reproduce.

**Dependencies:**

* Capture any failing import path if one exists in CI or Robert's environment.

**Recommended Implementation:**

* Avoid immediate code change unless failure reproduces.
* Consider removing persistence repository export from `backend.app.compliance.__init__` in a cleanup phase.

## Final Recommended Sequence

1. ARP-002 - Live Authorization and Two-Key Arming.
2. ARP-003 - Margin Gate Enforcement Design and Integration.
3. ARP-004 - AntiBleedGuard Integration Decision.
4. ARP-005 - Runtime Parse and Clean-Clone Reproducibility.
5. ARP-006 - Dashboard Canonicalization.
6. ARP-007 - CSSUnifiedTradeGate Authority Consolidation.
7. ARP-008 - RiskGovernor Authority Consolidation.
8. ARP-009 - Compliance Package Boundary Review.

## Certification Note

No remediation implementation should begin until Robert reviews ARP-001 findings, classifications, priority matrix, and execution plan.
