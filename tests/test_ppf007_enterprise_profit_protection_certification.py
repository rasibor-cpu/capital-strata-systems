from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from backend.governance.enterprise_execution_gateway import (
    EnterpriseExecutionGateway,
    EnterpriseExecutionRequest,
)
from backend.governance.enterprise_profit_protection_contracts import (
    PPFMaturityTier,
    PPFReasonCode,
)
from backend.governance.enterprise_profit_protection_manager import (
    EnterpriseProfitProtectionManager,
)
from backend.governance.enterprise_profit_protection_snapshot_adapters import (
    EnterpriseProfitProtectionSnapshotAdapter,
)
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.profit_protection_projection import (
    build_profit_protection_governance_projection,
)


NOW = datetime(2026, 7, 24, 16, 0, tzinfo=timezone.utc)


def _pnl(**overrides):
    payload = {
        "owner_approved_banked_net_profit": Decimal("100.00"),
        "recent_loss_amount": Decimal("0"),
        "observed_at": NOW.isoformat(),
    }
    payload.update(overrides)
    return payload


def _portfolio(**overrides):
    payload = {
        "owner_approved_principal_capital": Decimal("1000000.00"),
        "current_drawdown_pct": Decimal("0"),
        "previous_drawdown_pct": Decimal("0"),
        "volatility_score": Decimal("0"),
        "liquidity_score": Decimal("1"),
        "confidence_score": Decimal("1"),
        "correlation_score": Decimal("0"),
        "margin_utilization": Decimal("0"),
        "maximum_credible_loss": Decimal("8.00"),
    }
    payload.update(overrides)
    return payload


def _options(**overrides):
    payload = {
        "volatility_score": Decimal("0"),
        "liquidity_score": Decimal("1"),
        "confidence_score": Decimal("1"),
        "correlation_score": Decimal("0"),
        "margin_utilization": Decimal("0"),
        "maximum_credible_loss": Decimal("12.00"),
    }
    payload.update(overrides)
    return payload


def _futures(**overrides):
    payload = {
        "volatility_score": Decimal("0"),
        "liquidity_score": Decimal("1"),
        "confidence_score": Decimal("1"),
        "correlation_score": Decimal("0"),
        "margin_utilization": Decimal("0"),
        "maximum_credible_loss": Decimal("9.00"),
    }
    payload.update(overrides)
    return payload


def _snapshot(**overrides):
    payload = {
        "request_id": "ppf-007-risk",
        "maturity_tier": PPFMaturityTier.ESTABLISHED,
        "pnl_snapshot": _pnl(),
        "portfolio_snapshot": _portfolio(),
        "options_snapshot": _options(),
        "futures_snapshot": _futures(),
        "observed_at": NOW.isoformat(),
    }
    payload.update(overrides)
    return EnterpriseProfitProtectionSnapshotAdapter().build_risk_request(**payload)


