from __future__ import annotations

import json
import time
from decimal import Decimal

import pytest

from backend.app.brokers.execution_boundary import (
    resolve_mode_dominance,
    validate_execution_boundary,
)
from backend.intelligence.live_dashboard_trade_controls import (
    evaluate_exit_signal,
    format_option_symbol,
    profitability_allows,
)
from dashboard.auth.persistent_session_store import PersistentSessionStore
from dashboard.runtime.alerting_layer import ALERT_PAYLOAD_VERSION, build_alert_payload
from dashboard.runtime.api_bridge import (
    create_app,
    get_alert_payload,
    get_coinbase_micro_live_dry_run_probe_payload,
    get_dashboard_state_payload,
    get_frontend_payload,
    get_micro_live_broker_readiness_confirmation_payload,
    get_micro_live_operator_approval_gate_payload,
    get_micro_live_pilot_order_intent_payload,
    get_micro_live_pilot_readiness_payload,
    get_runtime_event_persistence_checklist_export_payload,
    get_runtime_event_persistence_checklist_payload,
    get_runtime_event_persistence_policy_inspection_payload,
    get_runtime_event_persistence_report_payload,
    get_runtime_event_persistence_scenarios_payload,
    get_runtime_event_persistence_sim_payload,
    get_runtime_events_payload,
)
from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.frontend_contract import (
    FRONTEND_SECTIONS,
    build_frontend_payload,
    build_section_payload,
)
from dashboard.runtime.live_dashboard_state import (
    ClusterSaturationRiskGovernor,
    MarkToMarketEngine,
    MomentumClusterAmplifier,
    SessionRecoveryEngine,
    SmartDriftEngine,
    build_asset_pnl_maps,
    build_cycle_runtime_summary,
    pnl_dict_for_asset as runtime_pnl_dict_for_asset,
    total_realized_pnl as runtime_total_realized_pnl,
)
from dashboard.runtime.trade_lifecycle_service import (
    TRADE_LIFECYCLE_SERVICE_VERSION,
    TradeLifecycleExecutionStateService,
    classify_exit_reason,
)
from dashboard.runtime.trade_lifecycle_replay_sink import (
    TRADE_LIFECYCLE_REPLAY_SINK_VERSION,
    TradeLifecycleReplaySink,
    TradeLifecycleReplaySinkError,
    load_trade_lifecycle_replay_events,
)
from dashboard.runtime.deployment_profiles import (
    DEPLOYMENT_PROFILE_VERSION,
    get_deployment_profiles,
    validate_deployment_environment,
)
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads
from dashboard.runtime.ws_bridge import (
    WEBSOCKET_EVENT_TYPES,
    WS_DELTA_SECTIONS,
    build_delta_ws_message,
    build_delta_ws_messages,
    build_heartbeat_ws_message,
    build_initial_ws_message,
    is_stale_ws_message,
)


def test_dashboard_state_to_dict_is_json_safe_and_redacted() -> None:
    state = DashboardState(session_id="TEST-SESSION", user_id="00017")
    state.last_scan_results["account_summary"] = {
        "cash_balance": Decimal("1234.56"),
        "api_key": "SHOULD_NOT_LEAK",
        "nested": {
            "token": "SHOULD_NOT_LEAK",
            "safe_value": Decimal("7.25"),
        },
    }

    payload = state.to_dict()
    encoded = json.dumps(payload)

    assert payload["payload_version"] == "1.0.0"
    assert payload["payload_schema"] == "css.dashboard.frontend.v1"
    assert payload["session_identifier"] == "TEST-SESSION"
    assert payload["source_metadata"]["secrets_redacted"] is True
    assert payload["account_summary"]["cash_balance"] == "1234.56"
    assert payload["account_summary"]["api_key"] == "REDACTED"
    assert payload["account_summary"]["nested"]["token"] == "REDACTED"
    assert "SHOULD_NOT_LEAK" not in encoded


