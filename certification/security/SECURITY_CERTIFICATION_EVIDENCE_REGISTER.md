# Security Certification Evidence Register

## 1. Purpose

This register is the Phase 101I security certification evidence artifact for Capital Strata Systems (CSS).

Its purpose is to identify security evidence required for certification review, document known CSS security concepts, separate referenced controls from pending evidence attachments, and preserve the documentation boundary during certification assembly. This document is documentation-only. It does not alter authentication, authorization, credentials, runtime behavior, broker behavior, dashboard behavior, execution behavior, risk controls, margin functionality, or trading logic.

No passwords, API keys, tokens, secrets, account numbers, credential values, or broker authentication material are included in this register.

## 2. Security Certification Scope

Security certification evidence covers authentication, session security, password protection, RBAC, credential protection, broker credential security, audit security, runtime security controls, live trading security controls, monitoring considerations, and known security evidence gaps.

This register covers:

* user authentication evidence
* session management and session timeout evidence
* password protection evidence
* RBAC and SUPER_USER authorization evidence
* legal and risk acceptance control evidence
* credential separation evidence
* broker credential protection evidence
* audit logging evidence
* live trading restriction evidence
* security monitoring evidence

This register does not certify production security readiness. It records security evidence availability and missing attachments for Robert review.

## 3. Authentication Security Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| SEC-AUTH-001 | CSS security architecture evidence | `docs/security/CSS_SECURITY_ARCHITECTURE.md` | CAPTURED | Defines security objectives, protection of broker credentials, unauthorized trading prevention, and auditability principles. |
| SEC-AUTH-002 | User authentication implementation evidence | `backend/security/user_auth.py`; `backend/app/security/user_registry.py`; `backend/app/auth/auth_router.py` | REFERENCED | Authentication paths are referenced; certification output remains pending. |
| SEC-AUTH-003 | Headless or app authentication evidence | `backend/app/headless_auth.py`; `backend/app/auth/auth_router.py` | REFERENCED | Authentication paths are referenced; controlled runtime evidence remains pending. |
| SEC-AUTH-004 | Failed-login behavior evidence | Pending evidence attachment | NOT_STARTED | Evidence must show authentication failure is controlled and does not disclose sensitive details. |
| SEC-AUTH-005 | Legal/risk acceptance before production auth expansion | Pending evidence attachment | NOT_STARTED | Governance evidence identifies formal legal and risk acceptance attachments as pending. |

## 4. Session Security Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| SEC-SESSION-001 | Session management implementation evidence | `engine/security/session_manager.py`; `backend/security/session_manager.py`; `backend/app/persistence/services/session_runtime_service.py` | REFERENCED | Session-related paths are referenced; certification run evidence remains pending. |
| SEC-SESSION-002 | Session timeout evidence | `engine/security/session_manager.py`; `backend/app/observability/session_time.py` | REFERENCED | Session timeout concepts are referenced; controlled evidence remains pending. |
| SEC-SESSION-003 | Active session required for protected action evidence | `engine/security/security_context.py`; `backend/app/observability/audit_context.py` | REFERENCED | Security context and audit context paths are referenced; retained proof remains pending. |
| SEC-SESSION-004 | Session lock, resume, and close evidence | Pending evidence attachment | NOT_STARTED | Governance and runtime evidence registers identify session lifecycle evidence as pending. |
| SEC-SESSION-005 | Session recovery security evidence | Pending evidence attachment | NOT_STARTED | Recovery and persistence evidence must prove safe session behavior. |

