# Phase 1 Runtime Gate Consolidation Evidence

## Purpose

This artifact records existing runtime gate consolidation evidence from current
CSS V1 core completion work.

This artifact is documentation-only. It does not change runtime behavior,
execution behavior, broker behavior, dashboard behavior, risk controls,
thresholds, credentials, or trading logic.

## Repository Evidence

| Field | Evidence |
| --- | --- |
| Branch | `css-evening-consolidation-2026-06-09` |
| Evidence HEAD | `2cb0221f6dfc2510eda836f0dd066201304ee10a` |
| Runtime consolidation commit | `2fdd93679b255f001ec244c59c870af7f8aeb784` |
| Runtime consolidation subject | `Source runtime governance from unified trade gate` |

## Canonical Trade Gate Authority

The canonical backend trade gate authority is:

```text
backend/governance/css_unified_trade_gate.py
```

The canonical dashboard adapter is:

```text
backend/governance/css_gate_dashboard_adapter.py
```

The runtime orchestrator path now records governance decision fields from the
canonical gate interface:

```text
backend/intelligence/trade_decision_orchestrator.py
-> TradeDecisionOrchestrator._evaluate_governance_gate(...)
-> self.trade_gate.approve_trade(...)
-> CSSUnifiedTradeGate
-> decision fields copied into runtime filters
```

## Runtime Decision Fields

Runtime decision payloads now expose canonical gate-derived fields:

```text
filters.governance_approved
filters.governance_reason
filters.governance_details
filters.governance_source = CSSUnifiedTradeGate
```

The runtime payload keeps execution disabled by preserving:

```text
execute_trade = False
```

## Regression Coverage

Focused regression coverage:

```text
tests/test_trade_decision_orchestrator_gate.py
```

The regression verifies:

| Assertion Area | Evidence |
| --- | --- |
| Orchestrator calls the trade gate | Recording gate receives `approve_trade(...)` call. |
| Candidate translation is stable | Symbol, asset class, expected value, cost, and probability are passed through. |
| Engine mode is preserved | `engine_mode` is forwarded to the gate. |
| Execution remains disabled | `execute_trade` remains `False`. |
| Runtime filter source is canonical | `governance_source` is `CSSUnifiedTradeGate`. |

## Related Certification Evidence

| Artifact | Relationship |
| --- | --- |
| `docs/governance/PHASE_105D_DASHBOARD_CANONICAL_GATE_INTEGRATION_CERTIFICATION.md` | Documents dashboard adapter path. |
| `docs/governance/PHASE_105E_DASHBOARD_DUPLICATE_RETIREMENT_CERTIFICATION.md` | Documents dashboard duplicate retirement. |
| `docs/governance/PHASE_105F_FINAL_TRADE_GATE_RUNTIME_PARITY_CERTIFICATION.md` | Documents runtime/dashboard authority parity. |
| `tests/test_dashboard_trade_gate_migration.py` | Verifies dashboard adapter behavior and canonical gate integration. |
| `tests/engine/test_regime_gate_registry.py` | Verifies canonical regime gate registry behavior. |
| `tests/engine/test_engine_loop_regime_gate_wiring.py` | Verifies regime gate pre-execution path. |

## Current Authority Path

Current reviewed authority path:

```text
Signal/runtime candidate
-> TradeDecisionOrchestrator
-> CSSUnifiedTradeGate for governance decision source
-> Runtime filters expose canonical governance result
-> execute_trade remains disabled in this orchestrator payload
```

Dashboard authority path:

```text
scripts/css_live_dashboard.py
-> CSSGateDashboardAdapter
-> CSSUnifiedTradeGate
-> dashboard-compatible decision dictionary
```

Execution safety path remains separately controlled by existing execution and
risk gates:

```text
engine/engine_loop.py
-> RegimeGate
-> ExecutionGate
-> AntiBleedGuard / MarginTradeGate / RiskGovernor
```

## Certification Interpretation

The runtime path has migrated toward canonical `CSSUnifiedTradeGate` decision
sourcing for governance fields while preserving execution-disabled behavior in
the orchestrator decision payload.

This evidence supports certification review for decision-source consolidation.
It does not certify live execution, broker execution, production runtime
operation, or final trade authorization.
