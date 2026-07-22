# CSS Audit Remediation Register

**Programme:** Release Gate 2 — Audit Remediation  
**Phase:** AR-001 — Canonical Audit Remediation Register  
**Document type:** Project governance only (no application code changes)  
**Authority source:** `CSS_V1_MASTER_COMPLETION_AUDIT.md` (2026-07-21)  
**Baseline HEAD:** `4ea738d86c167373deccbe4edf217e929de4414d`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Register status:** ACTIVE — Final Close-Out; Batch 2 COMPLETE (AR-011 CLOSED / NOT_CERTIFIED disposition; AR-013/014/040 partial residuals operational); next Batch 3 when authorized

## Input provenance

| Required input | Repository status | Use in this register |
| --- | --- | --- |
| `CSS_V1_MASTER_COMPLETION_AUDIT.md` | Present at repository root | Sole authoritative finding source |
| CSS Executive PMO Pack | **Not found** as a tracked repository artifact | Programme objectives inferred from audit §8–§10 |
| CSS Executive Audit Remediation Register | **Not found** as a tracked repository artifact | This document establishes the canonical register |

Only confirmed Master Audit findings are registered. No speculative items are added.

## Severity model

| Severity | Meaning |
| --- | --- |
| Critical | Blocks honest Production Certification / Release Gate 2 exit |
| High | Blocks safe broader rollout or creates material misrepresentation risk |
| Medium | Hardening required before commercial exposure or sustained operations |
| Low | Hygiene / clarity; does not block controlled-paper operation |

## Status model

`OPEN` · `IN_PROGRESS` · `BLOCKED` · `WAIVED` · `CLOSED` · `PARTIALLY CLOSED`

Effort band: `S` ≤ 2 days · `M` 3–5 days · `L` 1–2 weeks · `XL` > 2 weeks

---

## Register index

| ID | Subsystem | Severity | Effort | Status | Title |
| --- | --- | --- | --- | --- | --- |
| AR-001 | Documentation / Release | Critical | S | CLOSED | Reconcile contradictory production GO claims |
| AR-002 | Release hygiene | Critical | M | CLOSED | Clean worktree and evidence custody |
| AR-003 | Governance ownership | High | S | CLOSED | Assign accountable owners / CODEOWNERS |
| AR-004 | Documentation | High | S | CLOSED | Canonical README and release status page |
| AR-005 | Testing | Critical | S | CLOSED | Resolve or waive Phase 153i regression |
| AR-006 | Trading Engine | Critical | L | CLOSED | Designate singular paper trading authority |
| AR-007 | Execution Pipeline | Critical | XL | CLOSED | Replace synthetic unified-execution acceptance |
| AR-008 | Asset Lifecycle | Critical | L | CLOSED | Align equities taxonomy and strict persistence |
| AR-009 | Health Checks | Critical | M | CLOSED | Eliminate fail-open empty-check scoring |
| AR-010 | Health / Certification | Critical | M | CLOSED | Fail-closed missing telemetry in HealthValidator |
| AR-011 | Production Certification | Critical | L | CLOSED | Capture verified Phase 181 evidence package |
| AR-012 | Testing Framework | Critical | M | CLOSED | Current-SHA compile and bounded regression evidence |
| AR-013 | Readiness / OAT | Critical | L | PARTIALLY CLOSED | Execute and archive Operational Acceptance Testing |
| AR-014 | Performance / Endurance | Critical | XL | PARTIALLY CLOSED | Wall-clock endurance evidence (non-simulated) |
| AR-015 | Business Continuity | Critical | L | CLOSED | Backup / restore drill with measured RTO/RPO |
| AR-016 | Deployment | Critical | XL | CLOSED | Establish CI gates and controlled CD path |
| AR-017 | Institutional Reporting | Critical | XL | PARTIALLY CLOSED | Define and deliver V1 report MVP; honest catalogue |
| AR-018 | Executive Dashboards | High | L | CLOSED | Decide EIS/dashboard scope; commit or defer 182A |
| AR-019 | Audit Framework | High | L | OPEN | Canonical append-only enterprise audit authority |
| AR-020 | ISO 27001 Readiness | High | XL | OPEN | Replace fixture scores with control evidence |
| AR-021 | ISO 9001 Readiness | High | XL | OPEN | Replace fixture scores with QMS evidence |
| AR-022 | Notification System | Critical | L | PARTIALLY CLOSED | Real notification transports and startup wiring |
| AR-023 | Mobile / Security | Critical | M | CLOSED | Remove default credentials; strengthen auth policy |
| AR-024 | API Layer | Critical | L | CLOSED | Authenticate mutations; durable sessions; CSRF |
| AR-025 | PWA | High | M | PARTIALLY CLOSED | HTTPS installability and dual-manifest clarity |
| AR-026 | OANDA / Broker | Critical | M | CLOSED | Isolate/deprecate legacy executable OANDA methods |
| AR-027 | IBKR | High | S | CLOSED | Quarantine misleading IBKR ready health |
| AR-028 | Operations Centre | High | M | CLOSED | Host-activate OperationsService with required checks |
| AR-029 | Observability | High | L | CLOSED | Activate metrics persistence and external export |
| AR-030 | Monitoring | High | L | CLOSED | Retention, consolidation, independent monitoring |
| AR-031 | Options Income | High | L | CLOSED | Advisory data-provider activation (non-live) |
| AR-032 | Configuration | High | M | CLOSED | Review/commit Phase 181A bootstrap; remove aliases |
| AR-033 | Security / Identity | High | L | PARTIALLY CLOSED | Complete secret authority migration and activation |
| AR-034 | Risk Engine | High | M | OPEN | Constrain/remove low-information validate_trade path |
| AR-035 | Risk Committee | Medium | S | OPEN | Treat missing supervisor evidence as concern |
| AR-036 | Portfolio Engine | Medium | M | OPEN | Fail closed on corrupted decision history |
| AR-037 | Architecture | Medium | L | OPEN | Consolidate duplicate runtime/broker/risk authorities |
| AR-038 | Runtime | Medium | M | OPEN | Mandatory heartbeat after grace; snapshot consolidation |
| AR-039 | Mission Control | Medium | M | OPEN | Enforce authenticated session on all MC routes |
| AR-040 | Broker Connectivity | High | M | PARTIALLY CLOSED | Fresh approved Coinbase/OANDA read-only evidence |
| AR-041 | Governance Framework | High | M | OPEN | Ingest independently verified governance evidence |
| AR-042 | Executive Reporting | High | L | PARTIALLY CLOSED | Production feeds; distinguish management vs audited |
| AR-043 | Testing Framework | Medium | M | OPEN | Markers, coverage gate, lint/type/security CI |
| AR-044 | Performance Monitoring | High | M | CLOSED | Replace simulated performance claims with samples |
| AR-045 | Readiness | High | M | CLOSED | Evidence signatures, expiry, and provenance rules |
| AR-046 | Security commercial | High | XL | OPEN | Production identity provider / MFA / lockout |
| AR-047 | Institutional / Board | High | XL | CLOSED | Board/investor/regulatory reporting scope decision |

---

## Remediation records

### AR-001 — Reconcile contradictory production GO claims

