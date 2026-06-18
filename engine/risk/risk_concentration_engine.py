"""
Capital Strata Systems
Phase 94

Risk Concentration Engine
"""

from dataclasses import dataclass
from typing import Dict, Iterable


@dataclass(frozen=True)
class ConcentrationExposure:
    symbol: str
    asset_class: str
    exposure_value: float


@dataclass(frozen=True)
class ConcentrationResult:
    total_exposure: float
    by_asset_class: Dict[str, float]
    by_symbol: Dict[str, float]
    largest_asset_class: str
    largest_asset_class_pct: float
    largest_symbol: str
    largest_symbol_pct: float


class RiskConcentrationEngine:
    """
    Computes portfolio concentration by asset class and symbol.

    No broker calls.
    No execution.
    No portfolio mutation.
    """

    def analyze(
        self,
        exposures: Iterable[ConcentrationExposure],
    ) -> ConcentrationResult:
        exposure_list = list(exposures)

        by_asset_class: Dict[str, float] = {}
        by_symbol: Dict[str, float] = {}

        for exposure in exposure_list:
            value = abs(float(exposure.exposure_value or 0.0))
            asset_class = str(exposure.asset_class or "UNKNOWN").upper()
            symbol = str(exposure.symbol or "UNKNOWN").upper()

            by_asset_class[asset_class] = by_asset_class.get(asset_class, 0.0) + value
            by_symbol[symbol] = by_symbol.get(symbol, 0.0) + value

        total_exposure = sum(by_asset_class.values())

        if total_exposure <= 0:
            return ConcentrationResult(
                total_exposure=0.0,
                by_asset_class={},
                by_symbol={},
                largest_asset_class="NONE",
                largest_asset_class_pct=0.0,
                largest_symbol="NONE",
                largest_symbol_pct=0.0,
            )

        largest_asset_class = max(by_asset_class, key=by_asset_class.get)
        largest_symbol = max(by_symbol, key=by_symbol.get)

        return ConcentrationResult(
            total_exposure=round(total_exposure, 2),
            by_asset_class={k: round(v, 2) for k, v in by_asset_class.items()},
            by_symbol={k: round(v, 2) for k, v in by_symbol.items()},
            largest_asset_class=largest_asset_class,
            largest_asset_class_pct=round((by_asset_class[largest_asset_class] / total_exposure) * 100.0, 2),
            largest_symbol=largest_symbol,
            largest_symbol_pct=round((by_symbol[largest_symbol] / total_exposure) * 100.0, 2),
        )