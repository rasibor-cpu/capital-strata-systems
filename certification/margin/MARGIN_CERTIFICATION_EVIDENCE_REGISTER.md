# Margin Certification Evidence Register

## 1. Purpose

This register is the Phase 101G margin certification evidence artifact for Capital Strata Systems (CSS).

Its purpose is to identify margin evidence required for certification review, document the current margin governance and architecture posture, distinguish implemented or referenced margin components from pending certification evidence, and preserve the documentation boundary during certification assembly. This document is documentation-only. It does not create, modify, activate, simulate, or alter margin engine functionality.

## 2. Margin Certification Scope

Margin certification evidence covers margin governance, capital protection relationships, asset-class margin considerations, broker margin integration, margin monitoring, margin-call handling, and future evidence requirements.

This register covers:

* Institutional Margin Governance Framework evidence
* Margin Engine evidence
* Broker Margin Integration evidence
* capital protection relationship evidence
* futures, options, FX, and crypto margin considerations
* broker margin adapter considerations
* margin monitoring and dashboard visibility considerations
* margin call handling considerations
* known margin evidence gaps

This register does not approve live margin enforcement or production trading. It records margin evidence availability and missing attachments for Robert review.

## 3. Current Margin Architecture Status

CSS currently treats margin as a governance, risk, and capital-control domain. Margin authority is not owned by a single asset-class strategy or trading engine.

Current documented architecture status:

| Area | Current Status | Evidence Reference | Certification Evidence Status |
| --- | --- | --- | --- |
| Institutional Margin Governance Framework | Documented | `docs/governance/PHASE95_INSTITUTIONAL_MARGIN_GOVERNANCE_FRAMEWORK.md` | Governance artifact captured; runtime evidence pending. |
| Margin Architecture Definition | Documented | `docs/governance/PHASE96A_MARGIN_ARCHITECTURE_DEFINITION.md` | Governance artifact captured; runtime evidence pending. |
| Margin Engine | Referenced as implemented by prior phases | `engine/risk/margin_engine.py`; `tests/test_margin_engine.py` | Pending evidence attachment. |
| Broker Margin Contract | Referenced as implemented by prior phases | `engine/risk/broker_margin_contract.py`; `tests/test_broker_margin_contract.py` | Pending evidence attachment. |
| OANDA Margin Adapter | Referenced as implemented with simulated fallback and live retrieval attempt | `engine/risk/oanda_margin_adapter.py`; `tests/test_oanda_margin_adapter.py` | Pending evidence attachment. |
| Coinbase Margin Adapter | Referenced as implemented with simulated fallback and spot non-margin default behavior | `engine/risk/coinbase_margin_adapter.py`; `tests/test_coinbase_margin_adapter.py` | Pending evidence attachment. |
| Margin Trade Gate | Referenced as standalone decisioning | `engine/risk/margin_trade_gate.py`; `tests/test_margin_trade_gate.py` | Pending evidence attachment. |
| Margin Dashboard Visibility | Referenced as display-only | `scripts/css_live_dashboard.py`; `tests/test_margin_dashboard_integration.py` | Runtime display evidence pending. |
| Runtime Margin Enforcement | Captured for ExecutionGate path | `docs/governance/ARP_002D_MARGINTRADEGATE_REMEDIATION_REPORT.md`; `tests/test_margin_trade_gate_enforcement_integration.py` | ARP-002D evidence captured; Robert review and live broker margin evidence remain pending. |

Certification note: Existing governance materials describe a mature margin stack, but formal certification evidence is not complete until test output, runtime output, broker live-read evidence, screenshots or logs, and Robert approval are attached.

## 4. Margin Governance Evidence

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| MARGIN-GOV-001 | Institutional Margin Governance Framework | `docs/governance/PHASE95_INSTITUTIONAL_MARGIN_GOVERNANCE_FRAMEWORK.md` | CAPTURED | Defines margin as controlled institutional authority shared across capital, risk, execution governance, and broker-control layers. |
| MARGIN-GOV-002 | Margin Architecture Definition | `docs/governance/PHASE96A_MARGIN_ARCHITECTURE_DEFINITION.md` | CAPTURED | Defines margin authority hierarchy, canonical fields, provider expectations, and trade gate boundaries. |
| MARGIN-GOV-003 | Certification framework margin domain | `docs/governance/PHASE100A_INSTITUTIONAL_CERTIFICATION_FRAMEWORK.md` | CAPTURED | Defines margin as a certification domain. |
| MARGIN-GOV-004 | Margin evidence registry entry | `docs/governance/PHASE100B_CERTIFICATION_EVIDENCE_REGISTRY.md` | CAPTURED | Lists margin evidence categories and required evidence sources. |
| MARGIN-GOV-005 | Margin production readiness audit | `docs/governance/PHASE100C_PRODUCTION_READINESS_AUDIT.md` | CAPTURED | Records margin stack status and remaining enforcement/live-read evidence gaps. |
| MARGIN-GOV-006 | Margin closeout and remediation plan | `docs/governance/PHASE101A_CERTIFICATION_CLOSEOUT_AND_REMEDIATION_PLAN.md` | CAPTURED | Identifies margin enforcement, broker live-read evidence, and cross-asset evidence as remaining gaps. |