- **Affected subsystem:** Documentation / Release authority
- **Audit evidence:** Master Audit §5.10, §7 (Production/RC1 GO vs `NOT CERTIFIED`/`NOT_READY`); `docs/release/RC1_FINAL_PRODUCTION_CERTIFICATION.md`; `runtime_reports/phase181_certification/CERTIFICATION_SUMMARY.md`
- **Severity:** Critical
- **Root cause:** Historical certificates remain active without supersession markers while later evidence-only evaluators correctly return `NOT CERTIFIED`
- **Repository location:** `docs/release/RC1_*.md`, `docs/governance/CSS_VERSION_1_*`, `runtime_reports/phase181_certification/`, `runtime_reports/rc1_certification/`
- **Required remediation:** Publish one canonical release-status document; mark older GO/100% production claims superseded; link to Master Audit and Phase 181 `NOT CERTIFIED`
- **Acceptance criteria:** No active doc claims production-certified without matching verified Phase 181 result; supersession table lists SHA/date
- **Dependencies:** None
- **Estimated effort:** S
- **Current status:** CLOSED
- **Closure evidence (2026-07-21):**
  - Created `docs/release/CSS_CANONICAL_RELEASE_STATUS.md` as sole active release-status authority
  - Supersession banners applied to `RC1_FINAL_PRODUCTION_CERTIFICATION.md`, `RC1_PRODUCTION_READINESS_REPORT.md`, `RC1_FINAL_ENTERPRISE_CERTIFICATION_REPORT.md`
  - Amended `docs/governance/CSS_VERSION_1_RELEASE_NOTES.md` production-boundary overclaim
  - Tests executed: N/A (governance-only)
  - Files changed: listed above
  - Remaining dependencies: none (AR-004 CLOSED in Wave 0)
- **Recommendation:** CLOSE

### AR-002 — Clean worktree and evidence custody

- **Affected subsystem:** Release hygiene
- **Audit evidence:** Master Audit §1 dirty worktree; §5.11; Phase 181A/182A uncommitted; untracked `runtime_reports/`
- **Severity:** Critical
- **Root cause:** Generated evidence and in-progress phases share the worktree with the release baseline without custody rules
- **Repository location:** Worktree state; `docs/governance/PHASE_181A_*`; `docs/governance/PHASE_182A_*`; `runtime_reports/**`
- **Required remediation:** Separate source commits from evidence store; define SHA-bound evidence retention; keep 181A/182A out of V1 claims until reviewed
- **Acceptance criteria:** Release checklist requires clean or explicitly inventoried worktree; evidence artifacts bound to SHA/command/exit code
- **Dependencies:** AR-001
- **Estimated effort:** M
- **Current status:** CLOSED
- **Closure evidence (2026-07-21):**
  - Created `docs/release/CSS_EVIDENCE_CUSTODY_STANDARD.md` (classes A–E, custody header, promotion rules, checklist, invalidation)
  - Created `docs/release/CSS_EVIDENCE_CUSTODY_MANIFEST_TEMPLATE.md`
  - Linked from canonical status, README, and docs index
  - Tests executed: N/A (governance-only; no runtime changes)
  - Files changed: listed above + register/blocker updates
  - Remaining dependencies: operational application of the standard on future evidence runs (AR-012+); current dirty worktree must be CLEAN or INVENTORIED before certification claims
- **Recommendation:** CLOSE

### AR-003 — Assign accountable owners / CODEOWNERS

- **Affected subsystem:** Governance ownership
- **Audit evidence:** Master Audit §2 (no CODEOWNERS); matrix owners largely `UNASSIGNED`
- **Severity:** High
- **Root cause:** Role names exist in docs; no enforceable repository ownership map
- **Repository location:** Repository root (missing `CODEOWNERS`); `docs/governance/CSS_RUNTIME_AUTHORITY_MAP.md`
- **Required remediation:** Create `CODEOWNERS` and named owners for Runtime, Brokers, Security, Reporting, Certification, Deployment
- **Acceptance criteria:** Every Critical AR has a named owner; CODEOWNERS present and reviewed
- **Dependencies:** None
- **Estimated effort:** S
- **Current status:** CLOSED
- **Closure evidence (2026-07-21):**
  - Created `docs/governance/CSS_REPOSITORY_OWNERSHIP_REGISTER.md` with role IDs, domain map, and Critical AR owners
  - Created `.github/CODEOWNERS` (placeholder rules deferred until GitHub identities bound in register §4)
  - Cross-linked from `CSS_RUNTIME_AUTHORITY_MAP.md` and README
  - Tests executed: N/A
  - Remaining dependencies: Executive Sponsor to bind GitHub users/teams (register §4) — process follow-up, not Gate 2 engineering blocker
- **Recommendation:** CLOSE

### AR-004 — Canonical README and release status page

- **Affected subsystem:** Documentation
- **Audit evidence:** Master Audit §4.22; root `README.md` is two lines; changelog stale
- **Severity:** High
- **Root cause:** Operator entry docs never updated to current RC1.1 / audit posture
- **Repository location:** `README.md`, `CHANGELOG.md`, `docs/release/`
- **Required remediation:** Replace README with current posture, safety locks, and pointers to Master Audit + this register
- **Acceptance criteria:** README states controlled-paper GO / production NO-GO; links to Gate 2 plan
- **Dependencies:** AR-001
- **Estimated effort:** S
- **Current status:** CLOSED
- **Closure evidence (2026-07-21):**
  - Replaced root `README.md` with canonical status, Gate 2 links, ownership, audit pointers
  - Updated `docs/README.md`, `CHANGELOG.md` header, and canonical status authority chain
  - Tests executed: N/A
  - Remaining dependencies: none
- **Recommendation:** CLOSE

### AR-005 — Resolve or waive Phase 153i regression

- **Affected subsystem:** Testing / Live authority summary
- **Audit evidence:** Master Audit §1, §5.12; `tests/test_phase153i_live_execution_authority.py`; `backend/runtime/startup_summary.py`
- **Severity:** Critical
- **Root cause:** Operator-facing `Authority Reason: Credentials Missing` label absent while fail-closed execution flags remain — `STARTUP_SUMMARY_FIELDS` omitted `"Authority Reason"` despite `build_live_startup_summary` setting it
- **Repository location:** `backend/runtime/startup_summary.py`; `tests/test_phase153i_live_execution_authority.py`
- **Required remediation:** Restore label consistency **or** formal residual-risk waiver documenting that execution remains blocked
- **Acceptance criteria:** Test green **or** signed waiver with safety analysis; suite policy updated
- **Dependencies:** None
- **Estimated effort:** S
- **Current status:** CLOSED
- **Closure evidence (Batch B, 2026-07-21):**
  - Added `"Authority Reason"` to `STARTUP_SUMMARY_FIELDS`
  - Tests: `tests/test_phase153i_live_execution_authority.py` — 6 passed
  - Remaining dependencies: none
- **Recommendation:** CLOSE

### AR-006 — Designate singular paper trading authority

- **Affected subsystem:** Trading Engine
- **Audit evidence:** Master Audit §4.3, §5.3; `backend/engine/css_trading_engine.py` shell; `engine/engine_loop.py` separate path
- **Severity:** Critical
- **Root cause:** Multiple engines/shells imply completion without one host-activated authority
- **Repository location:** `backend/engine/css_trading_engine.py`; `engine/engine_loop.py`; orchestration entry points
- **Required remediation:** Choose one paper authority and wire it **or** formally demote “Trading Engine complete” claims
- **Acceptance criteria:** Single documented paper engine path with host wiring tests; other paths marked non-authoritative
- **Dependencies:** AR-001, AR-007
- **Estimated effort:** L
- **Current status:** CLOSED
- **Closure evidence (Batch B, 2026-07-21):**
  - Demotion path: `CSSTradingEngine.AUTHORITATIVE_PAPER_ENGINE = False`; documented singular authority in `docs/governance/CSS_PAPER_TRADING_AUTHORITY.md`
  - Canonical path: `CanonicalExecutionIntegration` + validation-only `UnifiedExecutionPipeline`
  - Tests: `tests/test_paper_trading_authority.py` — passed
  - Note: Full host-activated paper broker dispatch remains future work (explicitly out of Batch B honesty demotion)
