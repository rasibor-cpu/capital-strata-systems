from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.governance.enterprise_profit_protection_contracts import (
    EnterpriseProfitProtectionPolicy,
    PPFEnforcementStatus,
    PPFMaturityTier,
    PPFReasonCode,
    PPFRiskRequest,
)
from backend.governance.enterprise_profit_protection_manager import (
    EnterpriseProfitProtectionManager,
)


NOW = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


def _request(**overrides) -> PPFRiskRequest:
    payload = {
        "request_id": "ppf-001-test",
        "maturity_tier": PPFMaturityTier.STARTUP,
        "banked_net_profit": Decimal("100.00"),
        "principal_capital": Decimal("100000.00"),
        "current_drawdown_pct": Decimal("0"),
        "previous_drawdown_pct": Decimal("0"),
        "recent_loss_amount": Decimal("0"),
        "volatility_score": Decimal("0"),
        "liquidity_score": Decimal("1"),
        "confidence_score": Decimal("1"),
        "correlation_score": Decimal("0"),
        "margin_utilization": Decimal("0"),
        "observed_at": NOW.isoformat(),
    }
    payload.update(overrides)
    return PPFRiskRequest(**payload)


def _decision(**overrides):
    return EnterpriseProfitProtectionManager().evaluate(_request(**overrides), now=NOW)


@pytest.mark.parametrize(
    ("tier", "expected_ceiling", "expected_budget"),
    (
        (PPFMaturityTier.STARTUP, Decimal("0.80"), Decimal("80.00")),
        (PPFMaturityTier.GROWTH, Decimal("0.60"), Decimal("60.00")),
        (PPFMaturityTier.ESTABLISHED, Decimal("0.40"), Decimal("40.00")),
        (PPFMaturityTier.INSTITUTIONAL, Decimal("0.25"), Decimal("25.00")),
    ),
)
def test_ppf001_maturity_tier_ceilings(tier, expected_ceiling, expected_budget) -> None:
    decision = _decision(maturity_tier=tier)

    assert decision.effective_ceiling == expected_ceiling
    assert decision.base_budget == expected_budget
    assert decision.adjusted_budget == expected_budget
    assert decision.execution_allowed is False
    assert decision.advisory_only is True


@pytest.mark.parametrize("profit", (Decimal("0"), Decimal("-1.00")))
def test_ppf001_zero_or_negative_profit_produces_zero_budget(profit) -> None:
    decision = _decision(banked_net_profit=profit)

    assert decision.enforcement_status == PPFEnforcementStatus.ADVISORY_BLOCKED
    assert decision.base_budget == Decimal("0.00")
    assert decision.adjusted_budget == Decimal("0.00")
    assert PPFReasonCode.ZERO_OR_NEGATIVE_BANKED_PROFIT in decision.reason_codes


def test_ppf001_principal_is_excluded_from_default_risk_budget() -> None:
    with_principal = _decision(principal_capital=Decimal("1000000.00"))
    without_large_principal = _decision(principal_capital=Decimal("1.00"))

    assert with_principal.base_budget == Decimal("80.00")
    assert with_principal.adjusted_budget == without_large_principal.adjusted_budget
    assert PPFReasonCode.PRINCIPAL_EXCLUDED in with_principal.reason_codes


def test_ppf001_adaptive_multipliers_are_bounded_zero_to_one() -> None:
    decision = _decision(
        current_drawdown_pct=Decimal("1"),
        previous_drawdown_pct=Decimal("0"),
        recent_loss_amount=Decimal("1"),
        volatility_score=Decimal("1"),
        liquidity_score=Decimal("0"),
        confidence_score=Decimal("0"),
        correlation_score=Decimal("1"),
        margin_utilization=Decimal("1"),
    )

    assert all(Decimal("0") <= value <= Decimal("1") for value in decision.multipliers.values())
    assert all(value == Decimal("0.000000") for value in decision.multipliers.values())
    assert decision.adjusted_budget == Decimal("0.00")


@pytest.mark.parametrize("bad_value", ("NaN", "Infinity", "-Infinity"))
def test_ppf001_nan_and_infinite_inputs_fail_closed(bad_value) -> None:
    decision = _decision(confidence_score=bad_value)

    assert decision.enforcement_status == PPFEnforcementStatus.FAIL_CLOSED
    assert decision.adjusted_budget == Decimal("0.00")
    assert PPFReasonCode.INPUT_NOT_FINITE in decision.reason_codes


def test_ppf001_stale_inputs_fail_closed() -> None:
    decision = _decision(observed_at=(NOW - timedelta(minutes=10)).isoformat())

    assert decision.enforcement_status == PPFEnforcementStatus.FAIL_CLOSED
    assert PPFReasonCode.INPUT_STALE in decision.reason_codes


def test_ppf001_missing_required_inputs_fail_closed() -> None:
    decision = _decision(liquidity_score=None)

    assert decision.enforcement_status == PPFEnforcementStatus.FAIL_CLOSED
    assert PPFReasonCode.MISSING_REQUIRED_DATA in decision.reason_codes


def test_ppf001_negative_non_profit_inputs_fail_closed() -> None:
    decision = _decision(principal_capital=Decimal("-1"))

    assert decision.enforcement_status == PPFEnforcementStatus.FAIL_CLOSED
    assert PPFReasonCode.NEGATIVE_INPUT in decision.reason_codes