## 5. Capital Protection Relationship

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| MARGIN-CAPITAL-001 | Margin relationship to capital preservation | `docs/governance/PHASE95_INSTITUTIONAL_MARGIN_GOVERNANCE_FRAMEWORK.md`; `docs/governance/PHASE100A_INSTITUTIONAL_CERTIFICATION_FRAMEWORK.md` | CAPTURED | Margin is governed under capital preservation and risk-before-profit principles. |
| MARGIN-CAPITAL-002 | Margin does not bypass capital governor evidence | Pending evidence attachment | NOT_STARTED | Phase 101A requires proof that margin enforcement does not bypass CSSUnifiedTradeGate, broker controls, or capital governor. |
| MARGIN-CAPITAL-003 | Real balance and margin relationship evidence | Pending evidence attachment | NOT_STARTED | Live margin certification requires read-only broker/capital evidence without exposing secrets. |
| MARGIN-CAPITAL-004 | Margin-dependent exposure control evidence | Pending evidence attachment | NOT_STARTED | Missing broker margin data must block new margin-dependent exposure when enforcement applies. |
| MARGIN-CAPITAL-005 | Unknown live margin fail-closed evidence | Pending evidence attachment | NOT_STARTED | Phase 95 and Phase 101A require unknown live margin state to fail closed where enforcement applies. |
| MARGIN-CAPITAL-006 | MarginTradeGate enforcement remediation evidence | `docs/governance/ARP_002D_MARGINTRADEGATE_REMEDIATION_REPORT.md`; `tests/test_margin_trade_gate_enforcement_integration.py` | CAPTURED | ARP-002D captures pre-execution margin enforcement and fail-closed missing/unknown margin behavior in `ExecutionGate`; Robert review remains required. |

## 6. Asset-Class Margin Considerations

CSS margin certification must be asset-class aware. The governance framework recognizes that FX, crypto, futures, and options require different margin treatment while using consistent institutional governance.

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| MARGIN-ASSET-001 | Multi-asset margin governance evidence | `docs/governance/PHASE95_INSTITUTIONAL_MARGIN_GOVERNANCE_FRAMEWORK.md`; `docs/governance/PHASE100A_INSTITUTIONAL_CERTIFICATION_FRAMEWORK.md` | CAPTURED | Existing governance describes asset-class-specific margin treatment. |
| MARGIN-ASSET-002 | Cross-asset margin certification evidence | Pending evidence attachment | NOT_STARTED | Phase 101A identifies cross-asset certification evidence as incomplete. |
| MARGIN-ASSET-003 | Asset-class behavior runtime evidence | Pending evidence attachment | NOT_STARTED | Required for FX, crypto, futures, and options certification scope. |
| MARGIN-ASSET-004 | Asset-class margin dashboard evidence | Pending evidence attachment | NOT_STARTED | Runtime dashboard captures remain pending. |

## 7. Futures Margin Considerations

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| MARGIN-FUTURES-001 | Futures margin governance treatment | `docs/governance/PHASE95_INSTITUTIONAL_MARGIN_GOVERNANCE_FRAMEWORK.md` | CAPTURED | Governance states futures margin must distinguish initial, maintenance, intraday, and overnight margin. |
| MARGIN-FUTURES-002 | Futures margin escalation evidence | Pending evidence attachment | NOT_STARTED | Futures margin requires high-priority escalation evidence due to adverse movement risk. |
| MARGIN-FUTURES-003 | Futures broker margin source evidence | Pending evidence attachment | NOT_STARTED | Broker-authoritative futures margin evidence is not attached. |
| MARGIN-FUTURES-004 | Futures margin runtime test output | Pending evidence attachment | NOT_STARTED | Controlled futures margin behavior evidence remains pending. |

