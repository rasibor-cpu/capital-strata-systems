# CSS Certification Package Index

## 1. Package Purpose

This package is the authoritative evidence structure for Capital Strata Systems (CSS) certification.

The package exists to collect, organize, review, and retain evidence required to move CSS from controlled development and paper validation toward institutional production readiness.

The package must make certification review reproducible by identifying:

* what evidence exists
* where evidence is stored
* which certification domain it supports
* what evidence remains missing
* who reviewed the evidence
* whether evidence is approved for certification use

This phase is documentation and package structure only. It does not change runtime behavior, dashboard behavior, broker behavior, execution behavior, risk behavior, or margin behavior.

## 2. Package Structure

| Folder | Purpose |
| --- | --- |
| `certification/governance/` | Governance frameworks, phase closeouts, certification decisions, review notes. |
| `certification/testing/` | Unit, integration, regression, compile, and validation outputs. |
| `certification/runtime/` | Startup, shutdown, runtime smoke, and controlled run evidence. |
| `certification/dashboard/` | Dashboard screenshots, rendered panel captures, and display validation. |
| `certification/broker/` | Broker adapter evidence, broker mode evidence, credential safety notes, live-read artifacts. |
| `certification/risk/` | Risk engine, risk gate, stress, correlation, and risk decision evidence. |
| `certification/margin/` | Margin engine, broker margin adapters, margin gate, and margin dashboard evidence. |
| `certification/recovery/` | Session recovery, persistence, stale position handling, and safe restore evidence. |
| `certification/security/` | Authentication, authorization, secret handling, and security validation evidence. |
| `certification/operations/` | Runbooks, rollback procedures, incident response, monitoring, and sign-off evidence. |

## 3. Governance Evidence Section

Governance evidence must reference and retain:

| Phase | Artifact |
| --- | --- |
| Phase 100A | `docs/governance/PHASE100A_INSTITUTIONAL_CERTIFICATION_FRAMEWORK.md` |
| Phase 100B | `docs/governance/PHASE100B_CERTIFICATION_EVIDENCE_REGISTRY.md` |
| Phase 100C | `docs/governance/PHASE100C_PRODUCTION_READINESS_AUDIT.md` |
| Phase 101A | `docs/governance/PHASE101A_CERTIFICATION_CLOSEOUT_AND_REMEDIATION_PLAN.md` |

Expected governance evidence:

* certification framework
* evidence registry
* production readiness audit
* closeout and remediation plan
* review notes
* approval disposition

## 4. Risk Evidence Section

Risk evidence must reference:

| Phase | Evidence Focus |
| --- | --- |
| Phase 91 | Correlation intelligence evidence. |
| Phase 92 | Portfolio stress testing framework evidence. |
| Phase 92B | Follow-on portfolio risk evidence. |
| Phase 93 | Institutional risk expansion evidence. |
| Phase 94 | Institutional risk expansion evidence. |
| Phase 98 | Margin-aware trade gate evidence. |

Expected risk evidence:

* source file references
* test commands and outputs
* risk decision examples
* fail-closed behavior evidence
* remaining integration gaps

## 5. Margin Evidence Section

Margin evidence must reference:

| Phase | Evidence Focus |
| --- | --- |
| Phase 95 | Institutional margin governance framework. |
| Phase 96A | Margin architecture definition. |
| Phase 96B | Margin engine. |
| Phase 97A | Broker margin contract. |
| Phase 97B.1 | OANDA margin adapter skeleton. |
| Phase 97B.2 | OANDA live margin retrieval and fallback. |
| Phase 97C | Coinbase margin adapter. |
| Phase 99 | Margin dashboard visibility. |

Expected margin evidence:

* margin engine test output
* broker margin contract test output
* OANDA adapter test output
* Coinbase adapter test output
* margin trade gate test output
* margin dashboard output
* live-read evidence where approved

## 6. Broker Evidence Section

Broker evidence must cover:

### OANDA

Expected OANDA evidence:

* selected broker and broker mode
* credential safety evidence
* read-only account or margin retrieval evidence
* simulated fallback evidence
* no-order-placement evidence
* failure handling evidence

### Coinbase

Expected Coinbase evidence:

* selected broker and broker mode
* credential safety evidence
* read-only account or margin retrieval evidence
* spot non-margin default evidence
* simulated fallback evidence
* no-order-placement evidence
* failure handling evidence

## 7. Runtime Evidence Section

Runtime evidence must include:

* startup evidence
* shutdown evidence
* dashboard evidence
* audit log evidence
* runtime validation output
* selected broker mode
* margin dashboard panel output
* risk/margin gate visibility
* controlled failure path evidence

Runtime evidence must be captured from controlled runs only.

## 8. Recovery Evidence Section

Recovery evidence must include:

* session recovery behavior
* persistence file behavior
* stale position handling
* explicit resume behavior
* safe fallback behavior
* recovery failure evidence
* recovery audit notes

Recovery certification must confirm that stale open exposure is not restored unsafely.

## 9. Certification Status Table

| Status | Meaning |
| --- | --- |
| NOT_STARTED | Evidence has not been collected. |
| IN_PROGRESS | Evidence collection or review is underway. |
| CAPTURED | Evidence has been collected and stored in the package. |
| REVIEWED | Evidence has been reviewed by the assigned reviewer. |
| APPROVED | Evidence has been approved for certification use. |

Status changes must be recorded in the relevant evidence folder or review notes.

## 10. Missing Evidence Register

The following evidence is expected but not yet captured in this package:

| Evidence Item | Category | Status | Notes |
| --- | --- | --- | --- |
| Full test suite output | Testing | NOT_STARTED | Required before production candidate review. |
| Runtime smoke logs | Runtime | NOT_STARTED | Required for controlled certification. |
| Dashboard screenshots or captured output | Dashboard | NOT_STARTED | Required for operational review. |
| OANDA live-read evidence | Broker | NOT_STARTED | Read-only only; no order placement. |
| Coinbase live-read evidence | Broker | NOT_STARTED | Read-only only; no order placement. |
| Recovery validation evidence | Recovery | NOT_STARTED | Must include stale position behavior. |
| Credential redaction evidence | Security | NOT_STARTED | Must confirm no secret disclosure. |
| Operational runbook | Operations | NOT_STARTED | Required before production onboarding. |
| Rollback procedure | Operations | NOT_STARTED | Required before production onboarding. |
| Robert final sign-off | Operations | NOT_STARTED | Required for final certification approval. |

## 11. Final Certification Sign-Off

Final certification requires sign-off from:

| Reviewer | Responsibility | Status |
| --- | --- | --- |
| Developer | Confirms implementation scope, changed files, commands, and technical evidence. | NOT_STARTED |
| Governance | Confirms artifacts, evidence registry mapping, and certification status. | NOT_STARTED |
| Operations | Confirms runtime evidence, runbook, rollback, and operational safety. | NOT_STARTED |
| Robert | Performs final certification review and approval. | NOT_STARTED |

Final certification cannot be granted until all required sign-off states are reviewed and approved.

STATUS: CERTIFICATION PACKAGE STRUCTURE ESTABLISHED
