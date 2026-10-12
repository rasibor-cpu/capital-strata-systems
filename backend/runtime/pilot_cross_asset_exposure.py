"""Non-executing, fail-closed CAD exposure assessment for pilot instruments.

No broker calls or orders. Never use premium or margin as a substitute for
underlying notional; require an independently supplied worst-case loss.
An approved assessment is *not* authorization to trade.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any

from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG

_CENT = Decimal("0.01")
_CLASSES = frozenset({"CRYPTO", "FX", "FUTURES", "OPTIONS"})


def _positive(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean numeric input")
    try:
        n = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError("invalid numeric input") from exc
    if not n.is_finite() or n <= 0:
        raise ValueError("non-positive numeric input")
    return n


def _nonnegative(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean numeric input")
    try:
        n = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError("invalid numeric input") from exc
    if not n.is_finite() or n < 0:
        raise ValueError("negative numeric input")
    return n


@dataclass(frozen=True)
class CrossAssetExposureDecision:
    eligible_for_further_review: bool
    reason: str
    exposure_cad: Decimal
    cash_commitment_cad: Decimal
    maximum_loss_cad: Decimal


def assess_cross_asset_exposure(
    *,
    asset_class: str,
    quantity: Any,
    unit_price_quote: Any,
    contract_multiplier: Any,
    quote_to_cad: Any,
    cash_commitment_quote: Any,
    maximum_loss_quote: Any,
    estimated_fees_quote: Any,
    quote_fresh: bool,
    risk_bounded: bool,
    no_leverage: bool,
) -> CrossAssetExposureDecision:
    """Conservatively screen one *parent* exposure without broker execution.

    All quote-currency quantities and conversion rates must originate from a
    separately validated fresh trusted source. This component cannot establish
    quote provenance. Exposure is gross abs(notional), and also requires
    bounded maximum loss and cash commitment each to fit the CAD 20 ceiling.
    This deliberately excludes many real futures/options until a governed,
    reviewed risk model can prove their eligibility.
    """
    denied = CrossAssetExposureDecision(False, "CROSS_ASSET_INPUT_UNVERIFIED", Decimal("0"), Decimal("0"), Decimal("0"))
    try:
        if type(asset_class) is not str or asset_class not in _CLASSES:
            return denied
        if quote_fresh is not True or risk_bounded is not True or no_leverage is not True:
            return CrossAssetExposureDecision(False, "CROSS_ASSET_RISK_NOT_CERTIFIED", Decimal("0"), Decimal("0"), Decimal("0"))
        qty = _positive(quantity)
        price = _positive(unit_price_quote)
        multiplier = _positive(contract_multiplier)
        fx = _positive(quote_to_cad)
        cash = _nonnegative(cash_commitment_quote)
        worst = _nonnegative(maximum_loss_quote)
        fees = _nonnegative(estimated_fees_quote)
        up = lambda v: v.quantize(_CENT, rounding=ROUND_CEILING)
        gross_cad = up(qty * price * multiplier * fx + fees * fx)
        cash_cad = up((cash + fees) * fx)
        loss_cad = up((worst + fees) * fx)
        limit = DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_position_cad
        if max(gross_cad, cash_cad, loss_cad) > limit:
            return CrossAssetExposureDecision(False, "CROSS_ASSET_CAD20_LIMIT", gross_cad, cash_cad, loss_cad)
        return CrossAssetExposureDecision(True, "CROSS_ASSET_REVIEW_ONLY", gross_cad, cash_cad, loss_cad)
    except (ArithmeticError, ValueError, TypeError):
        return denied