def test_frontend_payload_schema_integrity_and_size() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())

    started = time.perf_counter()
    payload = build_frontend_payload(state)
    elapsed_ms = (time.perf_counter() - started) * 1000
    encoded = json.dumps(payload)

    assert elapsed_ms < 100.0
    assert len(encoded.encode("utf-8")) < 65536
    assert payload["payload_schema"] == "css.frontend.contract.v1"
    assert set(FRONTEND_SECTIONS) <= set(payload["sections"])
    assert payload["sections"]["account_summary"]["currency"] == "USD"
    assert payload["sections"]["positions"]["total"] == 2
    assert payload["sections"]["positions"]["items"][0]["symbol"] == "BTC-USD"
    assert payload["sections"]["positions"]["long_count"] == 1
    assert payload["sections"]["positions"]["short_count"] == 1
    assert payload["sections"]["risk"]["risk_state"] == "NORMAL"
    assert payload["sections"]["governance"]["governance_enabled"] is True
    assert payload["sections"]["execution"]["execution_state"] == "READY"
    assert payload["sections"]["execution"]["recent_trade_count"] == 2
    assert payload["sections"]["execution"]["recent_trades"][0]["symbol"] == "BTC-USD"
    assert payload["sections"]["opportunities"]["count"] == 2
    assert payload["sections"]["opportunities"]["items"][0]["status"] == "MONITOR_ONLY"


def test_api_bridge_routes_are_read_only_and_dashboard_state_fed() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    app = create_app(lambda: state)
    routes = {getattr(route, "path", "") for route in app.routes}

    required_routes = {
        "/api/v1/dashboard-state",
        "/api/v1/frontend-state",
        "/api/v1/account-summary",
        "/api/v1/positions",
        "/api/v1/risk",
        "/api/v1/governance",
        "/api/v1/opportunities",
        "/api/v1/broker",
        "/api/v1/broker-reconciliation",
        "/api/v1/alerts",
        "/api/v1/coinbase-micro-live-dry-run-probe",
        "/api/v1/micro-live-broker-readiness-confirmation",
        "/api/v1/micro-live-operator-approval-gate",
        "/api/v1/micro-live-pilot-order-intent",
        "/api/v1/micro-live-pilot-readiness",
        "/api/v1/runtime-events",
        "/api/v1/runtime-event-persistence-checklist",
        "/api/v1/runtime-event-persistence-checklist-export",
        "/api/v1/runtime-event-persistence-policy",
        "/api/v1/runtime-event-persistence-report",
        "/api/v1/runtime-event-persistence-sim",
        "/api/v1/runtime-event-persistence-scenarios",
        "/api/v1/deployment-profiles",
        "/api/v1/trade-lifecycle-replay",
        "/ws/v1/dashboard-state",
    }

    assert required_routes <= routes
    assert get_dashboard_state_payload(lambda: state)["session_id"] == "SMOKE-SESSION"
    assert get_frontend_payload(lambda: state)["sections"]["positions"]["total"] == 2
    assert (
        get_frontend_payload(lambda: state)["sections"]["broker_reconciliation"]["status"]
        == "BROKER_UNAVAILABLE"
    )
    assert get_alert_payload(lambda: state)["payload_version"] == ALERT_PAYLOAD_VERSION
    assert get_runtime_events_payload()["read_only"] is True
    assert (
        get_runtime_event_persistence_policy_inspection_payload()["persistence_enabled"]
        is False
    )
    assert get_runtime_event_persistence_sim_payload()["simulation_only"] is True
    assert get_runtime_event_persistence_sim_payload()["persistence_enabled"] is False
    assert (
        get_runtime_event_persistence_scenarios_payload()["persistence_enabled"]
        is False
    )
    assert get_runtime_event_persistence_report_payload()["simulation_only"] is True
    assert get_runtime_event_persistence_report_payload()["persistence_enabled"] is False
    assert (
        get_runtime_event_persistence_checklist_payload()["persistence_enabled"]
        is False
    )
    assert (
        get_runtime_event_persistence_checklist_export_payload()["persistence_enabled"]
        is False
    )
    assert (
        get_micro_live_pilot_readiness_payload(lambda: state)[
            "automatic_live_execution_enabled"
        ]
        is False
    )
    assert get_micro_live_pilot_order_intent_payload()["execution_allowed"] is False
    assert (
        get_coinbase_micro_live_dry_run_probe_payload()["order_submit_allowed"]
        is False
    )
    assert (
        get_coinbase_micro_live_dry_run_probe_payload()["broker_mutation_allowed"]
        is False
    )
    assert (
        get_micro_live_operator_approval_gate_payload(lambda: state)[
            "operator_approval_granted"
        ]
        is False
    )
    assert (
        get_micro_live_operator_approval_gate_payload(lambda: state)["trading_armed"]
        is False
    )
    assert (
        get_micro_live_broker_readiness_confirmation_payload(lambda: state)[
            "order_submit_allowed"
        ]
        is False
    )
    assert (
        get_micro_live_broker_readiness_confirmation_payload(lambda: state)[
            "broker_mutation_allowed"
        ]
        is False
    )
    assert build_section_payload(state, "risk")["data"]["risk_state"] == "NORMAL"