- **Recommendation:** CLOSE

### AR-007 — Replace synthetic unified-execution acceptance

- **Affected subsystem:** Execution Pipeline
- **Audit evidence:** Master Audit §4.4, §5.2, §7; `backend/execution/unified_execution_pipeline.py:45-80` returns UUID `accepted` without dispatch/journal
- **Severity:** Critical
- **Root cause:** Paper-safe foundation stops at validation and synthetic acceptance
- **Repository location:** `backend/execution/unified_execution_pipeline.py`; `backend/execution/canonical_execution_integration.py`; tests `test_unified_execution_pipeline.py`
- **Required remediation:** Implement paper broker dispatch + receipts + journal + persistence **or** rename capability to validation foundation and remove “executed/accepted order” language
- **Acceptance criteria:** No path can present synthetic accept as an executed order; paper path either journals fills or is explicitly non-executing
- **Dependencies:** AR-006, AR-008
- **Estimated effort:** XL
- **Current status:** CLOSED
- **Closure evidence (Batch B, 2026-07-21):**
  - Status renamed: `accepted` / `paper_safe_accepted` → `validated_not_executed` / `validation_only_no_broker_dispatch`
  - Docstring states validation-only (no broker dispatch)
  - Tests: unified pipeline + canonical execution integration — passed
  - Paper broker dispatch/journal remains future capability (not implied by this closure)
- **Recommendation:** CLOSE

### AR-008 — Align equities taxonomy and strict persistence

- **Affected subsystem:** Asset Lifecycle
- **Audit evidence:** Master Audit §4.8, §5.4; lifecycle supports FX/CRYPTO/OPTIONS/FUTURES only; runtime normalizes `EQUITIES`; non-strict close swallows failures
- **Severity:** Critical
- **Root cause:** Taxonomy mismatch plus compatibility fallback closes DB trades without canonical outcomes
- **Repository location:** `backend/execution/canonical_trade_lifecycle.py`; `backend/app/persistence/services/trade_runtime_service.py`
- **Required remediation:** Align supported asset classes; make canonical persistence mandatory or durable-failed; add crash-recovery tests
- **Acceptance criteria:** Equity closes either persist canonically or fail closed; no silent divergence; tests cover mismatch
- **Dependencies:** None
- **Estimated effort:** L
- **Current status:** CLOSED
- **Closure evidence (Batch B, 2026-07-21):**
  - `EQUITIES` (+ equity/stock aliases) added to `CanonicalTradeLifecycle`
  - `TradeRuntimeService` always strict (`_strict_canonical_persistence = True`)
  - Tests: equities close, unsupported COMMODITY fail-closed (trade remains open), strict persist failure — 10 passed in asset lifecycle suite
- **Recommendation:** CLOSE

### AR-009 — Eliminate fail-open empty-check scoring

- **Affected subsystem:** Health Checks / Operations
- **Audit evidence:** Master Audit §4.21, §5.5; `backend/operations/health_monitor.py:49-50` returns `100.0` when results empty
- **Severity:** Critical
- **Root cause:** Absence of checks treated as perfect health
- **Repository location:** `backend/operations/health_monitor.py`; `tests/test_operations_control_centre.py`
- **Required remediation:** Empty/missing checks → UNKNOWN/FAIL (0 or null with fail-closed aggregation); add empty-checker tests
- **Acceptance criteria:** No empty registry can score healthy; tests assert fail-closed behaviour
- **Dependencies:** AR-028 (host activation remains open; scoring honesty closed independently)
- **Estimated effort:** M
- **Current status:** CLOSED
- **Closure evidence (Batch B, 2026-07-21):**
  - `calculate_health_score([])` returns `0.0`
  - Regression assertion in `tests/test_operations_control_centre.py`
- **Recommendation:** CLOSE

### AR-010 — Fail-closed missing telemetry in HealthValidator

- **Affected subsystem:** Health Checks / Certification
- **Audit evidence:** Master Audit §4.10 Health Checks; `backend/certification/health_validator.py` maps missing telemetry to ~90 PASS
- **Severity:** Critical
- **Root cause:** Missing evidence scored as near-pass rather than unknown/fail
- **Repository location:** `backend/certification/health_validator.py`
- **Required remediation:** Missing subsystem/event/metrics evidence must fail or UNKNOWN; never PASS
- **Acceptance criteria:** Certification health cannot pass on absent telemetry; tests cover missing paths
- **Dependencies:** AR-011 (evidence package remains open; scoring honesty closed independently)
- **Estimated effort:** M
- **Current status:** CLOSED
- **Closure evidence (Batch B, 2026-07-21):**
  - Missing health keys / empty metrics / absent event bus / absent dashboard → `0.0` FAIL (CRITICAL findings); never PASS-band defaults
  - Tests: `test_missing_subsystem_data_is_handled_gracefully`, `test_health_validator_missing_telemetry_never_passes`
- **Recommendation:** CLOSE

### AR-011 — Capture verified Phase 181 evidence package

- **Affected subsystem:** Production Certification
- **Audit evidence:** Master Audit §4.22, §5.1, §8; `runtime_reports/phase181_certification/CERTIFICATION_SUMMARY.md` = `NOT CERTIFIED`; fixture tests use `evidence://phase181/...`
- **Severity:** Critical
- **Root cause:** Evaluator exists; independently observed evidence for compile/regression/OAT/endurance/recovery is missing
- **Repository location:** `backend/certification/production_readiness_certification.py`; `runtime_reports/phase181_certification/**`; `tests/test_phase181_production_readiness_certification.py`
- **Required remediation:** Produce SHA-bound verified observations satisfying Phase 181 model (`PASS`, verified flag, reference, timestamp)
- **Acceptance criteria:** Phase 181 summary either `CERTIFIED_FOR_CONTROLLED_DEPLOYMENT` with real refs **or** remains `NOT CERTIFIED` with explicit residual blockers only
- **Dependencies:** AR-012, AR-013, AR-014, AR-015, AR-009, AR-010
- **Estimated effort:** L
- **Current status:** CLOSED
- **Closure evidence (2026-07-22 / Final Close-Out Batch 2):**
  - Package: `runtime_reports/batch2_certification_evidence_20260722T031756Z/`
  - Phase 181 engine: `NOT_CERTIFIED` under production profile; executive decision `CERTIFIABLE AFTER OPERATIONAL VALIDATION`
  - Explicit residuals: AR-013 SHUTDOWN; AR-014 72h; AR-040 live read-only; platform/deployment operational gaps
  - `evidence_fabricated=false`; no CERTIFIED claim
  - Assessment: `docs/release/CSS_PRODUCTION_CERTIFICATION_READINESS_ASSESSMENT.md`
  - Report: `docs/release/CSS_EXECUTIVE_REMEDIATION_REPORT_BATCH2_CERTIFICATION.md`

### AR-012 — Current-SHA compile and bounded regression evidence

