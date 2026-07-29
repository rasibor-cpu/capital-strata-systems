from __future__ import annotations

import builtins
import inspect
import os
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

from dashboard.runtime.operational_identity import (
    OPERATIONAL_IDENTITY_VERSION,
    build_live_capital_banner_payload,
    build_operational_identity_payload,
)

GENERATED_AT = "2026-07-29T00:00:00+00:00"


def _platform_authority(**overrides: Any) -> dict[str, Any]:
    authority = {
        "runtime_mode": "LIVE",
        "execution_state": "ENABLED",
        "execution_authority": True,
        "order_submission": "ENABLED",
        "live_trading_enabled": True,
        "engine_mode": "GOVERNED",
    }
    authority.update(overrides)
    return authority


def _broker_readiness(**overrides: Any) -> dict[str, Any]:
    readiness = {
        "selected_broker": "OANDA",
        "connected": True,
        "broker_execution_armed": True,
        "readiness_status": "READY",
    }
    readiness.update(overrides)
    return readiness


def _certification(**overrides: Any) -> dict[str, Any]:
    cert = {
        "certification_status": "CERTIFIED",
    }
    cert.update(overrides)
    return cert


def test_operational_identity_imports_without_mobile_control_dependency() -> None:
    source = inspect.getsource(build_operational_identity_payload)
    assert "css_mobile_controls" not in source
    assert "load_mobile_controls" not in source
    assert "evaluate_kill_switch_state" not in source
    assert OPERATIONAL_IDENTITY_VERSION == "css.operational_identity.v2"


def test_missing_authority_fails_closed_with_deterministic_payload() -> None:
    payload = build_operational_identity_payload(generated_at_utc=GENERATED_AT)

    assert payload["generated_at_utc"] == GENERATED_AT
    assert payload["runtime_mode"] == "DISABLED"
    assert payload["live_capital_active"] is False
    assert payload["orders_enabled"] is False
    assert payload["order_activity_allowed"] is False
    assert "missing_platform_authority" in payload["authority_blockers"]
    assert "certification_not_ready" in payload["authority_blockers"]
    assert payload["source_metadata"]["no_environment_reads"] is True
    assert payload["source_metadata"]["no_filesystem_reads"] is True
    assert payload["source_metadata"]["no_order_placement"] is True


def test_malformed_authority_fails_closed() -> None:
    payload = build_operational_identity_payload(
        platform_status={"runtime_mode": "surprise", "execution_authority": "true"},
        broker_readiness={"broker_execution_armed": "true", "readiness_status": "READY"},
        certification={"certification_status": "CERTIFIED"},
        generated_at_utc=GENERATED_AT,
    )

    assert payload["runtime_mode"] == "DISABLED"
    assert payload["execution_authority"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["live_capital_active"] is False
    assert "runtime_mode_not_live" in payload["authority_blockers"]
    assert "execution_authority_blocked" in payload["authority_blockers"]
    assert "broker_execution_not_armed" in payload["authority_blockers"]


def test_live_text_and_mobile_controls_never_activate_live_capital() -> None:
    payload = build_operational_identity_payload(
        {
            "resolved_mode": "live",
            "environment": "LIVE",
            "broker_summary": {
                "broker_mode": "live",
                "connected": True,
                "readiness_status": "READY",
            },
        },
        mobile_controls={"runtime_mode": "live", "orders_enabled": True},
        generated_at_utc=GENERATED_AT,
    )

    assert payload["runtime_mode"] == "DISABLED"
    assert payload["live_capital_active"] is False
    assert payload["orders_enabled"] is False
    assert payload["source_metadata"]["mobile_controls_ignored"] is True
    assert "missing_platform_authority" in payload["authority_blockers"]


@pytest.mark.parametrize(
    ("platform_overrides", "broker_overrides", "cert_overrides", "expected_blocker"),
    [
        ({"order_submission": "BLOCKED"}, {}, {}, "order_submission_blocked"),
        ({}, {"broker_execution_armed": False}, {}, "broker_execution_not_armed"),
        ({}, {"readiness_status": "BROKER_BLOCKED"}, {}, "broker_readiness_not_ready"),
        ({}, {}, {"certification_status": "FAILED"}, "certification_not_ready"),
        (
            {"runtime_mode": "LIVE_READ_ONLY"},
            {},
            {},
            "runtime_mode_not_live",
        ),
    ],
)
def test_each_canonical_gate_blocks_live_capital(
    platform_overrides: dict[str, Any],
    broker_overrides: dict[str, Any],
    cert_overrides: dict[str, Any],
    expected_blocker: str,
) -> None:
    payload = build_operational_identity_payload(
        platform_status=_platform_authority(**platform_overrides),
        broker_readiness=_broker_readiness(**broker_overrides),
        certification=_certification(**cert_overrides),
        generated_at_utc=GENERATED_AT,
    )

    assert payload["live_capital_active"] is False
    assert payload["orders_enabled"] is False
    assert expected_blocker in payload["authority_blockers"]


def test_broker_readiness_alone_cannot_activate_live_capital() -> None:
    payload = build_operational_identity_payload(
        broker_readiness=_broker_readiness(),
        certification=_certification(),
        generated_at_utc=GENERATED_AT,
    )

    assert payload["broker_execution_armed"] is True
    assert payload["broker_readiness_status"] == "READY"
    assert payload["live_capital_active"] is False
    assert "missing_platform_authority" in payload["authority_blockers"]
    assert "runtime_mode_not_live" in payload["authority_blockers"]


def test_explicit_canonical_authority_activates_banner_without_enabling_orders() -> None:
    identity = build_operational_identity_payload(
        platform_status=_platform_authority(),
        broker_readiness=_broker_readiness(),
        certification=_certification(),
        generated_at_utc=GENERATED_AT,
    )
    banner = build_live_capital_banner_payload(identity)

    assert identity["live_capital_active"] is True
    assert identity["authority_blockers"] == []
    assert identity["orders_enabled"] is False
    assert identity["order_activity_allowed"] is False
    assert banner["visible"] is True
    assert banner["headline"] == "LIVE CAPITAL ACTIVE"
    assert banner["authority_blockers"] == []


def test_projection_has_no_runtime_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_side_effect(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("operational identity attempted an external side effect")

    with monkeypatch.context() as side_effect_guard:
        side_effect_guard.setattr(os, "getenv", fail_side_effect)
        side_effect_guard.setattr(os, "putenv", fail_side_effect)
        side_effect_guard.setattr(os, "system", fail_side_effect)
        side_effect_guard.setattr(socket, "socket", fail_side_effect)
        side_effect_guard.setattr(socket, "create_connection", fail_side_effect)
        side_effect_guard.setattr(subprocess, "run", fail_side_effect)
        side_effect_guard.setattr(subprocess, "Popen", fail_side_effect)
        side_effect_guard.setattr(Path, "open", fail_side_effect)
        side_effect_guard.setattr(Path, "read_text", fail_side_effect)
        side_effect_guard.setattr(Path, "write_text", fail_side_effect)
        side_effect_guard.setattr(builtins, "open", fail_side_effect)

        payload = build_operational_identity_payload(
            platform_status=_platform_authority(),
            broker_readiness=_broker_readiness(),
            certification=_certification(),
            generated_at_utc=GENERATED_AT,
        )

    assert payload["live_capital_active"] is True
    assert payload["orders_enabled"] is False
