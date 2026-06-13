# Risk Certification Evidence Register

## 1. Purpose

This register is the Phase 101F risk certification evidence artifact for Capital Strata Systems (CSS).

Its purpose is to identify risk-control evidence required for certification review, separate known CSS risk concepts from pending evidence attachments, and preserve the documentation boundary during certification assembly. This document is documentation-only. It does not change runtime behavior, dashboard behavior, broker behavior, execution behavior, margin behavior, risk-control behavior, or trading permissions.

## 2. Risk Certification Scope

Risk certification evidence covers capital protection, trade permission gating, RBAC risk controls, live trading restrictions, profitability controls, exposure controls, session risk governance, audit trails, and exception handling.

This register covers:

* CSS Unified Trade Gate evidence
* RBAC live-execution control evidence
* real-balance requirement evidence
* ProfitabilityGuard evidence
* position limit evidence
* asset-class allocation control evidence
* session governance evidence
* audit logging evidence
* exception handling evidence
* known risk evidence gaps

This register does not certify live trading. It records what evidence exists, what evidence is referenced, and what evidence remains pending for Robert review.

## 3. Capital Protection Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RISK-CAPITAL-001 | Capital Preservation First principle | `docs/governance/PHASE100A_INSTITUTIONAL_CERTIFICATION_FRAMEWORK.md` | CAPTURED | Phase 100A establishes capital preservation as a certification principle. |
| RISK-CAPITAL-002 | Real-balance requirement evidence | Pending evidence attachment | NOT_STARTED | Certification evidence must show real-balance controls before production-risk claims are accepted. |
| RISK-CAPITAL-003 | Capital governor or capital allocation control evidence | `backend/app/risk/capital_allocation_governor.py`; `backend/risk/trading_capital_policy.py`; `engine/core/capital_manager.py` | REFERENCED | Control paths are referenced by repository structure; retained certification output remains pending. |
| RISK-CAPITAL-004 | Drawdown and capital risk governor evidence | `engine/risk/risk_governor.py`; `tests/engine/test_risk_governor.py` | REFERENCED | Risk governor and tests are referenced; certification run output remains pending. |
| RISK-CAPITAL-005 | Runtime capital protection evidence | Pending evidence attachment | NOT_STARTED | Controlled runtime proof is required before production certification. |

## 4. Unified Trade Gate Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RISK-GATE-001 | CSS Unified Trade Gate existence evidence | `backend/governance/css_unified_trade_gate.py` | REFERENCED | Known CSS trade gate concept; certification evidence attachment remains pending. |
| RISK-GATE-002 | Unified gate decision output evidence | Pending evidence attachment | NOT_STARTED | Evidence must show gate decisions are reviewable and deterministic. |
| RISK-GATE-003 | Margin decision interaction review | `docs/governance/PHASE100A_INSTITUTIONAL_CERTIFICATION_FRAMEWORK.md`; `docs/governance/PHASE100C_PRODUCTION_READINESS_AUDIT.md` | CAPTURED | Existing governance identifies CSSUnifiedTradeGate and margin decision interaction as a remaining review item. |
| RISK-GATE-004 | No bypass of broker controls or capital governor | Pending evidence attachment | NOT_STARTED | Phase 101A requires evidence that margin enforcement does not bypass CSSUnifiedTradeGate, broker controls, or capital governor. |
| RISK-GATE-005 | Full trade permission path evidence | Pending evidence attachment | NOT_STARTED | End-to-end certification run evidence remains pending. |
| RISK-GATE-006 | AntiBleedGuard execution integration remediation | `docs/governance/ARP_002A_ANTIBLEEDGUARD_REMEDIATION_REPORT.md`; `tests/test_antibleed_guard_integration.py` | CAPTURED | ARP-002A captures AntiBleedGuard integration into `ExecutionGate`; Robert review remains required before certification approval. |
| RISK-GATE-007 | MarginTradeGate enforcement remediation | `docs/governance/ARP_002D_MARGINTRADEGATE_REMEDIATION_REPORT.md`; `tests/test_margin_trade_gate_enforcement_integration.py` | CAPTURED | ARP-002D captures MarginTradeGate enforcement in `ExecutionGate`; Robert review remains required before certification approval. |

## 5. RBAC Risk Control Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RISK-RBAC-001 | RBAC access control evidence | `engine/security/rbac.py`; `engine/security/access_control.py` | REFERENCED | RBAC implementation paths are referenced; certification evidence output remains pending. |
| RISK-RBAC-002 | RBAC live-execution control evidence | Pending evidence attachment | NOT_STARTED | Live execution must require explicit authorization. |
| RISK-RBAC-003 | Permission denial audit evidence | `engine/security/access_control.py`; `engine/security/audit_log.py` | REFERENCED | Known access control and audit logger paths; retained denial evidence remains pending. |
| RISK-RBAC-004 | Operator role and permission matrix | Pending evidence attachment | NOT_STARTED | Governance evidence register identifies the final role matrix as pending. |
| RISK-RBAC-005 | Production permission expansion approval evidence | Pending evidence attachment | NOT_STARTED | Unreviewed production permission expansion is a certification failure condition. |

