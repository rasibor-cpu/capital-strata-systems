# Operations Certification Evidence Register

## 1. Purpose

This register is the Phase 101J operations certification evidence artifact for Capital Strata Systems (CSS).

Its purpose is to identify operational evidence required for certification review, document known CSS operating concepts, separate referenced controls from pending evidence attachments, and preserve the documentation boundary during certification assembly. This document is documentation-only. It does not alter runtime behavior, operational behavior, broker behavior, execution behavior, dashboard behavior, risk controls, margin functionality, security controls, authentication, authorization, credentials, or trading logic.

## 2. Operations Certification Scope

Operations certification evidence covers daily startup, login and session operations, broker selection, paper trading workflow, live trading workflow, monitoring expectations, audit and reporting expectations, incident escalation, and manual operational controls.

This register covers:

* startup procedure evidence
* sign-on and session operation evidence
* broker selection workflow evidence
* paper-mode workflow evidence
* live-mode workflow evidence
* operational monitoring evidence
* audit review evidence
* operator responsibility evidence
* manual control procedure evidence
* incident escalation evidence

This register does not certify production operations. It records operational evidence availability and missing attachments for Robert review.

## 3. Daily Startup Operations Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| OPS-START-001 | Daily startup procedure | Pending evidence attachment | NOT_STARTED | Phase 100A and Phase 101A require startup evidence and production runbook materials. |
| OPS-START-002 | Controlled startup log | `certification/runtime/RUNTIME_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Runtime register maps startup evidence requirements; actual startup output remains pending. |
| OPS-START-003 | Startup checklist evidence | Pending evidence attachment | NOT_STARTED | Operator startup checklist is not attached. |
| OPS-START-004 | Startup warning review evidence | Pending evidence attachment | NOT_STARTED | Startup warnings must be captured and reviewed before certification. |
| OPS-START-005 | Startup confirms no unauthorized live execution | Pending evidence attachment | NOT_STARTED | Certification requires proof startup does not silently enable live trading. |

## 4. Login and Session Operations Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| OPS-LOGIN-001 | Sign-on procedure evidence | Pending evidence attachment | NOT_STARTED | Operator sign-on procedure is not attached. |
| OPS-LOGIN-002 | Login operation evidence | `certification/security/SECURITY_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Security register maps authentication evidence requirements; operational proof remains pending. |
| OPS-LOGIN-003 | Session initialization evidence | `certification/runtime/RUNTIME_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Runtime register maps session initialization evidence requirements; actual record remains pending. |
| OPS-LOGIN-004 | Session timeout or expiry operations evidence | Pending evidence attachment | NOT_STARTED | Session timeout handling evidence remains pending. |
| OPS-LOGIN-005 | Operator identity and role evidence | Pending evidence attachment | NOT_STARTED | Final RBAC/operator role matrix remains pending. |

## 5. Broker Selection Operations Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| OPS-BROKER-001 | Broker selection workflow evidence | Pending evidence attachment | NOT_STARTED | Selected broker workflow evidence is not attached. |
| OPS-BROKER-002 | Selected broker display evidence | `certification/broker/BROKER_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Broker register maps selected broker evidence requirements; display proof remains pending. |
| OPS-BROKER-003 | Broker mode display evidence | Pending evidence attachment | NOT_STARTED | Evidence must distinguish simulated, paper, practice, and live modes. |
| OPS-BROKER-004 | Unsupported broker fallback operations evidence | Pending evidence attachment | NOT_STARTED | Unsupported broker handling evidence remains pending. |
| OPS-BROKER-005 | Broker credential safety operations evidence | `certification/security/SECURITY_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Security register maps credential safety requirements; redaction evidence remains pending. |

## 6. Paper Trading Operations Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| OPS-PAPER-001 | Paper-mode workflow evidence | Pending evidence attachment | NOT_STARTED | Controlled paper workflow evidence remains pending. |
| OPS-PAPER-002 | Controlled paper run evidence | `certification/runtime/RUNTIME_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Runtime register maps controlled paper run evidence; retained run output remains pending. |
| OPS-PAPER-003 | Paper mode clearly displayed | Pending evidence attachment | NOT_STARTED | Phase 100A requires paper mode to be clearly displayed. |
| OPS-PAPER-004 | Paper run confirms no live order placement | Pending evidence attachment | NOT_STARTED | Paper/live separation evidence remains pending. |
| OPS-PAPER-005 | Paper run monitoring checklist | Pending evidence attachment | NOT_STARTED | Operator monitoring checklist for paper operation is not attached. |