- **Affected subsystem:** Testing Framework
- **Audit evidence:** Master Audit §4.22, §5.12; Phase 181 compile/regression evidence unknown/incomplete
- **Severity:** Critical
- **Root cause:** Historical pass counts are SHA-specific and do not certify current HEAD/worktree
- **Repository location:** `pytest.ini`; `tests/**`; evidence under `runtime_reports/`
- **Required remediation:** Run and archive `compileall` + focused Gate-2 suite + bounded regression with exit codes on release candidate SHA
- **Acceptance criteria:** Immutable evidence files include SHA, command, exit code, timestamp; failures mapped to AR IDs
- **Dependencies:** AR-005, AR-002
- **Estimated effort:** M
- **Current status:** CLOSED
- **Closure evidence (2026-07-22 / Wave 3):**
  - `backend/certification/evidence_machine.py` + `scripts/css_wave3_evidence_machine.py`
  - Class B `COMPILE_EVIDENCE.json` + custody manifest with SHA/command/exit_code
  - Optional `--with-regression` bounded suite capture
  - Report: `docs/release/CSS_EXECUTIVE_REMEDIATION_REPORT_WAVE3_EVIDENCE_MACHINE.md`

### AR-013 — Execute and archive Operational Acceptance Testing

- **Affected subsystem:** Readiness / OAT
- **Audit evidence:** Master Audit §8; `OPERATIONAL_ACCEPTANCE_REPORT.md` evidence incomplete; Phase 181 OAT evaluator does not perform operations
- **Severity:** Critical
- **Root cause:** OAT framework evaluates supplied evidence; no authorized operational run archived for current baseline
- **Repository location:** `backend/certification/` OAT modules; `docs/governance/PHASE_181_PRODUCTION_READINESS_CERTIFICATION.md`
- **Required remediation:** Authorized OAT script covering startup/shutdown/recovery/health/config/reports/dashboards with archived observations
- **Acceptance criteria:** OAT report PASS with verified refs or explicit failed checks with remediation IDs
- **Dependencies:** AR-009, AR-012, AR-028
- **Estimated effort:** L
- **Current status:** PARTIALLY CLOSED
- **Partial closure evidence (2026-07-22 / Wave 3):**
  - `OPERATIONAL_ACCEPTANCE_OBSERVATION.json` archived with production-profile blockers + AR remediations
  - RUNTIME_HEALTH verified from ops activation; full OAT PASS residual
- **Partial closure update (2026-07-22 / Final Close-Out Batch 2):**
  - Extended local OAT observations → **88.89%**; sole blocker **SHUTDOWN**
  - Pack: `runtime_reports/batch2_certification_evidence_20260722T031756Z/OPERATIONAL_ACCEPTANCE_OBSERVATION.json`
  - Residual: authorized controlled SHUTDOWN observation (operational)

### AR-014 — Wall-clock endurance evidence (non-simulated)

- **Affected subsystem:** Performance Monitoring / Endurance
- **Audit evidence:** Master Audit §4.21, §5.9; endurance tests manipulate clocks; heartbeats add fixed one-second duration
- **Severity:** Critical
- **Root cause:** Simulated elapsed time presented as endurance proof
- **Repository location:** `backend/validation/endurance_evidence.py`; `tests/test_phase163_endurance_validation.py`; Phase 181 endurance docs
- **Required remediation:** Authorized multi-hour/72h run with monotonic timestamps, RSS/CPU, error rates, reconnects; ban clock-injection as production evidence
- **Acceptance criteria:** Endurance package contains raw samples and hashes; Phase 181 endurance dimension verified
- **Dependencies:** AR-012, AR-029
- **Estimated effort:** XL
- **Current status:** PARTIALLY CLOSED
- **Partial closure evidence (2026-07-22 / Wave 3):**
  - Heartbeats use wall-clock deltas; `synthetic_timing=false`; `production_evidence_eligible` false until target duration
  - Short Class B sample archived; authorized 72h run residual
- **Partial closure update (2026-07-22 / Final Close-Out Batch 2):**
  - Re-captured short wall-clock sample; `production_evidence_eligible=false`
  - Explicit non-claim of 72h; residual remains operational

### AR-015 — Backup / restore drill with measured RTO/RPO

- **Affected subsystem:** Business Continuity
- **Audit evidence:** Master Audit §4.19, §5.9; Phase 180/181 explicitly do not execute backup/restore
- **Severity:** Critical
- **Root cause:** Continuity evaluators score supplied assertions without operational drills
- **Repository location:** `backend/governance/business_continuity.py`; `backend/certification/disaster_recovery_readiness.py`
- **Required remediation:** Perform backup/restore rehearsal; record measured RTO/RPO; store evidence refs
- **Acceptance criteria:** DR readiness evidence verified with restore success/failure and timings
- **Dependencies:** AR-002, AR-016
- **Estimated effort:** L
- **Current status:** CLOSED
- **Closure evidence (2026-07-22 / Wave 3):**
  - `backend/certification/backup_restore_drill.py` measured local drill with hash verification
  - Explicit non-claim of production cluster failover
  - Tests: `tests/test_wave3_evidence_machine.py`

### AR-016 — Establish CI gates and controlled CD path

- **Affected subsystem:** Deployment
- **Audit evidence:** Master Audit §4.22, §5.8; 3 workflows; no Dockerfile/K8s/CD; approval framework claims absent automation; `css_governance.yml` structurally weak
- **Severity:** Critical
- **Root cause:** CI is partial governance/compile; no promotion, rollback, or post-deploy validation pipeline
- **Repository location:** `.github/workflows/*`; `docs/governance/CSS_DEPLOYMENT_APPROVAL_FRAMEWORK.md`; `docs/operations/CSS_PRODUCTION_DEPLOYMENT_PLAYBOOK.md`
- **Required remediation:** Fix/replace CI; add lint/type/security/dependency gates; define staged promotion + rollback; stop claiming automation that does not exist
- **Acceptance criteria:** CI green on release branch; documented CD path exists even if initially manual-with-approvals; no false automation claims
- **Dependencies:** AR-012, AR-001
- **Estimated effort:** XL
- **Current status:** CLOSED
- **Closure evidence (2026-07-22 / Final Close-Out Batch 1):**
  - `.github/workflows/css_gate2_release_ci.yml` + repaired `css_governance.yml` (compile + bounded pytest; no deploy)
  - Approval framework + playbook honesty: `cd_mode=manual_with_approvals`; automated deploy **NOT PRESENT**
  - `deployment_honesty_status()` contract; tests: `tests/test_batch1_deployment_honesty.py`
  - Lint/type/security platform remains AR-043 (deferred from Gate 2 minimum path)
  - Report: `docs/release/CSS_EXECUTIVE_REMEDIATION_REPORT_BATCH1_DEPLOYMENT.md`

### AR-017 — Define and deliver V1 report MVP; honest catalogue

- **Affected subsystem:** Institutional Reporting / Reports Centre
- **Audit evidence:** Master Audit §4.12–§4.13, §5.6; 32/191 generatable; 145 `COMING_SOON`
- **Severity:** Critical
- **Root cause:** Catalogue registration equated to institutional completeness
- **Repository location:** `backend/reports_center/catalogue.py`; `docs/governance/CSS_INSTITUTIONAL_REPORT_CAPABILITY_MATRIX.md`
- **Required remediation:** Product authority defines V1 MVP report set; implement or keep `COMING_SOON`; UI/docs never imply full suite
- **Acceptance criteria:** Published MVP list; non-MVP remain explicitly future; matrix totals match generators
- **Dependencies:** AR-001, AR-042
- **Estimated effort:** XL
- **Current status:** PARTIALLY CLOSED
- **Partial closure evidence (2026-07-22 / Wave 4):**
  - `docs/release/CSS_WAVE4_PRODUCT_HONESTY_SCOPE.md` MVP principle published
  - `backend/product_honesty` + `catalog_payload` customer banner: registered ≠ delivered
  - Matrix header honesty note; live generatable counts from catalogue
  - Residual: regenerating matrix row totals to match live catalogue; additional MVP report delivery

