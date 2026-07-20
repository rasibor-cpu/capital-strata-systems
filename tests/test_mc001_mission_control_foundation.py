from __future__ import annotations

import json
from math import inf

from fastapi.testclient import TestClient

from dashboard.mission_control import (
    MISSION_CONTROL_SCHEMA_VERSION,
    MISSION_CONTROL_SECTIONS,
    build_mission_control_state,
    create_app,
    mission_control_state_json,
    validate_mission_control_state,
)
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.pages import PAGE_MODULES, render_page
from dashboard.mission_control.safety import validate_no_execution_controls, validate_no_secret_payload
from dashboard.mission_control.theme import MISSION_CONTROL_CSS


def test_mc001_repository_shell_registers_all_required_pages() -> None:
    keys = [section.key for section in MISSION_CONTROL_SECTIONS]

    assert keys == [
        "executive_overview",
        "reports_center",
        "runtime_operations",
        "trade_operations",
        "portfolio",
        "market_intelligence",
        "risk_command",
        "options_income",
        "broker_management",
        "alerts_incidents",
        "certification_readiness",
        "audit_explainability",
        "learning_performance",
        "users_governance",
        "system_configuration",
        "documentation_runbooks",
    ]
    assert set(PAGE_MODULES) == set(keys)


def test_mc001_canonical_contract_is_stable_safe_and_versioned() -> None:
    state = build_mission_control_state()
    encoded = mission_control_state_json(state)
    decoded = json.loads(encoded)

    assert state["schema_version"] == MISSION_CONTROL_SCHEMA_VERSION
    assert decoded["schema_version"] == MISSION_CONTROL_SCHEMA_VERSION
    assert list(decoded.keys()) == sorted(decoded.keys())
    assert state["contract_validation"]["valid"] is True
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True
    assert state["safety"]["broker_execution_armed"] is False
    assert state["safety"]["advisory_only"] is True
    assert state["safety"]["live_execution_certification"] == "NOT_GRANTED"


def test_mc001_mock_data_is_explicitly_labeled_not_live() -> None:
    state = build_mission_control_state()

    assert state["mock_data"] is True
    assert state["mock_data_label"] == "MOCK DATA - NOT LIVE"
    assert state["platform"]["runtime_mode"] == "paper"
    assert state["brokers"]["selection"]["mode"] == "PREVIEW_ONLY_MC001"
    assert state["configuration"]["live_limit_overrides"] == "DISABLED_MC001"


def test_mc001_shell_renders_navigation_topbar_safety_and_responsive_structure() -> None:
    state = build_mission_control_state()
    html = render_mission_control_shell(state, active_section="broker_management")

    assert "CSS Mission Control" in html
    assert 'aria-label="Mission Control navigation"' in html
    assert 'aria-current="page"' in html
    assert "Broker Management" in html
    assert "Execution: BLOCKED" in html
    assert "No execution authority is granted" in html
    assert "data-mission-control-schema" in html
    assert "@media (max-width: 680px)" in MISSION_CONTROL_CSS
    assert ".mc-shell" in MISSION_CONTROL_CSS


def test_mc001_every_page_renders_read_only_contract_content() -> None:
    state = build_mission_control_state()

    for section in MISSION_CONTROL_SECTIONS:
        rendered = render_page(section.key, state)
        assert section.label.split(" / ")[0].split(" and ")[0] in rendered
        assert "READ ONLY" in rendered


def test_mc001_broker_management_contains_active_list_onboarding_and_safety() -> None:
    state = build_mission_control_state()
    brokers = state["brokers"]
    active = brokers["active_broker"]

    assert active["selected_broker"] == "DEMO"
    assert "canonical_state_hash" in active
    assert {row["broker"] for row in brokers["broker_list"]} >= {"COINBASE", "OANDA", "BINANCE", "QUESTRADE", "PAPER"}
    assert "IBKR" not in {row["broker"] for row in brokers["broker_list"]}
    assert brokers.get("primary_roles", {}).get("PRIMARY_CRYPTO_BROKER") == "COINBASE"
    assert brokers["selection"]["enabled"] is False
    assert brokers["selection"]["arming_available"] is False
    assert brokers["selection"]["can_change_credentials"] is False
    assert brokers["selection"]["can_override_safety_gates"] is False
    assert brokers["onboarding"]["enabled"] is False
    assert brokers["onboarding"]["credential_storage"] == "NOT_AVAILABLE"
    assert brokers["safety"]["execution_allowed"] is False
    assert brokers["safety"]["live_trading_blocked"] is True
    assert brokers["safety"]["broker_execution_armed"] is False


def test_mc001_required_sections_have_fail_closed_unavailable_states() -> None:
    state = build_mission_control_state(allow_mock=False)

    assert state["mock_data"] is False
    assert state["platform"]["platform_status"] in {"UNAVAILABLE", "FAIL_CLOSED"}
    assert state["portfolio"]["equity"] == 0.0 or state["portfolio"]["equity"] == "UNAVAILABLE"
    assert state["certification"]["ready_for_live_trading"] == "NOT_CERTIFIED"
    assert state["trading"]["read_only"] is True
    assert state["runtime"]["controls"]["restart"] == "DISABLED_MC001"
    assert state["runtime"]["controls"]["shutdown"] == "DISABLED_MC001"


def test_mc001_state_rejects_missing_safety_flags_non_finite_and_secret_payloads() -> None:
    state = build_mission_control_state()
    bad = dict(state)
    bad["safety"] = {"execution_allowed": True}
    bad["portfolio"] = {"equity": inf}
    bad["configuration"] = {"api_key": "not-redacted"}

    validation = validate_mission_control_state(bad)

    assert validation["valid"] is False
    assert "safety_flag_invalid:execution_allowed" in validation["reasons"]
    assert any(reason.startswith("non_finite_value") for reason in validation["reasons"])
    assert any(reason.startswith("secret_bearing_field") for reason in validation["reasons"])


def test_mc001_contract_does_not_expose_execution_controls_or_secrets() -> None:
    state = build_mission_control_state()

    secrets_ok, secret_reasons = validate_no_secret_payload(state)
    controls_ok, control_reasons = validate_no_execution_controls(state)

    assert secrets_ok is True, secret_reasons
    assert controls_ok is True, control_reasons
    assert "submit_order" not in mission_control_state_json(state)
    assert "cancel_order" not in mission_control_state_json(state)


def test_mc001_fastapi_app_serves_shell_state_navigation_and_health() -> None:
    client = TestClient(create_app())

    state_response = client.get("/mission-control/state")
    page_response = client.get("/mission-control/broker-management")
    nav_response = client.get("/mission-control/navigation")
    health_response = client.get("/health")

    assert state_response.status_code == 200
    assert page_response.status_code == 200
    assert nav_response.status_code == 200
    assert health_response.status_code == 200
    assert state_response.json()["schema_version"] == MISSION_CONTROL_SCHEMA_VERSION
    assert len(nav_response.json()) == 16
    assert "Broker Management" in page_response.text
    assert health_response.json()["execution_allowed"] is False
    assert health_response.json()["live_trading_blocked"] is True


def test_mc001_documentation_index_uses_relative_safe_paths() -> None:
    state = build_mission_control_state()
    docs = state["documentation"]

    assert docs["browser_paths_expose_absolute_paths"] is False
    for group in ("architecture", "governance"):
        for path in docs[group]:
            assert not path.startswith("C:")
            assert not path.startswith("/")
            assert path.startswith("docs/")