def test_missing_fields_use_frontend_safe_defaults() -> None:
    payload = build_frontend_payload({})

    assert payload["sections"]["account_summary"]["currency"] == "USD"
    assert payload["sections"]["positions"]["total"] == 0
    assert payload["sections"]["risk"]["gate_status"] == "OPEN"
    assert payload["sections"]["governance"]["audit_enabled"] is True
    assert payload["sections"]["market"]["trend_state"] == "UNKNOWN"
    assert payload["sections"]["execution"]["execution_state"] == "IDLE"
    assert json.dumps(payload)


def test_websocket_snapshot_delta_and_heartbeat_payloads_are_stable() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    initial = build_initial_ws_message(state, sequence=1)

    updated = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    updated.last_scan_results["pnl_summary"] = {
        **updated.last_scan_results["pnl_summary"],
        "net_pnl": 99.25,
    }

    delta = build_delta_ws_message(initial, updated, sequence=2)
    typed_deltas = build_delta_ws_messages(initial, updated, sequence=4)
    heartbeat = build_heartbeat_ws_message(sequence=3)

    assert initial["message_type"] == "dashboard_snapshot"
    assert delta["message_type"] == "dashboard_delta"
    assert "pnl_summary" in delta["changed_sections"]
    assert set(delta["changed_sections"]) <= set(WS_DELTA_SECTIONS)
    assert any(message["message_type"] == "pnl_update" for message in typed_deltas)
    assert all(message["message_type"] != "dashboard_delta" for message in typed_deltas)
    assert {message["message_type"] for message in typed_deltas} <= WEBSOCKET_EVENT_TYPES
    assert is_stale_ws_message({"sequence": 1}, last_sequence=1) is True
    assert is_stale_ws_message({"sequence": 2}, last_sequence=1) is False
    assert heartbeat["message_type"] == "dashboard_heartbeat"
    assert heartbeat["changed_sections"] == []
    assert json.dumps(initial)
    assert json.dumps(delta)
    assert json.dumps(heartbeat)


def test_live_dashboard_separated_trade_helpers_preserve_formulas() -> None:
    allowed, composite, threshold = profitability_allows(
        engine_mode="BALANCED",
        signal_score=15.0,
        probability=0.2,
    )

    assert allowed is True
    assert composite == 16.0
    assert threshold == 15.8
    assert evaluate_exit_signal({"entry_price": 100, "current_price": 101.2}) == "RUNNER"
    assert evaluate_exit_signal({"entry_price": 100, "current_price": 98.9}) == "STOP_LOSS"
    assert format_option_symbol("SPY-C") == "SPY-C-500"
    assert format_option_symbol("SPY-C-500") == "SPY-C-500"