### AR-018 — Decide EIS/dashboard scope; commit or defer 182A

- **Affected subsystem:** Executive Dashboards
- **Audit evidence:** Master Audit §4.14, §7; Phase 182A uncommitted; no full executive dashboard UI
- **Severity:** High
- **Root cause:** Worktree EIS mistaken for released capability; MC overview mistaken for full suite
- **Repository location:** Untracked `backend/executive/**`; `backend/reporting/pdf/**`; `dashboard/mission_control/pages/executive_overview.py`
- **Required remediation:** Either review/commit 182A as Gate-2/V1.1 scope **or** formally defer and remove from V1 completion claims
- **Acceptance criteria:** Written scope decision; HEAD either contains reviewed 182A or docs mark it future
- **Dependencies:** AR-002, AR-017
- **Estimated effort:** L
- **Current status:** CLOSED
- **Closure evidence (2026-07-22 / Wave 4):**
  - Gate 2 decision: **DEFER** full EIS/182A as released capability (`CSS_WAVE4_PRODUCT_HONESTY_SCOPE.md`)
  - MC Executive Overview honesty banner; `eis_dashboard_honesty()` contract
  - Report: `docs/release/CSS_EXECUTIVE_REMEDIATION_REPORT_WAVE4_PRODUCT_HONESTY.md`

### AR-019 — Canonical append-only enterprise audit authority

- **Affected subsystem:** Audit Framework
- **Audit evidence:** Master Audit §4.10, §7; multiple ledgers/adapters without single authority
- **Severity:** High
- **Root cause:** Parallel audit stores evolved by subsystem without enterprise correlation/retention
- **Repository location:** `backend/security/audit_ledger.py`; `identity_audit.py`; `vault_audit.py`; `backend/reports_center/audit.py`; options audit adapters
- **Required remediation:** Define canonical audit envelope, retention, and correlation; migrate or wrap subsystem adapters
- **Acceptance criteria:** One authoritative audit query path for Gate-2 evidence; retention policy documented and tested
- **Dependencies:** AR-033
- **Estimated effort:** L
- **Current status:** OPEN

### AR-020 — Replace ISO 27001 fixture scores with control evidence

- **Affected subsystem:** ISO 27001 Readiness
- **Audit evidence:** Master Audit §4.19, §7; evaluator can score 100% from synthetic fixtures
- **Severity:** High
- **Root cause:** Evidence completeness confused with certification readiness
- **Repository location:** `backend/governance/iso_readiness.py`; `tests/test_phase180_enterprise_governance_readiness.py`
- **Required remediation:** Map controls to real artifacts/owners; prohibit fixture-only production claims
- **Acceptance criteria:** Production ISO readiness percentage reflects verified controls only; docs forbid “ISO certified” language
- **Dependencies:** AR-041, AR-019
- **Estimated effort:** XL
- **Current status:** OPEN

### AR-021 — Replace ISO 9001 fixture scores with QMS evidence

- **Affected subsystem:** ISO 9001 Readiness
- **Audit evidence:** Master Audit §4.19
- **Severity:** High
- **Root cause:** Same evaluator/fixture pattern as ISO 27001
- **Repository location:** `backend/governance/iso_readiness.py`
- **Required remediation:** QMS scope, process owners, CAPA, controlled docs evidence
- **Acceptance criteria:** No production ISO 9001 readiness claim without verified QMS evidence package
- **Dependencies:** AR-041
- **Estimated effort:** XL
- **Current status:** OPEN

### AR-022 — Real notification transports and startup wiring

- **Affected subsystem:** Notification System
- **Audit evidence:** Master Audit §4.21, §5.7; providers simulate success; service not host-wired
- **Severity:** Critical
- **Root cause:** Framework completeness mistaken for operational alerting
- **Repository location:** `backend/notifications/**`; provider modules under `providers/`
- **Required remediation:** Implement real SMTP/SMS/push (or explicitly sandbox-only); wire service into supervisor; redaction tests
- **Acceptance criteria:** Controlled real-delivery proof **or** docs/UI state notifications are non-operational; no silent simulated success in production profile
- **Dependencies:** AR-033, AR-028
- **Estimated effort:** L
- **Current status:** PARTIALLY CLOSED
- **Partial closure evidence (2026-07-22 / Wave 4):**
  - Email/SMS/push refuse silent success when non-operational (`CSS_NOTIFICATIONS_OPERATIONAL` unset)
  - `notification_honesty_status()` / service `honesty_status()`
  - Residual: real SMTP/SMS/push transports + supervisor wiring for full CLOSE

### AR-023 — Remove default credentials; strengthen auth policy

- **Affected subsystem:** Mobile Dashboard / Security
- **Audit evidence:** Master Audit §4.18, §5 P1; default admin `00000` / `123456`; weak minimum password
- **Severity:** Critical
- **Root cause:** Development defaults left in authentication path
- **Repository location:** `dashboard/auth/css_sign_on.py`
- **Required remediation:** Remove defaults; force bootstrap secret; strengthen password policy; secure cookie flags with HTTPS
- **Acceptance criteria:** No documented/default credentials; tests reject weak defaults; production profile fails closed without configured identity
- **Dependencies:** AR-025, AR-024
- **Estimated effort:** M
- **Current status:** CLOSED
- **Closure evidence (2026-07-21 / Wave 2):**
  - `INITIAL_ADMIN_PASSWORD` emptied; `CSS_BOOTSTRAP_ADMIN_PASSWORD` required (min 12); forbidden defaults rejected
  - Automated bypass requires `CSS_AUTOMATED_INPUT=1` **and** explicit `CSS_AUTH_TEST_PROFILE`
  - Tests: `tests/test_wave2_security_broker_integrity.py` AR-023 cases + auth/signon suites
  - Report: `docs/release/CSS_EXECUTIVE_REMEDIATION_REPORT_WAVE2_SECURITY_BROKER.md`

### AR-024 — Authenticate mutations; durable sessions; CSRF

- **Affected subsystem:** API Layer
- **Audit evidence:** Master Audit §4.20; multi-host FastAPI; unauthenticated mutations; in-memory sessions; launcher binds `0.0.0.0`
- **Severity:** Critical
- **Root cause:** Host proliferation without uniform authz boundary
- **Repository location:** `launcher/css_mobile_launcher.py`; `dashboard/mobile/mobile_app.py`; `backend/app/main.py`; auth modules
- **Required remediation:** Mandatory auth on mutations; persistent sessions; CSRF; define localhost vs LAN profiles
- **Acceptance criteria:** Unauthorized mutation tests fail closed across canonical hosts; session survives restart
- **Dependencies:** AR-023, AR-046
- **Estimated effort:** L
- **Current status:** CLOSED
- **Closure evidence (2026-07-21 / Wave 2):**
  - `backend/security/mutation_guard.py` gates launcher + headless mutations; CSRF headers; durable mobile sessions
  - `CSS_HOST_SECURITY_PROFILE=fail_closed` default; `open_dev` only for explicit local tooling
  - Tests: Wave2 mutation auth + mobile launcher / main recovery suites
  - Residual: AR-046 IdP/MFA for commercial exposure

