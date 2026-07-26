from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.routes import create_mission_control_router
from dashboard.mission_control.runtime_snapshot_provider import RuntimeSnapshotProvider
from dashboard.mission_control.runtime_source_resolver import RuntimeSourceResolver
from dashboard.runtime.frontend_contract import build_frontend_payload
from launcher import css_mobile_launcher


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _artifact_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    artifacts = tmp_path / "artifacts"
    supervisor_path = tmp_path / "runtime" / "supervisor" / "css_runtime_supervisor_state.json"
    heartbeat = datetime.now(timezone.utc).isoformat()
    _write_json(
        supervisor_path,
        {
            "status": "RUNNING",
            "last_heartbeat_at": heartbeat,
            "restart_count": 0,
            "failure_count": 0,
            "recovery_count": 0,
        },
    )
    _write_json(
        artifacts / "css_session_state_pcnrass.json",
        {
            "session": {
                "session_id": "desktop-runtime-session",
                "cycle_number": 19,
                "engine_mode": "SAFE",
                "resolved_mode": "paper",
                "selected_broker": "COINBASE",
                "broker_mode": "paper",
                "broker_execution_armed": False,
            }
        },
    )
    _write_json(
        artifacts / "css_account_state_pcnrass.json",
        {
            "account_balance": 1000.0,
            "total_equity": 1005.5,
            "buying_power": 990.0,
            "unrealized_pnl": 5.5,
            "lifetime_realized_pnl": 0.0,
            "selected_broker": "COINBASE",
            "broker_execution_armed": False,
        },
    )
    _write_json(
        artifacts / "runtime_portfolio_state.json",
        {
            "status": "OK",
            "account": {
                "cash": 1000.0,
                "equity": 1005.5,
                "buying_power": 990.0,
                "open_pnl": 5.5,
                "realized_pnl": 0.0,
                "total_pnl": 5.5,
            },
            "positions": [],
            "runtime_cycle": 19,
            "selected_broker": "COINBASE",
            "broker_mode": "paper",
            "advisory_only": True,
            "execution_allowed": False,
        },
    )
    return artifacts, supervisor_path, heartbeat


def test_mc004_resolver_binds_to_desktop_runtime_artifacts(tmp_path: Path) -> None:
    artifacts, supervisor_path, _ = _artifact_fixture(tmp_path)

    resolved = RuntimeSourceResolver(
        lambda: {"mission_control_data_source": "UNAVAILABLE"},
        artifact_root=artifacts,
        supervisor_state_path=supervisor_path,
    ).resolve()

    assert resolved["diagnostics"]["selected_source"] == "RUNTIME_ARTIFACT"
    assert resolved["diagnostics"]["process_boundary"] == "CROSS_PROCESS_FILE_ARTIFACT"
    assert resolved["payload"]["source"] == "RUNTIME_ARTIFACT"
    assert resolved["payload"]["execution_allowed"] is False
    assert resolved["payload"]["live_trading_blocked"] is True
    assert resolved["payload"]["broker_execution_armed"] is False
    assert resolved["payload"]["advisory_only"] is True


def test_mc004_provider_normalizes_active_artifact_snapshot(tmp_path: Path) -> None:
    artifacts, supervisor_path, _ = _artifact_fixture(tmp_path)

    state_payload = RuntimeSnapshotProvider(
        artifact_root=artifacts,
        supervisor_state_path=supervisor_path,
        active_source_binding=True,
    ).get_state_payload()
    snapshot = state_payload["runtime_snapshot"]

    assert snapshot["source"] == "RUNTIME_ARTIFACT"
    assert snapshot["runtime_id"] == "desktop-runtime-session"
    assert snapshot["runtime_status"] == "RUNNING"
    assert snapshot["portfolio"]["equity"] == 1005.5
    assert snapshot["source_diagnostics"]["selected_source"] == "RUNTIME_ARTIFACT"
    assert snapshot["execution_allowed"] is False
    assert snapshot["live_trading_blocked"] is True
    assert snapshot["broker_execution_armed"] is False