def test_ppf007_end_to_end_stack_certifies_enterprise_ceiling_and_projection() -> None:
    snapshot = _snapshot()
    manager = EnterpriseProfitProtectionManager()
    decision = manager.evaluate(snapshot.risk_request, now=NOW)
    gateway = EnterpriseExecutionGateway(profit_protection_manager=manager)

    options_reservation = gateway.request_exposure_reservation(
        EnterpriseExecutionRequest(
            request_id="ppf-007-options",
            reservation_id="ppf-007-options-reservation",
            module="OPTIONS",
            owner_id="engine-options",
            requested_exposure=snapshot.requested_exposure,
            risk_request=snapshot.risk_request,
        ),
        now=NOW,
    )
    futures_reservation = gateway.request_exposure_reservation(
        EnterpriseExecutionRequest(
            request_id="ppf-007-futures",
            reservation_id="ppf-007-futures-reservation",
            module="FUTURES",
            owner_id="engine-futures",
            requested_exposure=Decimal("9.00"),
            risk_request=snapshot.risk_request,
        ),
        now=NOW,
    )
    projection = build_profit_protection_governance_projection(
        {
            "schema_version": "css.ppf004.canonical_execution_advisory.v1",
            "status": futures_reservation.status.value,
            "accepted": futures_reservation.accepted,
            "reason_codes": [reason.value for reason in futures_reservation.reason_codes],
            "upstream_reason_codes": list(futures_reservation.upstream_reason_codes),
            "requested_exposure": "9.00",
            "reservation_id": "ppf-007-futures-reservation",
            "gateway_decision": futures_reservation.as_dict(),
            "observed_at": NOW.isoformat(),
            "source": "RUNTIME",
            "advisory_only": True,
            "execution_allowed": False,
        },
        generated_at=NOW.isoformat(),
        runtime_source="RUNTIME",
        runtime_state_hash="ppf-007-state-hash",
        now=NOW,
    )

    assert snapshot.accepted is True
    assert snapshot.requested_exposure == Decimal("12.00")
    assert snapshot.source_fields["banked_net_profit"] == "owner_approved_banked_net_profit"
    assert snapshot.source_fields["principal_capital"] == "owner_approved_principal_capital"
    assert decision.maturity_tier is PPFMaturityTier.ESTABLISHED
    assert decision.effective_ceiling == Decimal("0.40")
    assert decision.base_budget == Decimal("40.00")
    assert decision.adjusted_budget == Decimal("40.00")
    assert PPFReasonCode.PRINCIPAL_EXCLUDED in decision.reason_codes
    assert options_reservation.accepted is True
    assert futures_reservation.accepted is True
    assert futures_reservation.state.exposure_state.enterprise_risk_budget == Decimal("40.00")
    assert futures_reservation.state.exposure_state.reserved_exposure == Decimal("21.00")
    assert futures_reservation.state.exposure_state.remaining_enterprise_risk_budget == Decimal("19.00")
    assert set(futures_reservation.state.exposure_state.module_attribution) == {"OPTIONS", "FUTURES"}
    assert projection["status"] == "ADVISORY_APPROVED"
    assert projection["approved_banked_net_profit"] == "100.00"
    assert projection["effective_protection_ceiling"] == "0.40"
    assert projection["base_protection_budget"] == "40.00"
    assert projection["reserved_exposure"] == "21.00"
    assert projection["remaining_exposure_capacity"] == "19.00"
    assert projection["read_only"] is True
    assert projection["advisory_only"] is True
    assert projection["execution_allowed"] is False
    assert projection["live_trading_blocked"] is True
    assert projection["broker_execution_armed"] is False
    assert projection["policy_change_allowed"] is False
    assert projection["automatic_policy_increase_allowed"] is False


def test_ppf007_account_growth_does_not_automatically_increase_established_ceiling() -> None:
    baseline = _snapshot()
    grown_account = _snapshot(
        request_id="ppf-007-grown-account",
        portfolio_snapshot=_portfolio(
            equity=Decimal("5000000.00"),
            account_value=Decimal("5000000.00"),
            cash=Decimal("5000000.00"),
        ),
    )
    manager = EnterpriseProfitProtectionManager()

    baseline_decision = manager.evaluate(baseline.risk_request, now=NOW)
    grown_decision = manager.evaluate(grown_account.risk_request, now=NOW)

    assert baseline_decision.effective_ceiling == grown_decision.effective_ceiling == Decimal("0.40")
    assert baseline_decision.base_budget == grown_decision.base_budget == Decimal("40.00")
    assert baseline_decision.adjusted_budget == grown_decision.adjusted_budget == Decimal("40.00")
    assert grown_account.source_fields["banked_net_profit"] == "owner_approved_banked_net_profit"
    assert "equity" not in grown_account.source_fields.values()
    assert "account_value" not in grown_account.source_fields.values()
    assert "cash" not in grown_account.source_fields.values()


def test_ppf007_missing_or_contradictory_evidence_fails_closed_without_authority() -> None:
    snapshot = _snapshot(
        pnl_snapshot=_pnl(owner_approved_banked_net_profit="NaN"),
        portfolio_snapshot=_portfolio(owner_approved_principal_capital=Decimal("-1.00")),
    )
    state = build_mission_control_state(None, allow_mock=False)
    projection = state["profit_protection_governance"]

    assert snapshot.accepted is False
    assert snapshot.risk_request is None
    assert "FAIL_CLOSED" in [reason.value for reason in snapshot.reason_codes]
    assert projection["status"] == "FAIL_CLOSED"
    assert projection["remaining_exposure_capacity"] == "0.00"
    assert projection["read_only"] is True
    assert projection["advisory_only"] is True
    assert projection["execution_allowed"] is False
    assert projection["live_trading_blocked"] is True
    assert projection["broker_execution_armed"] is False
