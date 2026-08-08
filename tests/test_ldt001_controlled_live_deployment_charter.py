"""LDT-001 offline tests — charter package + existing fail-closed controls.

Planning-phase only. Does not contact brokers, arm live execution, or mutate
the running desktop CSS instance. Does not modify production execution paths.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG
from backend.runtime.live_execution_authority import evaluate_live_execution_authority
from backend.runtime.live_micro_pilot_governor import (
    LiveMicroPilotConfig,
    LiveMicroPilotConfigurationError,
    LiveMicroPilotGovernor,
)
from engine.execution.live_order_kill_switch import evaluate_live_order_kill_switch


REPO_ROOT = Path(__file__).resolve().parents[1]
CHARTER = REPO_ROOT / "docs" / "governance" / "LDT_001_CONTROLLED_LIVE_DEPLOYMENT_TEST_CHARTER.md"
GATE_MATRIX = REPO_ROOT / "docs" / "governance" / "LDT_001_PREFLIGHT_GATE_MATRIX.json"
EVIDENCE_SCHEMA = REPO_ROOT / "docs" / "governance" / "LDT_001_EVIDENCE_MANIFEST_SCHEMA.json"

LDT_MAX_ENTRY_ORDERS = 1
LDT_MAX_EXIT_ORDERS = 1
FORBIDDEN_SECRET_MARKERS = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "client_secret",
    "refresh_token=",
    "Authorization: Bearer",
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_ldt001_governance_artifacts_exist_and_forbid_secrets() -> None:
    assert CHARTER.is_file()
    assert GATE_MATRIX.is_file()
    assert EVIDENCE_SCHEMA.is_file()

    charter_text = CHARTER.read_text(encoding="utf-8")
    assert "NO LIVE TEST AUTHORIZED" in charter_text or "No live test is authorized" in charter_text
    assert "EUR_USD" in charter_text
    assert "OANDA" in charter_text
    assert "CAD 20" in charter_text or "CAD 20.00" in charter_text

    # Charter and gate matrix must not embed secrets. Evidence schema may list
    # forbidden markers as detection rules only.
    for path in (CHARTER, GATE_MATRIX):
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_SECRET_MARKERS:
            assert marker not in text
    schema_text = EVIDENCE_SCHEMA.read_text(encoding="utf-8")
    assert '"forbidden_content_markers"' in schema_text
    assert "BEGIN PRIVATE KEY" not in CHARTER.read_text(encoding="utf-8")


def test_ldt001_preflight_matrix_aggregate_is_no_go() -> None:
    matrix = _load_json(GATE_MATRIX)
    assert matrix["schema_version"] == "css.ldt001.preflight_gate_matrix.v1"
    assert matrix["charter_time_aggregate"] == "NO-GO"

    classes = {g["classification"] for g in matrix["gates"]}
    assert "BLOCKED" in classes or "NOT_TESTED" in classes

    anti = next(g for g in matrix["gates"] if g["id"] == "E5")
    assert anti["classification"] == "BLOCKED"

    authority = next(g for g in matrix["gates"] if g["id"] == "E8")
    assert authority["classification"] == "PASS"


def test_ldt001_evidence_manifest_schema_is_deterministic_and_redacted() -> None:
    schema = _load_json(EVIDENCE_SCHEMA)
    assert schema["schema_version"] == "css.ldt001.evidence_manifest.v1"
    assert schema["custody"]["hash_algorithm"] == "SHA-256"
    assert schema["manifest_object"]["secrets_present"] is False
    assert schema["manifest_object"]["live_test_authorized"] is False

    ids = [a["id"] for a in schema["required_artifacts"]]
    assert len(ids) == len(set(ids))
    assert "evidence_manifest" in ids
    assert "credential_diagnostics_redacted" in ids
    for marker in FORBIDDEN_SECRET_MARKERS:
        assert marker in schema["forbidden_content_markers"]

    # Deterministic sample manifest hash (offline fixture; no secrets).
    sample_artifacts = sorted(
        (
            {"id": "workspace_verification", "sha256": "a" * 64},
            {"id": "commit_and_manifest_hashes", "sha256": "b" * 64},
        ),
        key=lambda row: row["id"],
    )
    body = json.dumps(sample_artifacts, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    assert len(digest) == 64
    assert digest == hashlib.sha256(body.encode("utf-8")).hexdigest()


def test_ldt001_pilot_cannot_exceed_phase152a_cad20_ceiling() -> None:
    with pytest.raises(LiveMicroPilotConfigurationError):
        LiveMicroPilotConfig.from_mapping({"max_live_test_capital": "20.01"})
    with pytest.raises(LiveMicroPilotConfigurationError):
        LiveMicroPilotConfig.from_mapping({"max_position_size": "21.00"})
    with pytest.raises(LiveMicroPilotConfigurationError):
        LiveMicroPilotConfig.from_mapping({"daily_loss_limit": "2.01"})
    with pytest.raises(LiveMicroPilotConfigurationError):
        LiveMicroPilotConfig.from_mapping({"session_loss_limit": "4.01"})
    with pytest.raises(LiveMicroPilotConfigurationError):
        LiveMicroPilotConfig.from_mapping({"max_concurrent_positions": 2})
    with pytest.raises(LiveMicroPilotConfigurationError):
        LiveMicroPilotConfig.from_mapping({"allow_pyramiding": True})

    assert DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_total_cad == Decimal("20.00")
    assert DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_position_cad == Decimal("20.00")


def test_ldt001_operational_one_entry_one_exit_stricter_than_code_ceiling() -> None:
    # Code ceiling remains 10; LDT operational charter is stricter.
    assert DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_orders_per_session == 10
    assert LDT_MAX_ENTRY_ORDERS == 1
    assert LDT_MAX_EXIT_ORDERS == 1
    assert (LDT_MAX_ENTRY_ORDERS + LDT_MAX_EXIT_ORDERS) <= DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_orders_per_session


def test_ldt001_live_authority_blocked_without_founder_evidence() -> None:
    authority = evaluate_live_execution_authority({})
    assert authority.live_authority_state == "BLOCKED"
    assert authority.can_live_execute is False
    assert authority.execution_authority is False
    assert "operator_requested_live" in authority.failed_conditions


def test_ldt001_kill_switch_prevents_submission_when_engaged() -> None:
    decision = evaluate_live_order_kill_switch(env={"CSS_LIVE_ORDER_KILL_SWITCH": "1"})
    assert decision.blocked is True
    assert decision.reason == "env_kill_switch_engaged"

    clear = evaluate_live_order_kill_switch(controls={}, env={"CSS_LIVE_ORDER_KILL_SWITCH": "0"})
    # Clear env alone is not an authorization to trade; only proves switch can be clear in unit scope.
    assert clear.blocked is False


def test_ldt001_missing_preflight_evidence_is_no_go(tmp_path, monkeypatch) -> None:
    config = tmp_path / "pilot_config.json"
    state = tmp_path / "pilot_state.json"
    audit = tmp_path / "pilot_audit.jsonl"
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_CONFIG", str(config))
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_STATE", str(state))
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_AUDIT", str(audit))
    governor = LiveMicroPilotGovernor(config_path=config, state_path=state, audit_path=audit)

    decision = governor.evaluate_order(
        {
            "broker": "OANDA",
            "broker_mode": "live",
            "mobile_trading_mode": "LIVE",
            "symbol": "EUR_USD",
            "side": "BUY",
            "notional": "1.00",
        }
    )
    assert decision.approved is False
    assert decision.reason == "live_micro_pilot_config_missing"

    authority = evaluate_live_execution_authority(
        {
            "operator_requested_live": True,
            "go_no_go": "NO GO",
            "live_micro_pilot_state": "DISARMED",
        }
    )
    assert authority.live_authority_state == "BLOCKED"
    assert "go_no_go_allows" in authority.failed_conditions


def test_ldt001_unresolved_open_position_rejects_additional_entry(tmp_path, monkeypatch) -> None:
    config = tmp_path / "pilot_config.json"
    state = tmp_path / "pilot_state.json"
    audit = tmp_path / "pilot_audit.jsonl"
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_CONFIG", str(config))
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_STATE", str(state))
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_AUDIT", str(audit))
    governor = LiveMicroPilotGovernor(config_path=config, state_path=state, audit_path=audit)
    governor.write_config(
        {"pilot_enabled": True},
        user_ctx={"user_id": "00000", "role": "SUPER_USER"},
        confirmation_word="EXECUTE",
    )
    governor.arm(user_ctx={"user_id": "00000", "role": "SUPER_USER"}, confirmation_word="EXECUTE")

    decision = governor.evaluate_order(
        {
            "broker": "OANDA",
            "broker_mode": "live",
            "mobile_trading_mode": "LIVE",
            "symbol": "EUR_USD",
            "side": "BUY",
            "notional": "1.00",
            "authoritative_exposure_amount": "1.00",
            "authoritative_exposure_currency": "CAD",
        },
        open_positions=[{"symbol": "EUR_USD", "side": "BUY", "notional": "1.00", "authoritative_exposure_amount": "1.00", "authoritative_exposure_currency": "CAD"}],
    )
    assert decision.approved is False
    assert decision.reason in {"pyramiding_blocked", "max_concurrent_positions_breached"}


def test_ldt001_stale_market_data_blocks_authority() -> None:
    authority = evaluate_live_execution_authority(
        {
            "operator_requested_live": True,
            "live_micro_pilot_state": "ARMED",
            "capital_governor": "PASS",
            "unified_trade_gate": "PASS",
            "margin_gate": "PASS",
            "anti_bleed_guard": "PASS",
            "rbac": "PASS",
            "kill_switch": "CLEAR",
            "go_no_go": "GO",
            "broker_readiness": {
                "credentials_present": True,
                "authenticated": True,
                "connected": True,
                "account_loaded": True,
                "market_data_ready": False,
                "execution_enabled": True,
            },
        }
    )
    assert authority.live_authority_state == "BLOCKED"
    assert "market_data_ready" in authority.failed_conditions


def test_ldt001_authority_not_persistent_without_armed_state(tmp_path, monkeypatch) -> None:
    """Restart equivalent: missing/disarmed pilot state cannot yield AUTHORIZED."""
    config = tmp_path / "pilot_config.json"
    state = tmp_path / "pilot_state.json"
    audit = tmp_path / "pilot_audit.jsonl"
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_CONFIG", str(config))
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_STATE", str(state))
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_AUDIT", str(audit))
    governor = LiveMicroPilotGovernor(config_path=config, state_path=state, audit_path=audit)
    status = governor.status()
    assert status.get("pilot_armed") in {False, None} or status.get("live_micro_pilot_state") != "ARMED"

    authority = evaluate_live_execution_authority(
        {
            "operator_requested_live": True,
            "live_micro_pilot_state": "DISARMED",
            "broker_readiness": {
                "credentials_present": True,
                "authenticated": True,
                "connected": True,
                "account_loaded": True,
                "market_data_ready": True,
                "execution_enabled": True,
            },
            "capital_governor": "PASS",
            "unified_trade_gate": "PASS",
            "margin_gate": "PASS",
            "anti_bleed_guard": "PASS",
            "rbac": "PASS",
            "kill_switch": "CLEAR",
            "go_no_go": "GO",
        }
    )
    assert authority.live_authority_state == "BLOCKED"
    assert "live_micro_pilot_armed" in authority.failed_conditions


def test_ldt001_records_antibleed_vs_cad20_conflict_gap() -> None:
    guard = AntiBleedGuard()
    assert guard.minimum_profitable_trade_size == 50.0
    assert float(DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_position_cad) < guard.minimum_profitable_trade_size
    # Charter documents this as BLOCKED; offline test locks the conflict so it cannot be silently ignored.
    matrix = _load_json(GATE_MATRIX)
    assert next(g for g in matrix["gates"] if g["id"] == "E5")["classification"] == "BLOCKED"


def test_ldt001_authorization_expiry_gap_documented() -> None:
    """Single-use TTL token is a recorded gap; Phase 152A arm/disarm is the standing equivalent."""
    charter = CHARTER.read_text(encoding="utf-8")
    assert "single-use" in charter.lower() or "Single-use" in charter
    assert "Gap" in charter or "gap" in charter
    assert "across restart" in charter.lower() or "across restart" in charter
