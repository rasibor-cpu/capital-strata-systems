from __future__ import annotations

from datetime import datetime, timezone
from math import inf

from fastapi.testclient import TestClient

from dashboard.mission_control.app import create_app
from dashboard.mission_control.contracts import build_mission_control_state, validate_mission_control_state
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.rbac_console import ROLES


def _runtime_payload() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "payload_schema": "css.frontend.contract.v1",
        "generated_at": now,
        "session_id": "mc007b-session",
        "cycle_number": 78,
        "engine_mode": "SAFE",
        "resolved_mode": "paper",
        "mission_control_data_source": "RUNTIME",
        "session": {"session_id": "mc007b-session", "user_id": "operator", "role": "Operator", "engine_mode": "SAFE"},
        "alerts": {"active": [], "count": 0, "severity": "GREEN"},
        "sections": {
            "account_summary": {
                "cash_balance": 1500.0,
                "total_equity": 1525.5,
                "buying_power": 1400.0,
                "margin_used": 0.0,
                "currency": "USD",
                "broker": "COINBASE",
                "account_mode": "paper",
            },
            "pnl_summary": {"realized_pnl": 20.0, "unrealized_pnl": 5.5, "net_pnl": 25.5, "total_exposure": 100.0},
            "positions": {"total": 1, "total_exposure": 100.0, "open_positions": [{"symbol": "BTC-USD", "asset_class": "CRYPTO"}]},
            "risk": {"risk_state": "GREEN", "risk_score": 9.0, "gate_status": "BLOCKED", "current_drawdown": 0.0, "total_exposure": 100.0},
            "execution": {"execution_state": "BLOCKED", "accepted_trade_count": 0, "rejected_trade_count": 1, "avg_slippage": 0.01, "fee_cost": 0.25, "execution_cost_state": "PASS"},
            "market": {"regime_state": "RISK_ON", "trend_state": "UP", "volatility_state": "LOW", "liquidity_state": "GOOD"},
            "broker": {
                "selected_broker": "COINBASE",
                "broker_mode": "paper",
                "broker_health": "GREEN",
                "connection_status": "PASS",
                "authentication_status": "PASS",
                "account_data_health": "PASS",
                "balance_position_status": "PASS",
                "market_data_status": "PASS",
                "supported_assets": ["crypto"],
                "last_heartbeat": now,
                "execution_scope": "READ_ONLY",
            },
            "runtime_certification_snapshot": {"certification": "GREEN", "operational_state": "READ_ONLY", "generated_at": now},
            "configuration": {
                "feature_flags": {
                    "mission_control": True,
                    "legacy_panel": {"state": "deprecated", "description": "display only"},
                    "research_overlay": {"state": "experimental", "description": "lab"},
                }
            },
            "governance": {
                "governance_status": "GREEN",
                "audit_enabled": True,
                "approval_workflows": {
                    "configuration": {"approval_status": "approved", "chain": ["Operator", "Risk Officer"], "required_roles": ["Operator", "Risk Officer"]},
                    "risk": {"approval_status": "pending", "chain": ["Risk Officer", "Auditor"], "required_roles": ["Risk Officer", "Auditor"]},
                },
            },
            "audit": {
                "configuration_changes": [{"field": "feature_flags", "status": "reviewed"}],
                "change_history": [
                    {
                        "who": "operator",
                        "what": "configuration display update",
                        "when": now,
                        "reason": "governance review",
                        "approval_status": "approved",
                        "rollback_available": True,
                    }
                ],
                "decisions": [{"decision_id": "decision-btc-1", "symbol": "BTC-USD", "decision": "BLOCKED", "confidence": 0.62, "reason": "advisory_only"}],
                "committees": {
                    "Investment Committee": {"outcome": "WARNING", "reason": "watch"},
                    "Risk Committee": {"outcome": "PASS", "reason": "green"},
                    "Execution Committee": {"outcome": "FAIL", "reason": "read only"},
                    "Capital Committee": {"outcome": "PASS", "reason": "cash"},
                    "Compliance": {"outcome": "PASS", "reason": "reviewed"},
                    "Broker Committee": {"outcome": "PASS", "reason": "ready"},
                },
            },
        },
    }


