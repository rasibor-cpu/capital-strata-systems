from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from engine.domain.executions import ExecutionReport
from engine.ledger import CANONICAL_PNL_SOURCE
from engine.ledger.ledger_store import LedgerStore
from engine.ledger.pnl_engine import PnLEngine
from engine.ledger.pnl_snapshot_adapter import build_pnl_snapshot_contract


def _execution_report(
    *,
    side: str,
    qty: float,
    price: float,
    execution_id: str,
    symbol: str = "BTC-USD",
) -> ExecutionReport:
    now = datetime.now(timezone.utc)
    return ExecutionReport(
        order_id=f"ORD-{execution_id}",
        execution_id=execution_id,
        user_id="USER-1",
        company_id="COMPANY-1",
        branch_id="BRANCH-1",
        department_id="DEPT-1",
        symbol=symbol,
        side=side,
        currency="USD",
        order_date=now,
        requested_exec_date=None,
        execution_date=now,
        settlement_date=None,
        filled_qty=qty,
        fill_price=price,
        avg_price=price,
        gross_amount=qty * price,
        commission_rate_pct=0.0,
        brokerage_commission=0.0,
        tax_rate_pct=0.0,
        tax_amount=0.0,
        total_fees_and_taxes=0.0,
        net_amount=qty * price,
        counterparty_id=None,
        counterparty_name=None,
        counterparty_account=None,
        fi_id=None,
        fi_name=None,
        fi_branch_id=None,
        fi_branch_name=None,
        settlement_account_name=None,
        settlement_account_number=None,
        settlement_sort_code=None,
        settlement_routing_code=None,
        settlement_swift_bic=None,
        settlement_iban=None,
        settlement_currency="USD",
        settlement_reference=None,
        fee_schedule_id="",
        fee_schedule_version="",
        broker_name="TEST",
        is_paper=True,
        latency_ms=None,
        slippage_bps=None,
        slippage_amount=None,
        status="FILLED",
        seed=None,
        meta={},
    )


def _store_with_canonical_snapshot(
    *,
    executions: list[ExecutionReport],
    market_prices: dict[str, float],
) -> LedgerStore:
    store = LedgerStore()
    engine = PnLEngine(store)

    for execution in executions:
        engine.update_from_execution(execution)

    engine.snapshot(
        as_of=datetime.now(timezone.utc),
        market_prices=market_prices,
        company_id="COMPANY-1",
        branch_id="BRANCH-1",
        department_id="DEPT-1",
        user_id="USER-1",
    )

    return store


def test_adapter_represents_canonical_realized_pnl() -> None:
    store = _store_with_canonical_snapshot(
        executions=[
            _execution_report(
                side="BUY",
                qty=2.0,
                price=100.0,
                execution_id="BUY-1",
            ),
            _execution_report(
                side="SELL",
                qty=2.0,
                price=125.0,
                execution_id="SELL-1",
            ),
        ],
        market_prices={"BTC-USD": 125.0},
    )

    contract = build_pnl_snapshot_contract(
        store,
        starting_equity=Decimal("1000"),
        asset_class_by_symbol={"BTC-USD": "CRYPTO"},
        company_id="COMPANY-1",
        branch_id="BRANCH-1",
        department_id="DEPT-1",
        user_id="USER-1",
    )

    assert contract.realized_pnl == Decimal("50.0")
    assert contract.unrealized_pnl == Decimal("0.0")
    assert contract.net_pnl == Decimal("50.0")
    assert contract.equity == Decimal("1050.0")
    assert contract.asset_realized_pnl["CRYPTO"] == Decimal("50.0")
    assert contract.open_positions == 0
    assert contract.closed_positions == 1


def test_adapter_represents_canonical_unrealized_pnl() -> None:
    store = _store_with_canonical_snapshot(
        executions=[
            _execution_report(
                side="BUY",
                qty=3.0,
                price=100.0,
                execution_id="BUY-1",
            ),
        ],
        market_prices={"BTC-USD": 110.0},
    )

    contract = build_pnl_snapshot_contract(
        store,
        starting_equity=Decimal("1000"),
        asset_class_by_symbol={"BTC-USD": "CRYPTO"},
        company_id="COMPANY-1",
        branch_id="BRANCH-1",
        department_id="DEPT-1",
        user_id="USER-1",
    )

    assert contract.realized_pnl == Decimal("0")
    assert contract.unrealized_pnl == Decimal("30.0")
    assert contract.net_pnl == Decimal("30.0")
    assert contract.equity == Decimal("1030.0")
    assert contract.asset_unrealized_pnl["CRYPTO"] == Decimal("30.0")
    assert contract.open_positions == 1
    assert contract.closed_positions == 0


def test_adapter_includes_source_and_dashboard_safe_fields() -> None:
    store = _store_with_canonical_snapshot(
        executions=[
            _execution_report(
                side="BUY",
                qty=1.0,
                price=100.0,
                execution_id="BUY-1",
            ),
        ],
        market_prices={"BTC-USD": 90.0},
    )

    contract = build_pnl_snapshot_contract(
        store,
        starting_equity=Decimal("1000"),
        peak_equity=Decimal("1100"),
        max_drawdown=Decimal("0.05"),
        asset_class_by_symbol={"BTC-USD": "CRYPTO"},
        company_id="COMPANY-1",
        branch_id="BRANCH-1",
        department_id="DEPT-1",
        user_id="USER-1",
    )
    dashboard_safe = contract.to_runtime_dict()

    assert contract.source == CANONICAL_PNL_SOURCE
    assert dashboard_safe["source"] == CANONICAL_PNL_SOURCE
    assert dashboard_safe["realized_pnl"] == 0.0
    assert dashboard_safe["unrealized_pnl"] == -10.0
    assert dashboard_safe["net_pnl"] == -10.0
    assert dashboard_safe["equity"] == 990.0
    assert dashboard_safe["peak_equity"] == 1100.0
    assert dashboard_safe["current_drawdown"] == 0.1
    assert dashboard_safe["max_drawdown"] == 0.1
    assert dashboard_safe["asset_unrealized_pnl"] == {"CRYPTO": -10.0}
    assert dashboard_safe["open_positions"] == 1
    assert dashboard_safe["closed_positions"] == 0


def test_adapter_is_deterministic_and_requires_no_broker_connectivity() -> None:
    store = _store_with_canonical_snapshot(
        executions=[
            _execution_report(
                side="BUY",
                qty=1.0,
                price=100.0,
                execution_id="BUY-1",
            ),
            _execution_report(
                side="SELL",
                qty=1.0,
                price=125.0,
                execution_id="SELL-1",
            ),
        ],
        market_prices={"BTC-USD": 125.0},
    )

    kwargs = {
        "starting_equity": Decimal("1000"),
        "asset_class_by_symbol": {"BTC-USD": "CRYPTO"},
        "company_id": "COMPANY-1",
        "branch_id": "BRANCH-1",
        "department_id": "DEPT-1",
        "user_id": "USER-1",
    }

    first = build_pnl_snapshot_contract(store, **kwargs).to_runtime_dict()
    second = build_pnl_snapshot_contract(store, **kwargs).to_runtime_dict()

    assert first == second
    assert first["source"] == CANONICAL_PNL_SOURCE
