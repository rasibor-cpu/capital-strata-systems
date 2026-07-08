from __future__ import annotations

from fastapi.testclient import TestClient

from backend.analytics.broker_performance_intelligence import BrokerPerformanceIntelligenceEngine
from backend.analytics.decision_confidence_framework import DecisionConfidenceFramework
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator


def _green_broker_context() -> dict[str, dict[str, object]]:
    return {
        "broker": {
            "selected_broker": "DEMO",
            "broker_name": "Demo Broker",
            "broker_mode": "paper",
            "connected": True,
            "authenticated": True,
            "broker_ready": True,
            "api_health": "HEALTHY",
            "account_readiness": "READY",
            "recent_reliability_trend": "STABLE",
        },
        "execution": {
            "avg_slippage_bps": 1.0,
            "avg_spread_bps": 1.0,
            "rejection_count": 0,
            "error_count": 0,
            "total_orders": 100,
        },
        "operational": {
            "broker": "DEMO",
            "operational_state": "OPERATIONAL",
            "latency_ms": 35.0,
            "market_data_status": "OK",
            "balance_status": "AVAILABLE",
            "account_sync_status": "OK",
            "product_count": 4,
            "failure_reason": "NONE",
        },
        "diagnostics": {
            "broker": "DEMO",
            "broker_name": "DEMO",
            "credentials_present": True,
            "readiness_status": "READY",
            "failure_reason": "NONE",
        },
        "readiness": {
            "broker_ready": True,
            "readiness_status": "READY",
            "connected": True,
            "authenticated": True,
            "execution_supported": True,
        },
        "account": {
            "cash_balance": 1000.0,
            "total_equity": 1000.0,
            "buying_power": 900.0,
            "broker": "DEMO",
            "account_mode": "paper",
        },
    }


def test_phase47e_green_broker_performance_case() -> None:
    context = _green_broker_context()
    result = BrokerPerformanceIntelligenceEngine().score_broker(
        context["broker"],
        execution_metrics=context["execution"],
        operational_status=context["operational"],
        credential_diagnostics=context["diagnostics"],
        broker_readiness=context["readiness"],
    )

    assert result["broker_id"] == "DEMO"
    assert result["status"] == "GREEN"
    assert result["overall_score"] >= 75.0
    assert result["recommended_use"] == "PAPER_PRIMARY"
    assert result["blockers"] == []
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False
    assert result["live_trading_enabled"] is False


def test_phase47e_amber_degraded_broker_case() -> None:
    result = BrokerPerformanceIntelligenceEngine().score_broker(
        {
            "selected_broker": "DEMO",
            "broker_mode": "paper",
            "connected": True,
            "recent_reliability_trend": "DEGRADING",
        },
        execution_metrics={
            "execution_quality_score": 62.0,
            "rejection_rate": 0.05,
            "latency_ms": 500.0,
        },
        operational_status={
            "operational_state": "DEGRADED",
            "market_data_status": "OK",
            "balance_status": "NOT_AVAILABLE",
            "account_sync_status": "PENDING",
            "product_count": 2,
            "failure_reason": "NONE",
        },
        credential_diagnostics={"credentials_present": True, "readiness_status": "READY", "failure_reason": "NONE"},
        broker_readiness={"readiness_status": "WATCH", "connected": True},
    )

    assert result["status"] == "AMBER"
    assert result["recommended_use"] == "MONITOR_ONLY"
    assert "Broker latency is degraded" in result["weaknesses"]
    assert result["advisory_only"] is True


def test_phase47e_red_blocked_broker_case() -> None:
    result = BrokerPerformanceIntelligenceEngine().score_broker(
        {
            "selected_broker": "OANDA",
            "broker_mode": "live",
            "missing_credentials": True,
            "live_trading_enabled": False,
        },
        execution_metrics={"execution_quality_score": 30.0, "error_rate": 0.25, "latency_ms": 900.0},
        operational_status={"operational_state": "FAILED", "failure_reason": "TOKEN_INVALID"},
        credential_diagnostics={"credentials_present": False, "readiness_status": "BLOCKED", "failure_reason": "TOKEN_INVALID"},
        broker_readiness={"readiness_status": "BLOCKED"},
    )

    assert result["status"] == "RED"
    assert result["overall_score"] <= 39.0
    assert result["recommended_use"] == "DO_NOT_USE_FOR_LIVE"
    assert result["blockers"]
    assert result["execution_allowed"] is False


