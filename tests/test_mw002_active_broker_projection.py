"""MW-002 / RR-002 — active broker projection + Mission Control health matrix."""

from __future__ import annotations

from datetime import datetime, timezone

from dashboard.mission_control.active_broker_projection import (
    annotate_broker_list_with_inactive_evidence,
    broker_compatible_with_runtime_profile,
    canonical_broker_connection_state,
    project_active_broker_for_runtime_profile,
)
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.health import HEALTH_AMBER, HEALTH_GREEN, build_health_summary
from dashboard.mission_control.safety import SAFE_FLAGS


def _fresh() -> dict:
    return {"overall_freshness": "FRESH", "stale_mandatory_data": False}


def _safe_state(**overrides):
    state = {
        "safety": dict(SAFE_FLAGS),
        "contract_validation": {"valid": True},
        "runtime_snapshot": {"heartbeat_status": "FRESH", "runtime_status": "ONLINE"},
        "brokers": {"active_broker": {"selected_broker": "OANDA", "connection_status": "PASS", "broker_mode": "paper"}},
    }
    state.update(overrides)
    return state


def test_canonical_broker_state_mapping() -> None:
    assert canonical_broker_connection_state("PASS") == "READY"
    assert canonical_broker_connection_state("READY") == "READY"
    assert canonical_broker_connection_state("CONNECTED") == "READY"
    assert canonical_broker_connection_state("FAIL") == "FAIL"
    assert canonical_broker_connection_state("UNAVAILABLE") == "FAIL"
    assert canonical_broker_connection_state("BROKER_UNAVAILABLE") == "FAIL"
    assert canonical_broker_connection_state("DEGRADED") == "DEGRADED"
    assert canonical_broker_connection_state("AMBER") == "DEGRADED"
    assert canonical_broker_connection_state("") == "UNKNOWN"


def test_health_reason_code_projection_active_fail() -> None:
    summary = build_health_summary(
        _safe_state(
            brokers={"active_broker": {"selected_broker": "OANDA", "connection_status": "FAIL", "broker_mode": "paper"}}
        ),
        freshness_summary=_fresh(),
    )
    assert summary["health"] == HEALTH_AMBER
    assert "broker_state_not_green" in summary["reasons"]
    assert "active_broker_fail:OANDA" in summary["reasons"]
    assert summary["execution_allowed"] is False
    assert summary["live_trading_blocked"] is True
    assert summary["broker_execution_armed"] is False
    assert summary["advisory_only"] is True


def test_health_active_pass_is_green() -> None:
    summary = build_health_summary(_safe_state(), freshness_summary=_fresh())
    assert summary["health"] == HEALTH_GREEN
    assert "broker_state_not_green" not in summary["reasons"]


def test_health_degraded_maps_to_amber() -> None:
    summary = build_health_summary(
        _safe_state(
            brokers={"active_broker": {"selected_broker": "OANDA", "connection_status": "DEGRADED", "broker_mode": "paper"}}
        ),
        freshness_summary=_fresh(),
    )
    assert summary["health"] == HEALTH_AMBER
    assert "active_broker_degraded:OANDA" in summary["reasons"]


def test_health_no_active_broker() -> None:
    summary = build_health_summary(
        _safe_state(brokers={"active_broker": {}}),
        freshness_summary=_fresh(),
    )
    assert summary["health"] == HEALTH_AMBER
    assert "active_broker_missing" in summary["reasons"]
    assert summary["execution_allowed"] is False


def test_paper_live_coinbase_is_not_profile_compatible() -> None:
    assert broker_compatible_with_runtime_profile(
        selected_broker="COINBASE",
        broker_mode="live",
        runtime_mode="PAPER",
    ) is False
    assert broker_compatible_with_runtime_profile(
        selected_broker="OANDA",
        broker_mode="paper",
        runtime_mode="PAPER",
    ) is True
    assert broker_compatible_with_runtime_profile(
        selected_broker="CSS_PAPER",
        broker_mode="paper",
        runtime_mode="PAPER",
    ) is True


