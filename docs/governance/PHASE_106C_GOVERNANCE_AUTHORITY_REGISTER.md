# Phase 106C Governance Authority Register

## SECTION A — Governance Overview

The purpose of this Governance Authority Register is to define the single authoritative mapping of ownership boundaries, canonical files, and integration dependencies across the Capital Strata Systems (CSS) codebase. Following the completion of Phases 105A through 106B, this document serves as the permanent record to prevent structural regression, ambiguity, and the re-introduction of duplicated authorities.

## SECTION B — Canonical Authorities

### 1. Trade Gate Authority
- **Canonical File**: `backend/governance/css_unified_trade_gate.py`
- **Owning Component**: Governance Core
- **Upstream Dependencies**: `TradeDecisionOrchestrator`
- **Downstream Consumers**: Execution Gate
- **Certification Evidence**: `PHASE_105A_TRADE_GATE_CANONICALIZATION_CERTIFICATION.md`, `PHASE_105F_FINAL_TRADE_GATE_RUNTIME_PARITY_CERTIFICATION.md`

### 2. Regime Gate Authority
- **Canonical File**: `engine/regime/regime_gate.py`
- **Owning Component**: Regime Detection Layer
- **Upstream Dependencies**: `engine_loop.py`
- **Downstream Consumers**: Execution Path Validation
- **Certification Evidence**: `PHASE_105C_FINAL_REGIME_GATE_CANONICALIZATION_CERTIFICATION.md`

### 3. PnL Authority
- **Canonical File**: `engine/ledger/pnl_snapshot_adapter.py`
- **Owning Component**: Persistence / Ledger
- **Upstream Dependencies**: `PnlRuntimeService`, `TradeDecisionOrchestrator`
- **Downstream Consumers**: `dashboard/runtime/summary_builders/pnl_summary_builder.py`
- **Certification Evidence**: `PHASE_105B_PNL_AUTHORITY_CANONICALIZATION_CERTIFICATION.md`

### 4. Entry Point Authority
- **Canonical File**: `run_css.py`
- **Owning Component**: Application Launcher
- **Upstream Dependencies**: Operator / Deployment Pipeline
- **Downstream Consumers**: Backend APIs, Intelligence Engines
- **Certification Evidence**: `PHASE_105D_ENTRY_POINT_CANONICALIZATION_CERTIFICATION.md`

### 5. Dashboard Authority
- **Canonical File**: `dashboard/css_live_dashboard.py`
- **Owning Component**: Operations UI
- **Upstream Dependencies**: SQLite State, `pnl_summary_builder.py`
- **Downstream Consumers**: Operator Display
- **Certification Evidence**: `PHASE_105E_REPOSITORY_STRUCTURE_REMEDIATION_CERTIFICATION.md`

### 6. Security Authority
- **Canonical File**: `backend/app/headless_guarded_entry.py`
- **Owning Component**: Core API Firewall
- **Upstream Dependencies**: API Ingress
- **Downstream Consumers**: Internal Engine Execution
- **Certification Evidence**: `PHASE_106B_SECURITY_AUDIT_RECERTIFICATION_REPORT.md`

### 7. Authentication Authority
- **Canonical File**: `backend/app/auth/auth_router.py`
- **Owning Component**: Auth Service
- **Upstream Dependencies**: API Users
- **Downstream Consumers**: Session Tokens / Token Store
- **Certification Evidence**: `PHASE_106B_SECURITY_AUDIT_RECERTIFICATION_REPORT.md`

### 8. RBAC Authority
- **Canonical File**: `backend/app/security/role_validator.py`
- **Owning Component**: Role Access Control
- **Upstream Dependencies**: JWT / Token Store
- **Downstream Consumers**: Endpoint Route Guards
- **Certification Evidence**: `PHASE_106B_SECURITY_AUDIT_RECERTIFICATION_REPORT.md`

