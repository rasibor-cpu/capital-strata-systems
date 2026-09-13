from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    title: str
    description: str
    initial_cash: Decimal
    price_path: tuple[Decimal, ...]
    benchmark_path: tuple[Decimal, ...]
    learning_objective: str

    def __post_init__(self) -> None:
        if not self.scenario_id.strip() or not self.title.strip():
            raise ValueError("scenario_id and title are required")
        if self.initial_cash <= Decimal("0"):
            raise ValueError("initial_cash must be positive")
        if len(self.price_path) < 2 or len(self.price_path) != len(self.benchmark_path):
            raise ValueError("scenario paths must have equal length >= 2")
        if any(value <= Decimal("0") for value in self.price_path + self.benchmark_path):
            raise ValueError("scenario prices must be positive")


def default_scenario_catalog() -> tuple[Scenario, ...]:
    return (
        Scenario(
            "steady-uptrend",
            "Steady Uptrend",
            "Practice entries, position sizing, and disciplined exits in a rising market.",
            Decimal("10000"),
            (Decimal("100"), Decimal("103"), Decimal("106"), Decimal("110")),
            (Decimal("100"), Decimal("102"), Decimal("104"), Decimal("107")),
            "Avoid chasing while participating in a constructive trend.",
        ),
        Scenario(
            "drawdown-recovery",
            "Drawdown and Recovery",
            "Experience a material drawdown followed by partial recovery.",
            Decimal("10000"),
            (Decimal("100"), Decimal("88"), Decimal("82"), Decimal("94"), Decimal("102")),
            (Decimal("100"), Decimal("96"), Decimal("91"), Decimal("97"), Decimal("101")),
            "Preserve capital and avoid emotionally driven concentration.",
        ),
        Scenario(
            "range-false-breakout",
            "Range and False Breakout",
            "Practice invalidation discipline when a breakout quickly reverses.",
            Decimal("10000"),
            (Decimal("100"), Decimal("102"), Decimal("108"), Decimal("99"), Decimal("101")),
            (Decimal("100"), Decimal("101"), Decimal("102"), Decimal("101"), Decimal("102")),
            "Use explicit invalidation conditions rather than certainty.",
        ),
    )


def get_scenario(scenario_id: str) -> Scenario:
    for scenario in default_scenario_catalog():
        if scenario.scenario_id == scenario_id:
            return scenario
    raise KeyError(scenario_id)
