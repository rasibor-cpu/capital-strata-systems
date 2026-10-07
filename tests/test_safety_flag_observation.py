import json
from unittest.mock import patch

import pytest

from backend.certification.css064_endurance_package import observe_safety_flags
from backend.certification.ov002_endurance_monitor import capture_safety_assertions
from backend.runtime.safety_flag_observation import derive_safety_flags

SAFE_RUNTIME = {"runtime_mode": "PAPER", "execution_enabled": False, "advisory_only": True, "fail_closed": True}
SAFE_AUTHORITY = {"execution_authority": False, "can_live_execute": False}


def derive(**kw):
    args = dict(runtime_mode=SAFE_RUNTIME, authority=SAFE_AUTHORITY,
                mobile_trading_mode="MOBILE_READ_ONLY", legacy_broker_execution_armed=None)
    args.update(kw)
    return derive_safety_flags(**args)


def test_safe_state_observed():
    flags = derive()
    assert flags["observed"] is True
    assert (flags["execution_allowed"], flags["live_trading_blocked"],
            flags["broker_execution_armed"], flags["advisory_only"]) == (False, True, False, True)


@pytest.mark.parametrize("override,flag,value", [
    ({"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"}, "broker_execution_armed", True),
    ({"legacy_broker_execution_armed": True}, "broker_execution_armed", True),
    ({"authority": {"can_live_execute": True}}, "execution_allowed", True),
    ({"runtime_mode": {**SAFE_RUNTIME, "runtime_mode": "LIVE_MICRO_PILOT"}}, "live_trading_blocked", False),
    ({"runtime_mode": {**SAFE_RUNTIME, "execution_enabled": True}}, "advisory_only", False),
    ({"runtime_mode": {k: v for k, v in SAFE_RUNTIME.items() if k != "advisory_only"}}, "advisory_only", False),
])
def test_live_signals_are_reported_not_masked(override, flag, value):
    assert derive(**override)[flag] is value


@pytest.mark.parametrize("override", [
    {"runtime_mode": None}, {"runtime_mode": {"advisory_only": True}}, {"authority": None},
    {"mobile_trading_mode": None}, {"mobile_trading_mode": " "},
    {"legacy_broker_execution_armed": "yes"},
])
def test_unreadable_source_means_not_observed(override):
    flags = derive(**override)
    assert flags["observed"] is False
    assert all(flags[name] is None for name in ("execution_allowed", "live_trading_blocked",
                                                 "broker_execution_armed", "advisory_only"))
    assert not observe_safety_flags({"/api/v1/live-execution-authority": {"safety_flags": flags}})["ok"]


@pytest.fixture
def launcher_client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    import launcher.css_mobile_launcher as launcher

    monkeypatch.setattr(launcher, "MOBILE_CONTROLS_FILE", str(tmp_path / "css_mobile_controls.json"))
    return launcher, TestClient(launcher.app), tmp_path


def _payloads(client):
    return {path: client.get(path).json()
            for path in ("/api/v1/safety-flags", "/api/runtime-mode", "/api/v1/live-execution-authority")}


EXPECTED_FIELDS = {"execution_allowed": False, "live_trading_blocked": True,
                   "broker_execution_armed": False, "advisory_only": True}


def test_authoritative_endpoint_returns_all_four_flags_exactly(launcher_client):
    _, client, _ = launcher_client
    response = client.get("/api/v1/safety-flags")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["schema"] == "css.safety_flags.v1"
    for name, value in EXPECTED_FIELDS.items():
        assert name in body and type(body[name]) is bool and body[name] is value
    assert body["verdict"] == "SAFE" and body["fail_closed"] is False
    assert body["not_observed"] == [] and body["unsafe"] == [] and body["read_only"] is True


def test_authoritative_endpoint_is_read_only(launcher_client):
    _, client, _ = launcher_client
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/v1/safety-flags").status_code == 405


def test_authoritative_endpoint_not_observed_when_source_unreadable(launcher_client):
    _, client, tmp_path = launcher_client
    (tmp_path / "css_mobile_controls.json").write_text("{not json")
    body = client.get("/api/v1/safety-flags").json()
    assert body["verdict"] == "NOT_OBSERVED" and body["fail_closed"] is True
    assert set(body["not_observed"]) == set(EXPECTED_FIELDS)
    assert all(body[name] == "NOT_OBSERVED" for name in EXPECTED_FIELDS)


def test_authoritative_endpoint_reports_unsafe_when_armed(launcher_client):
    _, client, tmp_path = launcher_client
    (tmp_path / "css_mobile_controls.json").write_text(json.dumps({"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"}))
    body = client.get("/api/v1/safety-flags").json()
    assert body["verdict"] == "UNSAFE" and body["broker_execution_armed"] is True
    assert set(body["unsafe"]) == {"broker_execution_armed", "live_trading_blocked"}


def test_authoritative_endpoint_fails_closed_if_derivation_raises(launcher_client, monkeypatch):
    launcher, client, _ = launcher_client

    def boom(*_a, **_k):
        raise RuntimeError("state unavailable")

    monkeypatch.setattr(launcher, "get_launcher_observed_safety_flags", boom)
    body = client.get("/api/v1/safety-flags").json()
    assert body["verdict"] == "NOT_OBSERVED" and all(body[n] == "NOT_OBSERVED" for n in EXPECTED_FIELDS)


