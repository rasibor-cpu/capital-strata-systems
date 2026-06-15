# Phase 1 Operator Walkthrough Evidence

## Purpose

This artifact converts existing operations runbooks and controlled runtime/recovery evidence into retained operator walkthrough evidence for Phase 1 operations sign-off readiness.

This artifact is documentation-only. It does not change runtime behavior, broker behavior, trading logic, risk logic, dashboard behavior, credentials, thresholds, or execution behavior.

## Repository Verification

| Item | Evidence |
| --- | --- |
| Target branch | `css-evening-consolidation-2026-06-09` |
| Evidence assembly HEAD | `68e6408c757c1f574348745ab374ede25e1c4602` |
| Remote | `origin https://github.com/rasibor-cpu/capital-strata-systems.git` |
| Primary sources | `docs/governance/PHASE_103B_OPERATIONS_READINESS_REPORT.md`; `docs/operations/CSS_STARTUP_RUNBOOK.md`; `docs/operations/CSS_PAPER_TRADING_OPERATIONS_RUNBOOK.md`; `docs/operations/CSS_EMERGENCY_SHUTDOWN_RUNBOOK.md`; `docs/operations/CSS_RECOVERY_AND_RESTART_RUNBOOK.md`; `docs/operations/CSS_INCIDENT_RESPONSE_RUNBOOK.md`; `certification/runtime/PHASE_1_CONTROLLED_RUNTIME_SMOKE_VALIDATION_REPORT.md`; `certification/recovery/PHASE_1_RECOVERY_RESILIENCE_VALIDATION_REPORT.md` |

## Startup Procedure

| Step | Expected Operator Action | Evidence Basis | Status |
| --- | --- | --- | --- |
| Confirm repository context | Run and retain remote, branch, HEAD, and working-tree status before controlled operation | Startup runbook; runtime smoke report | Captured |
| Confirm approved mode | Confirm PAPER, PRACTICE, SIMULATION, or DEMO context only | Startup runbook; runtime smoke report | Captured |
| Confirm no live arm | Verify live execution is not armed and live trading is not enabled | Startup and emergency shutdown runbooks; live authorization evidence package | Captured |
| Authenticate without exposing sensitive material | Use approved sign-on path and do not retain credential values | Startup runbook; runtime smoke authentication evidence | Captured |
| Confirm session state | Validate active controlled session or safe fresh startup | Startup runbook; recovery validation report | Captured |
| Confirm dashboard visibility | Confirm runtime, broker mode, risk, margin, PnL, and audit/event visibility where applicable | Startup runbook; dashboard evidence report | Captured |
| Confirm trade-gate visibility | Confirm canonical decision path remains observable and non-executing in PAPER evidence | Runtime smoke report; runtime gate consolidation evidence | Captured |

## Shutdown Procedure

| Step | Expected Operator Action | Evidence Basis | Status |
| --- | --- | --- | --- |
| Stop new paper trade creation | Halt new paper activity before shutdown | Paper trading runbook; emergency shutdown runbook | Captured |
| Preserve evidence | Preserve terminal output, dashboard output, logs, branch, HEAD, and operator notes | Emergency shutdown and incident response runbooks | Captured |
| Confirm no broker order action | Do not place, cancel, or modify broker orders during shutdown | Emergency shutdown runbook | Captured |
| Close session if safe | Gracefully close session only when it does not risk further execution | Emergency shutdown and recovery runbooks | Captured |
| Record final disposition | Record normal shutdown, incident shutdown, or restart-required state | Runtime smoke report; incident response runbook | Captured |

## Recovery Procedure

| Step | Expected Operator Action | Evidence Basis | Status |
| --- | --- | --- | --- |
| Document interruption reason | Record incident or shutdown reason before restart | Recovery/restart runbook | Captured |
| Confirm safety boundary | Confirm no live mode, no live arm, no broker order, and no credential change | Recovery/restart runbook; recovery validation report | Captured |
| Re-run prechecks | Confirm remote, branch, HEAD, and working-tree state | Recovery/restart runbook | Captured |
| Validate session and state | Confirm session mode, database readiness, legal acceptance reachability, and dashboard state | Recovery validation report | Captured with observations |
| Escalate ambiguous state | Stop and escalate if session, broker, or live state is ambiguous | Recovery/restart runbook | Captured |

## Escalation Path

| Severity | Escalation Path | Required Decision |
| --- | --- | --- |
| Low | Operator to Operations Reviewer if repeated | Continue only if safety and evidence integrity remain clear |
| Medium | Operator to Operations Reviewer to Governance Reviewer | Pause affected activity and determine evidence validity |
| High | Operator to Operations Reviewer to Governance Reviewer to Robert | Stop new activity; Robert review before certification use or restart when safety/governance is affected |
| Critical | Operator to Robert immediately, with Developer, Governance Reviewer, and Operations Reviewer engaged | Emergency shutdown; do not restart until reviewed |

## Expected Operator Actions

| Area | Expected Action | Status |
| --- | --- | --- |
| Branch discipline | Operate only on approved target branch and commit | Captured |
| Mode discipline | PAPER/PRACTICE/SIMULATION only unless separately approved | Captured |
| Credential handling | Do not print, copy, edit, or retain credential values | Captured |
| Broker safety | Do not initiate broker order placement during certification evidence collection | Captured |
| Evidence preservation | Preserve logs, dashboard output, terminal output, and incident notes | Captured |
| Restart discipline | Restart only after safety checks, evidence preservation, and escalation decisions | Captured |

## Certification Result

| Operations Gap | Prior Status | Phase 1 Closure Status | Remaining Need |
| --- | --- | --- | --- |
| GAP-OPS-001: Operator training and walkthrough | Open | Captured as documentation-based walkthrough evidence | Formal operator sign-off acceptance |
| OPS-GAP-001 through OPS-GAP-004 | Not started / pending in register | Supported by startup, sign-on, broker display, paper workflow, and runtime evidence | Reviewer acceptance and live-read broker evidence where applicable |

## Recommendation

Accept this artifact as Phase 1 operator walkthrough evidence for controlled PAPER operations. Production operations sign-off still requires formal reviewer acceptance and closure of broker read-only, monitoring, incident, rollback, and final approval dependencies.