def test_execution_boundary_fails_closed_for_live_simulated_capital() -> None:
    dominance = resolve_mode_dominance(global_mode="live", selected_mode="paper")
    boundary = validate_execution_boundary(
        selected_mode="live",
        capital_source_label="SIMULATED",
    )

    assert dominance.corrected is True
    assert dominance.selected_mode == "live"
    assert boundary.allowed is False
    assert boundary.reason == "live_mode_cannot_use_simulated_capital"


def test_alerting_and_deployment_profiles_are_frontend_safe() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    payload = build_frontend_payload(state)
    payload["sections"]["broker"] = {
        **payload["sections"]["broker"],
        "connected": False,
        "missing_credentials": True,
    }
    payload["sections"]["risk"] = {
        **payload["sections"]["risk"],
        "risk_limits_breached": ["daily_loss_limit"],
    }

    alerts = build_alert_payload(payload)
    profiles = get_deployment_profiles()
    production = validate_deployment_environment(
        "production",
        {
            "tls_enabled": True,
            "persistent_sessions": True,
            "db_users": True,
            "kill_switch_available": True,
        },
    )

    assert alerts["payload_version"] == ALERT_PAYLOAD_VERSION
    assert alerts["alert_count"] >= 2
    assert profiles["payload_version"] == DEPLOYMENT_PROFILE_VERSION
    assert "production" in profiles["profiles"]
    assert production["ready"] is True
    assert validate_deployment_environment("production", {})["fail_closed"] is True


def test_persistent_session_store_hashes_tokens_and_restores_sessions(tmp_path) -> None:
    store_path = tmp_path / "sessions.json"
    store = PersistentSessionStore(store_path, max_age_seconds=3600)
    token = "clear-token"
    session = {"created": time.time(), "last_activity": time.time(), "user_ctx": {"user_id": "00017"}}

    store.save(token, session)
    raw = store_path.read_text(encoding="utf-8")
    restored = store.get(token)

    assert "clear-token" not in raw
    assert restored is not None
    assert restored["user_ctx"]["user_id"] == "00017"
    assert store.touch(token) is not None
    store.revoke(token)
    assert store.get(token) is None


def test_live_dashboard_runtime_state_helpers_aggregate_positions() -> None:
    asset_pnls = build_asset_pnl_maps(["BTC-USD"], ["EUR_USD"], ["SPY-C"], ["ES"])
    asset_pnls["CRYPTO"]["BTC-USD"] = 1.25
    asset_pnls["FX"]["EUR_USD"] = -0.25

    class CapitalGovernor:
        def allocate_trade(self, _position_id: str) -> bool:
            return True

    cluster_amplifier = MomentumClusterAmplifier()
    cluster_risk_governor = ClusterSaturationRiskGovernor()
    mtm_engine = MarkToMarketEngine(
        cluster_amplifier=cluster_amplifier,
        cluster_risk_governor=cluster_risk_governor,
        capital_governor=CapitalGovernor(),
        price_provider=lambda _symbol, fallback=100.0: fallback,
        session_context_provider=lambda: {
            "user_id": "00017",
            "role": "TRADER",
            "session_id": "SESSION-17",
        },
    )

    position = mtm_engine.register_position(
        "CRYPTO",
        "BTC-USD",
        12.0,
        0.7,
        allow_live_funding=True,
    )
    position["floating"] = 2.5
    summary = build_cycle_runtime_summary(asset_pnls, mtm_engine)

    assert runtime_total_realized_pnl(asset_pnls) == 1.0
    assert runtime_pnl_dict_for_asset(asset_pnls, "CRYPTO")["BTC-USD"] == 1.25
    assert summary["open_positions"] == 1
    assert summary["broker_test_positions"] == 1
    assert summary["mtm_unrealized"] == 2.5
    assert summary["display_by_asset"]["CRYPTO"] == 2.5
    assert summary["realized_by_asset"]["FX"] == -0.25
    assert position["cluster_name"] == "CRYPTO_CORE"
    assert position["session_user_id"] == "00017"
    assert position["session_role"] == "TRADER"