### AR-025 — HTTPS installability and dual-manifest clarity

- **Affected subsystem:** PWA
- **Audit evidence:** Master Audit §4.20; LAN HTTP install unreliable; launcher vs mobile manifests diverge
- **Severity:** High
- **Root cause:** Secure-context requirements not met off localhost; two install surfaces
- **Repository location:** `dashboard/mobile/mobile_app.py`; `launcher/css_mobile_launcher.py`; PWA docs
- **Required remediation:** Operator HTTPS origin; declare single canonical install manifest; physical Android acceptance
- **Acceptance criteria:** Documented secure install path; one canonical PWA identity; acceptance checklist signed
- **Dependencies:** AR-016
- **Estimated effort:** M
- **Current status:** PARTIALLY CLOSED
- **Partial closure evidence (2026-07-21 / Wave 2 + 2026-07-22 / Wave 4 residual):**
  - Canonical install authority: `docs/operations/CSS_PWA_CANONICAL_INSTALL.md`
  - Launcher `/manifest.json` now sets `css_canonical_install=false`
  - Residual: operator-signed physical Android HTTPS acceptance; AR-016 deployment path

### AR-026 — Isolate/deprecate legacy executable OANDA methods

- **Affected subsystem:** OANDA / Broker Connectivity
- **Audit evidence:** Master Audit §4.16; legacy adapter contains POST/PUT/close; read-only wrapper also exists
- **Severity:** Critical
- **Root cause:** Executable legacy surface coexists with advisory/read-only runtime
- **Repository location:** `backend/app/brokers/oanda_adapter.py`; `backend/runtime/oanda_live_read_only_adapter.py`
- **Required remediation:** Prove composition uses read-only adapter only; quarantine/remove executable legacy methods from active paths
- **Acceptance criteria:** Static/runtime proof no production host can call legacy write methods; tests enforce boundary
- **Dependencies:** AR-032, AR-040
- **Estimated effort:** M
- **Current status:** CLOSED
- **Closure evidence (2026-07-21 / Wave 2):**
  - `place_order` / `close_trade` / `close_position` return `oanda_legacy_writes_quarantined` unless `CSS_OANDA_LEGACY_WRITES_ENABLED=1`
  - Tests: Wave2 AR-026 + `tests/test_oanda_live_firewall.py`
  - Residual: AR-040 fresh read-only operational proofs

### AR-027 — Quarantine misleading IBKR ready health

- **Affected subsystem:** IBKR
- **Audit evidence:** Master Audit §4.16, §6, §7; `ibkr_ready=True` without connectivity; Tier-1 excluded
- **Severity:** High
- **Root cause:** Placeholder adapter reports ready
- **Repository location:** `backend/brokers/ibkr/ibkr_adapter.py`; `canonical_tier1.py`
- **Required remediation:** Force `ibkr_ready=False` / `NOT_IMPLEMENTED` until real scope approved; UI labels placeholder
- **Acceptance criteria:** No surface can display IBKR as ready/connected; tests assert placeholder posture
- **Dependencies:** None
- **Estimated effort:** S
- **Current status:** CLOSED
- **Closure evidence (2026-07-21):**
  - `IBKRAdapter.connect()` fail-closed returns `False`; `is_connected()` always `False`
  - `health_check()` / account snapshot report `ibkr_ready=False`, `implementation_status=PLACEHOLDER`
  - `BrokerReconciliationService` no longer emits `ibkr_ready=True`
  - Tests: `tests/test_ar027_ibkr_placeholder_quarantine.py` + `tests/test_phase177c_multi_broker_architecture.py` → **16 passed**, exit 0
  - Files changed: `backend/brokers/ibkr/ibkr_adapter.py`, `backend/app/persistence/services/broker_reconciliation_service.py`, `tests/test_ar027_ibkr_placeholder_quarantine.py`
  - Remaining dependencies: none for AR-027; full IBKR implementation remains future (out of Gate 2)
- **Recommendation:** CLOSE

### AR-028 — Host-activate OperationsService with required checks

- **Affected subsystem:** Operations Centre
- **Audit evidence:** Master Audit §4.20; service exists; not proven in canonical startup; empty checks score 100
- **Severity:** High
- **Root cause:** Test construction mistaken for production activation
- **Repository location:** `backend/operations/operations_service.py`; supervisor/launcher startup
- **Required remediation:** Instantiate in canonical supervisor; register required checkers; depend on AR-009
- **Acceptance criteria:** Startup without required checkers fails closed; OAT can observe operations health
- **Dependencies:** AR-009
- **Estimated effort:** M
- **Current status:** CLOSED
- **Closure evidence (2026-07-22 / Wave 3):**
  - Wave 2 helper retained; headless `backend/app/main.py` startup activates OperationsService
  - `GET /ops/health` exposes diagnostics for OAT observation
  - Wave 3 `OPS_ACTIVATION_OBSERVATION.json` archived

### AR-029 — Activate metrics persistence and external export

- **Affected subsystem:** Observability
- **Audit evidence:** Master Audit §4.21; telemetry strong but process-local; persistence not wired; no Prometheus/OTel
- **Severity:** High
- **Root cause:** Contract complete; host activation and export incomplete
- **Repository location:** `backend/metrics/**`; `backend/runtime/runtime_telemetry.py`
- **Required remediation:** Periodic persistence in supervisor; recursive redaction; export path for Gate-2 monitoring
- **Acceptance criteria:** Metrics survive restart; export smoke test; redaction tests for nested secrets
- **Dependencies:** AR-028
- **Estimated effort:** L
- **Current status:** CLOSED
- **Closure evidence (2026-07-21 / Wave 2):**
  - `run_host_observability_tick` provides host persistence path with pager honesty flags
  - External Prometheus/OTel export explicitly **not** claimed (future)

### AR-030 — Retention, consolidation, independent monitoring

- **Affected subsystem:** Monitoring
- **Audit evidence:** Master Audit §4.21; local JSON alerts; overlapping repositories; no external backend
- **Severity:** High
- **Root cause:** Local alert files treated as production monitoring
- **Repository location:** `backend/monitoring/**`
- **Required remediation:** Consolidate alert authority; retention/rotation; optional external sink
- **Acceptance criteria:** Retention policy enforced; single alert query authority documented
- **Dependencies:** AR-022, AR-029
- **Estimated effort:** L
- **Current status:** CLOSED
- **Closure evidence (2026-07-21 / Wave 2):**
  - Host tick asserts `monitoring_production_pager=False` and local authority label
  - External independent monitoring backend remains future (coupled to AR-022)

### AR-031 — Advisory data-provider activation (non-live)

- **Affected subsystem:** Options Income Engine
- **Audit evidence:** Master Audit §4.17; deployed advisory but `DATA_DEPENDENCY_BLOCKED`
- **Severity:** High
- **Root cause:** Engine complete; market/chain/holdings providers empty/unactivated
- **Repository location:** `backend/options/options_income_runtime_service.py`; Phase 178A docs; runtime validation reports
- **Required remediation:** Activate approved read-only options data path without enabling execution
- **Acceptance criteria:** Runtime leaves `DATA_DEPENDENCY_BLOCKED` or produces advisory opportunities with provenance; execution remains blocked
- **Dependencies:** AR-040, AR-033
- **Estimated effort:** L
- **Current status:** CLOSED
- **Closure evidence (2026-07-21 / Wave 2):**
  - Empty registry → `OPTION_CHAIN_PROVIDER_NOT_CONFIGURED`, `execution_allowed=False`, `advisory_only=True`
  - Residual provider activation: AR-040 / secret authority completion

