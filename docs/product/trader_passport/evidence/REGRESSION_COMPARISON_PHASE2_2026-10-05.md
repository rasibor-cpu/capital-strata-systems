# Full-suite regression comparison — phase 2 (2026-10-05)

Command (every copy): python -m pytest -q -p no:cacheprovider -p no:warnings --continue-on-collection-errors (PYTHONPATH=.)
Copies, each a fresh directory in scratch:
- baseline: pristine START df566ee (git archive)
- branch: this branch's working tree at commit time (git ls-files -co --exclude-standard)

| Copy | Result |
|---|---|
| baseline, fresh | 3 failed, 459 passed, 32 errors in 5.76s |
| branch, fresh | 3 failed, 581 passed, 3 skipped, 32 errors in 49.88s |

Failing/erroring test ids are **identical** (35 entries; diff empty). No new failures.

- The 3 skips are the axe scans in tests/onboarding/test_trader_passport_ui.py, because CSS_AXE_PATH isn't set in a
  plain full-suite run. The dedicated run with axe (pytest_trader_passport_phase2_2026-10-05.txt) has 0 skips:
  125 passed.
- Passed +122 vs baseline = the 125 dedicated tests minus the 3 axe scans skipped here.

## Pre-existing failures (also on the fresh baseline)

- ERROR tests/dashboard/test_mobile_trade_summary.py
- ERROR tests/scripts/test_auto_flatten_simulation.py
- ERROR tests/scripts/test_broker_resilience.py
- ERROR tests/scripts/test_continuous_reconciliation.py::test_broker_api_unavailable
- ERROR tests/scripts/test_continuous_reconciliation.py::test_broker_position_exists_local_absent
- ERROR tests/scripts/test_continuous_reconciliation.py::test_heartbeat_healthy_parity
- ERROR tests/scripts/test_continuous_reconciliation.py::test_local_ledger_exists_broker_absent
- ERROR tests/scripts/test_continuous_reconciliation.py::test_no_new_execution_allowed_after_mismatch
- ERROR tests/scripts/test_off_ledger_repair.py::test_continuous_reconciliation_locks_on_divergence
- ERROR tests/scripts/test_off_ledger_repair.py::test_detect_divergences_ghost_local
- ERROR tests/scripts/test_off_ledger_repair.py::test_detect_divergences_orphan_broker
- ERROR tests/scripts/test_off_ledger_repair.py::test_repair_record_creation_and_persistence
- ERROR tests/scripts/test_off_ledger_repair.py::test_repair_status_transitions
- ERROR tests/scripts/test_off_ledger_repair.py::test_startup_reconciliation_locks_on_divergence
- ERROR tests/scripts/test_post_trade_reconciliation.py::test_post_trade_api_timeout
- ERROR tests/scripts/test_post_trade_reconciliation.py::test_post_trade_mismatched_trade
- ERROR tests/scripts/test_post_trade_reconciliation.py::test_post_trade_missing_trade
- ERROR tests/scripts/test_post_trade_reconciliation.py::test_post_trade_success
- ERROR tests/scripts/test_slippage_protection.py::test_execution_exceeding_bounds
- ERROR tests/scripts/test_slippage_protection.py::test_missing_expected_price
- ERROR tests/scripts/test_slippage_protection.py::test_missing_expected_price_blocks_execution
- ERROR tests/scripts/test_slippage_protection.py::test_negative_zero_expected_price_blocks_execution
- ERROR tests/scripts/test_slippage_protection.py::test_price_bound_rejection
- ERROR tests/scripts/test_slippage_protection.py::test_resolve_expected_fx_price_invalid
- ERROR tests/scripts/test_slippage_protection.py::test_resolve_expected_fx_price_valid
- ERROR tests/scripts/test_slippage_protection.py::test_slippage_calculation_accuracy
- ERROR tests/scripts/test_slippage_protection.py::test_successful_execution_within_bounds
- ERROR tests/scripts/test_startup_reconciliation.py::test_broker_position_exists_local_absent
- ERROR tests/scripts/test_startup_reconciliation.py::test_local_position_exists_broker_absent
- ERROR tests/scripts/test_startup_reconciliation.py::test_reconciliation_api_error
- ERROR tests/scripts/test_startup_reconciliation.py::test_startup_lock_behavior
- ERROR tests/scripts/test_startup_reconciliation.py::test_startup_parity
- FAILED tests/dashboard/test_broker_balance_reconciliation.py::test_frontend_and_api_expose_broker_reconciliation_section
- FAILED tests/dashboard/test_frontend_payloads.py::test_api_bridge_routes_are_read_only_and_dashboard_state_fed
- FAILED tests/dashboard/test_mobile_governance.py::test_mobile_live_trade_routes_to_execution_gate

Root causes:
- The 32 errors (3 collection errors and their dependants): backend/data/ is excluded by .gitignore line 68 'data/',
  so backend.data.price_feed is missing from the repository.
- tests/dashboard/test_mobile_governance.py::test_mobile_live_trade_routes_to_execution_gate depends on runtime DB
  state (data/css_runtime.db, created at run time). On a fresh copy it returns MISSING_PNL_SNAPSHOT and fails; on a
  copy reused from an earlier run it passes. This explains why a re-run of an old baseline copy showed "2 failed".
  The phase-1 comparison's "3 failed" on both sides included this test, but its listing showed only two FAILED lines.

## Governance sweep (CI step) on the branch copy

PYTHONPATH=. python scripts/run_ai_governance_sweep.py → "All governance checks passed successfully.", Readiness
Score 100, Authority Status PASS, exit 0.
python -m compileall backend/app/onboarding backend/app/trade_origin → OK.