def test_session_recovery_engine_uses_context_provider(tmp_path) -> None:
    state_path = tmp_path / "session_state.json"
    recovery = SessionRecoveryEngine(
        state_path,
        context_provider=lambda: {
            "session_user_ctx": {"user_id": "00017"},
            "selected_broker": "COINBASE",
            "selected_broker_mode": "paper",
            "engine_mode": "SAFE",
            "session_lock_state": {"locked": False},
        },
    )

    recovery.save_state(
        cycle=3,
        crypto_pnl={"BTC-USD": 1.0},
        fx_pnl={},
        options_pnl={},
        futures_pnl={},
        last_trade="BTC-USD PAPER_OPENED",
        position_counter=7,
    )
    restored = recovery.load_state()

    assert restored is not None
    assert restored["cycle"] == 3
    assert restored["session_user_ctx"]["user_id"] == "00017"
    assert restored["selected_broker"] == "COINBASE"
    assert restored["selected_broker_mode"] == "paper"
    assert restored["position_counter"] == 7
    assert SessionRecoveryEngine(state_path, reset_on_boot=True).load_state() is None


def test_smart_drift_engine_is_deterministic_with_injected_rng() -> None:
    class FixedRng:
        def uniform(self, lo: float, _hi: float) -> float:
            return lo

    drift_engine = SmartDriftEngine({"CRYPTO": (-0.05, 0.1)}, rng=FixedRng())
    drift = drift_engine.generate_drift(
        {
            "asset_class": "CRYPTO",
            "signal_score": 12.0,
            "prob_positive": 0.75,
        }
    )

    assert drift == -0.022


def test_trade_lifecycle_service_books_position_exit_and_payloads() -> None:
    asset_pnls = {"CRYPTO": {"BTC-USD": 0.0}}
    audit_events = []

    class PnLTracker:
        def __init__(self) -> None:
            self.records = []

        def record_trade(self, **kwargs) -> None:
            self.records.append(kwargs)

    class CapitalTracker:
        def __init__(self) -> None:
            self.released = []

        def release_trade(self, position_id: str) -> None:
            self.released.append(position_id)

    class ClusterRisk:
        def __init__(self) -> None:
            self.released = []

        def release_cluster_slot(self, cluster_name: str) -> None:
            self.released.append(cluster_name)

    class ClusterAmplifier:
        def __init__(self) -> None:
            self.wins = []

        def record_cluster_win(self, symbol: str, pnl: float) -> None:
            self.wins.append((symbol, pnl))

    class LockedProfitLedger:
        def __init__(self) -> None:
            self.forced = []
            self.priority = 0
            self.defensive = 0
            self.recycled = 0

        def record_forced_exit(self, position_id: str, amount: float) -> None:
            self.forced.append((position_id, amount))

        def record_priority_exit(self) -> None:
            self.priority += 1

        def record_defensive_reduction_exit(self) -> None:
            self.defensive += 1

        def record_recycled_slot(self) -> None:
            self.recycled += 1

    pnl_tracker = PnLTracker()
    capital_tracker = CapitalTracker()
    cluster_risk = ClusterRisk()
    cluster_amplifier = ClusterAmplifier()
    locked_profit = LockedProfitLedger()
    service = TradeLifecycleExecutionStateService(
        pnl_tracker=pnl_tracker,
        capital_tracker=capital_tracker,
        pnl_dict_provider=lambda asset_class: asset_pnls[asset_class],
        cluster_amplifier=cluster_amplifier,
        cluster_risk_governor=cluster_risk,
        locked_profit_ledger=locked_profit,
        session_context_provider=lambda: {
            "user_id": "00017",
            "role": "TRADER",
            "session_id": "SESSION-17",
        },
        mode_provider=lambda: "paper",
        audit_recorder=audit_events.append,
    )
    position = {
        "position_id": "POS-1",
        "asset_class": "CRYPTO",
        "symbol": "BTC-USD",
        "cluster_name": "CRYPTO_CORE",
        "floating": -1.23456,
        "forced_exit": False,
        "broker_tested": True,
        "broker_order_ok": False,
    }

    result = service.book_position_exit(position, "STOP")
    payload = result.as_dict()

    assert result.booked is True
    assert result.status == "EXIT_BOOKED"
    assert result.classification == "FORCED_EXIT"
    assert result.last_trade == "BTC-USD EXIT STOP -1.2346"
    assert position["forced_exit"] is True
    assert position["exit_reason"] == "STOP"
    assert asset_pnls["CRYPTO"]["BTC-USD"] == -1.2346
    assert pnl_tracker.records[0]["realized_pnl"] == -1.2346
    assert capital_tracker.released == ["POS-1"]
    assert cluster_risk.released == ["CRYPTO_CORE"]
    assert cluster_amplifier.wins == [("BTC-USD", -1.2346)]
    assert locked_profit.forced == [("POS-1", -1.2346)]
    assert locked_profit.recycled == 1
    assert audit_events[0]["payload_version"] == TRADE_LIFECYCLE_SERVICE_VERSION
    assert payload["replay_payload"]["event_type"] == "trade_exit_replay_event"
    assert json.dumps(payload)


