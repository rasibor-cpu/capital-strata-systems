"""Phase 177 — summarized cash-flow statement (no invented adjustments)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from backend.financial_reporting.data_contracts import FinancialDataContract
from backend.financial_reporting.models import FinancialAmount, money, serialize_decimal


@dataclass(frozen=True)
class CashFlowStatement:
    currency: str
    operating_inflows: Decimal | None
    operating_outflows: Decimal | None
    net_operating: Decimal | None
    investing_inflows: Decimal | None
    investing_outflows: Decimal | None
    net_investing: Decimal | None
    financing_inflows: Decimal | None
    financing_outflows: Decimal | None
    net_financing: Decimal | None
    net_change_in_cash: Decimal | None
    opening_cash: Decimal | None
    expected_closing_cash: Decimal | None
    reported_closing_cash: Decimal | None
    cash_reconciliation_variance: Decimal | None
    reconciled: bool | None
    complete: bool
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        s = serialize_decimal
        return {
            "currency": self.currency,
            "operating": {
                "inflows": s(self.operating_inflows),
                "outflows": s(self.operating_outflows),
                "net": s(self.net_operating),
            },
            "investing": {
                "inflows": s(self.investing_inflows),
                "outflows": s(self.investing_outflows),
                "net": s(self.net_investing),
            },
            "financing": {
                "inflows": s(self.financing_inflows),
                "outflows": s(self.financing_outflows),
                "net": s(self.net_financing),
            },
            "net_change_in_cash": s(self.net_change_in_cash),
            "opening_cash": s(self.opening_cash),
            "expected_closing_cash": s(self.expected_closing_cash),
            "reported_closing_cash": s(self.reported_closing_cash),
            "cash_reconciliation_variance": s(self.cash_reconciliation_variance),
            "reconciled": self.reconciled,
            "complete": self.complete,
            "missing_fields": list(self.missing_fields),
            "warnings": list(self.warnings),
        }


def _v(amt: FinancialAmount) -> Decimal | None:
    return amt.for_total()


def generate_cash_flow_statement(contract: FinancialDataContract) -> CashFlowStatement:
    missing: list[str] = []
    warnings: list[str] = []

    def take(name: str, amt: FinancialAmount) -> Decimal | None:
        val = _v(amt)
        if val is None:
            missing.append(name)
        return val

    op_in = take("operating_cash_inflows", contract.operating_cash_inflows)
    op_out = take("operating_cash_outflows", contract.operating_cash_outflows)
    inv_in = take("investing_cash_inflows", contract.investing_cash_inflows)
    inv_out = take("investing_cash_outflows", contract.investing_cash_outflows)
    fin_in = take("financing_cash_inflows", contract.financing_cash_inflows)
    fin_out = take("financing_cash_outflows", contract.financing_cash_outflows)
    opening = take("opening_cash", contract.opening_cash)
    closing = take("closing_cash", contract.closing_cash)

    def net(a: Decimal | None, b: Decimal | None) -> Decimal | None:
        if a is None and b is None:
            return None
        return money((a or Decimal("0")) - (b or Decimal("0")))

    net_op = net(op_in, op_out)
    net_inv = net(inv_in, inv_out)
    net_fin = net(fin_in, fin_out)

    net_change = None
    if any(v is not None for v in (net_op, net_inv, net_fin)):
        net_change = money(
            (net_op or Decimal("0")) + (net_inv or Decimal("0")) + (net_fin or Decimal("0"))
        )

    expected_closing = None
    if opening is not None or net_change is not None:
        expected_closing = money((opening or Decimal("0")) + (net_change or Decimal("0")))

    variance = None
    reconciled: bool | None = None
    if expected_closing is not None and closing is not None:
        variance = money(expected_closing - closing)
        reconciled = variance == money(0)
        if not reconciled:
            warnings.append(
                f"cash flow not reconciled; variance={format(variance, 'f')}"
            )

    complete = net_change is not None and opening is not None and closing is not None

    return CashFlowStatement(
        currency=contract.currency,
        operating_inflows=op_in,
        operating_outflows=op_out,
        net_operating=net_op,
        investing_inflows=inv_in,
        investing_outflows=inv_out,
        net_investing=net_inv,
        financing_inflows=fin_in,
        financing_outflows=fin_out,
        net_financing=net_fin,
        net_change_in_cash=net_change,
        opening_cash=opening,
        expected_closing_cash=expected_closing,
        reported_closing_cash=closing,
        cash_reconciliation_variance=variance,
        reconciled=reconciled,
        complete=complete,
        missing_fields=tuple(sorted(set(missing))),
        warnings=tuple(warnings),
    )