@pytest.mark.parametrize("missing", ["execution_allowed", "live_trading_blocked", "broker_execution_armed", "advisory_only"])
def test_payload_builder_never_infers_missing_flag(missing):
    from backend.runtime.safety_flag_observation import authoritative_safety_flags_payload

    derived = {**EXPECTED_FIELDS}
    del derived[missing]
    body = authoritative_safety_flags_payload(derived, observed_at="t")
    assert body[missing] == "NOT_OBSERVED" and body["verdict"] == "NOT_OBSERVED" and body["fail_closed"] is True


def test_launcher_exposes_all_four_flags_explicitly(launcher_client):
    _, client, _ = launcher_client
    payloads = _payloads(client)
    flags = payloads["/api/v1/live-execution-authority"]["safety_flags"]
    assert flags["observed"] is True
    assert (flags["execution_allowed"], flags["live_trading_blocked"],
            flags["broker_execution_armed"], flags["advisory_only"]) == (False, True, False, True)
    result = observe_safety_flags(payloads)
    assert result["ok"], result["failures"]


def test_launcher_reports_armed_mobile_control(launcher_client):
    _, client, tmp_path = launcher_client
    (tmp_path / "css_mobile_controls.json").write_text(json.dumps({"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"}))
    payloads = _payloads(client)
    flags = payloads["/api/v1/live-execution-authority"]["safety_flags"]
    assert flags["broker_execution_armed"] is True and flags["live_trading_blocked"] is False
    assert not observe_safety_flags(payloads)["ok"]


def test_launcher_unreadable_controls_not_observed(launcher_client):
    _, client, tmp_path = launcher_client
    (tmp_path / "css_mobile_controls.json").write_text("{not json")
    flags = _payloads(client)["/api/v1/live-execution-authority"]["safety_flags"]
    assert flags["observed"] is False and flags["broker_execution_armed"] is None


# ---- OV-002 monitor: missing flags are never inferred safe -------------------

def _monitor(runtime, authority):
    flags = authority.get("safety_flags")
    surface = {"schema": "css.safety_flags.v1", **flags,
               "verdict": "SAFE" if flags == SAFE_FLAGS_BLOCK else "NOT_OBSERVED"} if flags is not None else {}
    responses = {"/api/runtime-mode": (200, runtime), "/api/v1/live-execution-authority": (200, authority),
                 "/health": (200, {"status": "healthy"}), "/api/v1/safety-flags": (200, surface)}
    with patch("backend.certification.ov002_endurance_monitor._http_json",
               side_effect=lambda path, timeout=8.0: responses[path]):
        return capture_safety_assertions()


SAFE_FLAGS_BLOCK = {"execution_allowed": False, "live_trading_blocked": True,
                    "broker_execution_armed": False, "advisory_only": True}


def test_monitor_passes_only_with_all_flags_observed():
    result = _monitor(SAFE_RUNTIME, {"data": SAFE_AUTHORITY, "safety_flags": SAFE_FLAGS_BLOCK})
    assert result["ok"] is True and result["not_observed"] == []


def test_monitor_missing_advisory_only_is_hard_failure():
    runtime = {k: v for k, v in SAFE_RUNTIME.items() if k != "advisory_only"}
    result = _monitor(runtime, {"data": SAFE_AUTHORITY, "safety_flags": SAFE_FLAGS_BLOCK})
    assert result["ok"] is False
    assert "runtime_mode.advisory_only" in result["not_observed"]
    assert result["advisory_only"] is False


@pytest.mark.parametrize("missing", sorted(SAFE_FLAGS_BLOCK))
def test_monitor_missing_observed_flag_is_hard_failure(missing):
    block = {k: v for k, v in SAFE_FLAGS_BLOCK.items() if k != missing}
    result = _monitor(SAFE_RUNTIME, {"data": SAFE_AUTHORITY, "safety_flags": block})
    assert result["ok"] is False and missing in result["not_observed"]


def test_monitor_missing_fail_closed_not_inferred():
    runtime = {k: v for k, v in SAFE_RUNTIME.items() if k != "fail_closed"}
    assert _monitor(runtime, {"data": SAFE_AUTHORITY, "safety_flags": SAFE_FLAGS_BLOCK})["ok"] is False


def test_monitor_without_authoritative_surface_fails():
    responses = {"/api/runtime-mode": (200, SAFE_RUNTIME),
                 "/api/v1/live-execution-authority": (200, {"data": SAFE_AUTHORITY, "safety_flags": SAFE_FLAGS_BLOCK}),
                 "/health": (200, {"status": "healthy"}), "/api/v1/safety-flags": (404, {"detail": "Not Found"})}
    with patch("backend.certification.ov002_endurance_monitor._http_json",
               side_effect=lambda path, timeout=8.0: responses[path]):
        result = capture_safety_assertions()
    assert result["ok"] is False and result["checks"]["safety_flags_surface_reachable"] is False


def test_monitor_armed_flag_fails():
    block = {**SAFE_FLAGS_BLOCK, "broker_execution_armed": True}
    assert _monitor(SAFE_RUNTIME, {"data": SAFE_AUTHORITY, "safety_flags": block})["ok"] is False
