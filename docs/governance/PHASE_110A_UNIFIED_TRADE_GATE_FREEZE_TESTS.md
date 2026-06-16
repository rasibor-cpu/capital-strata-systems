# Phase 110A: Unified Trade Gate Freeze Tests

## Overview
Phase 110A establishes regression testing coverage and documentation defining the current legacy dashboard trade-gate behavior (`scripts/css_live_dashboard.py`) before migrating completely to the canonical backend authority (`backend/governance/css_unified_trade_gate.py`).

The legacy dashboard uses `CSSGateDashboardAdapter` to translate signals into backend representations, but also maintains several pre-gate filters based on global session states (`SESSION_USER_CTX`, `is_session_locked()`, etc.).

## Mismatch Report

| Dashboard Gate Concept | Canonical GateConcept | Status | Notes |
|---|---|---|---|
| Session Lock Status | Session Timestamp Timeout | **Mismatch** | Dashboard relies on active locking (`is_session_locked()`); canonical relies on explicit `SESSION_TIMEOUT_SECONDS` (3600s). |
| Output Shape | `GateDecision` dataclass | **Mismatch** | Dashboard returns `tuple[bool, str]`; Canonical returns `GateDecision` object; Adapter translates to `Dict[str, Any]`. |
| Role Check | Role Authorization (`_check_role`) | **Mismatch** | Dashboard evaluates explicit RBAC flags (`can_execute_paper_trading`, etc.); Canonical merely checks `{"ADMIN", "SUPER_USER", "TRADER"}` string equality. |
| Probability | Threshold Rejection | **Mismatch (Adapter overrides)** | The dashboard adapter forcefully aligns `probability` to `max(probability, threshold)`, preventing the backend from rejecting on poor probability unless `cost >= expected_value`. |
| Expected Value | Signal Score mapping | **Mapped** | Dashboard `signal_score` maps precisely to Backend `expected_value` via adapter. |
| Safe Mode Live Execution | Engine Mode Thresholds | **Mismatch** | Dashboard strictly blocks live execution if `ENGINE_MODE == "SAFE"`; canonical only alters the probability threshold. |

## Deliverables Completed
1. `tests/test_dashboard_trade_gate_freeze.py`: Validates dashboard return tuple shape and evaluates adapter translation behavior (especially probability clamping).
2. Documented differences in this report to serve as the migration contract for Phase 110B.
3. Zero modifications to live broker execution or trading logic have occurred.