def test_mc007b_secure_operations_sections_are_present_read_only_and_consistent() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    required = (
        "rbac_console",
        "operator_console",
        "approval_workflow_console",
        "configuration_console",
        "broker_registry_console",
        "feature_flags_console",
        "audit_console",
        "change_history_console",
        "rollback_console",
        "governance_summary_console",
    )

    for name in required:
        payload = state[name]
        assert payload["read_only"] is True
        assert payload["execution_allowed"] is False
        assert payload["live_trading_blocked"] is True
        assert payload["broker_execution_armed"] is False
        assert payload["advisory_only"] is True
        assert payload["state_hash"] == state["runtime"]["state_hash"]
        assert payload["runtime_id"] == state["runtime"]["runtime_id"]

    assert set(required).issubset(set(state["source_consistency"]["checked_sections"]))
    assert state["contract_validation"]["valid"] is True


def test_mc007b_rbac_operator_and_approval_workflows() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    assert [row["role"] for row in state["rbac_console"]["roles"]] == list(ROLES)
    assert state["rbac_console"]["role_editing"] is False
    assert state["operator_console"]["available_actions"] == []
    workflows = {row["workflow"]: row for row in state["approval_workflow_console"]["workflows"]}
    assert workflows["configuration"]["approval_status"] == "approved"
    assert workflows["runtime"]["changes_enabled"] is False


def test_mc007b_broker_registry_configuration_feature_flags_and_governance_summary() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    assert state["broker_registry_console"]["active_broker"] == "COINBASE"
    assert state["broker_registry_console"]["editing_enabled"] is False
    assert state["configuration_console"]["safe_values_only"] is True
    assert state["feature_flags_console"]["summary"]["enabled"] == 1
    assert state["feature_flags_console"]["summary"]["deprecated"] == 1
    assert state["feature_flags_console"]["summary"]["experimental"] == 1
    assert state["governance_summary_console"]["operator_actions_enabled"] is False


def test_mc007b_audit_change_history_and_rollback_planner() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    assert state["audit_console"]["configuration_changes"] == [{"field": "feature_flags", "status": "reviewed"}]
    assert state["audit_console"]["deletion_enabled"] is False
    assert state["change_history_console"]["changes"][0]["who"] == "operator"
    assert state["rollback_console"]["eligible_targets"][0]["target"] == "configuration display update"
    assert state["rollback_console"]["perform_available"] is False


def test_mc007b_pages_render_secure_operations_panels() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    governance = render_mission_control_shell(state, active_section="users_governance")
    broker = render_mission_control_shell(state, active_section="broker_management")
    config = render_mission_control_shell(state, active_section="system_configuration")
    audit = render_mission_control_shell(state, active_section="audit_explainability")
    certification = render_mission_control_shell(state, active_section="certification_readiness")

    assert "RBAC Console" in governance
    assert "Approval Workflows" in governance
    assert "Broker Registry Console" in broker
    assert "Configuration Console" in config
    assert "Feature Flags" in config
    assert "Rollback Planner" in config
    assert "Audit Center" in audit
    assert "Governance Summary" in certification


def test_mc007b_offline_state_fails_closed_without_operations() -> None:
    state = build_mission_control_state(None, allow_mock=False)

    assert state["rbac_console"]["status"] == "fail_closed"
    assert state["governance_summary_console"]["status"] == "fail_closed"
    assert state["contract_validation"]["valid"] is False
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True
    assert state["safety"]["broker_execution_armed"] is False


def test_mc007b_fail_closed_on_missing_permissions_state_mismatch_and_non_finite() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    missing_permissions = dict(state)
    missing_permissions["permissions"] = {**state["permissions"], "read_only": False}
    mismatch = dict(state)
    mismatch["source_consistency"] = {**state["source_consistency"], "status": "FAIL_CLOSED", "mismatches": ["rbac_console"]}
    non_finite = dict(state)
    non_finite["configuration_console"] = {**state["configuration_console"], "versions": inf}

    permission_validation = validate_mission_control_state(missing_permissions)
    mismatch_validation = validate_mission_control_state(mismatch)
    non_finite_validation = validate_mission_control_state(non_finite)

    assert "permission_invalid:read_only" in permission_validation["reasons"]
    assert "source_consistency_failed" in mismatch_validation["reasons"]
    assert any(reason.startswith("non_finite_value:configuration_console.versions") for reason in non_finite_validation["reasons"])


def test_mc007b_fastapi_state_endpoint_exposes_secure_operations() -> None:
    client = TestClient(create_app(lambda: _runtime_payload()))

    response = client.get("/mission-control/api/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rbac_console"]["role_editing"] is False
    assert payload["rollback_console"]["perform_available"] is False