def test_trade_lifecycle_service_execute_exit_preserves_observer_and_capital_release() -> None:
    class PnLTracker:
        def record_trade(self, **_kwargs) -> None:
            return None

    class CapitalTracker:
        def __init__(self) -> None:
            self.released = []

        def release_trade(self, position_id: str) -> None:
            self.released.append(position_id)

    class NoopCluster:
        def release_cluster_slot(self, _cluster_name: str) -> None:
            return None

        def record_cluster_win(self, _symbol: str, _pnl: float) -> None:
            return None

    class LockedProfitLedger:
        def record_forced_exit(self, _position_id: str, _amount: float) -> None:
            return None

        def record_priority_exit(self) -> None:
            return None

        def record_defensive_reduction_exit(self) -> None:
            return None

        def record_recycled_slot(self) -> None:
            return None

    class Observer:
        def __init__(self) -> None:
            self.closed = []

        def close_position(self, symbol: str, price: float) -> float:
            self.closed.append((symbol, price))
            return 1.0

    capital_tracker = CapitalTracker()
    service = TradeLifecycleExecutionStateService(
        pnl_tracker=PnLTracker(),
        capital_tracker=capital_tracker,
        pnl_dict_provider=lambda _asset_class: {"BTC-USD": 0.0},
        cluster_amplifier=NoopCluster(),
        cluster_risk_governor=NoopCluster(),
        locked_profit_ledger=LockedProfitLedger(),
    )
    observer = Observer()
    position = {
        "position_id": "POS-2",
        "asset_class": "CRYPTO",
        "symbol": "BTC-USD",
        "cluster_name": "CRYPTO_CORE",
        "floating": 2.0,
        "forced_exit": False,
        "broker_tested": True,
        "broker_order_ok": False,
    }

    result = service.execute_exit(
        position,
        observer_symbol="POS-2::BTC-USD",
        observer_price=102.0,
        reason="TAKE_PROFIT",
        pnl_observer=observer,
    )

    assert result.booked is True
    assert result.classification == "PRIORITY_EXIT"
    assert observer.closed == [("POS-2::BTC-USD", 102.0)]
    assert capital_tracker.released == ["POS-2", "POS-2"]
    assert classify_exit_reason("DEFENSIVE_REDUCTION") == "DEFENSIVE_REDUCTION"