## 7. Live Trading Operations Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| OPS-LIVE-001 | Live-mode workflow evidence | Pending evidence attachment | NOT_STARTED | Live workflow is not approved by this register and evidence is not attached. |
| OPS-LIVE-002 | Live mode explicit authorization evidence | `certification/security/SECURITY_CERTIFICATION_EVIDENCE_REGISTER.md`; `certification/broker/BROKER_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Security and broker registers map live authorization requirements; runtime proof remains pending. |
| OPS-LIVE-003 | Live broker read-only evidence | Pending evidence attachment | NOT_STARTED | OANDA and Coinbase live-read evidence remains pending. |
| OPS-LIVE-004 | Live execution blocking evidence | Pending evidence attachment | NOT_STARTED | Unauthorized live execution must be blocked and evidenced. |
| OPS-LIVE-005 | Production onboarding approval evidence | Pending evidence attachment | NOT_STARTED | Phase 100C and Phase 101A state production onboarding remains blocked. |

## 8. Monitoring Operations Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| OPS-MONITOR-001 | Operational monitoring plan | Pending evidence attachment | NOT_STARTED | Phase 100C identifies production monitoring plan as missing. |
| OPS-MONITOR-002 | Dashboard monitoring evidence | Pending evidence attachment | NOT_STARTED | Dashboard runtime screenshots/logs remain pending. |
| OPS-MONITOR-003 | Broker monitoring evidence | Pending evidence attachment | NOT_STARTED | Broker live-read and broker-mode monitoring evidence remains pending. |
| OPS-MONITOR-004 | Risk and margin monitoring evidence | Pending evidence attachment | NOT_STARTED | Runtime evidence for risk and margin panels remains pending. |
| OPS-MONITOR-005 | Alerting or warning review evidence | Pending evidence attachment | NOT_STARTED | Warning and alert review procedure is not attached. |

## 9. Audit and Reporting Operations Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| OPS-AUDIT-001 | Audit review procedure | Pending evidence attachment | NOT_STARTED | Audit log retention and review procedure remains pending. |
| OPS-AUDIT-002 | Audit log evidence | `certification/runtime/RUNTIME_CERTIFICATION_EVIDENCE_REGISTER.md`; `certification/security/SECURITY_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Runtime and security registers map audit evidence requirements; retained logs remain pending. |
| OPS-AUDIT-003 | Reporting pack evidence | Pending evidence attachment | NOT_STARTED | Operational reporting evidence is not attached. |
| OPS-AUDIT-004 | Operator action review evidence | Pending evidence attachment | NOT_STARTED | Operator action review record remains pending. |
| OPS-AUDIT-005 | Certification sign-off record | Pending evidence attachment | NOT_STARTED | Developer, governance, operations, and Robert sign-off evidence remains pending. |

## 10. Incident Escalation Considerations

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| OPS-INCIDENT-001 | Incident response workflow | Pending evidence attachment | NOT_STARTED | Phase 100C and Phase 101A identify incident response workflow as incomplete. |
| OPS-INCIDENT-002 | Escalation contact and responsibility matrix | Pending evidence attachment | NOT_STARTED | Operator responsibility matrix is not attached. |
| OPS-INCIDENT-003 | Kill-switch or stop procedure evidence | Pending evidence attachment | NOT_STARTED | Incident response and kill-switch evidence remains pending. |
| OPS-INCIDENT-004 | Broker/account outage escalation evidence | Pending evidence attachment | NOT_STARTED | Broker/account data unavailability recovery evidence remains pending. |
| OPS-INCIDENT-005 | Incident audit trail evidence | Pending evidence attachment | NOT_STARTED | Incident events must be traceable through retained audit or runtime evidence. |