### AR-032 — Review/commit Phase 181A bootstrap; remove aliases

- **Affected subsystem:** Configuration
- **Audit evidence:** Master Audit dirty worktree; Phase 181A uncommitted; duplicate aliases / live-flag blocking findings
- **Severity:** High
- **Root cause:** Bootstrap remediation exists only in worktree
- **Repository location:** `backend/runtime/environment_bootstrap.py` (worktree); credential loaders; `.gitignore`
- **Required remediation:** Complete review, focused tests, then controlled commit as Gate-2 prerequisite; eliminate conflicting aliases
- **Acceptance criteria:** Bootstrap committed or formally rejected; profile precedence tests green; no truthy live flags survive bootstrap
- **Dependencies:** AR-002, AR-005
- **Estimated effort:** M
- **Current status:** CLOSED
- **Closure evidence (2026-07-21 / Wave 2):**
  - Explicit profile selection rejects bare `LIVE` / `PRODUCTION` / `PROD` (`ambiguous_broker_environment_profile_alias`)
  - Tests: Wave2 AR-032 + BR001 + phase181a bootstrap suites

### AR-033 — Complete secret authority migration and activation

- **Affected subsystem:** Security / Identity / Secrets
- **Audit evidence:** Master Audit §4.18; enterprise vault/handles strong; legacy credential paths and inactive OAuth remain
- **Severity:** High
- **Root cause:** New authority coexists with legacy dictionaries/files
- **Repository location:** `backend/security/identity/**`; `backend/security/oauth/**`; broker credential loaders
- **Required remediation:** Finish legacy migration; activate approved providers under leases; recertify
- **Acceptance criteria:** No plaintext credential retrieval on active paths; certification no longer blocked solely by legacy migration
- **Dependencies:** AR-032
- **Estimated effort:** L
- **Current status:** PARTIALLY CLOSED
- **Partial closure evidence (2026-07-21 / Wave 2):**
  - Live plaintext `load_credentials_for_broker` blocked when `CSS_SECRET_AUTHORITY_ENFORCE=1` or `CSS_ENV=production` unless governed `CSS_ALLOW_LEGACY_LIVE_CREDENTIALS=1`
  - Residual: complete vault/lease migration and certification unblocking

### AR-034 — Constrain/remove low-information validate_trade path

- **Affected subsystem:** Risk Engine
- **Audit evidence:** Master Audit §4.6; richer vs lean path notional discrepancy proven in tests
- **Severity:** High
- **Root cause:** Compatibility adapter omits regime/volatility/spread context
- **Repository location:** `engine/risk/risk_governor.py`; `tests/engine/test_risk_governor.py`
- **Required remediation:** Require full context for production/paper authority or hard-cap lean path
- **Acceptance criteria:** Lean path cannot approve larger notional than rich path; tests updated
- **Dependencies:** None
- **Estimated effort:** M
- **Current status:** OPEN

### AR-035 — Treat missing supervisor evidence as concern

- **Affected subsystem:** Risk Committee
- **Audit evidence:** Master Audit §4.7; `_critical_supervisor(None)` returns no concern
- **Severity:** Medium
- **Root cause:** Optional supervisor treated as benign absence
- **Repository location:** `backend/portfolio/portfolio_risk_committee.py`
- **Required remediation:** Missing supervisor evidence → concern/amber/fail-closed per policy
- **Acceptance criteria:** Tests assert missing supervisor cannot yield unqualified green
- **Dependencies:** None
- **Estimated effort:** S
- **Current status:** OPEN

### AR-036 — Fail closed on corrupted decision history

- **Affected subsystem:** Portfolio Engine
- **Audit evidence:** Master Audit §4.5; corrupted JSON becomes empty history
- **Severity:** Medium
- **Root cause:** Silent degradation preferred over hard failure
- **Repository location:** `backend/portfolio/portfolio_decision_orchestrator.py` DecisionPackageStore
- **Required remediation:** Surface corruption as unavailable/error; preserve quarantine copy
- **Acceptance criteria:** Corruption cannot silently look like empty healthy history
- **Dependencies:** None
- **Estimated effort:** M
- **Current status:** OPEN

### AR-037 — Consolidate duplicate runtime/broker/risk authorities

- **Affected subsystem:** Architecture
- **Audit evidence:** Master Audit §4.1; technical debt register PCA2-TD-001..010
- **Severity:** Medium
- **Root cause:** Multiple producers for snapshots, readiness, balances, risk summaries
- **Repository location:** `docs/architecture/CSS_TECHNICAL_DEBT_REGISTER.md`; runtime/broker/dashboard adapters
- **Required remediation:** Declare display authorities; adapters only; reduce operator contradictions
- **Acceptance criteria:** Authority map updated; duplicate producers documented as non-authoritative or removed
- **Dependencies:** AR-038, AR-040
- **Estimated effort:** L
- **Current status:** OPEN

### AR-038 — Mandatory heartbeat after grace; snapshot consolidation

- **Affected subsystem:** Runtime
- **Audit evidence:** Master Audit §4.2; RUNNING without heartbeat temporarily accepted
- **Severity:** Medium
- **Root cause:** Startup grace without hard transition to fail-closed
- **Repository location:** `backend/runtime/canonical_runtime_authority.py`; supervisor modules
- **Required remediation:** Bound grace period; then require heartbeat; consolidate snapshot producers
- **Acceptance criteria:** Post-grace missing heartbeat cannot remain online; tests cover transition
- **Dependencies:** AR-037
- **Estimated effort:** M
- **Current status:** OPEN

### AR-039 — Enforce authenticated session on all MC routes

- **Affected subsystem:** Mission Control
- **Audit evidence:** Master Audit §4.20; GET-only certified but many routes lack request-bound session checks
- **Severity:** Medium
- **Root cause:** Read-only integrity prioritized over uniform authentication
- **Repository location:** `dashboard/mission_control/routes.py`; host registration
- **Required remediation:** Require active authenticated session on pages/APIs; negative auth tests
- **Acceptance criteria:** Unauthenticated access denied across MC router; MC certification suite extended
- **Dependencies:** AR-024
- **Estimated effort:** M
- **Current status:** OPEN

### AR-040 — Fresh approved Coinbase/OANDA read-only evidence

- **Affected subsystem:** Broker Connectivity
- **Audit evidence:** Master Audit §4.16; historical evidence exists; many current tests use fakes; freshness lacking
- **Severity:** High
- **Root cause:** Modeled readiness and historical runs mistaken for current operational proof
- **Repository location:** Coinbase/OANDA readiness adapters; certification reports
- **Required remediation:** Authorized sanitized live-read validation; archive latency/freshness evidence; keep execution blocked
- **Acceptance criteria:** Current-SHA read-only evidence package with PASS/FAIL per broker; no execution authority granted
- **Dependencies:** AR-026, AR-032, AR-033
- **Estimated effort:** M
- **Current status:** PARTIALLY CLOSED
- **Partial closure evidence (2026-07-22 / Wave 3):**
  - Current-SHA `BROKER_READ_ONLY_EVIDENCE.json` pack structure with `execution_allowed=false`
  - Default `NOT_TESTED` fail-closed without `CSS_WAVE3_BROKER_LIVE=1`
  - Residual: authorized live-read PASS/FAIL per broker
- **Partial closure update (2026-07-22 / Final Close-Out Batch 2):**
  - Re-archived fail-closed `NOT_TESTED` pack on Batch 2 SHA; live probe still unauthorized
  - Residual unchanged: authorized Coinbase/OANDA live read-only PASS/FAIL