## 8. Options Margin Considerations

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| MARGIN-OPTIONS-001 | Options margin governance treatment | `docs/governance/PHASE95_INSTITUTIONAL_MARGIN_GOVERNANCE_FRAMEWORK.md` | CAPTURED | Governance states options margin depends on strategy, direction, and account permissions. |
| MARGIN-OPTIONS-002 | Long premium-paid option treatment evidence | Pending evidence attachment | NOT_STARTED | Evidence must distinguish long premium-paid options from margin-dependent option exposure. |
| MARGIN-OPTIONS-003 | Short options margin evidence | Pending evidence attachment | NOT_STARTED | Short options margin evidence is not attached. |
| MARGIN-OPTIONS-004 | Options strategy margin evidence | Pending evidence attachment | NOT_STARTED | Strategy-aware margin certification evidence remains pending. |
| MARGIN-OPTIONS-005 | Options Greeks relationship to margin evidence | Pending evidence attachment | NOT_STARTED | Greeks visibility exists separately; certification evidence tying Greeks to margin governance remains pending if required. |

## 9. FX Margin Considerations

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| MARGIN-FX-001 | FX margin governance treatment | `docs/governance/PHASE95_INSTITUTIONAL_MARGIN_GOVERNANCE_FRAMEWORK.md` | CAPTURED | Governance states FX margin is broker-driven and leverage-sensitive. |
| MARGIN-FX-002 | OANDA FX margin read-only evidence | Pending evidence attachment | NOT_STARTED | OANDA live-read evidence remains pending and must not place trades. |
| MARGIN-FX-003 | FX margin source and timestamp evidence | Pending evidence attachment | NOT_STARTED | Broker margin data must not be treated as authoritative unless source and timestamp are known. |
| MARGIN-FX-004 | FX paper/practice margin evidence | Pending evidence attachment | NOT_STARTED | Simulated or paper FX margin must be clearly labeled. |

## 10. Crypto Margin Considerations

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| MARGIN-CRYPTO-001 | Crypto margin governance treatment | `docs/governance/PHASE95_INSTITUTIONAL_MARGIN_GOVERNANCE_FRAMEWORK.md` | CAPTURED | Governance states crypto margin is not enabled by default and crypto spot is non-margin unless broker/exchange data clearly reports margin or leverage. |
| MARGIN-CRYPTO-002 | Coinbase spot non-margin evidence | `engine/risk/coinbase_margin_adapter.py`; `tests/test_coinbase_margin_adapter.py` | REFERENCED | Adapter/test paths are referenced; retained certification output remains pending. |
| MARGIN-CRYPTO-003 | Coinbase live read-only account evidence | Pending evidence attachment | NOT_STARTED | Coinbase live-read evidence remains pending and must not place trades. |
| MARGIN-CRYPTO-004 | Crypto leverage or margin-enabled account evidence | Pending evidence attachment | NOT_STARTED | No margin/leverage crypto evidence is attached. |

## 11. Broker Margin Integration Considerations

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| MARGIN-BROKER-001 | Broker Margin Contract evidence | `engine/risk/broker_margin_contract.py`; `tests/test_broker_margin_contract.py` | REFERENCED | Canonical broker margin contract paths are referenced; retained test output remains pending. |
| MARGIN-BROKER-002 | OANDA margin adapter evidence | `engine/risk/oanda_margin_adapter.py`; `tests/test_oanda_margin_adapter.py` | REFERENCED | OANDA adapter path is referenced; live-read evidence remains pending. |
| MARGIN-BROKER-003 | Coinbase margin adapter evidence | `engine/risk/coinbase_margin_adapter.py`; `tests/test_coinbase_margin_adapter.py` | REFERENCED | Coinbase adapter path is referenced; live-read evidence remains pending. |
| MARGIN-BROKER-004 | Broker live-read evidence | Pending evidence attachment | NOT_STARTED | Phase 101A identifies OANDA and Coinbase live-read evidence as incomplete. |
| MARGIN-BROKER-005 | Broker failure fallback evidence | Pending evidence attachment | NOT_STARTED | Missing credentials, unavailable account data, API failure, and network failure behavior must be captured. |
| MARGIN-BROKER-006 | Broker margin values mapped to canonical fields | Pending evidence attachment | NOT_STARTED | Evidence must show required margin, available margin, free margin, utilization, source, and state under approved scope. |

