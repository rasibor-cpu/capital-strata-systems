# Phase 183C-F Fail-Closed Runtime And Broker Contract Reconciliation

## Scope

Phase 183C-F reconciles runtime-mode projection, Mission Control source parity, broker readiness vocabulary, OANDA quarantine/firewall precedence, operational compatibility validation, and startup summary display semantics.

This is an implementation checkpoint only. It does not certify production, does not authorize live trading, does not begin OV-002 Attempt 3, and does not deploy or restart the CSS runtime.

## Runtime Mode Contract

Runtime authority remains `backend.runtime.runtime_mode.resolve_runtime_mode`.

Canonical runtime projections now expose separate fields:

- `requested_mode`: operator/session/requested intent when available.
- `observed_mode`: broker/profile/runtime evidence observed by the resolver.
- `effective_mode`: the resolver-authoritative runtime mode.
- `runtime_mode`: compatibility alias for `effective_mode`.
- `execution_posture`: `DISABLED` unless the resolver and downstream gates explicitly authorize execution.
- `broker_posture`: separate broker/account posture; not a runtime authority.
- `source`: `RUNTIME_MODE_RESOLVER`.
- `source_freshness`, `source_confidence`, `source_disagreement`, `degraded_reason`.

Unknown, incomplete, stale, or conflicting inputs do not normalize to `PAPER` and cannot become `LIVE`. Mobile controls remain ticket/access posture only and cannot elevate platform runtime mode.

## Broker Readiness Contract

Broker readiness separates:

- credential state;
- authentication state;
- transport/connectivity state;
- account/balance/market-data evidence;
- read-only readiness;
- execution authorization;
- overall canonical state.

Read-only evidence can produce advisory `GO` only for read-only validation while `execution_allowed=false`, `live_trading_blocked=true`, `broker_execution_armed=false`, and `advisory_only=true`. `READ_ONLY_READY` is the canonical operational state for read-only-ready brokers; it is not live execution readiness.

Injected Coinbase read-only readiness evidence no longer loads machine-local profile files, preventing local credential/profile contamination from downgrading deterministic fake-client tests or silently altering readiness.

Missing Coinbase credentials remain truthful: authentication and connection stay `NOT_TESTED` rather than being collapsed into a factual transport failure.

## Mission Control And Operational Compatibility

Mission Control source fields remain aligned with the resolver-selected source. Operational compatibility validation compares canonical views and preserves fail-closed safety flags.

State hashes remain authoritative when they match. When runtime and Mission Control snapshots are independently regenerated, volatile hash differences do not fail the compatibility report if runtime identity, session, and source match; downstream broker, portfolio, risk, certification, unavailable-projection, and safety checks still enforce real divergence.

The Phase170 validator CLI/test files are legitimate source/test files adopted into this checkpoint:

- `backend/runtime/operational_compatibility_validator.py`
- `scripts/css_operational_compatibility_validator.py`
- `tests/test_phase170_operational_compatibility_validator.py`

The validator module was previously excluded by the broad `backend/runtime/*` ignore rule. `.gitignore` now contains a narrow explicit exception for this canonical source file only; generated runtime outputs remain ignored.

## OANDA Quarantine And Firewall Precedence

Legacy OANDA write methods remain quarantined by default. `place_order` now evaluates the live firewall before returning the quarantine response when doing so requires no network access.

The response preserves quarantine as the primary denial:

- `primary_denial_code="oanda_legacy_writes_quarantined"`
- `quarantine_active=true`
- `firewall_active=true`
- `execution_authorized=false`
- `network_attempted=false`

If the live firewall also denies the request, the denial is exposed in `secondary_denial_codes`. This keeps quarantine authoritative without hiding firewall state.

## Startup Summary Semantics

The formatted startup summary now includes broker identity, broker mode, execution scope, and the safety-gate fields already present in the summary payload. Broker mode display does not imply live execution readiness.

## Verification Evidence

### Original Checkpoint

Focused Phase 183C-F checks initially reduced the original 26-node bundle to 10 residual failures. The historical checkpoint state was:

