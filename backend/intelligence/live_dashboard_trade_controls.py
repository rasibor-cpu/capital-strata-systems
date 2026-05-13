"""
Pure trade-control helpers extracted from the legacy live dashboard.

These functions intentionally preserve the current dashboard formulas while
moving the business rules out of the render/control script. They are small,
deterministic helpers and do not perform broker access or dashboard rendering.
"""

from __future__ import annotations

from typing import Any


R15B_EXIT_PROFILE = {
    "SAFE": {"tp": 0.010, "sl": -0.006},
    "CONSERVATIVE": {"tp": 0.012, "sl": -0.008},
    "BALANCED": {"tp": 0.015, "sl": -0.010},
    "AGGRESSIVE": {"tp": 0.020, "sl": -0.012},
    "EXPANSION": {"tp": 0.025, "sl": -0.015},
}

PROFITABILITY_THRESHOLDS = {
    "SAFE": 17.5,
    "CONSERVATIVE": 16.5,
    "BALANCED": 15.8,
    "AGGRESSIVE": 15.0,
    "EXPANSION": 14.2,
}

DEFAULT_OPTION_STRIKES = {
    "AAPL": "175",
    "SPY": "500",
    "QQQ": "400",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def mode_exit_profile(engine_mode: str) -> dict[str, float]:
    return dict(
        R15B_EXIT_PROFILE.get(
            str(engine_mode or "").upper(),
            R15B_EXIT_PROFILE["BALANCED"],
        )
    )


def evaluate_exit_signal(position: dict[str, Any]) -> str:
    entry = _safe_float(position.get("entry_price"), 0.0)
    current = _safe_float(position.get("current_price"), entry)

    if entry == 0:
        return "HOLD"

    pnl_pct = (current - entry) / entry

    if pnl_pct >= 0.015:
        return "TAKE_PROFIT"

    if pnl_pct <= -0.010:
        return "STOP_LOSS"

    if pnl_pct >= 0.010:
        return "RUNNER"

    return "HOLD"


def profitability_threshold(engine_mode: str) -> float:
    return PROFITABILITY_THRESHOLDS.get(str(engine_mode or "").upper(), 15.8)


def profitability_composite(signal_score: float, probability: float) -> float:
    return _safe_float(signal_score) + (_safe_float(probability) * 5.0)


def profitability_allows(
    *,
    engine_mode: str,
    signal_score: float,
    probability: float,
) -> tuple[bool, float, float]:
    score = _safe_float(signal_score)
    prob = _safe_float(probability)
    threshold = profitability_threshold(engine_mode)
    composite = profitability_composite(score, prob)
    return composite >= threshold, composite, threshold


def format_option_symbol(symbol: str) -> str:
    symbol_text = str(symbol or "")
    if "-" not in symbol_text:
        return symbol_text

    parts = symbol_text.split("-")

    if len(parts) == 3:
        return symbol_text

    if len(parts) == 2:
        underlying, opt_type = parts
        default_strike = DEFAULT_OPTION_STRIKES.get(underlying, "100")
        return f"{underlying}-{opt_type}-{default_strike}"

    return symbol_text
