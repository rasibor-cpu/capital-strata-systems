# Phase 1 Incident Tabletop Exercise Report

## Purpose

This report records a documentation-based Phase 1 incident tabletop exercise for operations certification readiness. It uses the existing incident response, emergency shutdown, recovery/restart, monitoring, and runtime/recovery evidence package.

This artifact is documentation-only. It does not change runtime behavior, broker behavior, trading logic, risk logic, dashboard behavior, credentials, thresholds, or execution behavior.

## Repository Verification

| Item | Evidence |
| --- | --- |
| Target branch | `css-evening-consolidation-2026-06-09` |
| Evidence assembly HEAD | `68e6408c757c1f574348745ab374ede25e1c4602` |
| Remote | `origin https://github.com/rasibor-cpu/capital-strata-systems.git` |

## Incident Scenario

Controlled PAPER certification run reports a broker/account unavailable condition and unclear dashboard readiness. No live order placement is observed, but operator monitoring cannot confirm broker/account data as authoritative.

## Actions Taken

| Step | Tabletop Action | Expected Evidence |
| --- | --- | --- |
| 1 | Pause new paper trade creation | Operator run notes |
| 2 | Preserve dashboard output, runtime output, branch, HEAD, and broker readiness reason | Evidence archive entry |
| 3 | Confirm runtime and broker mode remain PAPER/DEMO/PRACTICE/SIMULATION | Runtime/dashboard capture |
| 4 | Confirm no order placement, broker mutation, or credential exposure occurred | Broker safe-fail and operator notes |
| 5 | Classify incident | MEDIUM if monitoring degraded only; HIGH if evidence validity is compromised; CRITICAL if live mode, live arm, credential exposure, or broker order is detected |
| 6 | Escalate to Operations Reviewer and Governance Reviewer if evidence validity is affected | Incident record |
| 7 | Follow recovery/restart runbook if restart is needed | Restart evidence |
| 8 | Require Robert review for HIGH/CRITICAL disposition | Final reviewer record |

## Expected Decisions

| Decision Point | Expected Decision |
| --- | --- |
| Broker/account unavailable but PAPER mode clear | Continue only if run purpose does not require live-read broker evidence; otherwise defer broker evidence |
| Dashboard readiness unclear | Pause new paper activity until visibility is restored or evidence is classified partial |
| Session state ambiguous | Stop and follow recovery/restart runbook |
| Credential exposure suspected | Critical incident; emergency shutdown |
| Live mode or live arm appears | Critical incident; emergency shutdown |
| Broker order attempted | Critical incident; preserve evidence and do not resume without Robert review |

## Lessons Learned

| Lesson | Operational Effect |
| --- | --- |
| PAPER evidence can proceed only when mode, broker, and dashboard state are unambiguous | Operators must stop when visibility becomes unclear |
| Broker unavailable evidence is valid for safe-fail but not a substitute for approved read-only broker evidence | Broker certification remains separate |
| Incident severity depends on safety boundary impact, not just runtime success/failure | Clear escalation rules reduce ambiguity |
| Evidence preservation is part of the operational control | Failed or partial runs remain certification evidence |

## Residual Risks

| Risk | Severity | Closure Recommendation |
| --- | --- | --- |
| No live-read broker operational tabletop yet | Critical for production | Close with OANDA/Coinbase approved read-only package |
| No long-duration monitoring tabletop yet | High | Capture during extended controlled run or production-candidate validation |
| No signed operator tabletop attendance record | Medium | Add sign-off record during final Operations review |
| Audit retention owner/procedure still pending | High | Close with Governance/Operations retention owner assignment |

## Certification Result

| Operations Gap | Prior Status | Phase 1 Closure Status | Remaining Need |
| --- | --- | --- | --- |
| GAP-OPS-002: Incident tabletop | Open | Captured as documentation-based tabletop exercise | Formal Operations/Governance acceptance |
| OPS-GAP-008: Incident response and rollback evidence | Open | Partially captured | Final tabletop sign-off and any production-candidate incident drill required by governance |

## Recommendation

Accept this tabletop as Phase 1 controlled PAPER incident-response evidence. Production incident readiness remains conditional on live-read broker evidence, monitoring validation, audit retention ownership, operations sign-off, and Robert final approval.
