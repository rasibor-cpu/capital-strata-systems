from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from dashboard.runtime.state_builders.position_state_builder import PositionStateBuilder
from dashboard.runtime.summary_builders.pnl_summary_builder import PnLSummaryBuilder
from engine.domain.executions import ExecutionReport
from engine.ledger.ledger_store import LedgerStore
from engine.ledger.pnl_engine import PnLEngine


def _report(
    *,
    side: str,
    qty: float,
    price: float,
    execution_id: str,
) -> ExecutionReport:
    now = datetime.now(timezone.utc)
    return ExecutionReport(
        order_id=f"ORD-{execution_id}",
        execution_id=execution_id,
        user_id="USER-1",
        company_id="COMPANY-1",
        branch_id="BRANCH-1",
        department_id="DEPT-1",
        symbol="BTC-USD",
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


def test_ledger_and_dashboard_pnl_reconcile_for_deterministic_round_trip() -> None:
    store = LedgerStore()
    engine = PnLEngine(store)

    engine.update_from_execution(
        _report(side="BUY", qty=2.0, price=100.0, execution_id="BUY-1")
    )
    engine.update_from_execution(
        _report(side="SELL", qty=2.0, price=125.0, execution_id="SELL-1")
    )
    engine.snapshot(
        as_of=datetime.now(timezone.utc),
        market_prices={"BTC-USD": 125.0},
        company_id="COMPANY-1",
        branch_id="BRANCH-1",
        department_id="DEPT-1",
        user_id="USER-1",
    )

    [snapshot] = store.get_latest_pnl(
        company_id="COMPANY-1",
        branch_id="BRANCH-1",
        department_id="DEPT-1",
        user_id="USER-1",
    )
    assert snapshot.realized_pnl == Decimal("50.0")
    assert snapshot.unrealized_pnl == Decimal("0.0")

    position_state = PositionStateBuilder().build(
        {
            "positions": [
                {
                    "symbol": snapshot.symbol,
                    "asset_class": "CRYPTO",
                    "side": "LONG",
                    "qty": snapshot.meta["qty"],
                    "entry_price": snapshot.meta["avg_cost"],
                    "current_price": 125.0,
                    "realized_pnl": str(snapshot.realized_pnl),
                    "unrealized_pnl": str(snapshot.unrealized_pnl),
                }
            ]
        }
    )
    dashboard_summary = PnLSummaryBuilder().build(
        account_state={"equity": 1000.0},
        position_state=position_state,
    )

    assert dashboard_summary["realized_pnl"] == float(snapshot.realized_pnl)
    assert dashboard_summary["unrealized_pnl"] == float(snapshot.unrealized_pnl)
    assert dashboard_summary["net_pnl"] == 50.0