def test_ppf001_drawdown_behavior_is_monotonic_and_worsening_reduces_risk() -> None:
    low = _decision(current_drawdown_pct=Decimal("0.10"), previous_drawdown_pct=Decimal("0.10"))
    high = _decision(current_drawdown_pct=Decimal("0.30"), previous_drawdown_pct=Decimal("0.10"))

    assert high.adjusted_budget < low.adjusted_budget
    assert high.multipliers["drawdown_adjustment"] < low.multipliers["drawdown_adjustment"]
    assert PPFReasonCode.WORSENING_DRAWDOWN_REDUCED_RISK in high.reason_codes


def test_ppf001_recent_losses_never_increase_risk() -> None:
    no_loss = _decision(current_drawdown_pct=Decimal("0.10"), previous_drawdown_pct=Decimal("0.10"))
    recent_loss = _decision(
        current_drawdown_pct=Decimal("0.10"),
        previous_drawdown_pct=Decimal("0.10"),
        recent_loss_amount=Decimal("5.00"),
    )

    assert recent_loss.adjusted_budget < no_loss.adjusted_budget
    assert PPFReasonCode.RECENT_LOSS_REDUCED_RISK in recent_loss.reason_codes


def test_ppf001_confidence_behavior_is_monotonic() -> None:
    high_confidence = _decision(confidence_score=Decimal("0.90"))
    low_confidence = _decision(confidence_score=Decimal("0.30"))

    assert low_confidence.adjusted_budget < high_confidence.adjusted_budget
    assert low_confidence.multipliers["confidence_adjustment"] < high_confidence.multipliers["confidence_adjustment"]


def test_ppf001_volatility_behavior_is_monotonic() -> None:
    low_volatility = _decision(volatility_score=Decimal("0.10"))
    high_volatility = _decision(volatility_score=Decimal("0.80"))

    assert high_volatility.adjusted_budget < low_volatility.adjusted_budget
    assert high_volatility.multipliers["volatility_adjustment"] < low_volatility.multipliers["volatility_adjustment"]


def test_ppf001_liquidity_behavior_is_monotonic() -> None:
    high_liquidity = _decision(liquidity_score=Decimal("0.90"))
    low_liquidity = _decision(liquidity_score=Decimal("0.30"))

    assert low_liquidity.adjusted_budget < high_liquidity.adjusted_budget
    assert low_liquidity.multipliers["liquidity_adjustment"] < high_liquidity.multipliers["liquidity_adjustment"]


def test_ppf001_correlation_behavior_is_monotonic() -> None:
    low_correlation = _decision(correlation_score=Decimal("0.10"))
    high_correlation = _decision(correlation_score=Decimal("0.80"))

    assert high_correlation.adjusted_budget < low_correlation.adjusted_budget
    assert high_correlation.multipliers["correlation_adjustment"] < low_correlation.multipliers["correlation_adjustment"]


def test_ppf001_final_budget_never_exceeds_base_ceiling() -> None:
    policy = EnterpriseProfitProtectionPolicy(
        maturity_tier=PPFMaturityTier.STARTUP,
        tier_ceilings={PPFMaturityTier.STARTUP: Decimal("0.99")},
    )
    decision = EnterpriseProfitProtectionManager(policy).evaluate(_request(), now=NOW)

    assert decision.effective_ceiling == Decimal("0.80")
    assert decision.adjusted_budget <= decision.base_budget
    assert decision.base_budget == Decimal("80.00")
    assert PPFReasonCode.CEILING_CLAMPED_TO_CONSTITUTIONAL in decision.reason_codes


def test_ppf001_policy_can_tighten_but_not_increase_constitutional_ceiling() -> None:
    policy = EnterpriseProfitProtectionPolicy(
        maturity_tier=PPFMaturityTier.STARTUP,
        tier_ceilings={PPFMaturityTier.STARTUP: Decimal("0.50")},
    )
    decision = EnterpriseProfitProtectionManager(policy).evaluate(_request(), now=NOW)

    assert decision.effective_ceiling == Decimal("0.50")
    assert decision.base_budget == Decimal("50.00")
    assert PPFReasonCode.CEILING_CLAMPED_TO_CONSTITUTIONAL not in decision.reason_codes


def test_ppf001_decimal_rounding_is_deterministic_and_non_increasing() -> None:
    decision = _decision(banked_net_profit=Decimal("10.999"))

    assert decision.base_budget == Decimal("8.79")
    assert decision.adjusted_budget == Decimal("8.79")
    assert decision.as_dict()["base_budget"] == "8.79"


def test_ppf001_reason_codes_are_machine_readable() -> None:
    decision = _decision(
        current_drawdown_pct=Decimal("0.20"),
        previous_drawdown_pct=Decimal("0.10"),
        recent_loss_amount=Decimal("1.00"),
        confidence_score=Decimal("0.50"),
    )
    payload = decision.as_dict()

    assert all(isinstance(code, str) and code == code.upper() for code in payload["reason_codes"])
    assert "PRINCIPAL_EXCLUDED" in payload["reason_codes"]
    assert "RECENT_LOSS_REDUCED_RISK" in payload["reason_codes"]
    assert "WORSENING_DRAWDOWN_REDUCED_RISK" in payload["reason_codes"]
    assert payload["execution_allowed"] is False
    assert payload["advisory_only"] is True