## 5. Password Protection Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| SEC-PASSWORD-001 | Password hashing implementation evidence | `backend/security/user_auth.py`; `backend/app/security/user_registry.py` | REFERENCED | Password protection paths are referenced; no password values are included here. |
| SEC-PASSWORD-002 | Password change workflow evidence | `backend/security/user_auth.py`; `backend/app/security/auth_gate.py`; `backend/app/security/user_registry.py` | REFERENCED | Password change paths are referenced; certification output remains pending. |
| SEC-PASSWORD-003 | Password reset workflow evidence | `backend/security/user_auth.py`; `backend/security/permissions.py` | REFERENCED | Password reset and permissions paths are referenced; retained evidence remains pending. |
| SEC-PASSWORD-004 | No password disclosure in certification evidence | Pending evidence attachment | NOT_STARTED | Evidence must confirm no passwords appear in logs, docs, commits, screenshots, or test output. |
| SEC-PASSWORD-005 | Password policy review evidence | Pending evidence attachment | NOT_STARTED | Final password policy certification review remains pending. |

## 6. RBAC Security Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| SEC-RBAC-001 | RBAC implementation evidence | `engine/security/rbac.py`; `engine/security/access_control.py`; `backend/security/access_control.py`; `backend/app/security/access_control.py` | REFERENCED | RBAC and access-control paths are referenced; certification output remains pending. |
| SEC-RBAC-002 | User directory and role evidence | `engine/security/user_directory.py`; `backend/app/security/user_registry.py` | REFERENCED | User and role paths are referenced; final role matrix remains pending. |
| SEC-RBAC-003 | SUPER_USER authorization control evidence | `backend/security/permissions.py`; `backend/security/transaction_governor.py`; `backend/app/security/live_toggle.py` | REFERENCED | SUPER_USER and live-toggle control paths are referenced; controlled evidence remains pending. |
| SEC-RBAC-004 | Permission denial audit evidence | `engine/security/access_control.py`; `engine/security/audit_log.py` | REFERENCED | Denial audit paths are referenced; retained denial evidence remains pending. |
| SEC-RBAC-005 | Legal/risk acceptance control evidence | `certification/governance/GOVERNANCE_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Governance register identifies legal and risk acceptance evidence as pending before production certification. |
| SEC-RBAC-006 | Live-toggle RBAC remediation evidence | `docs/governance/ARP_002B_LIVE_TOGGLE_RBAC_REMEDIATION_REPORT.md`; `tests/test_live_toggle_rbac.py` | CAPTURED | ARP-002B captures replacement of hardcoded user ID live-toggle authorization with fail-closed RBAC/permission checks; Robert review remains required. |

## 7. Credential Protection Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| SEC-CRED-001 | Credential protection architecture evidence | `docs/security/CSS_SECURITY_ARCHITECTURE.md` | CAPTURED | Security architecture defines protection of broker credentials and sensitive information as security objectives. |
| SEC-CRED-002 | Credential loader evidence | `backend/app/brokers/credential_loader.py` | REFERENCED | Credential loading path is referenced; no credential values are included. |
| SEC-CRED-003 | Credential separation evidence | Pending evidence attachment | NOT_STARTED | Evidence must show credentials are separated by broker and operating mode where applicable. |
| SEC-CRED-004 | No secrets committed evidence | Pending evidence attachment | NOT_STARTED | Certification requires proof that no critical secrets are committed to source control. |
| SEC-CRED-005 | Credential redaction evidence | Pending evidence attachment | NOT_STARTED | Phase 100B and Phase 101A identify credential redaction evidence as missing. |

## 8. Broker Credential Security Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| SEC-BROKER-001 | Broker credential protection requirement | `docs/governance/PHASE100A_INSTITUTIONAL_CERTIFICATION_FRAMEWORK.md`; `certification/broker/BROKER_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Existing governance requires broker credentials to be protected and not disclosed. |
| SEC-BROKER-002 | Broker credentials scoped to selected broker | Pending evidence attachment | NOT_STARTED | Phase 100A identifies broker credential scoping as required. |
| SEC-BROKER-003 | OANDA credential safety evidence | Pending evidence attachment | NOT_STARTED | No OANDA credential values are included; safe read-only evidence remains pending. |
| SEC-BROKER-004 | Coinbase credential safety evidence | Pending evidence attachment | NOT_STARTED | No Coinbase credential values are included; safe read-only evidence remains pending. |
| SEC-BROKER-005 | Broker credential failure fallback evidence | Pending evidence attachment | NOT_STARTED | Missing or invalid credentials must not crash CSS or expose sensitive material. |
| SEC-BROKER-006 | Broker credential non-disclosure evidence | Pending evidence attachment | NOT_STARTED | Must confirm no broker credential values appear in logs, docs, commits, screenshots, or test output. |

