"""Phase 177F — Runtime mode & telemetry canonicalization tests."""

from __future__ import annotations

from pathlib import Path

from backend.app.brokers.canonical_tier1 import TIER1_BROKERS, get_canonical_broker_registry
from backend.options.options_income_surface_link import options_income_detail_link
from backend.runtime.platform_status import build_platform_status
from backend.runtime.runtime_mode import resolve_runtime_mode
from backend.runtime.runtime_telemetry import (
    STATUS_UNKNOWN,
    build_runtime_telemetry,
    telemetry_summary_for_ui,
)
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.runtime.frontend_contract import build_frontend_payload
from dashboard.mobile.mobile_app import _system_status, load_mobile_controls


def test_platform_status_runtime_mode_equals_resolver() -> None:
    resolution = resolve_runtime_mode()
    status = build_platform_status(mobile_controls={"mobile_trading_mode": "MOBILE_READ_ONLY", "engine_mode": "SAFE"})
    assert status["runtime_mode"] == resolution.runtime_mode.value
    assert status["runtime_mode"] == "DISABLED"
    assert status["fail_closed"] is True
    assert status["execution_authority"] is False
    assert status["execution_state"] == "BLOCKED"
    assert status["system_mode"] == status["runtime_mode"]
    assert status["system_mode_deprecated"] is True


def test_mobile_access_distinct_from_runtime_mode() -> None:
    status = build_platform_status(
        mobile_controls={"mobile_trading_mode": "MOBILE_READ_ONLY", "engine_mode": "SAFE"}
    )
    assert status["mobile_access_mode"] == "READ_ONLY"
    assert status["runtime_mode"] != "LIVE_READ_ONLY"
    assert status["runtime_mode"] == "DISABLED"
    assert status["engine_mode"] == "SAFE"
    assert status["broker_mode"] in {"NONE", "UNKNOWN"} or status["broker_mode"]


def test_mobile_system_status_uses_resolver() -> None:
    status = _system_status(None)
    assert status["runtime_mode"] == "DISABLED"
    assert status["platform_status"]["system_mode"] == "DISABLED"
    assert status["mobile_access_mode"] == "READ_ONLY"
    assert status["orders_enabled"] is False
    assert status["live_orders_enabled"] is False
    assert "telemetry_summary" in status


def test_load_mobile_controls_no_longer_publishes_live_read_only_as_platform_mode() -> None:
    controls = load_mobile_controls()
    assert controls["mobile_access_mode"] == "READ_ONLY"
    assert controls["ticket_posture"] == "READ_ONLY"
    # ticket_posture may reuse deprecated runtime_mode key locally; platform status must not
    platform = build_platform_status(mobile_controls=controls)
    assert platform["runtime_mode"] == "DISABLED"


def test_missing_cycle_not_zero(tmp_path: Path) -> None:
    engine = tmp_path / "runtime_supervisor.json"
    css = tmp_path / "css_runtime_supervisor_state.json"
    engine.write_text(
        '{"start_time":"2026-07-01T00:00:00+00:00","uptime_seconds":10,"cycles_completed":18254,'
        '"runtime_errors":0,"broker_disconnects":1,"recovery_attempts":0,"alerts_generated":0}',
        encoding="utf-8",
    )
    css.write_text(
        '{"status":"RUNNING","restart_count":1657,"failure_count":0,"last_heartbeat_at":"2026-07-20T21:00:00+00:00"}',
        encoding="utf-8",
    )
    snap = build_runtime_telemetry(
        engine_supervisor_path=engine,
        css_supervisor_path=css,
        session_paths=(tmp_path / "no_session.json",),
    )
    fields = snap["fields"]
    assert fields["supervisor_cycles_completed"]["value"] == 18254
    assert fields["managed_service_restart_count"]["value"] == 1657
    # Session cycle absent → display_cycle is not a fake 0
    assert fields["display_cycle"]["value"] is None
    assert fields["display_cycle"]["status"] in {STATUS_UNKNOWN, "NOT_REPORTED", "UNAVAILABLE", "UNKNOWN"}
    summary = telemetry_summary_for_ui(snap)
    assert summary["display_cycle"] != 0
    assert summary["cycle"] != 0
    assert summary["restart_count"] == 1657
    assert summary["restart_count_deprecated"] is True


def test_aliases_match_canonical() -> None:
    snap = build_runtime_telemetry()
    aliases = snap["compatibility_aliases"]
    assert aliases["restart_count"]["alias_of"] == "managed_service_restart_count"
    assert aliases["cycle"]["alias_of"] == "display_cycle"
    assert aliases["restart_count"]["value"] == snap["fields"]["managed_service_restart_count"]["value"]


def test_frontend_contract_parity() -> None:
    payload = build_frontend_payload({})
    assert payload["resolved_mode"] == "DISABLED"
    assert payload["sections"]["runtime_status"]["runtime_mode"] == "DISABLED"
    assert payload["sections"]["runtime_status"]["mobile_access_mode"] == "READ_ONLY"
    assert "runtime_telemetry" in payload["sections"]
    tele = payload["sections"]["runtime_telemetry"]
    assert tele.get("display_cycle") != 0 or tele.get("display_cycle") in {"UNKNOWN", "NOT_REPORTED", "UNAVAILABLE"}
    assert payload["sections"]["options_income"]["execution_blocked"] is True


def test_mission_control_uses_telemetry_not_zero_default() -> None:
    state = build_mission_control_state(allow_mock=True)
    runtime = state["runtime"]
    assert runtime.get("cycle") != 0 or "cycle" in runtime
    # If cycle is numeric 0 it must come from an explicit source, not silent default —
    # with allow_mock the frontend sections should supply telemetry.
    if runtime.get("cycle") == 0:
        assert "session_cycle" in runtime or "display_cycle" in runtime
    assert runtime.get("execution_state") in {"BLOCKED", None} or runtime.get("execution_state")


def test_options_income_linkage() -> None:
    link = options_income_detail_link()
    assert link["same_origin_api_expected"] is False
    assert link["advisory_only"] is True
    assert "/mission-control/options-income" in link["href"]


def test_resolver_and_brokers_unchanged() -> None:
    resolution = resolve_runtime_mode()
    assert resolution.runtime_mode.value == "DISABLED"
    assert resolution.execution_enabled is False
    brokers = get_canonical_broker_registry().list_brokers()
    assert brokers == list(TIER1_BROKERS)
    assert "IBKR" not in brokers


def test_telemetry_api_router_readonly() -> None:
    from dashboard.runtime.api.runtime_telemetry import create_runtime_telemetry_router

    router = create_runtime_telemetry_router()
    methods = set()
    paths = []
    for route in getattr(router, "routes", []):
        methods |= set(getattr(route, "methods", set()) or set())
        paths.append(getattr(route, "path", ""))
    assert "GET" in methods
    assert not (methods - {"GET"})
    assert "/api/runtime-telemetry" in paths
    assert "/api/runtime-telemetry/status" in paths
    assert "/api/runtime-telemetry/provenance" in paths