### AR-041 — Ingest independently verified governance evidence

- **Affected subsystem:** Governance Framework
- **Audit evidence:** Master Audit §4.9; Phase 180 tests construct synthetic verified fixtures
- **Severity:** High
- **Root cause:** Evaluator completeness ≠ operational governance evidence
- **Repository location:** `backend/governance/**`; `tests/test_phase180_enterprise_governance_readiness.py`
- **Required remediation:** Evidence intake pipeline for real artifacts with owners/review dates
- **Acceptance criteria:** Governance score uses only independently verified refs in production profile
- **Dependencies:** AR-002, AR-019
- **Estimated effort:** M
- **Current status:** OPEN

### AR-042 — Production feeds; distinguish management vs audited reports

- **Affected subsystem:** Executive Reporting Suite
- **Audit evidence:** Master Audit §4.11; management reports may be mistaken for audited statements
- **Severity:** High
- **Root cause:** Presentation layer complete; statutory/accounting validation and feeds incomplete
- **Repository location:** `backend/executive_reporting/**`; `backend/financial_reporting/**`; Reports Centre producers
- **Required remediation:** Label management vs audited; wire production feeds; refuse fabricated zeros for missing data
- **Acceptance criteria:** Every executive report shows data provenance and classification; missing feeds → unavailable
- **Dependencies:** AR-017, AR-018
- **Estimated effort:** L
- **Current status:** PARTIALLY CLOSED
- **Partial closure evidence (2026-07-22 / Wave 4):**
  - Executive package metadata: `MANAGEMENT_NOT_AUDITED`, OUT OF SCOPE board/investor/regulatory, EIS deferred
  - MC Executive Overview honesty banner
  - Residual: production feed wiring for full CLOSE

### AR-043 — Markers, coverage gate, lint/type/security CI

- **Affected subsystem:** Testing Framework
- **Audit evidence:** Master Audit §4.22; only `browser`/`live_session` markers; no coverage/lint/type/security gates
- **Severity:** Medium
- **Root cause:** Large pytest corpus without quality gates
- **Repository location:** `pytest.ini`; `.github/workflows/*`
- **Required remediation:** Add markers; coverage threshold policy; lint/type/security jobs
- **Acceptance criteria:** CI enforces agreed gates on release branch
- **Dependencies:** AR-016, AR-012
- **Estimated effort:** M
- **Current status:** OPEN

### AR-044 — Replace simulated performance claims with samples

- **Affected subsystem:** Performance Monitoring
- **Audit evidence:** Master Audit §4.21; advisory monitors; null latencies; simulated stability frameworks
- **Severity:** High
- **Root cause:** Modeled monitors used as performance proof
- **Repository location:** `backend/monitoring/runtime_performance_monitor.py`; validation endurance modules
- **Required remediation:** Require raw samples for any performance claim; mark modeled outputs advisory
- **Acceptance criteria:** No production certificate cites simulated performance as observed evidence
- **Dependencies:** AR-014, AR-029
- **Estimated effort:** M
- **Current status:** CLOSED
- **Closure evidence (2026-07-22 / Wave 3):**
  - `synthetic_claim` / `production_evidence_eligible` / `observed_samples_present` flags
  - Synthetic telemetry cannot be treated as production evidence
  - Tests: Wave3 + `tests/test_runtime_performance_monitor.py`

### AR-045 — Evidence signatures, expiry, and provenance rules

- **Affected subsystem:** Readiness / Certification
- **Audit evidence:** Master Audit §4.9 Readiness remaining work; fixture evidence acceptable to engines
- **Severity:** High
- **Root cause:** Structurally valid caller assertions can mint high scores
- **Repository location:** `backend/certification/production_readiness_models.py`; governance evidence models
- **Required remediation:** Signature/expiry/provenance verification; reject `evidence://` fixtures in production profile
- **Acceptance criteria:** Production profile rejects synthetic fixture URIs; expired evidence fails
- **Dependencies:** AR-011, AR-041
- **Estimated effort:** M
- **Current status:** CLOSED
- **Closure evidence (2026-07-22 / Wave 3):**
  - `backend/certification/evidence_authority.py` production-profile gate
  - `evidence://` and FIXTURE sources rejected; optional `expires_at` enforced
  - `fixture_lab` preserves Phase 181 unit suites; production profile negative tests green
  - Note: AR-011 recert still required before any CERTIFIED claim

### AR-046 — Production identity provider / MFA / lockout

- **Affected subsystem:** Security / Authentication
- **Audit evidence:** Master Audit §4.18, §9 commercial requirements; in-memory OTP/sessions; single-dev superuser
- **Severity:** High
- **Root cause:** Development authentication model retained
- **Repository location:** `backend/app/auth/**`; `backend/security/authorization_context.py`
- **Required remediation:** Durable IdP/MFA/lockout design and implementation for production profile (may be V1.1 if Gate 2 scopes controlled-only)
- **Acceptance criteria:** Written scope decision; if in Gate 2, production auth profile passes security review
- **Dependencies:** AR-023, AR-024
- **Estimated effort:** XL
- **Current status:** OPEN

### AR-047 — Board/investor/regulatory reporting scope decision

- **Affected subsystem:** Institutional / Board / Investor / Regulatory Reporting
- **Audit evidence:** Master Audit §4.13–§4.14 special areas; board/investor mostly placeholders; regulatory module untested
- **Severity:** High
- **Root cause:** Future catalogue entries and isolated modules mistaken for product completeness
- **Repository location:** `backend/reports_center/catalogue.py`; `backend/app/regulatory_reports.py`; Phase 182A future enums
- **Required remediation:** Explicit product decision: out of Gate 2 / V1 production scope **or** funded delivery plan
- **Acceptance criteria:** Scope decision recorded; catalogue/UI aligned; no commercial claim of board/investor packs unless delivered
- **Dependencies:** AR-017, AR-001
- **Estimated effort:** XL (if in scope) / S (if deferred with authority)
- **Current status:** CLOSED
- **Closure evidence (2026-07-22 / Wave 4):**
  - Gate 2 decision: **OUT OF SCOPE** (`CSS_WAVE4_PRODUCT_HONESTY_SCOPE.md`)
  - `regulatory_reports.py` demoted to prototype / non-product
  - Catalogue honesty banner + executive package limitations align

---

## Coverage confirmation

| Master Audit confirmed theme | Remediation IDs |
| --- | --- |
| P0 blockers §5.1–§5.12 | AR-001, AR-002, AR-005, AR-006, AR-007, AR-008, AR-009, AR-011, AR-014, AR-015, AR-016, AR-017, AR-022 |
| P1 hardening §5 | AR-023, AR-024, AR-025, AR-026, AR-019, AR-020, AR-021, AR-028, AR-029, AR-031 |
| Incorrectly believed complete §7 | Covered by corresponding AR rows above |
| Production readiness §8 | AR-011–AR-016, AR-045 |
| Commercial readiness §9 | AR-017, AR-022–AR-025, AR-033, AR-046, AR-047 |
| Critical path stages A–D §10 | Mapped in `CSS_RELEASE_GATE_2_PLAN.md` and `CSS_REMEDIATION_PRIORITY_QUEUE.md` |

**Total remediation records:** 47  
**Critical:** 18 · **High:** 22 · **Medium:** 7 · **Low:** 0

---

*End of CSS Audit Remediation Register. This document does not authorize code changes, deployment, restart, broker authentication, or live trading.*
