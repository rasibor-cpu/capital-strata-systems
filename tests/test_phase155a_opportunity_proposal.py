from __future__ import annotations

from copy import deepcopy

from backend.allocation.opportunity_validator import validate_opportunity_proposal


def _valid_payload() -> dict:
    return {
        "proposal_id": "caie-001",
        "symbol": "btc-usd",
        "asset_class": "crypto",
        "probability": 0.72,
        "confidence": 0.81,
        "expected_drawdown_pct": 0.12,
        "risk_score": 42.5,
        "requested_capital": 2500.0,
    }


def test_phase155a_valid_opportunity_proposal_passes() -> None:
    result = validate_opportunity_proposal(_valid_payload())

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["normalized"] == {
        "proposal_id": "caie-001",
        "symbol": "BTC-USD",
        "asset_class": "CRYPTO",
        "probability": 0.72,
        "confidence": 0.81,
        "expected_drawdown_pct": 0.12,
        "risk_score": 42.5,
        "requested_capital": 2500.0,
    }


def test_phase155a_missing_required_field_fails_closed() -> None:
    payload = _valid_payload()
    del payload["symbol"]

    result = validate_opportunity_proposal(payload)

    assert result["valid"] is False
    assert result["normalized"] is None
    assert result["errors"] == [
        {
            "field": "symbol",
            "code": "MISSING_REQUIRED_FIELD",
            "reason": "missing_required_field:symbol",
        }
    ]


def test_phase155a_invalid_probability_confidence_drawdown_and_risk_fail() -> None:
    payload = _valid_payload()
    payload["probability"] = 1.4
    payload["confidence"] = -0.2
    payload["expected_drawdown_pct"] = 1.5
    payload["risk_score"] = 150

    result = validate_opportunity_proposal(payload)

    assert result["valid"] is False
    assert result["normalized"] is None
    assert result["errors"] == [
        {
            "field": "probability",
            "code": "OUT_OF_RANGE",
            "reason": "probability_must_be_between_0_and_1",
        },
        {
            "field": "confidence",
            "code": "OUT_OF_RANGE",
            "reason": "confidence_must_be_between_0_and_1",
        },
        {
            "field": "expected_drawdown_pct",
            "code": "OUT_OF_RANGE",
            "reason": "expected_drawdown_pct_must_be_between_0_and_1",
        },
        {
            "field": "risk_score",
            "code": "OUT_OF_RANGE",
            "reason": "risk_score_must_be_between_0_and_100",
        },
    ]


def test_phase155a_negative_requested_capital_fails() -> None:
    payload = _valid_payload()
    payload["requested_capital"] = -1.0

    result = validate_opportunity_proposal(payload)

    assert result["valid"] is False
    assert result["normalized"] is None
    assert result["errors"] == [
        {
            "field": "requested_capital",
            "code": "NON_POSITIVE_CAPITAL",
            "reason": "requested_capital_must_be_positive",
        }
    ]


def test_phase155a_malformed_asset_class_fails() -> None:
    payload = _valid_payload()
    payload["asset_class"] = "crypto/fx"

    result = validate_opportunity_proposal(payload)

    assert result["valid"] is False
    assert result["normalized"] is None
    assert result["errors"] == [
        {
            "field": "asset_class",
            "code": "INVALID_ASSET_CLASS",
            "reason": "invalid_asset_class",
        }
    ]


def test_phase155a_error_reasons_are_deterministic() -> None:
    payload = _valid_payload()
    payload.update(
        {
            "asset_class": "invalid",
            "probability": 2.0,
            "confidence": 2.0,
            "expected_drawdown_pct": -1.0,
            "risk_score": -1.0,
            "requested_capital": 0.0,
        }
    )

    first = validate_opportunity_proposal(payload)
    second = validate_opportunity_proposal(deepcopy(payload))

    assert first == second
