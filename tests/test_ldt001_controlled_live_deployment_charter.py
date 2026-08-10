"""LDT-001 offline tests — charter package + existing fail-closed controls.

Planning-phase only. Does not contact brokers, arm live execution, or mutate
a running desktop CSS instance. Does not modify production execution paths.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from backend.app.risk.anti_bleed_policy import AntiBleedPolicyResolver
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
RC004_DOC = REPO_ROOT / "docs" / "governance" / "RC_004_OPERATIONAL_POSTURE.md"

CANDIDATE_BRANCH = "css-rc-live-001-candidate"
MR003G_HEAD = "fa35bb4f4b8f96b4b77bb74217b0fb0f35cf2204"
PHASE192_HEAD = "84a0e893385a624a8ebb5dfffd53f35ce4b30ba7"

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
    assert RC004_DOC.is_file()

    charter_text = CHARTER.read_text(encoding="utf-8")
    assert "NO LIVE TEST AUTHORIZED" in charter_text or "No live test is authorized" in charter_text
    assert "NOT FROZEN" in charter_text or "not a designated freeze" in charter_text.lower()
    assert "EUR_USD" in charter_text
    assert "OANDA" in charter_text
    assert "CAD 20" in charter_text or "CAD 20.00" in charter_text
    assert CANDIDATE_BRANCH in charter_text
    assert MR003G_HEAD in charter_text
    assert PHASE192_HEAD in charter_text
    assert "LIVE_TRADING_NOT_AUTHORIZED" in RC004_DOC.read_text(encoding="utf-8")

    for path in (CHARTER, GATE_MATRIX):
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_SECRET_MARKERS:
            assert marker not in text
    schema_text = EVIDENCE_SCHEMA.read_text(encoding="utf-8")
    assert '"forbidden_content_markers"' in schema_text


def test_ldt001_candidate_not_live_ready_and_aggregate_no_go() -> None:
    matrix = _load_json(GATE_MATRIX)
    assert matrix["schema_version"] == "css.ldt001.preflight_gate_matrix.v1"
    assert matrix["charter_time_aggregate"] == "NO-GO"
    assert matrix["as_of_candidate_head"] == PHASE192_HEAD
    assert matrix["as_of_candidate_branch"] == CANDIDATE_BRANCH
    assert matrix["as_of_mr003g_head"] == MR003G_HEAD
    assert matrix["freeze_sha_designated"] is False
    assert matrix["live_authorized"] is False
    assert matrix["lineage_blocker_status"] == "RESOLVED_ON_CANDIDATE"

    classes = {g["classification"] for g in matrix["gates"]}
    assert "BLOCKED" in classes

    anti = next(g for g in matrix["gates"] if g["id"] == "E5")
    assert anti["classification"] == "PASS"
    assert next(g for g in matrix["gates"] if g["id"] == "C8")["classification"] == "BLOCKED"
    assert next(g for g in matrix["gates"] if g["id"] == "D3")["classification"] == "PASS"
    assert next(g for g in matrix["gates"] if g["id"] == "A1")["classification"] == "NOT_TESTED"
    assert next(g for g in matrix["gates"] if g["id"] == "A3")["classification"] == "PASS"
    assert next(g for g in matrix["gates"] if g["id"] == "E8")["classification"] == "PASS"


def test_ldt001_no_ov002_or_live_authorization_claims() -> None:
    charter = CHARTER.read_text(encoding="utf-8")
    matrix = GATE_MATRIX.read_text(encoding="utf-8")
    for body in (charter, matrix):
        assert "OV-002 certification" not in body.lower() or "not claimed" in body.lower() or "BLOCKED_NOT_CLAIMED" in body
        assert "LIVE TRADING AUTHORIZED" not in body.upper()
        assert "freeze_sha_designated\": true" not in body.replace(" ", "")


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
            "notional_currency": "CAD",
        },
        open_positions=[{"symbol": "EUR_USD", "side": "BUY", "notional": "1.00"}],
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


def test_ldt001_micro_pilot_antibleed_aligns_with_cad20(tmp_path) -> None:
    # STANDARD default remains 50; LIVE_MICRO_PILOT uses MICRO_PILOT min 20 (Phase 184A).
    standard = AntiBleedGuard(state_file=str(tmp_path / "anti_bleed_standard.json"))
    assert standard.minimum_profitable_trade_size == 50.0
    cad20 = float(DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_position_cad)
    assert cad20 < standard.minimum_profitable_trade_size

    policy = AntiBleedPolicyResolver.resolve("LIVE_MICRO_PILOT")
    assert policy.minimum_profitable_trade_size == 20.0
    assert cad20 >= policy.minimum_profitable_trade_size
    guard = AntiBleedGuard(policy=policy, state_file=str(tmp_path / "anti_bleed_micro.json"))
    approved = guard.evaluate(
        symbol="EUR_USD",
        trade_size=cad20,
        expected_move_bps=50.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
    )
    assert approved["approved"] is True
    matrix = _load_json(GATE_MATRIX)
    assert next(g for g in matrix["gates"] if g["id"] == "E5")["classification"] == "PASS"


def test_ldt001_authorization_expiry_gap_documented() -> None:
    charter = CHARTER.read_text(encoding="utf-8")
    assert "single-use" in charter.lower() or "Single-use" in charter
    assert "Gap" in charter or "gap" in charter or "TTL" in charter
    assert "across restart" in charter.lower() or "across restart" in charter