### 9. Broker Execution Authority
- **Canonical File**: `backend/app/brokers/oanda_adapter.py`
- **Owning Component**: Broker Adapters
- **Upstream Dependencies**: `ExecutionGate`
- **Downstream Consumers**: OANDA REST API
- **Certification Evidence**: `PHASE_106B_SECURITY_AUDIT_RECERTIFICATION_REPORT.md`

### 10. Risk Authority
- **Canonical File**: `engine/risk/risk_governor.py`
- **Owning Component**: Pre-Execution Risk Evaluator
- **Upstream Dependencies**: `AntiBleedGuard`, `MarginTradeGate`
- **Downstream Consumers**: `ExecutionRouter`
- **Certification Evidence**: `PHASE_105F_FINAL_TRADE_GATE_RUNTIME_PARITY_CERTIFICATION.md`

### 11. Persistence Authority
- **Canonical File**: `backend/app/persistence/services/persistence_service.py`
- **Owning Component**: Database Repository Layer
- **Upstream Dependencies**: Runtime Services
- **Downstream Consumers**: SQLite Database
- **Certification Evidence**: `CSS_AUTHORITY_REMEDIATION_MASTER_PLAN.md`

### 12. Audit Authority
- **Canonical File**: `docs/governance/PHASE_106A_AUDIT_TRACKER_CLOSURE_REPORT.md`
- **Owning Component**: Governance Operations
- **Upstream Dependencies**: Remediation Phases 105A-105F
- **Downstream Consumers**: Internal Audit
- **Certification Evidence**: `PHASE_106A_AUDIT_TRACKER_CLOSURE_REPORT.md`

### 13. Certification Authority
- **Canonical File**: `docs/governance/CSS_AUTHORITY_REMEDIATION_MASTER_PLAN.md`
- **Owning Component**: Master Architecture
- **Upstream Dependencies**: Engineering Leads
- **Downstream Consumers**: Future Deployments
- **Certification Evidence**: `PHASE_106C_GOVERNANCE_AUTHORITY_REGISTER.md`

## SECTION C — Retired Authorities

The following authorities were explicitly retired to eliminate structural ambiguity:

| Retired Artifact | Replaced By | Retirement Phase | Evidence |
|------------------|-------------|------------------|----------|
| Duplicate `CSSUnifiedTradeGate` locations | `backend/governance/css_unified_trade_gate.py` | 105A, 105F | `PHASE_105A_TRADE_GATE...md` |
| `LEGACY_POSITION_STATE` calculations | `engine/ledger/pnl_snapshot_adapter.py` | 105B | `PHASE_105B_PNL_AUTHORITY...md` |
| Submodule `dashboard.py` / legacy dashboards | `dashboard/css_live_dashboard.py` | 105D, 105E | `PHASE_105E_REPOSITORY...md` |
| Fragmented launch scripts (`main.py`, etc.) | `run_css.py` | 105D | `PHASE_105D_ENTRY_POINT...md` |
| Duplicate `RiskGovernor` logic | `engine/risk/risk_governor.py` | 105F | `PHASE_105F_FINAL_TRADE_GATE...md` |

## SECTION D — Governance Rules

To preserve architectural integrity in future development, all engineers must adhere to the following rules:

1. **No Duplicate Authorities**: State mapping, access control, risk bounding, and trading decisions must have a singular, documented source of truth.
2. **Fail-Closed Requirement**: Every gate (Execution, Margin, Regime, Auth) must reject connections, orders, or logic if state is unknown, null, or errored.
3. **Certification Before Production**: Any changes to authorities listed in Section B must be accompanied by a dedicated governance update.
4. **Test Coverage**: Canonical gates must retain 100% test coverage against boundary edge cases.
5. **Audit Evidence**: Code modifications addressing findings must be mapped sequentially (e.g. `PHASE_106C`) and approved.

## SECTION E — Executive Governance Summary

Capital Strata Systems has completed its authority remediation and governance baseline mapping. With duplicate files removed, legacy paths deprecated, execution gates unified, and security controls validated, the repository represents a deterministic, auditable trading engine. The rules codified in this Governance Authority Register must govern all subsequent Phase execution and architecture.
