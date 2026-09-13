from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Mapping


ZERO = Decimal("0")


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware UTC")


def _require_non_negative(value: Decimal, field_name: str) -> None:
    if value < ZERO:
        raise ValueError(f"{field_name} must be non-negative")


class ChallengeType(str, Enum):
    CAPITAL_PRESERVATION = "CAPITAL_PRESERVATION"
    BENCHMARK_OUTPERFORMANCE = "BENCHMARK_OUTPERFORMANCE"
    DRAWDOWN_CONTROL = "DRAWDOWN_CONTROL"
    DECISION_DISCIPLINE = "DECISION_DISCIPLINE"


@dataclass(frozen=True)
class ForecastAssessment:
    """Probabilistic educational forecast, never a certainty claim."""

    as_of_utc: datetime
    horizon: str
    probability_up: Decimal
    probability_flat: Decimal
    probability_down: Decimal
    expected_low: Decimal
    expected_high: Decimal
    confidence: Decimal
    invalidation_condition: str

    def __post_init__(self) -> None:
        _require_utc(self.as_of_utc, "as_of_utc")
        total = self.probability_up + self.probability_flat + self.probability_down
        if total != Decimal("1"):
            raise ValueError("forecast probabilities must sum exactly to 1")
        for name, value in (
            ("probability_up", self.probability_up),
            ("probability_flat", self.probability_flat),
            ("probability_down", self.probability_down),
            ("confidence", self.confidence),
        ):
            if value < ZERO or value > Decimal("1"):
                raise ValueError(f"{name} must be between 0 and 1")
        if self.expected_high < self.expected_low:
            raise ValueError("expected_high must be >= expected_low")
        if not self.invalidation_condition.strip():
            raise ValueError("invalidation_condition is required")


@dataclass(frozen=True)
class SimulatedPosition:
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    mark_price: Decimal

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        _require_non_negative(self.quantity, "quantity")
        _require_non_negative(self.average_cost, "average_cost")
        _require_non_negative(self.mark_price, "mark_price")

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.mark_price

    @property
    def unrealized_pnl(self) -> Decimal:
        return self.quantity * (self.mark_price - self.average_cost)


@dataclass(frozen=True)
class SimulatedPortfolio:
    cash: Decimal
    positions: Mapping[str, SimulatedPosition] = field(default_factory=dict)
    realized_pnl: Decimal = ZERO
    high_water_mark: Decimal = ZERO
    starting_equity: Decimal = ZERO
    as_of_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        _require_utc(self.as_of_utc, "as_of_utc")
        _require_non_negative(self.cash, "cash")
        _require_non_negative(self.high_water_mark, "high_water_mark")
        _require_non_negative(self.starting_equity, "starting_equity")

    @property
    def market_value(self) -> Decimal:
        return sum((p.market_value for p in self.positions.values()), ZERO)

    @property
    def equity(self) -> Decimal:
        return self.cash + self.market_value

    @property
    def unrealized_pnl(self) -> Decimal:
        return sum((p.unrealized_pnl for p in self.positions.values()), ZERO)

    @property
    def total_pnl(self) -> Decimal:
        return self.realized_pnl + self.unrealized_pnl

    @property
    def drawdown_pct(self) -> Decimal:
        if self.high_water_mark <= ZERO:
            return ZERO
        drawdown = (self.high_water_mark - self.equity) / self.high_water_mark
        return max(ZERO, drawdown)


@dataclass(frozen=True)
class SimulatedFill:
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    timestamp_utc: datetime
    simulated: bool = True

    def __post_init__(self) -> None:
        _require_utc(self.timestamp_utc, "timestamp_utc")
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if self.quantity <= ZERO:
            raise ValueError("quantity must be positive")
        if self.price < ZERO:
            raise ValueError("price must be non-negative")
        if not self.simulated:
            raise ValueError("Simulator fills must always be simulated")


@dataclass(frozen=True)
class ChallengeDefinition:
    challenge_id: str
    challenge_type: ChallengeType
    target: Decimal
    minimum_observations: int = 1

    def __post_init__(self) -> None:
        if not self.challenge_id.strip():
            raise ValueError("challenge_id is required")
        if self.minimum_observations < 1:
            raise ValueError("minimum_observations must be >= 1")


@dataclass(frozen=True)
class ChallengeProgress:
    challenge_id: str
    observations: int
    metric_value: Decimal
    complete: bool


@dataclass(frozen=True)
class SimulationScore:
    return_pct: Decimal
    max_drawdown_pct: Decimal
    benchmark_excess_pct: Decimal
    decision_quality_pct: Decimal
    capital_preserved: bool
