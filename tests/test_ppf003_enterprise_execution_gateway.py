from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.governance.enterprise_execution_gateway import (
    EnterpriseExecutionGateway,
    EnterpriseExecutionGatewayReasonCode,
    EnterpriseExecutionGatewayStatus,
    EnterpriseExecutionRequest,
)
from backend.governance.enterprise_exposure_registry import ExposureReservationStatus
from backend.governance.enterprise_profit_protection_contracts import (
    PPFEnforcementStatus,
    PPFMaturityTier,
    PPFRiskRequest,
)


NOW = datetime(2026, 7, 24, 13, 0, tzinfo=timezone.utc)


def _risk_request(
    *,
    request_id: str = "risk-ppf003",
    profit: Decimal = Decimal("100.00"),
    observed_at: datetime = NOW,
) -> PPFRiskRequest:
    return PPFRiskRequest(
        request_id=request_id,
        maturity_tier=PPFMaturityTier.STARTUP,
        banked_net_profit=profit,
        principal_capital=Decimal("1000000.00"),
        current_drawdown_pct=Decimal("0"),
        previous_drawdown_pct=Decimal("0"),
        recent_loss_amount=Decimal("0"),
        volatility_score=Decimal("0"),
        liquidity_score=Decimal("1"),
        confidence_score=Decimal("1"),
        correlation_score=Decimal("0"),
        margin_utilization=Decimal("0"),
        observed_at=observed_at.isoformat(),
    )


def _execution_request(
    *,
    request_id: str = "exec-ppf003",
    reservation_id: str = "res-ppf003",
    module: str = "OPTIONS",
    owner_id: str = "engine-alpha",
    requested_exposure: Decimal = Decimal("10.00"),
    risk_request: PPFRiskRequest | None = None,
    observed_at: datetime = NOW,
) -> EnterpriseExecutionRequest:
    return EnterpriseExecutionRequest(
        request_id=request_id,
        reservation_id=reservation_id,
        module=module,
        owner_id=owner_id,
        requested_exposure=requested_exposure,
        risk_request=risk_request if risk_request is not None else _risk_request(observed_at=observed_at),
    )


def test_ppf003_approved_advisory_request() -> None:
    gateway = EnterpriseExecutionGateway()

    decision = gateway.evaluate_trade_request(_execution_request(), now=NOW)

    assert decision.accepted is True
    assert decision.status is EnterpriseExecutionGatewayStatus.ADVISORY_APPROVED
    assert decision.execution_allowed is False
    assert EnterpriseExecutionGatewayReasonCode.PPF_APPROVED in decision.reason_codes
    assert EnterpriseExecutionGatewayReasonCode.BUDGET_SOURCE_PPF in decision.reason_codes
    assert decision.state.exposure_state.enterprise_risk_budget == Decimal("80.00")


def test_ppf003_rejected_constitutional_request() -> None:
    gateway = EnterpriseExecutionGateway()
    request = _execution_request(risk_request=_risk_request(profit=Decimal("0.00")))

    decision = gateway.evaluate_trade_request(request, now=NOW)

    assert decision.accepted is False
    assert decision.status is EnterpriseExecutionGatewayStatus.ADVISORY_REJECTED
    assert EnterpriseExecutionGatewayReasonCode.CONSTITUTIONAL_POLICY_REJECTED in decision.reason_codes
    assert decision.ppf_decision.enforcement_status is PPFEnforcementStatus.ADVISORY_BLOCKED


def test_ppf003_rejected_registry_request() -> None:
    gateway = EnterpriseExecutionGateway()

    decision = gateway.request_exposure_reservation(
        _execution_request(requested_exposure=Decimal("81.00")),
        now=NOW,
    )

    assert decision.accepted is False
    assert decision.status is EnterpriseExecutionGatewayStatus.ADVISORY_REJECTED
    assert EnterpriseExecutionGatewayReasonCode.EXPOSURE_REGISTRY_REJECTED in decision.reason_codes
    assert EnterpriseExecutionGatewayReasonCode.BUDGET_EXCEEDED in decision.reason_codes


def test_ppf003_reservation_lifecycle_through_gateway() -> None:
    gateway = EnterpriseExecutionGateway()

    reserved = gateway.request_exposure_reservation(_execution_request(), now=NOW)
    committed = gateway.commit_execution("res-ppf003", owner_id="engine-alpha", now=NOW)
    released = gateway.release_execution("res-ppf003", owner_id="engine-alpha", now=NOW)

    assert reserved.accepted is True
    assert reserved.reservation.status is ExposureReservationStatus.RESERVED
    assert committed.accepted is True
    assert committed.reservation.status is ExposureReservationStatus.COMMITTED
    assert released.accepted is True
    assert released.reservation.status is ExposureReservationStatus.RELEASED
    assert released.state.exposure_state.remaining_enterprise_risk_budget == Decimal("80.00")


