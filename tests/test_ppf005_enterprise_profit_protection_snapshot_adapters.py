from __future__ import annotations

from decimal import Decimal

from backend.governance.enterprise_profit_protection_contracts import (
    PPFEnforcementStatus,
    PPFMaturityTier,
    PPFReasonCode,
)
from backend.governance.enterprise_profit_protection_manager import (
    EnterpriseProfitProtectionManager,
)
from backend.governance.enterprise_profit_protection_snapshot_adapters import (
    EnterpriseProfitProtectionSnapshotAdapter,
    PPFSnapshotAdapterReasonCode,
)


OBSERVED_AT = "2026-07-24T13:00:00+00:00"


def _pnl(**overrides):
    payload = {
        "owner_approved_banked_net_profit": Decimal("100.00"),
        "recent_loss_amount": Decimal("0"),
        "observed_at": OBSERVED_AT,
    }
    payload.update(overrides)
    return payload


def _portfolio(**overrides):
    payload = {
        "owner_approved_principal_capital": Decimal("1000000.00"),
        "current_drawdown_pct": Decimal("0.10"),
        "previous_drawdown_pct": Decimal("0.05"),
        "volatility_score": Decimal("0.20"),
        "liquidity_score": Decimal("0.90"),
        "confidence_score": Decimal("0.80"),
        "correlation_score": Decimal("0.30"),
        "margin_utilization": Decimal("0.15"),
        "maximum_credible_loss": Decimal("8.00"),
    }
    payload.update(overrides)
    return payload


def _options(**overrides):
    payload = {
        "volatility_score": Decimal("0.40"),
        "liquidity_score": Decimal("0.70"),
        "confidence_score": Decimal("0.60"),
        "correlation_score": Decimal("0.50"),
        "margin_utilization": Decimal("0.25"),
        "maximum_credible_loss": Decimal("12.00"),
    }
    payload.update(overrides)
    return payload


def _futures(**overrides):
    payload = {
        "volatility_score": Decimal("0.30"),
        "liquidity_score": Decimal("0.75"),
        "confidence_score": Decimal("0.65"),
        "correlation_score": Decimal("0.45"),
        "margin_utilization": Decimal("0.35"),
        "maximum_credible_loss": Decimal("9.00"),
    }
    payload.update(overrides)
    return payload


def _build(**overrides):
    payload = {
        "request_id": "ppf-005-request",
        "maturity_tier": PPFMaturityTier.ESTABLISHED,
        "pnl_snapshot": _pnl(),
        "portfolio_snapshot": _portfolio(),
        "options_snapshot": _options(),
        "futures_snapshot": _futures(),
        "observed_at": OBSERVED_AT,
    }
    payload.update(overrides)
    return EnterpriseProfitProtectionSnapshotAdapter().build_risk_request(**payload)


def test_ppf005_builds_risk_request_from_explicit_snapshots() -> None:
    result = _build()

    assert result.accepted is True
    assert result.reservation_ready is True
    assert result.requested_exposure == Decimal("12.00")
    assert result.execution_allowed is False
    assert result.advisory_only is True
    assert result.risk_request.banked_net_profit == Decimal("100.00")
    assert result.risk_request.principal_capital == Decimal("1000000.00")
    assert result.risk_request.volatility_score == Decimal("0.40")
    assert result.risk_request.liquidity_score == Decimal("0.70")
    assert result.risk_request.confidence_score == Decimal("0.60")
    assert result.risk_request.correlation_score == Decimal("0.50")
    assert result.risk_request.margin_utilization == Decimal("0.35")
    assert PPFSnapshotAdapterReasonCode.OPTIONS_SNAPSHOT_USED in result.reason_codes
    assert PPFSnapshotAdapterReasonCode.FUTURES_SNAPSHOT_USED in result.reason_codes


def test_ppf005_established_tier_preserves_40_percent_banked_profit_ceiling() -> None:
    result = _build()

    decision = EnterpriseProfitProtectionManager().evaluate(
        result.risk_request,
        now=__import__("datetime").datetime.fromisoformat(OBSERVED_AT),
    )

    assert decision.effective_ceiling == Decimal("0.40")
    assert decision.base_budget == Decimal("40.00")
    assert decision.adjusted_budget <= Decimal("40.00")
    assert PPFReasonCode.PRINCIPAL_EXCLUDED in decision.reason_codes