## 9. Audit Security Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| SEC-AUDIT-001 | Audit logger implementation evidence | `engine/security/audit_log.py`; `engine/security/access_audit_log.py`; `backend/security/audit_ledger.py` | REFERENCED | Audit logging paths are referenced; retained runtime evidence remains pending. |
| SEC-AUDIT-002 | Access denial audit evidence | `engine/security/access_control.py`; `backend/security/access_control.py` | REFERENCED | Access-control paths are referenced; denial log evidence remains pending. |
| SEC-AUDIT-003 | Security event audit evidence | Pending evidence attachment | NOT_STARTED | Certification must show authentication, authorization, session, and live-toggle security events are logged. |
| SEC-AUDIT-004 | Audit log retention evidence | Pending evidence attachment | NOT_STARTED | Phase 100B and Phase 101A identify audit log retention evidence as pending. |
| SEC-AUDIT-005 | Audit evidence redaction review | Pending evidence attachment | NOT_STARTED | Must confirm audit evidence does not expose secrets or account identifiers. |

## 10. Runtime Security Controls

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| SEC-RUNTIME-001 | Runtime security control evidence | `certification/runtime/RUNTIME_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Runtime register maps startup, session, audit, and live blocking evidence gaps. |
| SEC-RUNTIME-002 | Controlled runtime sign-on evidence | Pending evidence attachment | NOT_STARTED | Must show operator sign-on under approved scope without exposing sensitive values. |
| SEC-RUNTIME-003 | Runtime failure safe behavior evidence | Pending evidence attachment | NOT_STARTED | Missing data, invalid credentials, and runtime exceptions must fail safely or degrade safely. |
| SEC-RUNTIME-004 | Runtime warnings security review | Pending evidence attachment | NOT_STARTED | Warnings must be actionable and must not disclose sensitive material. |
| SEC-RUNTIME-005 | Runtime security smoke evidence | Pending evidence attachment | NOT_STARTED | Controlled runtime security evidence remains pending. |

## 11. Live Trading Security Controls

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| SEC-LIVE-001 | Live trading explicit authorization evidence | `docs/governance/PHASE100A_INSTITUTIONAL_CERTIFICATION_FRAMEWORK.md`; `certification/broker/BROKER_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Existing governance requires live broker execution to be explicitly authorized; runtime proof remains pending. |
| SEC-LIVE-002 | SUPER_USER live authorization evidence | `backend/app/security/live_toggle.py`; `backend/security/permissions.py`; `backend/security/transaction_governor.py` | REFERENCED | SUPER_USER and live-toggle paths are referenced; controlled evidence remains pending. |
| SEC-LIVE-003 | No unauthorized live execution evidence | Pending evidence attachment | NOT_STARTED | Unauthorized live execution path is a certification failure condition. |
| SEC-LIVE-004 | Paper/live separation security evidence | Pending evidence attachment | NOT_STARTED | Controlled paper run must confirm no live order placement. |
| SEC-LIVE-005 | Live mode approval gate evidence | Pending evidence attachment | NOT_STARTED | Live mode must not be used without explicit authorization and retained approval evidence. |
| SEC-LIVE-006 | Live-toggle hardcoded identity removal evidence | `docs/governance/ARP_002B_LIVE_TOGGLE_RBAC_REMEDIATION_REPORT.md`; `tests/test_live_toggle_rbac.py` | CAPTURED | Evidence shows user ID `1369` is no longer required for authorization and does not grant authorization without role/permission authority. |

