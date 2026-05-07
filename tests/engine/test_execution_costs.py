from __future__ import annotations

from datetime import datetime, timezone

from engine.domain.executions import ExecutionReport
from engine.domain.fees import FeeSchedule
from engine.execution.cost_model import ExecutionCostModel
from engine.execution.execution_cost_engine import ExecutionCostEngine


def _execution_report(side: str = "BUY", gross_amount: float = 1000.0) -> ExecutionReport:
    now = datetime.now(timezone.utc)
    return ExecutionReport(
        order_id="ORD-1",
        execution_id="EXE-1",
        user_id="USER-1",
        company_id="COMPANY-1",
        branch_id="BRANCH-1",
        department_id="DEPT-1",
        symbol="EUR_USD",
        side=side,
        currency="USD",
        order_date=now,
        requested_exec_date=None,
        execution_date=now,
        settlement_date=None,
        filled_qty=10.0,
        fill_price=100.0,
        avg_price=100.0,
        gross_amount=gross_amount,
        commission_rate_pct=0.0,
        brokerage_commission=0.0,
        tax_rate_pct=0.0,
        tax_amount=0.0,
        total_fees_and_taxes=0.0,
        net_amount=gross_amount,
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


def test_execution_cost_engine_known_notional_is_deterministic() -> None:
    adjusted = ExecutionCostEngine(deterministic=True).apply_costs(
        instrument="EUR_USD",
        notional=10000.0,
        raw_pnl=100.0,
    )

    assert adjusted == 93.4


def test_execution_cost_engine_unknown_asset_uses_safe_fallback() -> None:
    adjusted = ExecutionCostEngine(deterministic=True).apply_costs(
        instrument="UNKNOWN",
        notional=10000.0,
        raw_pnl=100.0,
    )

    assert adjusted == 93.1
    assert adjusted < 100.0


def test_execution_cost_model_applies_non_negative_fees_for_buy() -> None:
    report = _execution_report(side="BUY", gross_amount=1000.0)
    schedule = FeeSchedule(
        fee_schedule_id="SCHED-1",
        version="1",
        effective_from=datetime.now(timezone.utc),
        commission_rate_pct=0.10,
        tax_rate_pct=0.05,
    )

    updated = ExecutionCostModel.apply_fees(report, schedule)

    assert updated.brokerage_commission == 1.0
    assert updated.tax_amount == 0.5
    assert updated.total_fees_and_taxes == 1.5
    assert updated.net_amount == 1001.5
    assert updated.total_fees_and_taxes >= 0.0


def test_execution_cost_model_sell_reduces_net_settlement() -> None:
    report = _execution_report(side="SELL", gross_amount=1000.0)
    schedule = FeeSchedule(
        fee_schedule_id="SCHED-1",
        version="1",
        effective_from=datetime.now(timezone.utc),
        commission_rate_pct=0.10,
        tax_rate_pct=0.05,
    )

    updated = ExecutionCostModel.apply_fees(report, schedule)

    assert updated.total_fees_and_taxes == 1.5
    assert updated.net_amount == 998.5
