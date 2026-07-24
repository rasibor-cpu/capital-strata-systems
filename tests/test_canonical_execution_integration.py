from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from backend.execution.canonical_execution_integration import CanonicalExecutionIntegration
from backend.execution.unified_execution_pipeline import UnifiedExecutionResult
from backend.governance.enterprise_execution_gateway import EnterpriseExecutionGateway
from backend.governance.enterprise_profit_protection_contracts import (
    PPFMaturityTier,
    PPFRiskRequest,
)


class _GateApproved:
    def approve_trade(self, candidate, session, portfolio_state, engine_mode):
        from backend.governance.css_unified_trade_gate import GateDecision

        return GateDecision(
            approved=True,
            reason="approved",
            engine_mode=engine_mode,
            timestamp=1.0,
            details={},
        )


class _GateBlocked:
    def approve_trade(self, candidate, session, portfolio_state, engine_mode):
        from backend.governance.css_unified_trade_gate import GateDecision

        return GateDecision(
            approved=False,
            reason="blocked",
            engine_mode=engine_mode,
            timestamp=1.0,
            details={},
        )


class _ExecutionGateAllow:
    def evaluate_trade(self, **kwargs):
        return {"decision": {"final": "ALLOW"}, "reason": "approved"}


class _ExecutionGateBlock:
    def evaluate_trade(self, **kwargs):
        return {"decision": {"final": "BLOCK"}, "reason": "risk_reject"}


class _PipelineSpy:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, request):
        self.calls.append(request)
        return UnifiedExecutionResult(
            trade_id="spy-trade",
            symbol=request.symbol,
            asset_class=request.asset_class,
            side=request.side,
            quantity=request.quantity,
            mode=request.mode,
            status="validated_not_executed",
            reason="validation_only_no_broker_dispatch",
        )


class _GatewayRaises:
    def request_exposure_reservation(self, request):
        raise RuntimeError("ppf gateway unavailable")


def _request() -> dict[str, object]:
    return {
        "asset_class": "FX",
        "symbol": "EUR/USD",
        "side": "BUY",
        "quantity": 1,
        "mode": "paper",
    }


def _context() -> dict[str, object]:
    return {
        "instrument": "EUR_USD",
        "side": "BUY",
        "notional": 1000.0,
        "stop_distance_pct": 0.01,
        "equity": 100000.0,
        "equity_peak": 100000.0,
        "regime_persistence": 0.5,
        "policy": "core",
        "volatility_state": "MEDIUM",
        "expected_move_bps": 12.0,
        "fee_bps": 0.5,
        "spread_bps": 1.0,
        "slippage_bps": 0.5,
        "margin_snapshot": {"available_margin": 100000.0},
        "broker_mode": "PAPER",
    }


def _ppf_risk_request(*, profit: Decimal = Decimal("100.00")) -> PPFRiskRequest:
    now = datetime.now(timezone.utc)
    return PPFRiskRequest(
        request_id="ppf-004-risk",
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
        observed_at=now.isoformat(),
    )


def _request_with_ppf(
    *,
    requested_exposure: Decimal = Decimal("10.00"),
    reservation_id: str = "ppf-004-reservation",
    module: str = "OPTIONS",
    owner_id: str = "engine-alpha",
    risk_request: PPFRiskRequest | None = None,
) -> dict[str, object]:
    payload = _request()
    payload.update(
        {
            "requested_exposure": requested_exposure,
            "ppf_reservation_id": reservation_id,
            "ppf_module": module,
            "ppf_owner_id": owner_id,
            "ppf_risk_request": risk_request or _ppf_risk_request(),
        }
    )
    return payload