## 12. Security Monitoring Considerations

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| SEC-MONITOR-001 | Security monitoring architecture evidence | `docs/security/CSS_SECURITY_ARCHITECTURE.md` | CAPTURED | Security architecture establishes auditability and traceability objectives. |
| SEC-MONITOR-002 | Supervisor alert evidence | `engine/security/supervisor_alerts.py`; `engine/security/exposure_alerts.py` | REFERENCED | Supervisor and exposure alert paths are referenced; retained monitoring evidence remains pending. |
| SEC-MONITOR-003 | Authentication monitoring evidence | Pending evidence attachment | NOT_STARTED | Evidence must show login failures, lockouts, or suspicious authentication events are reviewable where applicable. |
| SEC-MONITOR-004 | Authorization monitoring evidence | Pending evidence attachment | NOT_STARTED | Evidence must show access denials and permission boundaries are monitored. |
| SEC-MONITOR-005 | Credential exposure monitoring evidence | Pending evidence attachment | NOT_STARTED | Evidence must show credential exposure review or scanning results. |

## 13. Known Gaps / Future Evidence

| Gap ID | Gap | Area | Required Future Evidence |
| --- | --- | --- | --- |
| SEC-GAP-001 | Formal security certification run is not attached. | Runtime Security | Controlled security validation output, logs, and review notes. |
| SEC-GAP-002 | Credential redaction evidence is not attached. | Credential Protection | Evidence that logs, docs, commits, screenshots, and test output contain no secrets. |
| SEC-GAP-003 | Broker credential safety evidence is not attached. | Broker Security | OANDA and Coinbase credential safety review without exposing credential values. |
| SEC-GAP-004 | Final RBAC role matrix is not attached. | RBAC | Operator, reviewer, broker-access, SUPER_USER, and approval role matrix. |
| SEC-GAP-005 | Live trading authorization proof is not attached. | Live Trading | Evidence that live trading requires explicit approval and SUPER_USER-controlled authorization where applicable. |
| SEC-GAP-006 | Audit retention evidence is not attached. | Audit | Retained audit logs and retention/review procedure. |
| SEC-GAP-007 | Legal and risk acceptance evidence is not attached. | Governance / Security | Formal legal and risk acceptance artifacts before production authorization. |
| SEC-GAP-008 | Security monitoring evidence is not attached. | Monitoring | Authentication, authorization, credential exposure, and supervisor alert monitoring evidence. |

## 14. Certification Notes

This register is a security evidence map, not a production security certification approval.

Current security certification posture:

* CSS has documented security architecture concepts covering confidentiality, integrity, availability, non-repudiation, governance, least privilege, defense in depth, fail-safe defaults, separation of duties, and zero-trust principles.
* Known CSS security concepts include user authentication, session management, session timeout controls, RBAC controls, legal/risk acceptance controls, credential separation, broker credential protection, audit logging, live trading restrictions, and SUPER_USER authorization controls.
* Existing source paths reference authentication, session, RBAC, access-control, audit, credential-loading, and live-toggle concepts.
* Formal retained evidence for security runtime behavior, credential redaction, RBAC role matrix, broker credential safety, live trading authorization, monitoring, and audit retention remains pending.

Certification implication:

CSS may continue controlled certification evidence assembly and controlled paper-readiness review. CSS is not institutionally production certified for security until security evidence is captured, retained, reviewed, approved, and Robert records final approval.

Documentation-only confirmation:

* No code changes were made.
* No tests were modified.
* No authentication behavior was changed.
* No authorization behavior was changed.
* No credentials were changed.
* No runtime behavior was changed.
* No dashboard behavior was changed.
* No broker behavior was changed.
* No execution behavior was changed.
* No risk-control behavior was changed.
* No margin functionality was changed.
* No trading logic was changed.
* No passwords, API keys, tokens, secrets, account numbers, or credential values were added.