## 12. Margin Monitoring Considerations

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| MARGIN-MONITOR-001 | Margin dashboard visibility evidence | `scripts/css_live_dashboard.py`; `tests/test_margin_dashboard_integration.py` | REFERENCED | Display-only margin dashboard path is referenced; runtime screenshot/log evidence remains pending. |
| MARGIN-MONITOR-002 | Margin state and escalation state evidence | Pending evidence attachment | NOT_STARTED | Runtime evidence must show margin state and escalation state. |
| MARGIN-MONITOR-003 | Margin trade gate decision visibility evidence | Pending evidence attachment | NOT_STARTED | Phase 101A calls for paper run evidence with margin gate decision visible. |
| MARGIN-MONITOR-004 | Simulated source labeling evidence | Pending evidence attachment | NOT_STARTED | Simulated margin data must be clearly labeled and must not authorize live trades. |
| MARGIN-MONITOR-005 | Margin event audit evidence | Pending evidence attachment | NOT_STARTED | Margin events must record source, utilization, required margin, available margin, and related context. |

## 13. Margin Call Handling Considerations

| Evidence ID | Required Evidence | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| MARGIN-CALL-001 | Margin escalation governance evidence | `docs/governance/PHASE95_INSTITUTIONAL_MARGIN_GOVERNANCE_FRAMEWORK.md` | CAPTURED | Governance defines margin escalation states and monitoring expectations. |
| MARGIN-CALL-002 | Margin call handling procedure | Pending evidence attachment | NOT_STARTED | Operational margin call runbook or procedure is not attached. |
| MARGIN-CALL-003 | Forced restriction or defensive-only behavior evidence | Pending evidence attachment | NOT_STARTED | Margin trade gate behavior must be evidenced before certification claims. |
| MARGIN-CALL-004 | Broker margin call notification evidence | Pending evidence attachment | NOT_STARTED | No broker margin call notification evidence is attached. |
| MARGIN-CALL-005 | Margin call audit trail evidence | Pending evidence attachment | NOT_STARTED | Escalation and response events must be audit-visible. |

## 14. Known Gaps / Future Evidence

| Gap ID | Gap | Area | Required Future Evidence |
| --- | --- | --- | --- |
| MARGIN-GAP-001 | Full CSSUnifiedTradeGate-to-ExecutionGate authority chain remains unconsolidated. | Enforcement | ARP-002D captures `ExecutionGate` enforcement; future evidence must consolidate or formally document the complete CSSUnifiedTradeGate, capital governor, ExecutionGate, and broker-control ordering. |
| MARGIN-GAP-002 | OANDA live-read evidence is incomplete. | Broker Margin | Approved read-only OANDA account or margin evidence with no order placement. |
| MARGIN-GAP-003 | Coinbase live-read evidence is incomplete. | Broker Margin | Approved read-only Coinbase account or margin-like evidence with no order placement. |
| MARGIN-GAP-004 | Runtime margin dashboard evidence is missing. | Monitoring | Controlled runtime screenshots or logs showing margin dashboard visibility. |
| MARGIN-GAP-005 | Cross-asset margin certification evidence is incomplete. | Asset Classes | FX, crypto, futures, and options margin behavior evidence under approved scope. |
| MARGIN-GAP-006 | Margin call handling evidence is missing. | Operations | Margin call procedure, escalation, response, and audit trail evidence. |
| MARGIN-GAP-007 | Margin event audit retention evidence is missing. | Audit | Retained margin event logs and retention/review procedure. |
| MARGIN-GAP-008 | Unknown live margin fail-closed evidence is missing. | Safe Failure | Controlled validation showing unknown live margin state blocks margin-dependent exposure where enforcement applies. |

## 15. Certification Notes

This register is a margin evidence map, not a production margin certification approval.

Current margin certification posture:

* CSS treats margin as a governance, risk, and capital-control domain.
* The Institutional Margin Governance Framework and Margin Architecture Definition are captured.
* Prior phases and evidence registry materials reference a Margin Engine, Broker Margin Contract, OANDA Margin Adapter, Coinbase Margin Adapter, Margin Trade Gate, and display-only margin dashboard visibility.
* Formal certification attachments for test output, runtime output, broker live-read evidence, asset-class behavior, margin event audit logs, and margin call handling remain pending.
* Runtime margin enforcement remains deferred to a future phase and is not activated by this register.

Certification implication:

CSS may continue controlled certification evidence assembly and controlled paper-readiness review. CSS is not institutionally production certified for margin until margin evidence is captured, retained, reviewed, approved, and Robert records final approval.

Documentation-only confirmation:

* No code changes were made.
* No tests were modified.
* No runtime behavior was changed.
* No dashboard behavior was changed.
* No broker behavior was changed.
* No execution behavior was changed.
* No risk-control behavior was changed.
* No margin functionality was created, modified, activated, simulated, or altered.
* No trading logic was changed.
