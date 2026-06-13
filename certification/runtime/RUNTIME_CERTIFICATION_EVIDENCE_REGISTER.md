# Runtime Certification Evidence Register

## 1. Purpose

This register is the Phase 101D runtime certification evidence artifact for Capital Strata Systems (CSS).

Its purpose is to identify the runtime evidence required to support controlled certification review, distinguish captured runtime claims from pending evidence attachments, and preserve the documentation boundary for certification work. This document is documentation-only. It does not change runtime behavior, dashboard behavior, broker behavior, execution behavior, risk logic, margin logic, governance logic, or trading permissions.

## 2. Runtime Certification Scope

Runtime certification evidence covers controlled observations of CSS while the system is started, operated, monitored, stopped, restored, and reviewed.

This register covers:

* startup and sign-on evidence
* session restore evidence
* engine mode evidence
* runtime event evidence
* replay and audit evidence
* paper and practice runtime evidence
* live runtime blocking evidence
* known runtime evidence gaps

This register does not approve production operation. It identifies evidence needed before CSS can move from controlled paper readiness toward institutional production certification.

## 3. Startup / Sign-on Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RUNTIME-START-001 | Controlled CSS startup log | Pending evidence attachment. | NOT_STARTED | Phase 100A and Phase 101A require startup evidence for certification. |
| RUNTIME-START-002 | Operator sign-on or session initialization record | Pending evidence attachment. | NOT_STARTED | Evidence must show who initiated the controlled run and under what approved scope. |
| RUNTIME-START-003 | Initial broker selection and broker mode display | Pending evidence attachment. | NOT_STARTED | Evidence must distinguish simulated, paper, practice, and live contexts. |
| RUNTIME-START-004 | Startup warnings and failure handling output | Pending evidence attachment. | NOT_STARTED | Evidence must capture warnings and confirm they are actionable. |
| RUNTIME-START-005 | No unauthorized live execution at startup | Pending evidence attachment. | NOT_STARTED | Certification requires proof that startup does not silently enable live trading. |

## 4. Session Restore Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RUNTIME-RESTORE-001 | Session recovery behavior record | Pending evidence attachment. | NOT_STARTED | Phase 100C and Phase 101A identify recovery certification as incomplete. |
| RUNTIME-RESTORE-002 | Persistence file handling evidence | Pending evidence attachment. | NOT_STARTED | Evidence must show what state is restored and what is intentionally not restored. |
| RUNTIME-RESTORE-003 | Stale exposure handling evidence | Pending evidence attachment. | NOT_STARTED | Certification requires confirmation that stale open exposure is not restored unsafely. |
| RUNTIME-RESTORE-004 | Failed restore safe behavior | Pending evidence attachment. | NOT_STARTED | Evidence must show failed recovery degrades safely or fails closed. |

## 5. Engine Mode Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RUNTIME-MODE-001 | Paper or practice mode evidence | Pending evidence attachment. | NOT_STARTED | CSS governance allows controlled paper operation within approved constraints. |
| RUNTIME-MODE-002 | Simulated source labeling evidence | Pending evidence attachment. | NOT_STARTED | Phase 100A requires simulated and live sources to be clearly labeled. |
| RUNTIME-MODE-003 | Live mode authorization evidence | Pending evidence attachment. | NOT_STARTED | Live mode requires explicit approval and retained evidence. |
| RUNTIME-MODE-004 | Broker mode consistency evidence | Pending evidence attachment. | NOT_STARTED | Evidence must show runtime broker mode matches the selected operating context. |
| RUNTIME-MODE-005 | Margin state and margin source mode evidence | Pending evidence attachment. | NOT_STARTED | Phase 99 added display-only visibility; certification still requires captured runtime evidence. |

## 6. Runtime Event Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RUNTIME-EVENT-001 | Runtime event log sample | Pending evidence attachment. | NOT_STARTED | Material decisions, state transitions, broker interactions, risk outcomes, and recovery events must be reviewable. |
| RUNTIME-EVENT-002 | Warning and exception handling evidence | Pending evidence attachment. | NOT_STARTED | Certification requires no unresolved critical runtime exception. |
| RUNTIME-EVENT-003 | Risk decision visibility evidence | Pending evidence attachment. | NOT_STARTED | Runtime evidence should show risk state observations under controlled scenarios. |
| RUNTIME-EVENT-004 | Margin decision visibility evidence | Pending evidence attachment. | NOT_STARTED | Runtime evidence should show margin state and margin trade gate decision visibility without enforcement changes. |
| RUNTIME-EVENT-005 | Dashboard runtime panel evidence | Pending evidence attachment. | NOT_STARTED | Dashboard captures belong under dashboard evidence, but runtime evidence must reference controlled run context. |