def test_mc004_in_process_launcher_callback_cannot_override_artifact_without_cross_process_registry(tmp_path: Path) -> None:
    artifacts, supervisor_path, _ = _artifact_fixture(tmp_path)
    callback_payload = build_frontend_payload({"session_id": "in-process-only", "generated_at": datetime.now(timezone.utc).isoformat()})
    callback_payload["mission_control_data_source"] = "RUNTIME"

    resolved = RuntimeSourceResolver(
        lambda: callback_payload,
        artifact_root=artifacts,
        supervisor_state_path=supervisor_path,
    ).resolve()
    diagnostics = resolved["diagnostics"]

    assert diagnostics["selected_source"] == "RUNTIME_ARTIFACT"
    registry = next(item for item in diagnostics["candidate_sources"] if item["source_type"] == "RUNTIME_REGISTRY")
    assert registry["available"] is False
    assert registry["failure"] == "registry_not_cross_process_safe"


def test_mc004_cross_process_registry_has_precedence_when_explicitly_safe(tmp_path: Path) -> None:
    artifacts, supervisor_path, _ = _artifact_fixture(tmp_path)
    registry_payload = build_frontend_payload({"session_id": "registry-session", "generated_at": datetime.now(timezone.utc).isoformat()})
    registry_payload["mission_control_runtime_registry_cross_process_safe"] = True
    registry_payload["mission_control_data_source"] = "RUNTIME"

    resolved = RuntimeSourceResolver(
        lambda: registry_payload,
        artifact_root=artifacts,
        supervisor_state_path=supervisor_path,
    ).resolve()

    assert resolved["diagnostics"]["selected_source"] == "RUNTIME_REGISTRY"
    assert resolved["payload"]["frontend_payload"]["session_id"] == "registry-session"


def test_mc004_endpoint_has_precedence_over_artifacts_when_configured(monkeypatch, tmp_path: Path) -> None:
    artifacts, supervisor_path, _ = _artifact_fixture(tmp_path)
    endpoint_payload = build_frontend_payload({"session_id": "endpoint-session", "generated_at": datetime.now(timezone.utc).isoformat()})

    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _: int) -> bytes:
            return json.dumps(endpoint_payload).encode("utf-8")

    monkeypatch.setattr("dashboard.mission_control.runtime_endpoint_reader.urlopen", lambda *args, **kwargs: _Response())

    resolved = RuntimeSourceResolver(
        artifact_root=artifacts,
        supervisor_state_path=supervisor_path,
        endpoint_url="http://127.0.0.1:8765",
    ).resolve()

    assert resolved["diagnostics"]["selected_source"] == "RUNTIME_ENDPOINT"
    assert resolved["payload"]["frontend_payload"]["session_id"] == "endpoint-session"


def test_mc004_missing_sources_fail_closed_unavailable(tmp_path: Path) -> None:
    state_payload = RuntimeSnapshotProvider(
        artifact_root=tmp_path / "missing-artifacts",
        supervisor_state_path=tmp_path / "missing-runtime" / "supervisor.json",
        active_source_binding=True,
    ).get_state_payload()
    snapshot = state_payload["runtime_snapshot"]

    assert snapshot["source"] == "UNAVAILABLE"
    assert snapshot["runtime_status"] == "OFFLINE"
    assert snapshot["execution_allowed"] is False
    assert snapshot["live_trading_blocked"] is True
    assert snapshot["broker_execution_armed"] is False
    assert snapshot["advisory_only"] is True
    assert snapshot["source_diagnostics"]["selected_available"] is False