def test_project_active_oanda_practice_ready_ignores_inactive_coinbase_fail() -> None:
    active = project_active_broker_for_runtime_profile(
        {
            "selected_broker": "COINBASE",
            "broker_mode": "live",
            "connection_status": "FAIL",
            "failure_reason": "coinbase_unconfigured",
        },
        broker={
            "selected_broker": "COINBASE",
            "broker_mode": "live",
            "connection_status": "FAIL",
            "campaign_broker": "OANDA",
            "paper_broker_mode": "practice",
            "paper_connection_status": "PASS",
        },
        runtime_snapshot={"runtime_mode": "PAPER", "broker": {"selected_broker": "COINBASE", "broker_mode": "live", "transport": "FAIL"}},
        runtime_mode="PAPER",
    )
    assert active["selected_broker"] == "OANDA"
    assert active["broker_mode"] == "practice"
    assert active["connection_status"] == "PASS"
    assert active["inactive_projected_broker"]["selected_broker"] == "COINBASE"
    assert active["inactive_projected_broker"]["connection_status"] == "FAIL"

    summary = build_health_summary(
        _safe_state(brokers={"active_broker": active}),
        freshness_summary=_fresh(),
    )
    assert summary["health"] == HEALTH_GREEN
    assert "broker_state_not_green" not in summary["reasons"]


def test_project_active_css_paper_ready_when_stale_live_coinbase_selected() -> None:
    active = project_active_broker_for_runtime_profile(
        {
            "selected_broker": "COINBASE",
            "broker_mode": "live",
            "connection_status": "FAIL",
        },
        broker={"selected_broker": "COINBASE", "broker_mode": "live", "connection_status": "FAIL"},
        runtime_snapshot={"runtime_mode": "PAPER"},
        runtime_mode="PAPER",
    )
    assert active["selected_broker"] == "CSS_PAPER"
    assert active["broker_mode"] == "paper"
    assert active["connection_status"] == "PASS"
    assert active["inactive_projected_broker"]["selected_broker"] == "COINBASE"

    rows = annotate_broker_list_with_inactive_evidence(
        [{"broker": "COINBASE", "selected": True, "status": "FAIL", "readiness": "NOT_READY"}],
        active_broker=active,
    )
    coinbase = next(row for row in rows if row["broker"] == "COINBASE")
    assert coinbase["selected"] is False
    assert coinbase["not_active_for_runtime_profile"] is True
    assert coinbase["connection_health"] == "FAIL"
    assert any(row.get("selected") and row.get("broker") in {"CSS_PAPER", "PAPER"} for row in rows)


def test_true_active_oanda_fail_remains_amber() -> None:
    active = project_active_broker_for_runtime_profile(
        {
            "selected_broker": "OANDA",
            "broker_mode": "paper",
            "connection_status": "FAIL",
            "failure_reason": "practice_unreachable",
        },
        broker={"selected_broker": "OANDA", "broker_mode": "paper", "connection_status": "FAIL"},
        runtime_snapshot={"runtime_mode": "PAPER"},
        runtime_mode="PAPER",
    )
    assert active["selected_broker"] == "OANDA"
    assert active["connection_status"] == "FAIL"
    assert "inactive_projected_broker" not in active

    summary = build_health_summary(
        _safe_state(brokers={"active_broker": active}),
        freshness_summary=_fresh(),
    )
    assert summary["health"] == HEALTH_AMBER
    assert "active_broker_fail:OANDA" in summary["reasons"]


def test_multiple_brokers_one_active_drives_health() -> None:
    active = project_active_broker_for_runtime_profile(
        {
            "selected_broker": "OANDA",
            "broker_mode": "practice",
            "connection_status": "PASS",
        },
        broker={
            "selected_broker": "OANDA",
            "broker_mode": "practice",
            "connection_status": "PASS",
            "inactive_broker_evidence": {"COINBASE": "FAIL", "BINANCE": "FAIL"},
        },
        runtime_snapshot={"runtime_mode": "PAPER"},
        runtime_mode="PAPER",
    )
    assert active["selected_broker"] == "OANDA"
    summary = build_health_summary(
        _safe_state(brokers={"active_broker": active}),
        freshness_summary=_fresh(),
    )
    assert summary["health"] == HEALTH_GREEN