def test_phase47f_high_confidence_paper_decision() -> None:
    context = _green_broker_context()
    performance = BrokerPerformanceIntelligenceEngine().score_broker(
        context["broker"],
        execution_metrics=context["execution"],
        operational_status=context["operational"],
        credential_diagnostics=context["diagnostics"],
        broker_readiness=context["readiness"],
    )

    result = DecisionConfidenceFramework().evaluate_confidence(
        broker_readiness=context["readiness"],
        broker_diagnostics=context["diagnostics"],
        broker_performance=performance,
        runtime_health={"engine_mode": "SAFE", "resolved_mode": "paper"},
        trade_gate_context={"gate_status": "OPEN", "risk_state": "NORMAL"},
        account_context=context["account"],
        live_readiness_constraints={"can_live_execute": False, "execution_authority": False},
        requested_mode="paper",
    )

    assert result["confidence_band"] == "HIGH"
    assert result["decision"] == "PROCEED_PAPER"
    assert result["missing_inputs"] == []
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_phase47f_blocked_live_decision_does_not_authorize_trading() -> None:
    context = _green_broker_context()
    performance = BrokerPerformanceIntelligenceEngine().score_broker(
        {**context["broker"], "broker_mode": "live"},
        execution_metrics=context["execution"],
        operational_status=context["operational"],
        credential_diagnostics=context["diagnostics"],
        broker_readiness=context["readiness"],
    )

    result = DecisionConfidenceFramework().evaluate_confidence(
        broker_readiness=context["readiness"],
        broker_diagnostics=context["diagnostics"],
        broker_performance=performance,
        runtime_health={"engine_mode": "SAFE", "resolved_mode": "paper"},
        trade_gate_context={"gate_status": "OPEN", "risk_state": "NORMAL"},
        account_context=context["account"],
        live_readiness_constraints={"can_live_execute": False, "execution_authority": False, "go_no_go": "NO GO"},
        requested_mode="live",
    )

    assert result["confidence_band"] == "BLOCKED"
    assert result["decision"] == "BLOCKED"
    assert "Live mode decision cannot be authorized by this advisory framework" in result["reasons"]
    assert result["execution_allowed"] is False
    assert result["live_trading_enabled"] is False


def test_phase47f_missing_inputs_are_handled_without_execution_authority() -> None:
    result = DecisionConfidenceFramework().evaluate_confidence(requested_mode="paper")

    assert result["confidence_band"] == "LOW"
    assert result["decision"] == "MONITOR"
    assert "broker_readiness" in result["missing_inputs"]
    assert "broker_performance" in result["missing_inputs"]
    assert result["execution_allowed"] is False
    assert result["advisory_only"] is True


def test_phase47ef_endpoint_response_shape_is_advisory_only() -> None:
    context = _green_broker_context()
    state = DashboardHydrationCoordinator().hydrate(
        account_payload=context["account"],
        broker_payload={
            **context["broker"],
            "broker_readiness": context["readiness"],
            "broker_credential_diagnostics": context["diagnostics"],
            "broker_operational_status": {"selected": context["operational"]},
        },
        risk_payload={"risk_state": "NORMAL", "gate_status": "OPEN"},
        execution_payload=context["execution"],
        session_payload={"engine_mode": "SAFE", "live_or_paper": "paper"},
    )

    response = TestClient(create_app(lambda: state)).get("/api/v1/broker-performance-intelligence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["section"] == "broker_performance_intelligence"
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
    data = payload["data"]
    assert set(data) >= {"broker_performance_intelligence", "decision_confidence", "generated_at", "advisory_only"}
    assert data["broker_performance_intelligence"]["status"] == "GREEN"
    assert data["decision_confidence"]["decision"] == "PROCEED_PAPER"
    assert data["advisory_only"] is True
    assert data["execution_allowed"] is False
    assert data["live_trading_enabled"] is False