def test_ppf005_does_not_imply_banked_profit_from_realized_pnl_or_equity() -> None:
    result = _build(
        pnl_snapshot={
            "realized_pnl": Decimal("100.00"),
            "unrealized_pnl": Decimal("25.00"),
            "total_equity": Decimal("100125.00"),
            "recent_loss_amount": Decimal("0"),
            "observed_at": OBSERVED_AT,
        }
    )

    assert result.accepted is False
    assert result.risk_request is None
    assert PPFSnapshotAdapterReasonCode.NO_IMPLIED_BANKED_PROFIT in result.reason_codes
    assert PPFSnapshotAdapterReasonCode.FAIL_CLOSED in result.reason_codes


def test_ppf005_does_not_imply_principal_from_equity_or_cash() -> None:
    result = _build(
        portfolio_snapshot={
            "cash": Decimal("1000000.00"),
            "equity": Decimal("1000000.00"),
            "current_drawdown_pct": Decimal("0"),
            "previous_drawdown_pct": Decimal("0"),
            "volatility_score": Decimal("0"),
            "liquidity_score": Decimal("1"),
            "confidence_score": Decimal("1"),
            "correlation_score": Decimal("0"),
            "margin_utilization": Decimal("0"),
        }
    )

    assert result.accepted is False
    assert PPFSnapshotAdapterReasonCode.NO_IMPLIED_PRINCIPAL in result.reason_codes
    assert PPFSnapshotAdapterReasonCode.FAIL_CLOSED in result.reason_codes


def test_ppf005_nonfinite_snapshot_input_fails_closed() -> None:
    result = _build(options_snapshot=_options(volatility_score="NaN"))

    assert result.accepted is False
    assert result.risk_request is None
    assert PPFSnapshotAdapterReasonCode.INPUT_NOT_FINITE in result.reason_codes
    assert PPFSnapshotAdapterReasonCode.FAIL_CLOSED in result.reason_codes


def test_ppf005_out_of_range_score_fails_closed() -> None:
    result = _build(portfolio_snapshot=_portfolio(liquidity_score=Decimal("1.01")))

    assert result.accepted is False
    assert PPFSnapshotAdapterReasonCode.INPUT_OUT_OF_RANGE in result.reason_codes


def test_ppf005_missing_requested_exposure_keeps_evaluation_ready_but_not_reservation_ready() -> None:
    result = _build(
        portfolio_snapshot=_portfolio(maximum_credible_loss=None),
        options_snapshot=_options(maximum_credible_loss=None),
        futures_snapshot=_futures(maximum_credible_loss=None),
    )

    assert result.accepted is True
    assert result.risk_request is not None
    assert result.requested_exposure is None
    assert result.reservation_ready is False
    assert PPFSnapshotAdapterReasonCode.REQUESTED_EXPOSURE_UNAVAILABLE in result.reason_codes


def test_ppf005_negative_principal_fails_closed() -> None:
    result = _build(portfolio_snapshot=_portfolio(owner_approved_principal_capital=Decimal("-1.00")))

    assert result.accepted is False
    assert PPFSnapshotAdapterReasonCode.NEGATIVE_INPUT in result.reason_codes
    assert PPFSnapshotAdapterReasonCode.FAIL_CLOSED in result.reason_codes


def test_ppf005_negative_banked_profit_is_passed_to_ppf_for_zero_budget_governance() -> None:
    result = _build(pnl_snapshot=_pnl(owner_approved_banked_net_profit=Decimal("-1.00")))

    decision = EnterpriseProfitProtectionManager().evaluate(
        result.risk_request,
        now=__import__("datetime").datetime.fromisoformat(OBSERVED_AT),
    )

    assert result.accepted is True
    assert decision.enforcement_status is PPFEnforcementStatus.ADVISORY_BLOCKED
    assert decision.adjusted_budget == Decimal("0.00")


def test_ppf005_reason_codes_are_deterministic_and_machine_readable() -> None:
    result = _build()

    assert result.reason_codes == (
        PPFSnapshotAdapterReasonCode.ADVISORY_ONLY,
        PPFSnapshotAdapterReasonCode.PNL_SNAPSHOT_USED,
        PPFSnapshotAdapterReasonCode.PORTFOLIO_SNAPSHOT_USED,
        PPFSnapshotAdapterReasonCode.OPTIONS_SNAPSHOT_USED,
        PPFSnapshotAdapterReasonCode.FUTURES_SNAPSHOT_USED,
        PPFSnapshotAdapterReasonCode.OK,
    )
    payload = result.as_dict()
    assert all(code == code.upper() for code in payload["reason_codes"])
    assert payload["execution_allowed"] is False
    assert payload["advisory_only"] is True