def test_mission_control_state_paper_aligns_away_from_stale_coinbase_live() -> None:
    now = datetime.now(timezone.utc).isoformat()
    frontend = {
        "generated_at": now,
        "resolved_mode": "PAPER",
        "runtime_mode": "PAPER",
        "mission_control_data_source": "RUNTIME",
        "mission_control_mock_data": False,
        "session": {"session_id": "mw002", "cycle_number": 1, "engine_mode": "SAFE", "resolved_mode": "PAPER"},
        "sections": {
            "broker": {
                "selected_broker": "COINBASE",
                "broker_mode": "live",
                "connection_status": "FAIL",
                "authentication_status": "FAIL",
                "account_data_health": "FAIL",
                "market_data_status": "FAIL",
                "broker_health": "RED",
                "execution_scope": "READ_ONLY",
                "campaign_broker": "OANDA",
                "paper_broker_mode": "practice",
                "paper_connection_status": "PASS",
                "failure_reason": "coinbase_disabled",
            },
            "account_summary": {
                "cash_balance": 1000,
                "total_equity": 1000,
                "buying_power": 1000,
                "broker": "CSS_PAPER",
                "account_mode": "paper",
            },
            "pnl_summary": {"realized_pnl": 0, "unrealized_pnl": 0, "net_pnl": 0},
            "positions": {"open_count": 0, "positions": []},
            "risk": {"risk_state": "GREEN", "gate_status": "BLOCKED"},
            "market": {"regime_state": "RISK_ON"},
            "execution": {},
            "governance": {},
            "runtime_certification_snapshot": {"certification": "PAPER_OK", "operational_state": "ONLINE"},
            "alerts": {"active": [], "count": 0},
        },
    }
    # Inject a ready runtime snapshot so projection sees PAPER mode + stale live selection.
    state = build_mission_control_state(
        {
            "frontend_payload": frontend,
            "runtime_snapshot": {
                "runtime_id": "mw002",
                "session_id": "mw002",
                "source": "RUNTIME",
                "runtime_mode": "PAPER",
                "runtime_status": "ONLINE",
                "runtime_health": "GREEN",
                "heartbeat_status": "FRESH",
                "last_heartbeat": now,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "broker": {
                    "selected_broker": "COINBASE",
                    "broker_mode": "live",
                    "transport": "FAIL",
                    "authentication": "FAIL",
                    "account": "FAIL",
                    "market_data": "FAIL",
                    "execution_scope": "READ_ONLY",
                    "failure_reason": "coinbase_disabled",
                },
                "portfolio": {"equity": 1000, "cash": 1000, "buying_power": 1000},
                "alerts": {"active_alerts": [], "count": 0},
                "risk": {"risk_status": "GREEN"},
                "certification": {"rc1_certification": "PAPER_OK"},
            },
        },
        allow_mock=False,
    )
    active = state["brokers"]["active_broker"]
    assert active["selected_broker"] == "OANDA"
    assert active["connection_status"] == "PASS"
    assert active["inactive_projected_broker"]["selected_broker"] == "COINBASE"
    assert state["platform"]["selected_broker"] == "OANDA"
    assert state["health"]["health"] == HEALTH_GREEN
    assert "broker_state_not_green" not in state["health"]["reasons"]
    assert state["health"]["execution_allowed"] is False
    assert state["health"]["live_trading_blocked"] is True
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True
    assert state["safety"]["broker_execution_armed"] is False

    coinbase_rows = [row for row in state["brokers"]["broker_list"] if str(row.get("broker")).upper() == "COINBASE"]
    assert coinbase_rows
    assert all(row.get("selected") is False for row in coinbase_rows)
    assert any(row.get("not_active_for_runtime_profile") or row.get("connection_health") == "FAIL" for row in coinbase_rows)


def test_live_authority_flags_remain_fail_closed_on_green_health() -> None:
    summary = build_health_summary(_safe_state(), freshness_summary=_fresh())
    assert summary["health"] == HEALTH_GREEN
    assert summary["execution_allowed"] is False
    assert summary["live_trading_blocked"] is True
    assert summary["broker_execution_armed"] is False
    assert summary["advisory_only"] is True
    assert summary["read_only"] is True
