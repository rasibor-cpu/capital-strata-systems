from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.allocation import OpportunityProposal, validate_opportunity_proposal


NOW = datetime(2026, 9, 14, 22, 30, tzinfo=timezone.utc)


def valid_payload():
    return {
        "proposal_id": "opp-001",
        "source": "shadow-test",
        "broker": "PAPER",
        "symbol": "AAPL",
        "asset_class": "EQUITY",
        "side": "BUY",
        "probability_win": Decimal("0.62"),
        "confidence": Decimal("0.74"),
        "capital_required": Decimal("1000"),
        "max_drawdown_pct": Decimal("0.08"),
        "expected_return_pct": Decimal("0.03"),
        "liquidity_score": Decimal("0.95"),
        "regime_alignment": Decimal("0.80"),
        "observed_at_utc": NOW,
    }


def test_valid_proposal_passes_and_normalizes():
    result = validate_opportunity_proposal(valid_payload())
    assert result.valid is True
    assert result.errors == ()
    assert isinstance(result.proposal, OpportunityProposal)
    assert result.proposal.symbol == "AAPL"
    assert result.proposal.asset_class == "EQUITY"
    assert result.proposal.side == "BUY"


@pytest.mark.parametrize(
    "field",
    [
        "proposal_id",
        "source",
        "broker",
        "symbol",
        "asset_class",
        "side",
        "probability_win",
        "confidence",
        "capital_required",
        "max_drawdown_pct",
        "expected_return_pct",
        "liquidity_score",
        "regime_alignment",
        "observed_at_utc",
    ],
)
def test_missing_required_fields_fail_closed(field):
    payload = valid_payload()
    payload.pop(field)
    result = validate_opportunity_proposal(payload)
    assert result.valid is False
    assert result.proposal is None
    assert f"{field}:MISSING" in result.errors


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("probability_win", Decimal("-0.01")),
        ("probability_win", Decimal("1.01")),
        ("confidence", Decimal("-0.01")),
        ("confidence", Decimal("1.01")),
        ("liquidity_score", Decimal("-0.01")),
        ("liquidity_score", Decimal("1.01")),
        ("regime_alignment", Decimal("-0.01")),
        ("regime_alignment", Decimal("1.01")),
    ],
)
def test_probability_confidence_and_scores_out_of_range_fail(field, value):
    payload = valid_payload()
    payload[field] = value
    result = validate_opportunity_proposal(payload)
    assert result.valid is False
    assert f"{field}:OUT_OF_RANGE" in result.errors


def test_negative_capital_fails_closed():
    payload = valid_payload()
    payload["capital_required"] = Decimal("-1")
    result = validate_opportunity_proposal(payload)
    assert result.valid is False
    assert "capital_required:NON_POSITIVE" in result.errors


@pytest.mark.parametrize("value", [Decimal("-0.01"), Decimal("1.01")])
def test_invalid_drawdown_fails_closed(value):
    payload = valid_payload()
    payload["max_drawdown_pct"] = value
    result = validate_opportunity_proposal(payload)
    assert result.valid is False
    assert "max_drawdown_pct:OUT_OF_RANGE" in result.errors


@pytest.mark.parametrize("asset_class", ["STOCKS", "UNKNOWN", "", "equity/options"])
def test_malformed_or_unsupported_asset_class_fails(asset_class):
    payload = valid_payload()
    payload["asset_class"] = asset_class
    result = validate_opportunity_proposal(payload)
    assert result.valid is False


def test_naive_timestamp_fails_closed():
    payload = valid_payload()
    payload["observed_at_utc"] = datetime(2026, 9, 14, 22, 30)
    result = validate_opportunity_proposal(payload)
    assert result.valid is False
    assert "observed_at_utc:NAIVE_DATETIME" in result.errors


def test_nonfinite_decimal_fails_closed():
    payload = valid_payload()
    payload["confidence"] = Decimal("NaN")
    result = validate_opportunity_proposal(payload)
    assert result.valid is False
    assert "confidence:NON_FINITE" in result.errors


def test_existing_dataclass_can_be_revalidated():
    payload = valid_payload()
    proposal = OpportunityProposal(**payload)
    result = validate_opportunity_proposal(proposal)
    assert result.valid is True


def test_phase155a_has_no_execution_surface():
    prohibited = {
        "place_order",
        "submit_order",
        "cancel_order",
        "replace_order",
        "withdraw",
        "transfer",
        "deposit",
        "fund_account",
        "move_money",
    }
    assert prohibited.isdisjoint(set(dir(OpportunityProposal)))
