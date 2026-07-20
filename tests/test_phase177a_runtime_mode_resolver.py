"""
Phase 177A — Canonical Runtime Mode Resolution tests.

Fail-closed. No live trading enablement. Advisory resolver only.
"""

from __future__ import annotations

import inspect
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.runtime.runtime_mode import (
    RuntimeMode,
    normalize_runtime_mode,
    resolve_runtime_mode,
)
from dashboard.runtime.api.runtime_mode import create_runtime_mode_router
from launcher import css_mobile_launcher


def test_supported_modes_only():
    assert set(m.value for m in RuntimeMode) == {
        "PAPER",
        "LIVE_READ_ONLY",
        "LIVE_MICRO_PILOT",
        "LIVE",
        "DISABLED",
    }


def test_normalize_rejects_engine_strategy_modes():
    assert normalize_runtime_mode("SAFE") is None
    assert normalize_runtime_mode("BALANCED") is None
    assert normalize_runtime_mode("PAPER") is RuntimeMode.PAPER
    assert normalize_runtime_mode("LIVE_EXECUTION") is RuntimeMode.LIVE
    assert normalize_runtime_mode("live_read_only") is RuntimeMode.LIVE_READ_ONLY


def test_fail_closed_empty_context_is_disabled():
    resolution = resolve_runtime_mode(env={}, session={}, broker_startup={})
    assert resolution.runtime_mode is RuntimeMode.DISABLED
    assert resolution.execution_enabled is False
    assert resolution.execution_authority == "BLOCKED"
    assert resolution.order_submission == "BLOCKED"
    assert "incomplete" in resolution.reason or "unresolved" in resolution.reason or "fail_closed" in resolution.reason


def test_no_silent_paper_fallback():
    resolution = resolve_runtime_mode(
        env={},
        session={"broker_mode": "paper"},
        broker_startup={"broker_mode": "paper"},
        allow_implicit_paper=False,
    )
    assert resolution.runtime_mode is RuntimeMode.DISABLED
    assert resolution.execution_enabled is False


def test_explicit_operator_intent_paper():
    resolution = resolve_runtime_mode(
        env={"CSS_RUNTIME_MODE": "PAPER"},
        session={},
        broker_startup={},
    )
    assert resolution.runtime_mode is RuntimeMode.PAPER
    assert resolution.execution_enabled is False
    assert resolution.order_submission == "BLOCKED"


def test_live_read_only_blocks_execution():
    resolution = resolve_runtime_mode(
        env={"CSS_RUNTIME_MODE": "LIVE_READ_ONLY", "CSS_BROKER_ENVIRONMENT_PROFILE": "LIVE_READ_ONLY"},
        session={},
        broker_startup={"broker_mode": "live"},
    )
    assert resolution.runtime_mode is RuntimeMode.LIVE_READ_ONLY
    assert resolution.execution_enabled is False
    assert resolution.order_submission == "BLOCKED"


def test_live_mode_still_blocked_by_resolver():
    resolution = resolve_runtime_mode(
        env={"CSS_RUNTIME_MODE": "LIVE", "CSS_BROKER_ENVIRONMENT_PROFILE": "LIVE_EXECUTION"},
        evidence={"can_live_execute": True, "live_authority_state": "GRANTED"},
    )
    assert resolution.runtime_mode is RuntimeMode.LIVE
    # Phase 177A does not enable live trading
    assert resolution.execution_enabled is False
    assert resolution.order_submission == "BLOCKED"
    assert resolution.trading_impact is False


def test_micro_pilot_resolution():
    resolution = resolve_runtime_mode(
        env={
            "CSS_RUNTIME_MODE": "LIVE_READ_ONLY",
            "CSS_BROKER_ENVIRONMENT_PROFILE": "LIVE_READ_ONLY",
            "CSS_LIVE_MICRO_PILOT_ARMED": "1",
        },
    )
    assert resolution.runtime_mode is RuntimeMode.LIVE_MICRO_PILOT
    assert resolution.execution_enabled is False


def test_conflict_operator_vs_profile_fail_closed():
    resolution = resolve_runtime_mode(
        env={
            "CSS_RUNTIME_MODE": "PAPER",
            "CSS_BROKER_ENVIRONMENT_PROFILE": "LIVE_READ_ONLY",
        },
    )
    assert resolution.runtime_mode is RuntimeMode.DISABLED
    assert "conflict" in resolution.reason


def test_profile_selection_maps_live_execution_to_live():
    resolution = resolve_runtime_mode(
        env={"CSS_BROKER_ENVIRONMENT_PROFILE": "LIVE_EXECUTION"},
    )
    assert resolution.runtime_mode is RuntimeMode.LIVE
    assert resolution.execution_enabled is False


def test_api_runtime_mode_endpoint():
    app = FastAPI()
    app.include_router(create_runtime_mode_router(state_provider=lambda: {}))
    client = TestClient(app)
    resp = client.get("/api/runtime-mode")
    assert resp.status_code == 200
    body = resp.json()
    assert body["runtime_mode"] == "DISABLED"
    assert body["execution_enabled"] is False
    assert body["trading_impact"] is False
    assert "password" not in body


def test_launcher_mounts_runtime_mode_router_once():
    src = inspect.getsource(css_mobile_launcher)
    assert src.count("create_runtime_mode_router(state_provider=") == 1


def test_launcher_runtime_summary_not_hardcoded_paper(monkeypatch):
    monkeypatch.setattr(css_mobile_launcher, "_safe_load_artifact", lambda *_a, **_k: {})
    monkeypatch.setenv("CSS_RUNTIME_MODE", "LIVE_READ_ONLY")
    monkeypatch.setenv("CSS_BROKER_ENVIRONMENT_PROFILE", "LIVE_READ_ONLY")
    summary = css_mobile_launcher.get_runtime_summary()
    assert summary["runtime_mode"] == "LIVE_READ_ONLY"
    assert summary["execution_enabled"] is False
    assert summary["order_submission"] == "BLOCKED"


def test_launcher_runtime_summary_fail_closed_without_intent(monkeypatch):
    monkeypatch.setattr(css_mobile_launcher, "_safe_load_artifact", lambda *_a, **_k: {})
    monkeypatch.delenv("CSS_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("CSS_BROKER_ENVIRONMENT_PROFILE", raising=False)
    monkeypatch.delenv("BROKER_ENVIRONMENT_PROFILE", raising=False)
    monkeypatch.delenv("CSS_BROKER_PROFILE", raising=False)
    summary = css_mobile_launcher.get_runtime_summary()
    assert summary["runtime_mode"] == "DISABLED"
    assert summary["execution_enabled"] is False


def test_allow_implicit_paper_only_when_requested():
    resolution = resolve_runtime_mode(env={}, allow_implicit_paper=True)
    assert resolution.runtime_mode is RuntimeMode.PAPER
    assert resolution.execution_enabled is False
