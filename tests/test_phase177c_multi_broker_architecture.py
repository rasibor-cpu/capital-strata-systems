"""Phase 177C — Canonical Tier-1 multi-broker architecture tests."""

from __future__ import annotations

from backend.app.brokers.broker_registry import get_adapter, get_broker_spec, list_supported_brokers
from backend.app.brokers.canonical_tier1 import (
    ROADMAP_EXCLUDED_BROKERS,
    TIER1_BROKERS,
    get_canonical_broker_registry,
    reset_canonical_broker_registry_for_tests,
)
from backend.app.brokers.contamination_isolation import (
    analyze_environment_contamination,
    analyze_runtime_state_contamination,
)
from backend.app.brokers.live_read_only import assert_execution_blocked, build_live_read_only_contract
from backend.broker_reporting import build_broker_executive_report_package
from backend.runtime.broker_startup_selection import normalize_broker, startup_broker_from_choice
from backend.runtime.runtime_mode import resolve_runtime_mode
from dashboard.mission_control.state_adapter import build_broker_registry


def setup_function() -> None:
    reset_canonical_broker_registry_for_tests()


def test_tier1_registry_contains_four_brokers_no_ibkr() -> None:
    registry = get_canonical_broker_registry()
    assert tuple(registry.list_brokers()) == TIER1_BROKERS
    assert "IBKR" not in registry.list_brokers()
    assert registry.is_roadmap_excluded("IBKR")
    assert "ALPACA" in ROADMAP_EXCLUDED_BROKERS


def test_primary_roles_assigned() -> None:
    roles = get_canonical_broker_registry().primary_roles()
    assert roles["PRIMARY_CRYPTO_BROKER"] == "COINBASE"
    assert roles["SECONDARY_CRYPTO_BROKER"] == "BINANCE"
    assert roles["PRIMARY_FX_BROKER"] == "OANDA"
    assert roles["PRIMARY_CANADIAN_EQUITIES_BROKER"] == "QUESTRADE"


def test_legacy_metadata_registry_aligned() -> None:
    brokers = set(list_supported_brokers())
    assert brokers == {"coinbase", "binance", "oanda", "questrade"}
    assert get_broker_spec("binance").display_name == "Binance"
    assert get_broker_spec("questrade").display_name == "Questrade"


def test_binance_questrade_adapters_are_structured_and_non_executable() -> None:
    for broker in ("binance", "questrade"):
        adapter = get_adapter(broker)()
        readiness = adapter.readiness()
        assert readiness["expected_condition"] is True
        assert readiness["execution_allowed"] is False
        assert readiness["state"] in {"CREDENTIALS_REQUIRED", "CONFIGURATION_REQUIRED"}


def test_mission_control_broker_list_tier1() -> None:
    rows = build_broker_registry({"selected_broker": "NONE", "broker_mode": "paper"})
    names = {row["broker"] for row in rows}
    assert {"COINBASE", "BINANCE", "OANDA", "QUESTRADE", "PAPER"} <= names
    assert "IBKR" not in names
    for row in rows:
        if row["broker"] == "PAPER":
            continue
        assert row.get("role")
        assert row.get("execution_blocked") is True
        assert row.get("execution") == "DISABLED"


def test_live_read_only_blocks_execution() -> None:
    for broker in TIER1_BROKERS:
        contract = build_live_read_only_contract(broker)
        assert contract.runtime_mode == "LIVE_READ_ONLY"
        assert assert_execution_blocked(contract)
        assert "submit_order" in contract.blocked_actions
        assert "authenticate" in contract.allowed_actions


def test_cross_broker_endpoint_contamination_detected() -> None:
    env = {
        "OANDA_BASE_URL": "https://api.coinbase.com",
        "COINBASE_BASE_URL": "https://api.coinbase.com",
    }
    report = analyze_environment_contamination(env, selected_broker="OANDA")
    assert report.cross_broker_contamination is True
    assert any(f.code == "CROSS_BROKER_ENDPOINT" for f in report.findings)


def test_clean_env_passes_contamination() -> None:
    env = {
        "COINBASE_BASE_URL": "https://api.coinbase.com",
        "OANDA_BASE_URL": "https://api-fxtrade.oanda.com",
        "BINANCE_BASE_URL": "https://api.binance.com",
        "QUESTRADE_BASE_URL": "https://api.questrade.com",
    }
    report = analyze_environment_contamination(env)
    assert report.status == "PASS"
    assert report.cross_broker_contamination is False


def test_runtime_state_nested_foreign_field_detected() -> None:
    state = {"oanda": {"coinbase_base_url": "https://api.coinbase.com", "api_version": "v3"}}
    report = analyze_runtime_state_contamination(state)
    assert report.cross_broker_contamination is True


def test_ibkr_normalizes_to_none() -> None:
    assert normalize_broker("IBKR") == "NONE"
    assert startup_broker_from_choice("4") == "BINANCE"
    assert startup_broker_from_choice("5") == "QUESTRADE"


def test_runtime_resolver_unchanged_fail_closed() -> None:
    resolution = resolve_runtime_mode()
    assert resolution.runtime_mode.value == "DISABLED"
    assert resolution.execution_enabled is False


def test_broker_executive_report_paginated() -> None:
    package = build_broker_executive_report_package(
        active_broker={"selected_broker": "NONE", "broker_mode": "paper"},
        css_version="Phase-177C",
        commit_reference="test",
    )
    assert package.execution_allowed is False
    assert package.trading_impact is False
    assert package.advisory_only is True
    doc = package.document
    assert doc["presentation"]["mode"] == "paginated"
    assert doc["page_count"] >= 3
    page_types = {p["page_type"] for p in doc["pages"]}
    assert "cover" in page_types
    assert "summary" in page_types
    assert "toc" in page_types
    assert set(package.per_broker.keys()) == set(TIER1_BROKERS)