- Original bundle after remediation: 16 passed, 10 failed.
- Combined focused Phase 183C-F suite: 122 passed.
- Operational compatibility tests: 4 passed.
- Collection: 3277 tests collected.
- Repeated complete suite: 10 failed, 3262 passed, 5 skipped, 2 warnings.
- The first complete suite showed one first-run-only Phase176J readiness failure that passed directly and did not recur in the repeated complete suite; it remains tracked as transient/order-dependent evidence, not remediated in this phase.

### Original Residual Failures

The original residual nodes were:

- `tests/dashboard/test_mobile_live_order_kill_switch.py::test_mobile_live_order_kill_switch_does_not_block_paper_tickets`
- `tests/test_asset_lifecycle_integration.py::test_strict_persistence_default_fail_closed`
- `tests/test_canonical_trade_lifecycle.py::test_unsupported_asset_class_fails_closed`
- `tests/test_dashboard_subtabs.py::test_launcher_show_screen_syncs_quick_nav`
- `tests/test_ov001_controlled_shutdown.py::test_oat_reaches_100_with_shutdown`
- `tests/test_phase176_institutional_reports_center.py::test_transaction_journal_and_ticket`
- `tests/test_phase179d_enterprise_broker_runtime.py::test_mission_control_reports_and_certification_remain_fail_closed`
- `tests/test_phase180b_branding_certification.py::test_all_application_manifests_and_heads_use_brand_service`
- `tests/test_pnl_snapshot_persistence_contract.py::test_trade_decision_orchestrator_persists_pnl_snapshot`
- `tests/test_trade_decision_orchestrator_gate.py::test_trade_decision_orchestrator_sources_governance_from_canonical_gate`

### Subsequent Resolution

Subsequent reconciliation resolved the prior residual nodes without changing runtime code, broker adapters, execution controls, certification logic, tests, or live-trading state in Phase 183G-GH.

### Revalidation Command And Result

Revalidation on 2026-07-29 with the repository virtual environment passed the prior 10 residual nodes as a combined bundle:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\dashboard\test_mobile_live_order_kill_switch.py::test_mobile_live_order_kill_switch_does_not_block_paper_tickets tests\test_asset_lifecycle_integration.py::test_strict_persistence_default_fail_closed tests\test_canonical_trade_lifecycle.py::test_unsupported_asset_class_fails_closed tests\test_dashboard_subtabs.py::test_launcher_show_screen_syncs_quick_nav tests\test_ov001_controlled_shutdown.py::test_oat_reaches_100_with_shutdown tests\test_phase176_institutional_reports_center.py::test_transaction_journal_and_ticket tests\test_phase179d_enterprise_broker_runtime.py::test_mission_control_reports_and_certification_remain_fail_closed tests\test_phase180b_branding_certification.py::test_all_application_manifests_and_heads_use_brand_service tests\test_pnl_snapshot_persistence_contract.py::test_trade_decision_orchestrator_persists_pnl_snapshot tests\test_trade_decision_orchestrator_gate.py::test_trade_decision_orchestrator_sources_governance_from_canonical_gate -q
```

Result: 10 passed.

### Current Disposition

Safety posture remains:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

The prior residual nodes now pass in the focused revalidation bundle. This does not imply that a complete regression suite passed in Phase 183G-GH.

### Broker Expected Reports

Phase 183G-GH relocated the RC1B expected broker reports into the governed broker certification evidence area:

- `certification/broker/coinbase_rc1b_expected_report.json`
- `certification/broker/oanda_rc1b_expected_report.json`

These files are expected-output baselines for the `rc1b.broker_certification.v1` report shape. They are non-runtime reports and comparison evidence only. They do not enable execution, arm brokers, authorize live trading, provide broker credentials, or prove current broker connectivity unless separately validated by an approved read-only certification run.

### Relationship To Final Certification Evidence

This document remains a historical implementation checkpoint and revalidation note. It is not the final production certification authority. Later canonical certification documents must own any final production, broker-readiness, deployment, or OV-002 disposition.

No broker authentication, network access, runtime start/restart, deployment, production certification, live-readiness claim, or OV-002 Attempt 3 action occurred.

## Remaining Work

The prior deterministic residual clusters are now locally green in the focused revalidation bundle. Later phases should still run broader collection and complete-suite evidence before changing production, live-readiness, deployment, or OV-002 posture.