def test_trade_lifecycle_service_applies_defensive_reduction_order() -> None:
    class Noop:
        def record_trade(self, **_kwargs) -> None:
            return None

        def release_trade(self, _position_id: str) -> None:
            return None

        def release_cluster_slot(self, _cluster_name: str) -> None:
            return None

        def record_cluster_win(self, _symbol: str, _pnl: float) -> None:
            return None

        def record_forced_exit(self, _position_id: str, _amount: float) -> None:
            return None

        def record_priority_exit(self) -> None:
            return None

        def record_defensive_reduction_exit(self) -> None:
            return None

        def record_recycled_slot(self) -> None:
            return None

    asset_pnls = {"FX": {"EUR_USD": 0.0, "GBP_USD": 0.0}}
    service = TradeLifecycleExecutionStateService(
        pnl_tracker=Noop(),
        capital_tracker=Noop(),
        pnl_dict_provider=lambda asset_class: asset_pnls[asset_class],
        cluster_amplifier=Noop(),
        cluster_risk_governor=Noop(),
        locked_profit_ledger=Noop(),
    )
    positions = [
        {
            "position_id": "POS-1",
            "asset_class": "FX",
            "symbol": "EUR_USD",
            "cluster_name": "FX_MAJOR",
            "floating": 1.0,
            "age_cycles": 4,
            "forced_exit": False,
            "broker_order_ok": False,
        },
        {
            "position_id": "POS-2",
            "asset_class": "FX",
            "symbol": "GBP_USD",
            "cluster_name": "FX_MAJOR",
            "floating": -2.0,
            "age_cycles": 1,
            "forced_exit": False,
            "broker_order_ok": False,
        },
    ]

    result = service.apply_defensive_exposure_reduction(
        positions=positions,
        is_session_locked=lambda: True,
        limit=1,
    )

    assert result.reductions == 1
    assert result.last_trade == "GBP_USD EXIT DEFENSIVE_REDUCTION -2.0000"
    assert positions[0]["forced_exit"] is False
    assert positions[1]["forced_exit"] is True
    assert asset_pnls["FX"]["GBP_USD"] == -2.0


def test_trade_lifecycle_replay_sink_persists_jsonl_and_redacts(tmp_path) -> None:
    sink_path = tmp_path / "trade_lifecycle_replay.jsonl"
    sink = TradeLifecycleReplaySink(sink_path)

    result = sink.record(
        {
            "event_type": "position_exit_booked",
            "position_id": "POS-1",
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "mode": "paper",
            "session_id": "SESSION-17",
            "realized_pnl": Decimal("1.25"),
            "api_secret": "do-not-export",
        }
    )
    events = load_trade_lifecycle_replay_events(sink_path)
    serialized = sink_path.read_text(encoding="utf-8")

    assert result["ok"] is True
    assert len(events) == 1
    assert events[0]["sink_payload_version"] == TRADE_LIFECYCLE_REPLAY_SINK_VERSION
    assert events[0]["event_type"] == "position_exit_booked"
    assert events[0]["payload"]["realized_pnl"] == "1.25"
    assert "do-not-export" not in serialized
    assert "REDACTED" in serialized


def test_trade_lifecycle_replay_sink_non_strict_failure_does_not_raise(tmp_path) -> None:
    sink = TradeLifecycleReplaySink(tmp_path)

    result = sink.record({"event_type": "position_exit_booked", "position_id": "POS-FAIL"})

    assert result["ok"] is False
    assert "error" in result


def test_trade_lifecycle_replay_sink_strict_failure_raises(tmp_path) -> None:
    sink = TradeLifecycleReplaySink(tmp_path, strict=True)

    with pytest.raises(TradeLifecycleReplaySinkError):
        sink.record({"event_type": "position_exit_booked", "position_id": "POS-FAIL"})