def test_ppf003_owner_validation_rejects_non_owner_mutation() -> None:
    gateway = EnterpriseExecutionGateway()
    gateway.request_exposure_reservation(_execution_request(), now=NOW)

    decision = gateway.commit_execution("res-ppf003", owner_id="engine-beta", now=NOW)

    assert decision.accepted is False
    assert decision.status is EnterpriseExecutionGatewayStatus.FAIL_CLOSED
    assert EnterpriseExecutionGatewayReasonCode.RESERVATION_OWNER_INVALID in decision.reason_codes
    assert gateway.exposure_registry.reservations()[0].status is ExposureReservationStatus.RESERVED


def test_ppf003_missing_governance_state_fails_closed() -> None:
    gateway = EnterpriseExecutionGateway()

    decision = gateway.commit_execution("missing", owner_id="engine-alpha", now=NOW)

    assert decision.accepted is False
    assert decision.status is EnterpriseExecutionGatewayStatus.FAIL_CLOSED
    assert EnterpriseExecutionGatewayReasonCode.MISSING_GOVERNANCE_STATE in decision.reason_codes


def test_ppf003_stale_governance_fails_closed() -> None:
    gateway = EnterpriseExecutionGateway(max_registry_age_seconds=1)
    gateway.evaluate_trade_request(_execution_request(), now=NOW)

    decision = gateway.request_exposure_reservation(
        _execution_request(
            request_id="exec-stale",
            reservation_id="res-stale",
            observed_at=NOW + timedelta(seconds=2),
        ),
        now=NOW + timedelta(seconds=2),
    )

    assert decision.accepted is False
    assert decision.status is EnterpriseExecutionGatewayStatus.FAIL_CLOSED
    assert EnterpriseExecutionGatewayReasonCode.STALE_GOVERNANCE_STATE in decision.reason_codes


def test_ppf003_invalid_execution_request_fails_closed() -> None:
    gateway = EnterpriseExecutionGateway()

    decision = gateway.request_exposure_reservation(
        _execution_request(request_id="", requested_exposure=Decimal("NaN")),
        now=NOW,
    )

    assert decision.accepted is False
    assert decision.status is EnterpriseExecutionGatewayStatus.FAIL_CLOSED
    assert EnterpriseExecutionGatewayReasonCode.INVALID_EXECUTION_REQUEST in decision.reason_codes


def test_ppf003_unknown_module_fails_closed() -> None:
    gateway = EnterpriseExecutionGateway()

    decision = gateway.request_exposure_reservation(
        _execution_request(module="UNKNOWN"),
        now=NOW,
    )

    assert decision.accepted is False
    assert decision.status is EnterpriseExecutionGatewayStatus.FAIL_CLOSED
    assert EnterpriseExecutionGatewayReasonCode.UNKNOWN_MODULE in decision.reason_codes


def test_ppf003_invalid_risk_request_fails_closed() -> None:
    gateway = EnterpriseExecutionGateway()
    request = EnterpriseExecutionRequest(
        request_id="exec-invalid-risk",
        reservation_id="res-invalid-risk",
        module="OPTIONS",
        owner_id="engine-alpha",
        requested_exposure=Decimal("1.00"),
        risk_request=None,
    )

    decision = gateway.request_exposure_reservation(request, now=NOW)

    assert decision.accepted is False
    assert decision.status is EnterpriseExecutionGatewayStatus.FAIL_CLOSED
    assert EnterpriseExecutionGatewayReasonCode.INVALID_RISK_REQUEST in decision.reason_codes


def test_ppf003_deterministic_reason_codes_for_reservation() -> None:
    gateway = EnterpriseExecutionGateway()

    decision = gateway.request_exposure_reservation(_execution_request(), now=NOW)

    assert decision.reason_codes == (
        EnterpriseExecutionGatewayReasonCode.ADVISORY_ONLY,
        EnterpriseExecutionGatewayReasonCode.PPF_EVALUATED,
        EnterpriseExecutionGatewayReasonCode.PPF_APPROVED,
        EnterpriseExecutionGatewayReasonCode.BUDGET_SOURCE_PPF,
        EnterpriseExecutionGatewayReasonCode.PRINCIPAL_EXCLUDED,
        EnterpriseExecutionGatewayReasonCode.EXPOSURE_REGISTRY_ACCEPTED,
        EnterpriseExecutionGatewayReasonCode.EXPOSURE_RESERVED,
        EnterpriseExecutionGatewayReasonCode.OK,
    )
    assert decision.upstream_reason_codes == (
        "ADVISORY_ONLY",
        "PRINCIPAL_EXCLUDED",
        "FINAL_BUDGET_CAPPED_BY_BASE_CEILING",
        "OK",
    )
