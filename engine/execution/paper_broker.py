from datetime import datetime
from typing import List
import uuid
import random

from engine.execution.broker_base import BrokerAdapter
from engine.domain.orders import OrderIntent
from engine.domain.executions import ExecutionReport
from engine.execution.cost_model import ExecutionCostModel
from engine.domain.fees import FeeSchedule


class PaperBrokerAdapter(BrokerAdapter):
    """
    Deterministic paper execution adapter.

    - Simulates MARKET and LIMIT orders
    - Generates execution timestamps, latency, slippage
    - Produces ExecutionReport(s)
    - Applies ExecutionCostModel
    """

    def __init__(
        self,
        fee_schedule: FeeSchedule,
        *,
        broker_name: str = "PAPER",
        seed: int = 42,
        base_latency_ms: int = 25,
        slippage_bps: float = 1.0
    ):
        self.fee_schedule = fee_schedule
        self.broker_name = broker_name
        self.random = random.Random(seed)
        self.base_latency_ms = base_latency_ms
        self.slippage_bps = slippage_bps

    # ─────────────────────────────
    # BrokerAdapter interface
    # ─────────────────────────────
    def submit_order(self, order: OrderIntent) -> List[ExecutionReport]:
        """
        Execute an OrderIntent in paper mode and return ExecutionReport(s).
        """

        now = datetime.utcnow()

        # Simulated latency
        latency_ms = self.base_latency_ms + self.random.randint(0, 10)

        # Determine fill price
        fill_price = self._determine_fill_price(order)

        # Gross amount
        gross_amount = float(order.quantity) * float(fill_price)

        # Slippage calculation (bps)
        slippage_amount = gross_amount * (self.slippage_bps / 10_000.0)

        # Build raw execution report (pre-fees)
        report = ExecutionReport(
            order_id=order.order_id,
            execution_id=str(uuid.uuid4()),

            user_id=order.user_id,
            company_id=order.company_id,
            branch_id=order.branch_id,
            department_id=order.department_id,

            symbol=order.symbol,
            side=order.side,
            currency=order.currency,

            order_date=order.order_date,
            requested_exec_date=order.requested_exec_date,
            execution_date=now,
            settlement_date=None,

            filled_qty=order.quantity,
            fill_price=fill_price,
            avg_price=fill_price,
            gross_amount=gross_amount,

            commission_rate_pct=0.0,
            brokerage_commission=0.0,
            tax_rate_pct=0.0,
            tax_amount=0.0,
            total_fees_and_taxes=0.0,
            net_amount=0.0,

            counterparty_id=order.counterparty_id,
            counterparty_name=order.counterparty_name,
            counterparty_account=order.counterparty_account,

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
            settlement_currency=None,
            settlement_reference=None,

            fee_schedule_id="",
            fee_schedule_version="",

            broker_name=self.broker_name,
            is_paper=True,

            latency_ms=latency_ms,
            slippage_bps=self.slippage_bps,
            slippage_amount=slippage_amount,

            status="FILLED",
            seed=str(self.random.random()),

            meta=None
        )

        # Apply fees & taxes
        report = ExecutionCostModel.apply_fees(report, self.fee_schedule)

        return [report]

    def cancel_order(self, order_id: str) -> None:
        """
        Paper broker cancel is a no-op (orders execute immediately).
        """
        return None

    # ─────────────────────────────
    # Internal helpers
    # ─────────────────────────────
    def _determine_fill_price(self, order: OrderIntent) -> float:
        """
        Determines fill price based on order type.
        """
        if order.order_type.upper() == "LIMIT" and order.limit_price is not None:
            return float(order.limit_price)

        # MARKET order: simulate slight price drift
        base_price = float(order.limit_price) if order.limit_price else 1.0
        drift = self.random.uniform(-0.0005, 0.0005)
        return round(base_price * (1.0 + drift), 6)