def test_trade_lifecycle_service_writes_named_replay_events(tmp_path) -> None:
    class Noop:
        def record_trade(self, **_kwargs) -> None:
            return None

        def release_trade(self, _position_id: str) -> None:
            return None

        def release_cluster_slot(self, _cluster_name: str) -> None:
            return None

        def record_cluster_win(self, _symbol: str, _pnl: float) -> None:
            return None

        def record_forced_exit(self, _position_id: str, _amount: float) -> None:
            return None

        def record_priority_exit(self) -> None:
            return None

        def record_defensive_reduction_exit(self) -> None:
            return None

        def record_recycled_slot(self) -> None:
            return None

    sink_path = tmp_path / "lifecycle_replay.jsonl"
    sink = TradeLifecycleReplaySink(sink_path)
    asset_pnls = {"FX": {"EUR_USD": 0.0}}
    service = TradeLifecycleExecutionStateService(
        pnl_tracker=Noop(),
        capital_tracker=Noop(),
        pnl_dict_provider=lambda asset_class: asset_pnls[asset_class],
        cluster_amplifier=Noop(),
        cluster_risk_governor=Noop(),
        locked_profit_ledger=Noop(),
        session_context_provider=lambda: {
            "user_id": "00017",
            "role": "TRADER",
            "session_id": "SESSION-17",
        },
        mode_provider=lambda: "paper",
        replay_recorder=sink.record,
    )
    position = {
        "position_id": "POS-9",
        "asset_class": "FX",
        "symbol": "EUR_USD",
        "cluster_name": "FX_MAJOR",
        "floating": -2.5,
        "age_cycles": 5,
        "forced_exit": False,
        "broker_tested": True,
        "broker_order_ok": False,
    }

    result = service.book_position_exit(position, "DEFENSIVE_REDUCTION")
    events = load_trade_lifecycle_replay_events(sink_path)
    event_types = {event["event_type"] for event in events}

    assert result.booked is True
    assert len(result.replay_events) == 6
    assert {
        "position_exit_booked",
        "defensive_reduction_applied",
        "realized_pnl_handoff",
        "capital_released",
        "locked_profit_updated",
        "lifecycle_audit_payload_created",
    } <= event_types
    assert all(event["schema_version"] == "css.replay_event_envelope.v1" for event in events)
    assert len({event["correlation_id"] for event in events}) == 1
    assert all(event["payload"]["payload"]["session_id"] == "SESSION-17" for event in events)
    assert json.dumps([event["payload"] for event in events], sort_keys=True)


def test_trade_lifecycle_service_non_strict_replay_failure_keeps_booking(tmp_path) -> None:
    class Noop:
        def __init__(self) -> None:
            self.released = []

        def record_trade(self, **_kwargs) -> None:
            return None

        def release_trade(self, position_id: str) -> None:
            self.released.append(position_id)

        def release_cluster_slot(self, _cluster_name: str) -> None:
            return None

        def record_cluster_win(self, _symbol: str, _pnl: float) -> None:
            return None

        def record_forced_exit(self, _position_id: str, _amount: float) -> None:
            return None

        def record_priority_exit(self) -> None:
            return None

        def record_defensive_reduction_exit(self) -> None:
            return None

        def record_recycled_slot(self) -> None:
            return None

    sink = TradeLifecycleReplaySink(tmp_path, strict=True)
    asset_pnls = {"CRYPTO": {"BTC-USD": 0.0}}
    log_messages = []
    service = TradeLifecycleExecutionStateService(
        pnl_tracker=Noop(),
        capital_tracker=Noop(),
        pnl_dict_provider=lambda asset_class: asset_pnls[asset_class],
        cluster_amplifier=Noop(),
        cluster_risk_governor=Noop(),
        locked_profit_ledger=Noop(),
        replay_recorder=sink.record,
        logger=log_messages.append,
    )
    position = {
        "position_id": "POS-10",
        "asset_class": "CRYPTO",
        "symbol": "BTC-USD",
        "cluster_name": "CRYPTO_CORE",
        "floating": 1.0,
        "forced_exit": False,
        "broker_tested": False,
        "broker_order_ok": False,
    }

    result = service.book_position_exit(position, "TAKE_PROFIT")

    assert result.booked is True
    assert position["forced_exit"] is True
    assert asset_pnls["CRYPTO"]["BTC-USD"] == 1.0
    assert any("Replay handoff failed" in message for message in log_messages)
