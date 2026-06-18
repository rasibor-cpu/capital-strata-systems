# Phase 1 Full Suite Validation Summary

## Purpose

This artifact records the latest broad pytest validation observed during CSS V1
core completion work.

This artifact is documentation-only. It does not change runtime behavior,
execution behavior, broker behavior, dashboard behavior, risk controls,
thresholds, credentials, or trading logic.

## Repository Evidence

| Field | Evidence |
| --- | --- |
| Branch | `css-evening-consolidation-2026-06-09` |
| Evidence HEAD | `2cb0221f6dfc2510eda836f0dd066201304ee10a` |
| Remote | `origin https://github.com/rasibor-cpu/capital-strata-systems.git` |
| Validation Command | `.\.venv\Scripts\python.exe -m pytest tests -q` |

## Full Suite Result

```text
339 passed, 32 warnings in 28.72s
```

Collection evidence from the same validation sequence:

```text
339 tests collected in 4.53s
```

## Warning Summary

The validation completed successfully with non-failing warnings. Observed
warnings were deprecation warnings for `datetime.utcnow()` usage in test or
runtime-support paths, including:

| Area | Representative Path |
| --- | --- |
| Engine loop regime gate wiring | `engine/engine_loop.py` |
| AntiBleedGuard / execution safety integration | `backend/app/risk/anti_bleed_guard.py` |
| Intelligence event tests | `tests/intelligence/` |
| Persistence runtime tests | `backend/app/persistence/services/session_runtime_service.py` |
| Trade runtime persistence tests | `backend/app/persistence/services/trade_runtime_service.py` |

No warning caused a test failure.

## Validation Scope Covered

| Domain | Representative Tests |
| --- | --- |
| Governance | `tests/governance/` |
| Runtime | `tests/test_trade_decision_orchestrator_gate.py`, `tests/test_session_schema_initialization.py` |
| Broker | `tests/test_oanda_margin_adapter.py`, `tests/test_coinbase_margin_adapter.py`, `tests/engine/test_broker_readiness.py` |
| Dashboard | `tests/dashboard/`, `tests/test_dashboard_trade_gate_migration.py` |
| Risk | `tests/engine/test_risk_governor.py`, `tests/test_margin_trade_gate.py`, `tests/test_antibleed_guard_integration.py` |
| Recovery | `tests/test_session_schema_initialization.py`, persistence runtime tests |
| Security | `tests/test_security_phase_alpha.py`, `tests/test_live_toggle_rbac.py`, `tests/test_password_reset_recovery.py` |
| Operations | Runbook-backed evidence plus runtime/dashboard safety tests |

## Certification Interpretation

The latest broad test suite evidence supports controlled certification evidence
assembly. It confirms the current branch can collect and execute the available
test corpus without failures at the recorded HEAD.

This result does not replace runtime certification, broker live-read evidence,
dashboard screenshot capture, recovery certification, credential redaction
review, operational sign-off, or Robert final approval.
