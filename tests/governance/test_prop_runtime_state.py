from backend.governance.prop_runtime_state import (
    PropRuntimeState,
    build_default_runtime_state,
)

from backend.app.accounting.unified_pnl_state import (
    UnifiedPnLState,
    build_default_unified_pnl_state,
)


def test_default_runtime_state_builds():

    state = build_default_runtime_state()

    assert isinstance(
        state,
        PropRuntimeState,
    )

    assert (
        state.account_id
        == "SIM-ACCOUNT"
    )

    assert (
        state.status
        == "ACTIVE"
    )

    assert (
        state.unified_pnl_state
        is None
    )


def test_governance_snapshot_fields_exist():

    state = build_default_runtime_state()

    snapshot = (
        state.governance_snapshot()
    )

    expected_fields = [
        "status",
        "evaluation_mode",
        "current_balance",
        "peak_balance",
        "total_equity",
        "total_pnl",
        "current_drawdown",
        "daily_loss_breached",
        "max_drawdown_breached",
        "trailing_drawdown_breached",
        "updated_timestamp",
    ]

    for field in expected_fields:

        assert (
            field in snapshot
        )


def test_runtime_math_behaves_without_unified_state():

    state = build_default_runtime_state()

    state.update_equity(
        realized_pnl=500.0,
        unrealized_pnl=250.0,
        current_balance=101000.0,
    )

    assert (
        state.total_equity()
        == 101250.0
    )

    assert (
        state.total_pnl()
        == 750.0
    )

    assert (
        state.current_drawdown()
        == 0.0
    )

    assert (
        state.daily_loss_breached()
        is False
    )

    assert (
        state.max_drawdown_breached()
        is False
    )

    assert (
        state.trailing_drawdown_breached()
        is False
    )


def test_unified_pnl_state_can_attach_safely():

    state = build_default_runtime_state()

    unified = (
        build_default_unified_pnl_state()
    )

    state.unified_pnl_state = (
        unified
    )

    assert (
        state.unified_pnl_state
        is unified
    )

    assert (
        state.total_equity()
        == 100000.0
    )


def test_sync_from_unified_pnl_state():

    state = build_default_runtime_state()

    unified = UnifiedPnLState(
        account_id="SIM-ACCOUNT",
        starting_balance=100000.0,
        cash_balance=105000.0,
        realized_pnl=3000.0,
        unrealized_pnl=2000.0,
        peak_equity=107000.0,
        open_positions=2,
        total_trades=10,
        winning_trades=7,
        losing_trades=3,
        created_timestamp=1.0,
        updated_timestamp=1.0,
        status="ACTIVE",
    )

    state.unified_pnl_state = (
        unified
    )

    state.sync_from_unified_pnl_state()

    assert (
        state.current_balance
        == 105000.0
    )

    assert (
        state.realized_pnl
        == 3000.0
    )

    assert (
        state.unrealized_pnl
        == 2000.0
    )

    assert (
        state.peak_balance
        >= 107000.0
    )


def test_governance_snapshot_includes_unified_snapshot_only_when_present():

    state = build_default_runtime_state()

    snapshot = (
        state.governance_snapshot()
    )

    assert (
        "unified_pnl_snapshot"
        not in snapshot
    )

    state.unified_pnl_state = (
        build_default_unified_pnl_state()
    )

    snapshot = (
        state.governance_snapshot()
    )

    assert (
        "unified_pnl_snapshot"
        in snapshot
    )


def test_as_dict_returns_dictionary():

    state = build_default_runtime_state()

    result = state.as_dict()

    assert isinstance(
        result,
        dict,
    )

    assert (
        result["account_id"]
        == "SIM-ACCOUNT"
    )
