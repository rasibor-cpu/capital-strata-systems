from decimal import Decimal
import pytest
from backend.runtime.pilot_cross_asset_exposure import assess_cross_asset_exposure


def assess(**kw):
    values = dict(
        asset_class="CRYPTO", quantity="1", unit_price_quote="10",
        contract_multiplier="1", quote_to_cad="1",
        cash_commitment_quote="10", maximum_loss_quote="10",
        estimated_fees_quote="0.10", quote_fresh=True,
        risk_bounded=True, no_leverage=True,
    )
    values.update(kw)
    return assess_cross_asset_exposure(**values)


@pytest.mark.parametrize("asset", ["CRYPTO", "FX", "FUTURES", "OPTIONS"])
def test_small_bounded_nonleveraged_instrument_is_review_only(asset):
    result = assess(asset_class=asset)
    assert result.eligible_for_further_review
    assert result.reason == "CROSS_ASSET_REVIEW_ONLY"
    assert result.exposure_cad == Decimal("10.10")


@pytest.mark.parametrize("kw", [
    {"asset_class": "EQUITIES"},
    {"quantity": "-1"},
    {"unit_price_quote": "NaN"},
    {"quote_to_cad": "0"},
    {"contract_multiplier": "100"},
    {"quote_fresh": False},
    {"risk_bounded": False},
    {"no_leverage": False},
    {"maximum_loss_quote": "Infinity"},
    {"estimated_fees_quote": True},
    {"maximum_loss_quote": "21"},
    {"cash_commitment_quote": "21"},
])
def test_unknown_unsafe_or_oversized_fails_closed(kw):
    assert not assess(**kw).eligible_for_further_review


def test_contract_multiplier_and_fx_conversion():
    assert not assess(
        asset_class="OPTIONS", unit_price_quote="0.30",
        contract_multiplier="100", quote_to_cad="1.2"
    ).eligible_for_further_review


def test_round_up_fees_never_understates_cap():
    result = assess(quantity="1", unit_price_quote="19.995",
                    cash_commitment_quote="19.995", maximum_loss_quote="19.995",
                    estimated_fees_quote="0.005")
    assert result.exposure_cad == Decimal("20.00")
    assert result.eligible_for_further_review