## 11. Manual Operational Controls

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| OPS-MANUAL-001 | Manual operational control procedure | Pending evidence attachment | NOT_STARTED | Manual controls are expected, but procedure evidence is not attached. |
| OPS-MANUAL-002 | Manual recovery checklist | `certification/recovery/RECOVERY_RESILIENCE_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Recovery register maps manual recovery expectations; runbook remains pending. |
| OPS-MANUAL-003 | Manual live-mode approval control | Pending evidence attachment | NOT_STARTED | Live mode must require explicit authorization and retained approval evidence. |
| OPS-MANUAL-004 | Manual broker mode verification control | Pending evidence attachment | NOT_STARTED | Operator must verify broker and mode before controlled operation. |
| OPS-MANUAL-005 | Manual rollback procedure | Pending evidence attachment | NOT_STARTED | Phase 100C identifies rollback procedure as incomplete. |

## 12. Known Gaps / Future Evidence

| Gap ID | Gap | Area | Required Future Evidence |
| --- | --- | --- | --- |
| OPS-GAP-001 | Daily startup runbook is not attached. | Startup Operations | Approved startup procedure, checklist, and controlled startup evidence. |
| OPS-GAP-002 | Sign-on and session operations evidence is not attached. | Login / Session | Operator sign-on, session initialization, timeout, and role evidence. |
| OPS-GAP-003 | Broker selection workflow evidence is not attached. | Broker Operations | Selected broker, broker mode, and unsupported broker fallback evidence. |
| OPS-GAP-004 | Paper-mode workflow evidence is not attached. | Paper Operations | Controlled paper run proof, display evidence, and no live order placement evidence. |
| OPS-GAP-005 | Live-mode workflow evidence is not attached. | Live Operations | Explicit authorization, read-only broker evidence, and live blocking proof. |
| OPS-GAP-006 | Monitoring plan and dashboard captures are not attached. | Monitoring | Dashboard screenshots/logs, warnings, alerts, risk, margin, and broker monitoring evidence. |
| OPS-GAP-007 | Audit review and reporting evidence is not attached. | Audit / Reporting | Audit review procedure, retained logs, report pack, and operator action review evidence. |
| OPS-GAP-008 | Incident response and rollback evidence is not attached. | Incident / Rollback | Incident workflow, escalation matrix, kill-switch, outage handling, and rollback procedure. |
| OPS-GAP-009 | Final operations sign-off is not attached. | Sign-Off | Operations review and Robert final approval disposition. |

## 13. Certification Notes

This register is an operations evidence map, not an operational production approval.

Current operations certification posture:

* CSS governance identifies controlled paper readiness as the current appropriate operational posture.
* Operational runbook, rollback procedure, production monitoring plan, incident response workflow, runtime certification evidence, and final operational approval remain incomplete.
* Known operational concepts include startup procedures, sign-on procedures, broker selection workflow, paper-mode workflow, live-mode workflow, operational monitoring expectations, audit review expectations, operator responsibilities, and manual control procedures.
* Formal retained evidence for operations execution, monitoring, audit review, incident response, manual controls, and sign-off remains pending.

Certification implication:

CSS may continue controlled certification evidence assembly and controlled paper-readiness review. CSS is not institutionally production certified for operations until operational evidence is captured, retained, reviewed, approved, and Robert records final approval.

Documentation-only confirmation:

* No code changes were made.
* No tests were modified.
* No runtime behavior was changed.
* No operational behavior was changed.
* No dashboard behavior was changed.
* No broker behavior was changed.
* No execution behavior was changed.
* No risk-control behavior was changed.
* No margin functionality was changed.
* No security controls were changed.
* No authentication behavior was changed.
* No authorization behavior was changed.
* No credentials were changed.
* No trading logic was changed.