## 7. Replay / Audit Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RUNTIME-AUDIT-001 | Audit log retention evidence | Pending evidence attachment. | NOT_STARTED | Phase 100A and Phase 100B require audit log evidence and retention requirements. |
| RUNTIME-AUDIT-002 | Replayable runtime output evidence | Pending evidence attachment. | NOT_STARTED | Certification evidence must be reproducible enough for another reviewer to challenge the claim. |
| RUNTIME-AUDIT-003 | Runtime decision trace evidence | Pending evidence attachment. | NOT_STARTED | Evidence must connect observed decisions to retained logs or terminal output. |
| RUNTIME-AUDIT-004 | Controlled run transcript or terminal output | Pending evidence attachment. | NOT_STARTED | Runtime logs, screenshots, and terminal output are expected evidence sources. |

## 8. Paper / Practice Runtime Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RUNTIME-PAPER-001 | Controlled paper run evidence | Pending evidence attachment. | NOT_STARTED | Phase 101A recommends controlled paper operation only within existing governance constraints. |
| RUNTIME-PAPER-002 | Paper run with margin dashboard visible | Pending evidence attachment. | NOT_STARTED | Phase 101A identifies this as required testing evidence. |
| RUNTIME-PAPER-003 | Paper run with margin gate decision visible | Pending evidence attachment. | NOT_STARTED | Evidence must show visibility only, not execution enforcement changes. |
| RUNTIME-PAPER-004 | Paper run confirming no live order placement | Pending evidence attachment. | NOT_STARTED | Required to prove paper/live separation. |
| RUNTIME-PAPER-005 | Controlled shutdown evidence | Pending evidence attachment. | NOT_STARTED | Runtime evidence must include shutdown behavior, not only startup. |

## 9. Live Runtime Blocking Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RUNTIME-LIVE-001 | Unauthorized live execution blocked evidence | Pending evidence attachment. | NOT_STARTED | Phase 100A identifies unauthorized live execution path as a certification failure condition. |
| RUNTIME-LIVE-002 | Unknown live margin state fail-closed evidence | Pending evidence attachment. | NOT_STARTED | Phase 101A calls for LIVE UNKNOWN fail-closed validation before new exposure. |
| RUNTIME-LIVE-003 | Live broker read-only evidence | Pending evidence attachment. | NOT_STARTED | Live-read evidence belongs to broker evidence but must be tied to controlled runtime context. |
| RUNTIME-LIVE-004 | Live mode approval gate evidence | Pending evidence attachment. | NOT_STARTED | Live mode must not be used without explicit authorization and retained evidence. |
| RUNTIME-LIVE-005 | No production onboarding approval evidence | Pending evidence attachment. | NOT_STARTED | Phase 100C and Phase 101A state production onboarding remains blocked. |

## 10. Known Gaps / Future Evidence

| Gap ID | Gap | Area | Required Future Evidence |
| --- | --- | --- | --- |
| RUNTIME-GAP-001 | No formal end-to-end runtime certification run is attached. | Runtime | Controlled certification session logs, screenshots, and terminal output. |
| RUNTIME-GAP-002 | Startup and shutdown evidence is not attached. | Startup / Shutdown | Captured startup and shutdown output from approved run. |
| RUNTIME-GAP-003 | Session restore and persistence evidence is not attached. | Recovery | Restore behavior, persistence handling, and stale exposure evidence. |
| RUNTIME-GAP-004 | Runtime audit replay evidence is not attached. | Audit / Replay | Retained logs and replayable decision traces. |
| RUNTIME-GAP-005 | Paper/practice run evidence is not attached. | Paper Runtime | Controlled paper run proof with no live order placement. |
| RUNTIME-GAP-006 | Live blocking evidence is not attached. | Live Safety | Proof that unauthorized live behavior and unknown live risk states are blocked. |

## 11. Certification Notes

This register is a runtime evidence map, not a runtime certification approval.

Current runtime certification posture:

* CSS governance identifies controlled paper readiness as the appropriate near-term posture.
* Formal runtime certification evidence remains incomplete.
* Runtime startup, shutdown, recovery, audit, and live blocking evidence must still be attached.
* Dashboard and broker evidence may support runtime review, but must remain categorized in their own package areas when captured.

Certification implication:

CSS can continue controlled certification evidence assembly and controlled paper-readiness review. CSS is not institutionally production certified until runtime evidence is captured, retained, reviewed, approved, and Robert records final approval.

Documentation-only confirmation:

* No runtime behavior was changed.
* No dashboard behavior was changed.
* No broker behavior was changed.
* No execution behavior was changed.
* No risk behavior was changed.
* No margin behavior was changed.
* No governance logic was changed.
* No trading logic was changed.
* No tests were modified.
