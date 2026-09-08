from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.commercialization.performance_attribution import (
    AttributablePerformance,
)


@dataclass(frozen=True, slots=True)
class PerformanceAccountState:
    """
    Immutable COM-002C performance-accounting state.

    All values represent CSS-attributable realized performance only.

    high_water_mark:
        Highest cumulative attributable realized P&L achieved so far.

    loss_carryforward:
        Amount by which current cumulative attributable realized P&L
        remains below the historical high-water mark.

    This state does not calculate or authorize a fee.
    """

    currency: str
    cumulative_attributable_pnl: Decimal = Decimal("0")
    high_water_mark: Decimal = Decimal("0")
    loss_carryforward: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for name, value in (
            (
                "cumulative_attributable_pnl",
                self.cumulative_attributable_pnl,
            ),
            ("high_water_mark", self.high_water_mark),
            ("loss_carryforward", self.loss_carryforward),
        ):
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be Decimal")
            if not value.is_finite():
                raise ValueError(f"{name} must be finite")

        if (
            not self.currency
            or self.currency != self.currency.strip()
            or self.currency != self.currency.upper()
        ):
            raise ValueError(
                "currency must be canonical uppercase text"
            )

        if self.high_water_mark < Decimal("0"):
            raise ValueError(
                "high_water_mark cannot be negative"
            )

        if self.loss_carryforward < Decimal("0"):
            raise ValueError(
                "loss_carryforward cannot be negative"
            )

        expected_loss = max(
            self.high_water_mark
            - self.cumulative_attributable_pnl,
            Decimal("0"),
        )

        if self.loss_carryforward != expected_loss:
            raise ValueError(
                "loss_carryforward must equal the gap "
                "between high_water_mark and cumulative "
                "attributable P&L"
            )


@dataclass(frozen=True, slots=True)
class PerformanceAccountingTransition:
    """
    Immutable result of applying one attributable-performance record.

    recovered_loss:
        Portion of positive realized P&L used to recover an existing
        drawdown below the previous high-water mark.

    new_economic_gain:
        Portion of this trade's attributable realized P&L that raises
        cumulative performance above the previous high-water mark.

    Neither value is a fee or fee entitlement.
    """

    trade_id: str
    previous_state: PerformanceAccountState
    new_state: PerformanceAccountState
    attributable_realized_pnl: Decimal
    recovered_loss: Decimal
    new_economic_gain: Decimal

    @property
    def real_fee_collection_allowed(self) -> bool:
        return False

    @property
    def client_funds_deduction_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def initial_performance_account(
    currency: str,
) -> PerformanceAccountState:
    return PerformanceAccountState(
        currency=currency,
        cumulative_attributable_pnl=Decimal("0"),
        high_water_mark=Decimal("0"),
        loss_carryforward=Decimal("0"),
    )


def apply_attributable_performance(
    state: PerformanceAccountState,
    performance: AttributablePerformance,
) -> PerformanceAccountingTransition:
    """
    Apply one immutable COM-002B attributable realized-P&L record.

    Losses reduce cumulative performance and create/increase loss
    carryforward.

    Subsequent gains first recover that deficit. Only performance above
    the previous high-water mark is classified as new economic gain.

    This function does not calculate fees.
    """

    if state.currency != performance.currency:
        raise ValueError(
            "performance currency does not match account currency"
        )

    pnl = performance.realized_pnl

    if not isinstance(pnl, Decimal):
        raise TypeError(
            "attributable realized_pnl must be Decimal"
        )

    if not pnl.is_finite():
        raise ValueError(
            "attributable realized_pnl must be finite"
        )

    previous_cumulative = (
        state.cumulative_attributable_pnl
    )
    previous_hwm = state.high_water_mark
    previous_loss = state.loss_carryforward

    new_cumulative = previous_cumulative + pnl

    recovered_loss = Decimal("0")

    if pnl > 0 and previous_loss > 0:
        recovered_loss = min(
            pnl,
            previous_loss,
        )

    new_economic_gain = max(
        new_cumulative - previous_hwm,
        Decimal("0"),
    )

    new_hwm = max(
        previous_hwm,
        new_cumulative,
        Decimal("0"),
    )

    new_loss = max(
        new_hwm - new_cumulative,
        Decimal("0"),
    )

    new_state = PerformanceAccountState(
        currency=state.currency,
        cumulative_attributable_pnl=new_cumulative,
        high_water_mark=new_hwm,
        loss_carryforward=new_loss,
    )

    return PerformanceAccountingTransition(
        trade_id=performance.trade_id,
        previous_state=state,
        new_state=new_state,
        attributable_realized_pnl=pnl,
        recovered_loss=recovered_loss,
        new_economic_gain=new_economic_gain,
    )
