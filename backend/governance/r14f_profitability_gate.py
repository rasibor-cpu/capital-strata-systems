"""R14F pre-position profitability gate, callable outside the dashboard runtime.

Identical thresholds and arithmetic to `_legacy_css_profitability_threshold` and
`_legacy_css_profitability_allows` in scripts/css_live_dashboard.py, which read the
dashboard's global ENGINE_MODE and cannot be imported without starting that runtime.
Here the legacy engine mode is an explicit argument. tests/test_r14f_gate_parity.py
executes the dashboard's own functions and requires identical results, so any change
to the thresholds must be made (and reviewed) in both places.
"""
from __future__ import annotations

from dataclasses import dataclass

R14F_MODE_THRESHOLDS = {
    "SAFE": 17.5,
    "CONSERVATIVE": 16.5,
    "BALANCED": 15.8,
    "AGGRESSIVE": 15.0,
    "EXPANSION": 14.2,
}
R14F_DEFAULT_THRESHOLD = 15.8
PROBABILITY_WEIGHT = 5.0


@dataclass(frozen=True)
class R14FDecision:
    allowed: bool
    composite: float
    threshold: float
    engine_mode: str


def r14f_threshold(engine_mode: str, asset_class: str) -> float:
    threshold = R14F_MODE_THRESHOLDS.get(str(engine_mode).upper(), R14F_DEFAULT_THRESHOLD)
    asset_key = str(asset_class or "").upper()
    if asset_key == "CRYPTO":
        threshold -= 0.30
    elif asset_key == "FX":
        threshold -= 0.90
    return threshold


def evaluate_r14f(*, engine_mode: str, asset_class: str, signal_score: float, probability: float) -> R14FDecision:
    composite = float(signal_score or 0.0) + (float(probability or 0.0) * PROBABILITY_WEIGHT)
    threshold = r14f_threshold(engine_mode, asset_class)
    return R14FDecision(composite >= threshold, composite, threshold, str(engine_mode).upper())