## 6. Live Trading Restriction Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RISK-LIVE-001 | No unauthorized live execution evidence | Pending evidence attachment | NOT_STARTED | Unauthorized live execution path is a certification failure condition. |
| RISK-LIVE-002 | Live execution requires explicit authorization | `docs/governance/PHASE100A_INSTITUTIONAL_CERTIFICATION_FRAMEWORK.md` | CAPTURED | Phase 100A defines this requirement; runtime proof remains pending. |
| RISK-LIVE-003 | Paper/live separation evidence | Pending evidence attachment | NOT_STARTED | Controlled paper run must prove no live order placement. |
| RISK-LIVE-004 | Unknown live risk state fails closed evidence | Pending evidence attachment | NOT_STARTED | Phase 101A calls for LIVE UNKNOWN fail-closed validation before new exposure. |
| RISK-LIVE-005 | Broker read-only certification evidence | `certification/broker/BROKER_CERTIFICATION_EVIDENCE_REGISTER.md` | CAPTURED | Broker register maps read-only broker evidence gaps; attachments remain pending. |

## 7. Profitability Guard Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RISK-PROFIT-001 | ProfitabilityGuard existence evidence | `backend/intelligence/profitability_guard.py` | REFERENCED | Known CSS profitability control path; certification output remains pending. |
| RISK-PROFIT-002 | Profitability gate evidence | `backend/intelligence/profitability_gate.py`; `docs/governance/profitability_runtime_trace.txt` | REFERENCED | Existing paths suggest profitability gate/runtime trace references; retained certification evidence remains pending. |
| RISK-PROFIT-003 | Profitability does not bypass risk evidence | Pending evidence attachment | NOT_STARTED | Phase 100A establishes Risk Before Profit as a certification principle. |
| RISK-PROFIT-004 | Runtime profitability decision evidence | Pending evidence attachment | NOT_STARTED | Controlled runtime evidence must show profitability decisions remain subordinate to risk controls. |

## 8. Position Limit Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RISK-POSITION-001 | Position limit policy evidence | `engine/governance/position_limit_policy.py`; `tests/engine/test_position_limit_policy.py` | REFERENCED | Position limit implementation and test paths are referenced; retained test output remains pending. |
| RISK-POSITION-002 | Position count or size enforcement evidence | Pending evidence attachment | NOT_STARTED | Certification evidence must show position limits under controlled scenarios. |
| RISK-POSITION-003 | Position limit denial audit evidence | Pending evidence attachment | NOT_STARTED | Denials must be audit-visible for certification. |
| RISK-POSITION-004 | Multi-asset position limit evidence | Pending evidence attachment | NOT_STARTED | Cross-asset certification evidence remains incomplete. |

## 9. Asset Class Exposure Control Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RISK-ASSET-001 | Asset allocator or allocation control evidence | `engine/allocation/asset_allocator.py`; `backend/intelligence/allocation_intelligence_engine.py` | REFERENCED | Allocation paths are referenced; certification evidence attachment remains pending. |
| RISK-ASSET-002 | Asset-class exposure control evidence | Pending evidence attachment | NOT_STARTED | Evidence must show FX, crypto, futures, and options exposure rules under approved scope. |
| RISK-ASSET-003 | Asset-class PnL and exposure visibility evidence | `docs/governance/PHASE100C_PRODUCTION_READINESS_AUDIT.md` | CAPTURED | Audit notes reference asset-class position counts and PnL visibility; runtime proof remains pending. |
| RISK-ASSET-004 | Cross-asset certification evidence | Pending evidence attachment | NOT_STARTED | Phase 101A identifies cross-asset certification evidence as incomplete. |
| RISK-ASSET-005 | Concentration or allocation breach evidence | Pending evidence attachment | NOT_STARTED | Certification requires retained evidence for exposure-control warnings or denials. |

## 10. Session Risk Governance Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RISK-SESSION-001 | Session lifecycle control evidence | `engine/security/session_manager.py`; `backend/security/session_manager.py` | REFERENCED | Session manager paths are referenced; runtime session evidence remains pending. |
| RISK-SESSION-002 | Active session required for risk-sensitive action | `engine/security/security_context.py` | REFERENCED | Security context references session validation and RBAC authorization; retained evidence remains pending. |
| RISK-SESSION-003 | Session lock, resume, and close risk evidence | Pending evidence attachment | NOT_STARTED | Runtime certification register identifies session evidence gaps. |
| RISK-SESSION-004 | Stale exposure handling evidence | Pending evidence attachment | NOT_STARTED | Recovery and stale exposure certification remain pending. |
| RISK-SESSION-005 | Operator session audit evidence | Pending evidence attachment | NOT_STARTED | Evidence must tie risk-sensitive actions to session and operator context. |