def test_mc004_mission_control_state_and_runtime_source_api_share_snapshot(tmp_path: Path) -> None:
    artifacts, supervisor_path, _ = _artifact_fixture(tmp_path)
    provider = RuntimeSnapshotProvider(
        artifact_root=artifacts,
        supervisor_state_path=supervisor_path,
        active_source_binding=True,
    ).get_state_payload
    app = FastAPI()
    app.include_router(create_mission_control_router(provider))
    client = TestClient(app)

    state = client.get("/mission-control/api/state").json()
    runtime = client.get("/mission-control/api/runtime").json()
    source = client.get("/mission-control/api/runtime-source").json()
    heartbeat = client.get("/mission-control/api/heartbeat").json()

    assert runtime["state_hash"] == state["runtime_snapshot"]["state_hash"]
    assert source["state_hash"] == runtime["state_hash"]
    assert heartbeat["state_hash"] == runtime["state_hash"]
    assert source["diagnostics"]["selected_source"] == "RUNTIME_ARTIFACT"
    assert state["runtime"]["source"] == "RUNTIME_ARTIFACT"
    assert state["runtime"]["authoritative_source"] == "RUNTIME_ARTIFACT"
    assert state["runtime"]["selected_source"] == "RUNTIME_ARTIFACT"
    assert state["runtime"]["source_disagreement"] is False
    assert state["runtime"]["source_status"] in {"GREEN", "AMBER"}
    assert state["source_registry"]["runtime_snapshot"]["source"] == "RUNTIME_ARTIFACT"
    assert state["source_registry"]["runtime"]["source"] == "RUNTIME_ARTIFACT"


def test_mc004_source_disagreement_is_exposed_and_execution_blocked() -> None:
    state = build_mission_control_state(
        {
            "runtime_snapshot": {
                "source": "RUNTIME_ARTIFACT",
                "runtime_status": "RUNNING",
                "runtime_mode": "paper",
                "engine_mode": "SAFE",
                "source_diagnostics": {
                    "selected_source": "RUNTIME_ENDPOINT",
                    "selected_available": True,
                    "selected_freshness_status": "FRESH",
                    "candidate_sources": [
                        {"source_type": "RUNTIME_ENDPOINT", "available": True},
                        {"source_type": "RUNTIME_ARTIFACT", "available": True},
                    ],
                },
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
            }
        },
        allow_mock=False,
    )

    assert state["runtime"]["source"] == "RUNTIME_ENDPOINT"
    assert state["runtime"]["source_disagreement"] is True
    assert state["runtime"]["source_status"] == "AMBER"
    assert state["runtime"]["source_confidence"] == "MEDIUM"
    assert state["runtime"]["available_sources"] == ["RUNTIME_ENDPOINT", "RUNTIME_ARTIFACT"]
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True
    assert state["safety"]["broker_execution_armed"] is False


def test_mc004_stale_source_is_degraded_not_execution_ready() -> None:
    state = build_mission_control_state(
        {
            "runtime_snapshot": {
                "source": "RUNTIME_ARTIFACT",
                "runtime_status": "RUNNING",
                "runtime_mode": "paper",
                "engine_mode": "SAFE",
                "source_diagnostics": {
                    "selected_source": "RUNTIME_ARTIFACT",
                    "selected_available": True,
                    "selected_freshness_status": "STALE",
                    "candidate_sources": [
                        {"source_type": "RUNTIME_ARTIFACT", "available": True},
                    ],
                },
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
            }
        },
        allow_mock=False,
    )

    assert state["runtime"]["source"] == "RUNTIME_ARTIFACT"
    assert state["runtime"]["source_freshness"] == "STALE"
    assert state["runtime"]["source_status"] == "AMBER"
    assert state["runtime"]["source_confidence"] == "LOW"
    assert state["runtime"]["execution_state"] == "BLOCKED"
    assert state["safety"]["execution_allowed"] is False


def test_mc004_launcher_registration_exposes_runtime_source_route_read_only() -> None:
    client = TestClient(css_mobile_launcher.app)
    endpoints = (
        "/mission-control/api/runtime",
        "/mission-control/api/runtime-source",
    )

    for endpoint in endpoints:
        assert client.get(endpoint).status_code == 200
        for method in ("post", "put", "patch", "delete"):
            response = getattr(client, method)(endpoint)
            assert response.status_code in {404, 405}


def test_mc004_demo_payload_remains_isolated_from_active_runtime_binding() -> None:
    state = build_mission_control_state({"source": "DEMO", "mock_data": True}, allow_mock=False)

    assert state["mock_data"] is True
    assert state["runtime_snapshot"]["source"] != "RUNTIME_ARTIFACT"
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True
