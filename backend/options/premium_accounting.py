from __future__ import annotations

from dataclasses import dataclass


class PremiumAccountingError(ValueError):
    """Raised when paper premium accounting would fail open."""


@dataclass(frozen=True)
class PremiumAccountingSnapshot:
    premium_received: float
    premium_realized: float
    premium_remaining: float
    yield_ratio: float
    yield_on_collateral: float
    annualized_yield: float
    capital_efficiency: float

    def to_dict(self) -> dict[str, float]:
        return {
            "premium_received": self.premium_received,
            "premium_realized": self.premium_realized,
            "premium_remaining": self.premium_remaining,
            "yield": self.yield_ratio,
            "yield_on_collateral": self.yield_on_collateral,
            "annualized_yield": self.annualized_yield,
            "capital_efficiency": self.capital_efficiency,
        }


class PremiumAccounting:
    def open_snapshot(self, *, premium_received: float, collateral_reserved: float, dte: int) -> PremiumAccountingSnapshot:
        premium = _non_negative(premium_received, "premium_received")
        collateral = _non_negative(collateral_reserved, "collateral_reserved")
        days = max(0, int(dte or 0))
        return _snapshot(premium, 0.0, premium, collateral, days)

    def realize_all(self, *, premium_received: float, collateral_reserved: float, dte: int) -> PremiumAccountingSnapshot:
        premium = _non_negative(premium_received, "premium_received")
        collateral = _non_negative(collateral_reserved, "collateral_reserved")
        days = max(0, int(dte or 0))
        return _snapshot(premium, premium, 0.0, collateral, days)

    def close_early(
        self,
        *,
        premium_received: float,
        buyback_cost: float,
        collateral_reserved: float,
        dte: int,
    ) -> PremiumAccountingSnapshot:
        premium = _non_negative(premium_received, "premium_received")
        cost = _non_negative(buyback_cost, "buyback_cost")
        collateral = _non_negative(collateral_reserved, "collateral_reserved")
        realized = max(0.0, premium - cost)
        remaining = max(0.0, premium - realized)
        return _snapshot(premium, realized, remaining, collateral, max(0, int(dte or 0)))


def _snapshot(premium: float, realized: float, remaining: float, collateral: float, dte: int) -> PremiumAccountingSnapshot:
    yield_ratio = (premium / collateral) if collateral > 0 else 0.0
    realized_yield = (realized / collateral) if collateral > 0 else 0.0
    annualized = yield_ratio * (365.0 / dte) if dte > 0 else 0.0
    return PremiumAccountingSnapshot(
        premium_received=round(premium, 6),
        premium_realized=round(realized, 6),
        premium_remaining=round(remaining, 6),
        yield_ratio=round(yield_ratio, 8),
        yield_on_collateral=round(realized_yield, 8),
        annualized_yield=round(annualized, 8),
        capital_efficiency=round(yield_ratio, 8),
    )


def _non_negative(value: float, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PremiumAccountingError(f"{field} must be numeric") from exc
    if number < 0.0:
        raise PremiumAccountingError(f"{field} cannot be negative")
    return number


__all__ = ["PremiumAccounting", "PremiumAccountingError", "PremiumAccountingSnapshot"]
