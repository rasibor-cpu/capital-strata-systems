"""Paper-only starting-capital presets and illustrative scaling for CSS.

This module never places orders or modifies trading gates.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

DEFAULT_USER_CAPITAL_CAD = Decimal("100000")
ENGINEERING_CAPITAL_CAD = Decimal("14600")
REFERENCE_CAPITAL_CAD = Decimal("146")
PRESETS_CAD = (Decimal("10000"), Decimal("25000"), Decimal("100000"), Decimal("250000"))
MIN_CUSTOM_CAD = Decimal("1000")
MAX_CUSTOM_CAD = Decimal("1000000")


def validate_capital(value: object) -> Decimal:
    """Accept finite CAD amounts within the permitted virtual-capital range."""
    if isinstance(value, bool):
        raise ValueError("invalid_simulated_capital")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid_simulated_capital") from None
    if not amount.is_finite() or amount < MIN_CUSTOM_CAD or amount > MAX_CUSTOM_CAD:
        raise ValueError("simulated_capital_out_of_range")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("simulated_capital_requires_cents")
    return amount


def starting_capital(*, profile: str = "standard", custom_cad: object | None = None) -> float:
    """Explicitly select engineering, standard, small, intermediate, advanced or custom."""
    choices = {
        "engineering": ENGINEERING_CAPITAL_CAD,
        "standard": DEFAULT_USER_CAPITAL_CAD,
        "small": PRESETS_CAD[0],
        "intermediate": PRESETS_CAD[1],
        "advanced": PRESETS_CAD[3],
    }
    if profile == "custom":
        if custom_cad is None:
            raise ValueError("custom_capital_required")
        return float(validate_capital(custom_cad))
    if custom_cad is not None or profile not in choices:
        raise ValueError("invalid_simulation_profile")
    return float(choices[profile])


def reference_comparison(net_pnl_cad: object, *, simulation_capital_cad: object,
                         reference_capital_cad: object = REFERENCE_CAPITAL_CAD) -> dict:
    """Illustrative normalized P&L, never an executable-fill or broker prediction."""
    sim = validate_capital(simulation_capital_cad)
    reference = Decimal(str(reference_capital_cad))
    if not reference.is_finite() or reference <= 0:
        raise ValueError("invalid_reference_capital")
    pnl = Decimal(str(net_pnl_cad))
    if not pnl.is_finite():
        raise ValueError("invalid_pnl")
    return {
        "simulation_capital_cad": float(sim),
        "reference_capital_cad": float(reference),
        "scale_ratio": float(sim / reference),
        "illustrative_reference_pnl_cad": float((pnl * reference / sim).quantize(Decimal("0.01"))),
        "executable_at_reference_capital": False,
        "warning": "Illustrative normalization only; minimum orders, fees, spreads, liquidity, FX and rounding do not scale linearly.",
    }
