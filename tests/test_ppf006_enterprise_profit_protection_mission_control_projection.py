from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.governance.enterprise_execution_gateway import EnterpriseExecutionGateway, EnterpriseExecutionRequest
from backend.governance.enterprise_profit_protection_contracts import PPFMaturityTier, PPFRiskRequest
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.pages.risk_command import render as render_risk_command
from dashboard.mission_control.profit_protection_projection import (
    SCHEMA_VERSION,
    build_profit_protection_governance_projection,
)


NOW = datetime(2026, 7, 24, 13, 0, tzinfo=timezone.utc)


def _risk_request(*, observed_at: datetime = NOW) -> PPFRiskRequest:
    return PPFRiskRequest(
        request_id="ppf006-risk",
        maturity_tier=PPFMaturityTier.ESTABLISHED,
        banked_net_profit=Decimal("100.00"),
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


def _gateway_payload(*, observed_at: datetime = NOW) -> dict[str, object]:
    gateway = EnterpriseExecutionGateway()
    request = EnterpriseExecutionRequest(
        request_id="ppf006-exec",
        reservation_id="ppf006-reservation",
        module="OPTIONS",
        owner_id="engine-alpha",
        requested_exposure=Decimal("10.00"),
        risk_request=_risk_request(observed_at=observed_at),
    )
    decision = gateway.request_exposure_reservation(request, now=observed_at)
    return {
        "schema_version": "css.ppf004.canonical_execution_advisory.v1",
        "status": decision.status.value,
        "accepted": decision.accepted,
        "reason_codes": [reason.value for reason in decision.reason_codes],
        "upstream_reason_codes": list(decision.upstream_reason_codes),
        "requested_exposure": "10.00",
        "reservation_id": "ppf006-reservation",
        "gateway_decision": decision.as_dict(),
        "observed_at": observed_at.isoformat(),
        "source": "RUNTIME",
        "advisory_only": True,
        "execution_allowed": False,
    }


def test_ppf006_projects_enterprise_profit_protection_governance() -> None:
    projection = build_profit_protection_governance_projection(
        _gateway_payload(),
        generated_at=NOW.isoformat(),
        runtime_source="RUNTIME",
        runtime_state_hash="runtime-hash",
        now=NOW,
    )

    assert projection["schema_version"] == SCHEMA_VERSION
    assert projection["status"] == "ADVISORY_APPROVED"
    assert projection["maturity_tier"] == "ESTABLISHED"
    assert projection["approved_banked_net_profit"] == "100.00"
    assert projection["effective_protection_ceiling"] == "0.40"
    assert projection["base_protection_budget"] == "40.00"
    assert projection["adjusted_protection_budget"] == "40.00"
    assert projection["committed_exposure"] == "0"
    assert projection["reserved_exposure"] == "10.00"
    assert projection["remaining_exposure_capacity"] == "30.00"
    assert projection["execution_allowed"] is False
    assert projection["read_only"] is True
    assert projection["policy_change_allowed"] is False
    assert projection["automatic_policy_increase_allowed"] is False


def test_ppf006_missing_evidence_fails_closed_without_capacity() -> None:
    projection = build_profit_protection_governance_projection(
        {},
        generated_at=NOW.isoformat(),
        runtime_source="RUNTIME",
        now=NOW,
    )

    assert projection["status"] == "FAIL_CLOSED"
    assert projection["fail_closed"] is True
    assert projection["remaining_exposure_capacity"] == "0.00"
    assert "MISSING_PPF_GOVERNANCE_EVIDENCE" in projection["reason_codes"]
    assert "MISSING_PPF_DECISION" in projection["reason_codes"]
    assert "MISSING_EXPOSURE_STATE" in projection["reason_codes"]
    assert projection["execution_allowed"] is False


def test_ppf006_missing_exposure_state_fails_closed() -> None:
    evidence = _gateway_payload()
    gateway_decision = dict(evidence["gateway_decision"])
    state = dict(gateway_decision["state"])
    state["exposure_state"] = None
    gateway_decision["state"] = state
    gateway_decision["registry_result"] = None
    evidence["gateway_decision"] = gateway_decision

    projection = build_profit_protection_governance_projection(
        evidence,
        generated_at=NOW.isoformat(),
        runtime_source="RUNTIME",
        now=NOW,
    )

    assert projection["status"] == "FAIL_CLOSED"
    assert "MISSING_EXPOSURE_STATE" in projection["reason_codes"]
    assert projection["execution_allowed"] is False


def test_ppf006_stale_observation_fails_closed() -> None:
    old = NOW - timedelta(minutes=10)
    projection = build_profit_protection_governance_projection(
        _gateway_payload(observed_at=old),
        generated_at=NOW.isoformat(),
        runtime_source="RUNTIME",
        now=NOW,
        max_age_seconds=300,
    )

    assert projection["status"] == "FAIL_CLOSED"
    assert projection["data_freshness"]["freshness_status"] == "STALE"
    assert "DATA_STALE" in projection["reason_codes"]


def test_ppf006_invalid_monetary_evidence_fails_closed() -> None:
    evidence = _gateway_payload()
    gateway_decision = dict(evidence["gateway_decision"])
    ppf_decision = dict(gateway_decision["ppf_decision"])
    ppf_decision["adjusted_budget"] = "NaN"
    gateway_decision["ppf_decision"] = ppf_decision
    evidence["gateway_decision"] = gateway_decision

    projection = build_profit_protection_governance_projection(
        evidence,
        generated_at=NOW.isoformat(),
        runtime_source="RUNTIME",
        now=NOW,
    )

    assert projection["status"] == "FAIL_CLOSED"
    assert "INVALID_PPF_EVIDENCE" in projection["reason_codes"]
    assert projection["execution_allowed"] is False


def test_ppf006_reason_codes_are_deterministic_and_machine_readable() -> None:
    projection = build_profit_protection_governance_projection(
        _gateway_payload(),
        generated_at=NOW.isoformat(),
        runtime_source="RUNTIME",
        now=NOW,
    )

    assert projection["reason_codes"] == [
        "ADVISORY_ONLY",
        "READ_ONLY_PROJECTION",
        "PPF_EVIDENCE_PROJECTED",
        "OK",
    ]
    assert all(code == code.upper() for code in projection["reason_codes"])


def test_ppf006_mission_control_state_exposes_read_only_projection() -> None:
    observed_at = datetime.now(timezone.utc)
    state = build_mission_control_state(
        {"profit_protection_governance": _gateway_payload(observed_at=observed_at)},
        allow_mock=False,
    )

    projection = state["profit_protection_governance"]

    assert projection["status"] == "ADVISORY_APPROVED"
    assert projection["execution_allowed"] is False
    assert projection["read_only"] is True
    assert state["source_registry"]["profit_protection_governance"]["source_module"] == (
        "dashboard.mission_control.profit_protection_projection"
    )


def test_ppf006_mission_control_defaults_missing_evidence_to_fail_closed() -> None:
    state = build_mission_control_state(None, allow_mock=False)
    projection = state["profit_protection_governance"]

    assert projection["status"] == "FAIL_CLOSED"
    assert projection["remaining_exposure_capacity"] == "0.00"
    assert projection["execution_allowed"] is False
    assert "MISSING_PPF_GOVERNANCE_EVIDENCE" in projection["reason_codes"]


def test_ppf006_risk_command_page_renders_projection_without_authority() -> None:
    observed_at = datetime.now(timezone.utc)
    state = build_mission_control_state(
        {"profit_protection_governance": _gateway_payload(observed_at=observed_at)},
        allow_mock=False,
    )

    html = render_risk_command(state)

    assert "Profit Protection Governance" in html
    assert "ADVISORY_APPROVED" in html
    assert "execution_allowed" in html
    assert "False" in html
