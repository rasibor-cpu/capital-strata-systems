# Phase 105D Dashboard Canonical Gate Integration Certification

## Scope

Phase 105D certifies the dashboard trade-gate integration with the canonical backend trade gate through a dedicated adapter layer.

This phase is wiring and translation only. It does not change UI rendering, broker behavior, trading behavior, margin logic, risk logic, authentication, execution flow, or credential handling.

## Prior Architecture

The dashboard runtime contains the public trade-gate entrypoint:

```text
scripts/css_live_dashboard.py
-> approve_trade_before_register(...)
```

Earlier dashboard iterations carried local governance surfaces that could drift from backend governance. The current dashboard path preserves dashboard-local session, lock, role, and mode prechecks, then delegates the trade decision to the backend canonical gate through the adapter.

## New Architecture

The dashboard trade decision path is:

```text
scripts/css_live_dashboard.py
-> CSSGateDashboardAdapter
-> backend/governance/css_unified_trade_gate.py
-> GateDecision
-> dashboard-compatible decision dict
```

The canonical governance decision originates from:

```text
backend/governance/css_unified_trade_gate.py
```

The adapter returns dashboard-compatible output while preserving canonical backend reason and details.

## Adapter Responsibilities

`backend/governance/css_gate_dashboard_adapter.py` is responsible for translation only:

- Translate dashboard candidate payloads to canonical gate candidate fields.
- Translate dashboard session and role profile payloads to canonical session fields.
- Normalize dashboard portfolio state keys to canonical lower-case asset-class keys.
- Convert canonical object-shaped or dict-shaped gate decisions into dashboard-compatible dictionaries.
- Preserve canonical backend reason in `backend_reason`.
- Preserve canonical backend details in `backend_details`.

The adapter must not duplicate governance rules, position-limit rules, probability thresholds, role authorization rules, broker rules, or execution rules.

## Decision Shape

Dashboard-compatible decision output:

```json
{
  "approved": true,
  "reason": "UNIFIED_GATE_APPROVED",
  "backend_reason": "approved: canonical backend reason",
  "backend_details": {}
}
```

For rejected decisions, `reason` and `backend_reason` preserve the canonical rejection reason.

## Tests Executed

Targeted validation for this phase:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_dashboard_trade_gate_migration.py -q
```

Relevant regression validation:

```text
.\.venv\Scripts\python.exe -m pytest tests\engine\test_regime_gate_registry.py tests\engine\test_engine_loop_regime_gate_wiring.py -q
```

## Certification Findings

- The adapter translates canonical object-shaped `GateDecision` output.
- The adapter translates dict-shaped gate decisions without adding governance logic.
- ALLOW decisions are preserved as dashboard-compatible approvals.
- BLOCK decisions preserve canonical rejection reasons.
- Dashboard approved-path decisions flow through the adapter.
- Dashboard blocked-path decisions flow through the adapter and preserve reason text.
- Dashboard no longer defines a local `CSSUnifiedTradeGate` class.

## Boundaries Preserved

- No dashboard rendering changes.
- No broker execution changes.
- No trading behavior changes.
- No margin logic changes.
- No risk logic changes.
- No authentication changes.
- No execution flow changes.
- No credential handling changes.
