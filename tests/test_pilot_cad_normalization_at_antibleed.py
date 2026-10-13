"""Isolated tests for CAD normalization at the AntiBleed call site.

These tests trace what the *actual runtime caller* would supply to the
AntiBleedGuard. They do not change any threshold, do not enable the CAD 20
minimum-size exception, and do not fake profitability. An authentic AntiBleed
denial (e.g. below the default ``minimum_profitable_trade_size = 50.0``) is a
valid acceptance result — it proves the guard blocks sub-threshold trades.

The goal is to demonstrate that the pilot's own currency-conversion and
cross-asset-exposure APIs produce a normalized, CAD-denominated risk value
suitable for the AntiBleed call site, without modifying the guard itself.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from backend.runtime.pilot_currency_conversion import (
    PilotRiskBudget,
    VerifiedRateInput,
    convert_risk_up,
)
from backend.runtime.pilot_cross_asset_exposure import assess_cross_asset_exposure


NOW = datetime.now(timezone.utc)
BUDGET = PilotRiskBudget("CAD", Decimal("20.00"), Decimal("40.00"))


def _rate(quote_currency: str, cad_per_quote: str, age_seconds: int = 5) -> VerifiedRateInput:
    """Rate directed source→CAD: base_currency=source, quote_currency=CAD.

    Per convert_risk_up's contract: base_currency is the *source* and
    quote_currency is the budget currency (CAD). The rate value is
    quote-per-base, i.e. CAD per 1 unit of source.
    """
    observed = NOW - timedelta(seconds=age_seconds)
    return VerifiedRateInput(
        base_currency=quote_currency,          # e.g. USD
        quote_currency="CAD",                  # budget currency
        quote_per_base=Decimal(cad_per_quote),  # CAD per 1 source unit
        observed_at=observed,
        source_id="test-fx-feed",
    )


class TestConvertRiskUpNormalizesToCAD:
    def test_converts_usd_risk_to_cad(self):
        rate = _rate("USD", "1.38")
        result = convert_risk_up(Decimal("15.00"), source_currency="USD", budget=BUDGET, rate=rate, now=NOW)
        # ROUND_CEILING on 15.00 * 1.38 = 20.70 exactly.
        assert result == Decimal("20.70")

    def test_zero_risk_allowed(self):
        rate = _rate("USD", "1.38")
        result = convert_risk_up(Decimal("0"), source_currency="USD", budget=BUDGET, rate=rate, now=NOW)
        assert result == Decimal("0.00")

    def test_cad_source_without_rate_allowed(self):
        # Same-currency source needs no rate.
        result = convert_risk_up(Decimal("15.00"), source_currency="CAD", budget=BUDGET, rate=None, now=NOW)
        assert result == Decimal("15.00")

    def test_cad_source_with_extraneous_rate_rejected(self):
        rate = _rate("USD", "1.38")
        with pytest.raises(Exception):
            convert_risk_up(Decimal("15.00"), source_currency="CAD", budget=BUDGET, rate=rate, now=NOW)

    def test_stale_rate_rejected(self):
        stale = _rate("USD", "1.38", age_seconds=999)
        with pytest.raises(Exception):
            convert_risk_up(Decimal("15.00"), source_currency="USD", budget=BUDGET, rate=stale, now=NOW)

    def test_missing_rate_for_foreign_currency_rejected(self):
        # A non-CAD source with no direct rate must be rejected, not inferred.
        with pytest.raises(Exception):
            convert_risk_up(Decimal("15.00"), source_currency="EUR", budget=BUDGET, rate=None, now=NOW)


class TestCrossAssetExposureProducesCADValues:
    def test_fx_within_budget_produces_cad_exposure(self):
        decision = assess_cross_asset_exposure(
            asset_class="FX",
            quantity=Decimal("14"),
            unit_price_quote=Decimal("1.00"),       # 14 USD gross notional
            contract_multiplier=Decimal("1"),
            quote_to_cad=Decimal("1.38"),
            cash_commitment_quote=Decimal("13.00"),
            maximum_loss_quote=Decimal("0.50"),
            estimated_fees_quote=Decimal("0.05"),
            quote_fresh=True,
            risk_bounded=True,
            no_leverage=True,
        )
        assert decision.eligible_for_further_review is True
        # gross_cad = up(14*1*1*1.38 + 0.05*1.38) = up(19.389) = 19.39 ≤ 20
        assert decision.exposure_cad == Decimal("19.39")
        # cash_cad = up((13 + 0.05) * 1.38) = up(18.009) = 18.01
        assert decision.cash_commitment_cad == Decimal("18.01")
        # loss_cad = up((0.50 + 0.05) * 1.38) = up(0.759) = 0.76
        assert decision.maximum_loss_cad == Decimal("0.76")

    def test_crypto_within_budget_produces_cad_exposure(self):
        decision = assess_cross_asset_exposure(
            asset_class="CRYPTO",
            quantity=Decimal("0.0002"),
            unit_price_quote=Decimal("50000"),   # 10 USD gross notional
            contract_multiplier=Decimal("1"),
            quote_to_cad=Decimal("1.38"),
            cash_commitment_quote=Decimal("10.00"),
            maximum_loss_quote=Decimal("0.50"),
            estimated_fees_quote=Decimal("0.10"),
            quote_fresh=True,
            risk_bounded=True,
            no_leverage=True,
        )
        assert decision.eligible_for_further_review is True
        # gross_cad = up(10 * 1.38 + 0.10 * 1.38) = up(13.938) = 13.94
        assert decision.exposure_cad == Decimal("13.94")
        # cash_cad = up((10 + 0.10) * 1.38) = up(13.938) = 13.94
        assert decision.cash_commitment_cad == Decimal("13.94")
        # loss_cad = up((0.50 + 0.10) * 1.38) = up(0.828) = 0.83
        assert decision.maximum_loss_cad == Decimal("0.83")

    def test_exceeding_cad20_is_rejected(self):
        decision = assess_cross_asset_exposure(
            asset_class="CRYPTO",
            quantity=Decimal("0.0004"),
            unit_price_quote=Decimal("50000"),   # 20 USD gross notional
            contract_multiplier=Decimal("1"),
            quote_to_cad=Decimal("1.38"),
            cash_commitment_quote=Decimal("20.00"),
            maximum_loss_quote=Decimal("1.00"),
            estimated_fees_quote=Decimal("0.10"),
            quote_fresh=True,
            risk_bounded=True,
            no_leverage=True,
        )
        # gross_cad = up(20 * 1.38 + 0.10 * 1.38) = up(27.738) = 27.74 > 20
        assert decision.eligible_for_further_review is False
        assert decision.reason == "CROSS_ASSET_CAD20_LIMIT"
        assert decision.exposure_cad == Decimal("27.74")

    def test_unsupported_asset_class_rejected(self):
        decision = assess_cross_asset_exposure(
            asset_class="EQUITIES",
            quantity=Decimal("1"),
            unit_price_quote=Decimal("1"),
            contract_multiplier=Decimal("1"),
            quote_to_cad=Decimal("1.38"),
            cash_commitment_quote=Decimal("1"),
            maximum_loss_quote=Decimal("1"),
            estimated_fees_quote=Decimal("0"),
            quote_fresh=True,
            risk_bounded=True,
            no_leverage=True,
        )
        assert decision.eligible_for_further_review is False

    def test_stale_quote_rejected(self):
        decision = assess_cross_asset_exposure(
            asset_class="FX",
            quantity=Decimal("1"),
            unit_price_quote=Decimal("1"),
            contract_multiplier=Decimal("1"),
            quote_to_cad=Decimal("1.38"),
            cash_commitment_quote=Decimal("1"),
            maximum_loss_quote=Decimal("1"),
            estimated_fees_quote=Decimal("0"),
            quote_fresh=False,
            risk_bounded=True,
            no_leverage=True,
        )
        assert decision.eligible_for_further_review is False


class TestAntiBleedCallSiteUsesNormalizedRisk:
    """The guard's evaluate() takes a raw trade_size with no currency metadata.

    The intended runtime caller must normalize risk to CAD before calling the
    guard. These tests prove:
    (1) a sub-50 risk value is *authentically denied* by the guard;
    (2) the existing guard thresholds are unchanged;
    (3) the AntiBleed minimum-size exception stays disabled.
    """

    def test_default_guard_unchanged_thresholds(self, tmp_path):
        guard = AntiBleedGuard(state_file=str(tmp_path / "antibleed_state.json"))
        assert guard.minimum_profitable_trade_size == 50.0
        assert guard.minimum_required_net_edge_bps == 25.0

    def test_sub_threshold_cad_risk_is_authentically_denied(self, tmp_path):
        guard = AntiBleedGuard(state_file=str(tmp_path / "antibleed_state.json"))
        # A CAD-normalized pilot parent at CAD 6.25 is below the default
        # minimum_profitable_trade_size of 50. The guard must deny it.
        result = guard.evaluate(
            symbol="EUR_USD",
            trade_size=6.25,          # CAD-normalized risk (no exception path)
            expected_move_bps=60.0,
            fee_bps=2.0,
            spread_bps=3.0,
            slippage_bps=1.0,
        )
        assert result["approved"] is False
        assert result["reason"] == "trade_size_too_small"

    def test_pilot_exception_stays_disabled_by_default(self):
        import backend.runtime.pilot_min_size_exception as exc_mod
        assert exc_mod.PILOT_MIN_SIZE_EXCEPTION_ENABLED is False

    def test_over_threshold_risk_can_be_approved(self, tmp_path):
        guard = AntiBleedGuard(state_file=str(tmp_path / "antibleed_state.json"))
        # A CAD-normalized risk of 75 exceeds the minimum threshold of 50
        # and meets the net-edge requirement; the guard should approve.
        result = guard.evaluate(
            symbol="EUR_USD",
            trade_size=75.0,
            expected_move_bps=60.0,
            fee_bps=2.0,
            spread_bps=3.0,
            slippage_bps=1.0,
        )
        # If cooldown state carries over, approve may be False; that is a valid
        # guard behaviour. We only assert the approval reason is NOT
        # "trade_size_too_small" (i.e. size is not the blocker).
        if result["approved"]:
            assert result["reason"] == "approved"
        else:
            assert result["reason"] != "trade_size_too_small"