def test_canonical_execution_approved_route() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateAllow(),
    )

    result = integration.execute(
        engine_run_id="run-1",
        canonical_decision={"decision": "ALLOW"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request(),
        execution_context=_context(),
    )

    assert result.execution_decision["can_execute"] is True
    assert result.execution_decision["final_decision"] == "ALLOW"
    assert result.execution_result["status"] == "validated_not_executed"
    assert result.execution_result["reason"] == "validation_only_no_broker_dispatch"
    assert result.profit_protection_governance["status"] == "FAIL_CLOSED"
    assert result.profit_protection_governance["execution_allowed"] is False


def test_canonical_execution_blocked_by_governance() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateBlocked(),
        execution_gate=_ExecutionGateAllow(),
    )

    result = integration.execute(
        engine_run_id="run-2",
        canonical_decision={"decision": "BLOCK"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request(),
        execution_context=_context(),
    )

    assert result.execution_decision["can_execute"] is False
    assert result.execution_decision["final_decision"] == "BLOCK"
    assert result.execution_result["status"] == "blocked"


def test_canonical_execution_blocked_by_execution_gate() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateBlock(),
    )

    result = integration.execute(
        engine_run_id="run-3",
        canonical_decision={"decision": "BLOCK"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request(),
        execution_context=_context(),
    )

    assert result.execution_decision["can_execute"] is False
    assert result.execution_decision["blocked_by"] == ["execution_gate"]


def test_canonical_execution_existing_result_unchanged_when_no_ppf_gateway_is_supplied() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateAllow(),
    )

    result = integration.execute(
        engine_run_id="run-no-ppf-data",
        canonical_decision={"decision": "ALLOW"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request(),
        execution_context=_context(),
    )

    assert result.execution_decision["can_execute"] is True
    assert result.execution_result == {
        "trade_id": result.execution_result["trade_id"],
        "symbol": "EUR/USD",
        "asset_class": "FX",
        "side": "BUY",
        "quantity": 1,
        "mode": "paper",
        "status": "validated_not_executed",
        "reason": "validation_only_no_broker_dispatch",
    }
    assert result.profit_protection_governance["status"] == "FAIL_CLOSED"
    assert result.profit_protection_governance["reason_codes"] == [
        "ADVISORY_ONLY",
        "INVALID_RISK_REQUEST",
    ]


def test_canonical_execution_attaches_advisory_ppf_approval() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateAllow(),
    )

    result = integration.execute(
        engine_run_id="run-ppf-approved",
        canonical_decision={"decision": "ALLOW"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request_with_ppf(),
        execution_context=_context(),
    )

    ppf = result.profit_protection_governance

    assert result.execution_result["status"] == "validated_not_executed"
    assert ppf["status"] == "ADVISORY_APPROVED"
    assert ppf["accepted"] is True
    assert ppf["requested_exposure"] == "10.00"
    assert ppf["reservation_id"] == "ppf-004-reservation"
    assert ppf["advisory_only"] is True
    assert ppf["execution_allowed"] is False


def test_canonical_execution_attaches_constitutional_rejection_without_changing_execution() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateAllow(),
    )

    result = integration.execute(
        engine_run_id="run-ppf-constitutional-reject",
        canonical_decision={"decision": "ALLOW"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request_with_ppf(risk_request=_ppf_risk_request(profit=Decimal("0.00"))),
        execution_context=_context(),
    )

    ppf = result.profit_protection_governance

    assert result.execution_decision["final_decision"] == "ALLOW"
    assert result.execution_result["status"] == "validated_not_executed"
    assert ppf["status"] == "ADVISORY_REJECTED"
    assert "CONSTITUTIONAL_POLICY_REJECTED" in ppf["reason_codes"]


def test_canonical_execution_attaches_registry_rejection_without_changing_execution() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateAllow(),
    )

    result = integration.execute(
        engine_run_id="run-ppf-registry-reject",
        canonical_decision={"decision": "ALLOW"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request_with_ppf(requested_exposure=Decimal("81.00")),
        execution_context=_context(),
    )

    ppf = result.profit_protection_governance

    assert result.execution_result["status"] == "validated_not_executed"
    assert ppf["status"] == "ADVISORY_REJECTED"
    assert "BUDGET_EXCEEDED" in ppf["reason_codes"]


def test_canonical_execution_missing_ppf_risk_data_is_structured_fail_closed_diagnostic() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateAllow(),
    )

    execution_request = _request_with_ppf()
    execution_request.pop("ppf_risk_request")

    result = integration.execute(
        engine_run_id="run-ppf-missing-risk",
        canonical_decision={"decision": "ALLOW"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=execution_request,
        execution_context=_context(),
    )

    assert result.execution_result["status"] == "validated_not_executed"
    assert result.profit_protection_governance["status"] == "FAIL_CLOSED"
    assert result.profit_protection_governance["reason_codes"] == [
        "ADVISORY_ONLY",
        "INVALID_RISK_REQUEST",
    ]


def test_canonical_execution_ppf_exception_is_structured_fail_closed_diagnostic() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateAllow(),
        enterprise_execution_gateway=_GatewayRaises(),
    )

    result = integration.execute(
        engine_run_id="run-ppf-exception",
        canonical_decision={"decision": "ALLOW"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request_with_ppf(),
        execution_context=_context(),
    )

    assert result.execution_result["status"] == "validated_not_executed"
    assert result.profit_protection_governance["status"] == "FAIL_CLOSED"
    assert result.profit_protection_governance["execution_allowed"] is False
    assert "ppf gateway unavailable" in result.profit_protection_governance["error"]


def test_canonical_execution_ppf_advisory_does_not_change_pipeline_dispatch() -> None:
    pipeline = _PipelineSpy()
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateAllow(),
        unified_pipeline=pipeline,
        enterprise_execution_gateway=EnterpriseExecutionGateway(),
    )

    result = integration.execute(
        engine_run_id="run-ppf-pipeline-spy",
        canonical_decision={"decision": "ALLOW"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request_with_ppf(),
        execution_context=_context(),
    )

    assert len(pipeline.calls) == 1
    assert result.execution_result["trade_id"] == "spy-trade"
    assert result.profit_protection_governance["execution_allowed"] is False


def test_canonical_execution_ppf_advisory_never_enables_live_authority() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateBlocked(),
        execution_gate=_ExecutionGateAllow(),
    )

    result = integration.execute(
        engine_run_id="run-ppf-live-authority",
        canonical_decision={"decision": "BLOCK"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request_with_ppf(),
        execution_context=_context(),
    )

    assert result.execution_decision["can_execute"] is False
    assert result.execution_result["status"] == "blocked"
    assert result.profit_protection_governance["accepted"] is True
    assert result.profit_protection_governance["execution_allowed"] is False


def test_canonical_execution_ppf_reason_codes_are_deterministic() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateAllow(),
    )

    result = integration.execute(
        engine_run_id="run-ppf-reasons",
        canonical_decision={"decision": "ALLOW"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request_with_ppf(),
        execution_context=_context(),
    )

    assert result.profit_protection_governance["reason_codes"] == [
        "ADVISORY_ONLY",
        "PPF_EVALUATED",
        "PPF_APPROVED",
        "BUDGET_SOURCE_PPF",
        "PRINCIPAL_EXCLUDED",
        "EXPOSURE_REGISTRY_ACCEPTED",
        "EXPOSURE_RESERVED",
        "OK",
    ]
