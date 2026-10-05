# Full-suite regression comparison (2026-10-05)

Command (both copies): python -m pytest -q -p no:cacheprovider -p no:warnings --continue-on-collection-errors
Copies: pristine origin/main df566ee (git archive) vs this branch's working tree, both in scratch directories.

main:   3 failed, 459 passed, 32 errors in 5.77s
branch: 3 failed, 537 passed, 1 skipped, 32 errors in 24.28s

Failing/erroring test ids: identical on both (34 entries; diff empty). They pre-date this branch:
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

Root cause of the 3 collection errors: backend/data/ is excluded by .gitignore line 68 'data/', so backend.data.price_feed is missing from the repository (git check-ignore -v backend/data/price_feed.py).

## Governance sweep (CI step) on this branch

PYTHONPATH=. python scripts/run_ai_governance_sweep.py -> "All governance checks passed successfully." (Readiness Score 100, Authority PASS), exit 0