## 11. Audit Trail Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RISK-AUDIT-001 | Audit logger evidence | `engine/security/audit_log.py`; `engine/security/access_audit_log.py` | REFERENCED | Audit logger paths are referenced; retained runtime audit evidence remains pending. |
| RISK-AUDIT-002 | Risk decision audit evidence | Pending evidence attachment | NOT_STARTED | Certification requires reviewable risk outcomes and state transitions. |
| RISK-AUDIT-003 | Trade gate decision audit evidence | Pending evidence attachment | NOT_STARTED | Unified trade gate decisions must be retained for certification review. |
| RISK-AUDIT-004 | Exception and denial audit evidence | Pending evidence attachment | NOT_STARTED | Denials, warnings, and exceptions must be traceable. |
| RISK-AUDIT-005 | Audit retention evidence | Pending evidence attachment | NOT_STARTED | Phase 100B and Phase 101A identify audit log retention evidence as pending. |

## 12. Exception Handling Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| RISK-EXCEPTION-001 | Unknown risk state safe behavior evidence | Pending evidence attachment | NOT_STARTED | Missing data and unknown risk states must fail safely or fail closed where enforced. |
| RISK-EXCEPTION-002 | Risk engine exception handling evidence | Pending evidence attachment | NOT_STARTED | Controlled failure-path output must be retained. |
| RISK-EXCEPTION-003 | Broker or account data unavailable risk behavior | Pending evidence attachment | NOT_STARTED | Phase 101A calls for recovery from broker/account data unavailability. |
| RISK-EXCEPTION-004 | Runtime warning evidence | Pending evidence attachment | NOT_STARTED | Runtime warnings must be actionable and reviewable. |
| RISK-EXCEPTION-005 | No critical unresolved runtime exception evidence | Pending evidence attachment | NOT_STARTED | Phase 100A lists unresolved critical runtime exception as a certification failure condition. |

## 13. Known Gaps / Future Evidence

| Gap ID | Gap | Area | Required Future Evidence |
| --- | --- | --- | --- |
| RISK-GAP-001 | End-to-end risk certification run is not attached. | Runtime Risk | Controlled run logs, screenshots, and retained risk decision output. |
| RISK-GAP-002 | Unified trade gate certification output is not attached. | Trade Gate | Gate decisions, reasons, denials, and approval-path evidence. |
| RISK-GAP-003 | RBAC live-execution evidence is not attached. | RBAC / Live Restriction | Permission matrix, authorization proof, and denial audit evidence. |
| RISK-GAP-004 | Real-balance risk requirement evidence is not attached. | Capital Protection | Approved proof that live risk decisions use real balance where required. |
| RISK-GAP-005 | ProfitabilityGuard runtime evidence is not attached. | Profitability Guard | Proof that profitability controls do not bypass risk-first governance. |
| RISK-GAP-006 | Position limit and asset-class exposure evidence is not attached. | Exposure Control | Controlled limit and exposure scenarios across approved asset classes. |
| RISK-GAP-007 | Session risk governance evidence is not attached. | Session Governance | Session lifecycle, stale exposure, and operator action evidence. |
| RISK-GAP-008 | Risk audit retention evidence is not attached. | Audit | Retained audit logs and retention/review procedure evidence. |
| RISK-GAP-009 | Exception handling evidence is not attached. | Safe Failure | Failure-path records for unknown state, unavailable data, and exceptions. |

## 14. Certification Notes

This register is a risk evidence map, not a production risk certification approval.

Current risk certification posture:

* Known CSS risk concepts include CSS Unified Trade Gate, RBAC controls, real-balance requirements, ProfitabilityGuard, position limits, asset-class exposure controls, session governance controls, and audit logging controls.
* Existing source and governance references identify risk architecture and certification expectations.
* Formal retained evidence for runtime risk behavior, trade gate decisions, RBAC live restrictions, real-balance enforcement, exposure limits, and exception handling remains pending.

Certification implication:

CSS may continue controlled certification evidence assembly and controlled paper-readiness review. CSS is not institutionally production certified until risk evidence is captured, retained, reviewed, approved, and Robert records final approval.

Documentation-only confirmation:

* No code changes were made.
* No tests were modified.
* No runtime behavior was changed.
* No dashboard behavior was changed.
* No broker behavior was changed.
* No execution behavior was changed.
* No margin behavior was changed.
* No risk controls were changed.
* No trading logic was changed.
