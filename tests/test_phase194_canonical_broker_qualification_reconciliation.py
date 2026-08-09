from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.app.brokers.operational_qualification.canonical_path import (
    CANONICAL_TIER1,
    FORBIDDEN_EXECUTION_ACTIONS,
    build_canonical_broker_path_matrix,
    canonical_broker_path,
    phase194_safety_contract,
)


EXPECTED_TIER1 = ("COINBASE", "BINANCE", "OANDA", "QUESTRADE")


def test_phase194_canonical_tier1_exact_set():
    assert tuple(CANONICAL_TIER1) == EXPECTED_TIER1


@pytest.mark.parametrize("broker", EXPECTED_TIER1)
def test_active_tier1_has_canonical_runtime_consumer(broker):
    result = canonical_broker_path(broker)

    assert result.tier1_active is True
    assert result.roadmap_excluded is False
    assert result.canonical_registry_present is True
    assert result.enterprise_runtime_consumer
    assert result.live_read_only_advertised is True
    assert result.canonical_status == "CANONICAL_READ_ONLY_PATH_AVAILABLE"
    assert result.execution_authority is False
    assert result.live_trading_authorized is False


def test_ibkr_remains_roadmap_excluded():
    result = canonical_broker_path("IBKR")

    assert result.tier1_active is False
    assert result.roadmap_excluded is True
    assert result.canonical_status == "BLOCKED_ROADMAP_EXCLUDED"
    assert "ROADMAP_EXCLUDED" in result.blockers
    assert result.execution_authority is False


def test_plugin_requires_explicit_registration():
    result = canonical_broker_path("PLUGIN")

    assert result.tier1_active is False
    assert result.plugin_only is True
    assert result.canonical_status == "PLUGIN_REGISTRATION_REQUIRED"
    assert "PLUGIN_REQUIRES_EXPLICIT_REGISTRATION" in result.blockers
    assert result.execution_authority is False


def test_unknown_broker_fails_canonical_scope():
    result = canonical_broker_path("UNKNOWN_BROKER")

    assert result.tier1_active is False
    assert result.canonical_status == "NOT_CANONICAL"
    assert "BROKER_NOT_IN_CANONICAL_SCOPE" in result.blockers


def test_matrix_is_deterministic():
    first = [item.as_dict() for item in build_canonical_broker_path_matrix()]
    second = [item.as_dict() for item in build_canonical_broker_path_matrix()]

    assert first == second

    assert [row["broker"] for row in first] == [
        "OANDA",
        "COINBASE",
        "BINANCE",
        "QUESTRADE",
        "IBKR",
        "PLUGIN",
    ]


def test_phase194_safety_contract_is_fail_closed():
    contract = phase194_safety_contract()

    assert contract["network_allowed"] is False
    assert contract["authentication_performed"] is False
    assert contract["runtime_activation_allowed"] is False
    assert contract["broker_contact_allowed"] is False
    assert contract["order_submission_allowed"] is False
    assert contract["execution_authority"] is False
    assert contract["live_trading_authorized"] is False
    assert contract["freeze_sha_designated"] is False


def test_forbidden_execution_actions_are_explicit():
    forbidden = set(FORBIDDEN_EXECUTION_ACTIONS)

    assert "submit_order" in forbidden
    assert "place_order" in forbidden
    assert "cancel_order" in forbidden
    assert "close_position" in forbidden
    assert "transfer_funds" in forbidden
    assert "arm_execution" in forbidden


def test_phase194_module_has_no_network_execution_or_secret_imports():
    path = Path(
        "backend/app/brokers/operational_qualification/canonical_path.py"
    )

    tree = ast.parse(path.read_text(encoding="utf-8-sig"))

    forbidden_import_fragments = (
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "socket",
        "coinbase_executor",
        "execution_gate",
        "live_execution_authority",
        "oanda_adapter",
    )

    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue

        for name in names:
            lowered = name.lower()
            if any(fragment in lowered for fragment in forbidden_import_fragments):
                violations.append(name)

    assert violations == []


def test_no_phase194_object_can_grant_execution():
    for row in build_canonical_broker_path_matrix():
        payload = row.as_dict()

        assert payload["execution_authority"] is False
        assert payload["live_trading_authorized"] is False
