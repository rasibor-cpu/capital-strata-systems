"""Phase 193 — hardened operational qualification tests (offline)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.app.brokers.multi_broker_readiness.audit_matrix import register_plugin_capability
from backend.app.brokers.multi_broker_readiness.contracts import BrokerCapabilityProfile
from backend.app.brokers.operational_qualification import (
    QualificationStateMachine,
    SCORE_FORMULA_VERSION,
    build_broker_readiness_matrix,
    build_qualification_evidence,
    build_state_evidence_flags,
    compute_hardened_scores,
    hash_qualification_payload,
    qualify_broker,
    readiness_label_for_score,
    run_operational_qualification_precheck,
    verify_operational_qualification_firewall,
)
from backend.app.brokers.operational_qualification.evidence import FORBIDDEN_EVIDENCE_MARKERS
from backend.app.governance.enterprise_certification_registry import (
    CertificationClaimError,
    CertificationRegistryEntry,
    RegistryEntityType,
    RegistryRepository,
    assert_valid_certification_claim,
    seed_phase_registry,
)
from backend.app.governance.enterprise_certification_registry.hashing import RegistryHash


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "governance" / "PHASE_193_CONTROLLED_OPERATIONAL_QUALIFICATION.md"
PKG = ROOT / "backend" / "app" / "brokers" / "operational_qualification"
START_HEAD = "b15c69f2a6a6ca604846c7353f3100c8d407b20c"


def _oanda_env() -> dict[str, str]:
    return {
        "OANDA_API_KEY": "REDACTED_PRESENT",
        "OANDA_BASE_URL": "https://example.invalid/v3",
        "OANDA_ACCOUNT_ID": "REDACTED_ACCOUNT",
    }


def test_phase193_governance_doc_hardening() -> None:
    assert DOC.is_file()
    text = DOC.read_text(encoding="utf-8")
    for token in (
        "NO NETWORK",
        "NO AUTH",
        "NO EXECUTION",
        "193.2-hardened",
        "implementation_maturity_score",
        "operational_readiness_score",
        "aggregate_qualification_score",
        "FOUNDATION_ONLY",
        "mandatory",
        "LIVE_TRADING_NOT_AUTHORIZED",
        START_HEAD,
    ):
        assert token in text


def test_deterministic_state_transitions_with_full_gates() -> None:
    sm = QualificationStateMachine()
    evidence = {
        "precheck_ready": True,
        "config_ready": True,
        "auth_config_ready": True,
        "read_only_framework_ready": True,
        "qualification_complete": True,
    }
    stage, history = sm.run_to_completion(evidence)
    assert stage == "QUALIFIED"
    assert [h.to_state for h in history][-1] == "QUALIFIED"


def test_state_machine_ignores_score_only_advancement() -> None:
    sm = QualificationStateMachine()
    stage, history = sm.run_to_completion(
        {
            "readiness_score": 100,
            "aggregate_qualification_score": 100,
            "implementation_maturity_score": 100,
            "operational_readiness_score": 100,
            "readiness_label": "QUALIFIED",
            "precheck_ready": False,
        }
    )
    assert stage == "NOT_STARTED"
    assert history[0].failure_reason == "missing_evidence:precheck_ready"


def test_invalid_transition_rejection() -> None:
    sm = QualificationStateMachine()
    assert sm.assert_transition_allowed("PRECHECK_READY") is True
    assert sm.assert_transition_allowed("QUALIFIED") is False
    stuck = sm.evaluate({"precheck_ready": False})
    assert stuck.success is False
    blocked = sm.force_blocked("test")
    assert blocked.to_state == "BLOCKED"


def test_empty_env_broker_matrix_hardened() -> None:
    matrix = build_broker_readiness_matrix(env={}, timestamp="2026-08-01T12:00:00Z")
    by_broker = {row.broker: row for row in matrix}
    for broker in ("OANDA", "COINBASE", "IBKR", "BINANCE", "QUESTRADE", "PLUGIN"):
        row = by_broker[broker]
        assert row.execution_authority is False
        assert row.live_execution_certification == "NOT_AUTHORIZED"
        assert row.read_only_qualification == "NOT_READY"
        assert row.qualification_stage not in {"READ_ONLY_READY", "QUALIFIED"}
        assert row.score_formula_version == SCORE_FORMULA_VERSION
        # Missing configuration cannot be PRECHECK_READY or above.
        assert row.qualification_stage in {"NOT_STARTED", "BLOCKED"}
        # Credentials absent → ops <= 25 (or 0 if registry invalid).
        assert row.operational_readiness_score <= 25

    assert by_broker["IBKR"].qualification_stage == "BLOCKED"
    assert by_broker["IBKR"].operational_readiness_score == 0
    assert by_broker["IBKR"].aggregate_qualification_score <= 25
    assert by_broker["OANDA"].qualification_stage == "NOT_STARTED"
    assert by_broker["COINBASE"].qualification_stage == "NOT_STARTED"
    assert by_broker["QUESTRADE"].qualification_stage == "NOT_STARTED"


def test_score_caps_not_configured_and_missing_credentials() -> None:
    scores = compute_hardened_scores(
        implementation_status="PARTIAL",
        audit_classification="PARTIAL",
        capability_profile_ok=True,
        provider_compatible=True,
        certification_readiness=True,
        registry_entry_ok=True,
        schema_compatible=True,
        governance_aligned=True,
        rc004_live_denied=True,
        authorization_ttl_classified=True,
        credentials_configured=False,
        endpoint_configured=False,
        configured_readiness="NOT_CONFIGURED",
    )
    assert scores.operational_readiness_score <= 25
    assert scores.uncapped_operational_readiness_score > scores.operational_readiness_score
    assert scores.score_formula_version == SCORE_FORMULA_VERSION


def test_score_caps_invalid_registry_forces_ops_zero() -> None:
    scores = compute_hardened_scores(
        implementation_status="PARTIAL",
        audit_classification="PARTIAL",
        capability_profile_ok=True,
        provider_compatible=True,
        certification_readiness=True,
        registry_entry_ok=False,
        schema_compatible=True,
        governance_aligned=True,
        rc004_live_denied=True,
        authorization_ttl_classified=True,
        credentials_configured=True,
        endpoint_configured=True,
        configured_readiness="READY",
    )
    assert scores.operational_readiness_score == 0
    assert scores.mandatory_gate_results.registry_valid is False


def test_score_caps_implementation_blocked_aggregate() -> None:
    scores = compute_hardened_scores(
        implementation_status="BLOCKED",
        audit_classification="BLOCKED",
        capability_profile_ok=True,
        provider_compatible=False,
        certification_readiness=False,
        registry_entry_ok=True,
        schema_compatible=True,
        governance_aligned=True,
        rc004_live_denied=True,
        authorization_ttl_classified=True,
        credentials_configured=True,
        endpoint_configured=True,
        configured_readiness="READY",
    )
    assert scores.implementation_maturity_score == 0
    assert scores.aggregate_qualification_score <= 25
    assert scores.readiness_label in {"BLOCKED", "FOUNDATION_ONLY"}


def test_readiness_label_boundaries() -> None:
    assert readiness_label_for_score(0) == "BLOCKED"
    assert readiness_label_for_score(24) == "BLOCKED"
    assert readiness_label_for_score(25) == "FOUNDATION_ONLY"
    assert readiness_label_for_score(49) == "FOUNDATION_ONLY"
    assert readiness_label_for_score(50) == "PARTIAL"
    assert readiness_label_for_score(69) == "PARTIAL"
    assert readiness_label_for_score(70) == "PRECHECK_READY"
    assert readiness_label_for_score(84) == "PRECHECK_READY"
    assert readiness_label_for_score(85) == "READ_ONLY_READY"
    assert readiness_label_for_score(99) == "READ_ONLY_READY"
    assert readiness_label_for_score(100) == "QUALIFIED"


def test_mandatory_gate_enforcement_in_state_flags() -> None:
    # Missing configuration → cannot be precheck_ready.
    flags = build_state_evidence_flags(
        registry_entry_ok=True,
        capability_profile_ok=True,
        schema_compatible=True,
        rc004_live_denied=True,
        authorization_ttl_classified=True,
        provider_compatible=True,
        hard_blocked=False,
        endpoint_configured=False,
        credentials_configured=True,
        authenticated_online=False,
        certification_readiness=True,
    )
    assert flags["precheck_ready"] is False
    assert flags["auth_config_ready"] is False
    assert flags["read_only_framework_ready"] is False

    # Credentials missing → cannot reach AUTH_READY gate.
    flags2 = build_state_evidence_flags(
        registry_entry_ok=True,
        capability_profile_ok=True,
        schema_compatible=True,
        rc004_live_denied=True,
        authorization_ttl_classified=True,
        provider_compatible=True,
        hard_blocked=False,
        endpoint_configured=True,
        credentials_configured=False,
        authenticated_online=False,
        certification_readiness=True,
    )
    assert flags2["precheck_ready"] is True
    assert flags2["config_ready"] is True
    assert flags2["auth_config_ready"] is False

    # No authenticated online → cannot reach READ_ONLY_READY even with config+creds.
    flags3 = build_state_evidence_flags(
        registry_entry_ok=True,
        capability_profile_ok=True,
        schema_compatible=True,
        rc004_live_denied=True,
        authorization_ttl_classified=True,
        provider_compatible=True,
        hard_blocked=False,
        endpoint_configured=True,
        credentials_configured=True,
        authenticated_online=False,
        certification_readiness=True,
    )
    assert flags3["auth_config_ready"] is True
    assert flags3["read_only_framework_ready"] is False
    assert flags3["qualification_complete"] is False


def test_configured_env_cannot_reach_readonly_without_auth_online() -> None:
    result = qualify_broker("OANDA", _oanda_env(), timestamp="2026-08-01T12:00:00Z", qualification_id="oq-cfg")
    assert result.stage == "AUTH_READY"
    assert result.evidence.read_only_qualification == "NOT_READY"
    assert result.stage not in {"READ_ONLY_READY", "QUALIFIED"}
    assert result.execution_authority is False
    assert result.operational_readiness_score > 25
    assert result.evidence.score_formula_version == SCORE_FORMULA_VERSION
    assert result.evidence.blocker_count == len(result.evidence.blocker_list)
    assert result.evidence.mandatory_gate_results["authenticated_online"] is False
    assert result.evidence.mandatory_gate_results["execution_authority_denied"] is True


def test_missing_registry_entry_fails_closed() -> None:
    empty = RegistryRepository()
    result = qualify_broker("OANDA", _oanda_env(), repository=empty, timestamp="2026-08-01T12:00:00Z")
    assert result.stage == "BLOCKED"
    assert result.operational_readiness_score == 0
    assert any("registry_claim_invalid" in b for b in result.evidence.blocker_list)


def test_suspended_entry_fails_closed() -> None:
    result = qualify_broker(
        "IBKR",
        {"IBKR_ACCOUNT_ID": "x", "IBKR_HOST": "127.0.0.1"},
        timestamp="2026-08-01T12:00:00Z",
    )
    assert result.stage == "BLOCKED"
    assert result.operational_readiness_score == 0
    assert result.aggregate_qualification_score <= 25


def test_stale_registry_generation_fails_closed() -> None:
    result = qualify_broker(
        "OANDA",
        _oanda_env(),
        expected_min_generation=99,
        timestamp="2026-08-01T12:00:00Z",
    )
    assert result.stage == "BLOCKED"
    assert "stale_registry_generation" in result.evidence.blocker_list


def test_provider_fingerprint_mismatch_fails_closed() -> None:
    result = qualify_broker(
        "OANDA",
        _oanda_env(),
        expected_provider_name="WRONG_PROVIDER",
        timestamp="2026-08-01T12:00:00Z",
    )
    assert result.stage == "BLOCKED"
    assert any(b.startswith("provider_fingerprint_mismatch") for b in result.evidence.blocker_list)


def test_rc004_live_posture_remains_denied() -> None:
    pre = run_operational_qualification_precheck("COINBASE", {})
    assert pre.rc004_live_denied is True
    assert pre.execution_authority is False


def test_read_only_ttl_is_not_live_authority() -> None:
    result = qualify_broker("OANDA", _oanda_env(), timestamp="2026-08-01T12:00:00Z")
    assert result.evidence.diagnostics["read_only_ttl_is_not_live_authority"] is True


def test_deterministic_evidence_hashes() -> None:
    a = qualify_broker("OANDA", _oanda_env(), timestamp="2026-08-01T12:00:00Z", qualification_id="oq-fixed")
    b = qualify_broker("OANDA", _oanda_env(), timestamp="2026-08-01T12:00:00Z", qualification_id="oq-fixed")
    assert a.evidence.evidence_hash == b.evidence.evidence_hash
    assert a.aggregate_qualification_score == b.aggregate_qualification_score

    base = {
        "qualification_id": "oq-1",
        "broker": "OANDA",
        "asset_class": "FX",
        "provider_name": "P",
        "provider_version": "1",
        "schema_version": "193.2",
        "capability_profile": {"fx": True, "execution_authority": False},
        "registry_generation": 1,
        "rc004_posture": "PAPER_ONLY_NO_LIVE_UNLOCK",
        "qualification_stage": "NOT_STARTED",
        "implementation_maturity_score": 70,
        "operational_readiness_score": 25,
        "aggregate_qualification_score": 47,
        "readiness_label": "FOUNDATION_ONLY",
        "mandatory_gate_results": {
            "registry_valid": True,
            "configuration_present": False,
            "credentials_present": False,
            "authenticated_online": False,
            "implementation_not_blocked": True,
            "rc004_live_denied": True,
            "execution_authority_denied": True,
        },
        "generated_timestamp": "2026-08-01T12:00:00Z",
        "read_only_qualification": "NOT_READY",
    }
    e1 = build_qualification_evidence(**base, blocker_list=["b", "a"])
    e2 = build_qualification_evidence(**base, blocker_list=["a", "b"])
    assert e1.evidence_hash == e2.evidence_hash
    e3 = build_qualification_evidence(
        **{**base, "aggregate_qualification_score": 48, "readiness_label": "FOUNDATION_ONLY"},
        blocker_list=["a", "b"],
    )
    assert e3.evidence_hash != e1.evidence_hash


def test_secrets_not_present_in_evidence() -> None:
    result = qualify_broker("OANDA", _oanda_env(), timestamp="2026-08-01T12:00:00Z")
    blob = str(result.evidence.as_dict()).lower()
    assert "redacted_present" not in blob
    assert result.evidence.diagnostics.get("secret_values_captured") is False
    for marker in ("begin private key", "authorization: bearer", "refresh_token="):
        assert marker not in blob


def test_execution_authority_always_false() -> None:
    for broker in ("OANDA", "COINBASE", "IBKR", "BINANCE", "QUESTRADE", "PLUGIN"):
        result = qualify_broker(broker, {}, timestamp="2026-08-01T12:00:00Z")
        assert result.execution_authority is False
        assert result.evidence.execution_authority is False


def test_static_no_network_no_auth_no_order_boundary() -> None:
    report = verify_operational_qualification_firewall()
    assert report["ok"] is True, report["violations"]
    assert report["execution_authority"] is False
    assert report["can_authenticate"] is False
    assert report["can_network"] is False
    for path in PKG.glob("*.py"):
        if path.name == "firewall.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"authenticate", "place_order", "submit_order"}


def test_plugin_extensibility_without_inferred_capabilities() -> None:
    profile = BrokerCapabilityProfile(
        broker_type="ACME_PLUGIN",
        crypto=True,
        market_data=True,
        account_information=True,
        execution_authority=False,
    )
    register_plugin_capability(profile)
    result = qualify_broker(
        "ACME_PLUGIN",
        {"BROKER_API_KEY": "x", "BROKER_BASE_URL": "https://example.invalid"},
        timestamp="2026-08-01T12:00:00Z",
    )
    assert result.stage == "BLOCKED"
    assert result.execution_authority is False


def test_claim_guard_still_active() -> None:
    repo = seed_phase_registry()
    with pytest.raises(CertificationClaimError):
        assert_valid_certification_claim(repo, registry_id="broker:IBKR")
    entry = assert_valid_certification_claim(repo, registry_id="phase:193")
    assert entry.execution_authority is False


def test_matrix_sorted_deterministic() -> None:
    a = build_broker_readiness_matrix(env={}, timestamp="2026-08-01T12:00:00Z")
    b = build_broker_readiness_matrix(env={}, timestamp="2026-08-01T12:00:00Z")
    assert [r.broker for r in a] == sorted(r.broker for r in a)
    assert [r.evidence_hash for r in a] == [r.evidence_hash for r in b]
    assert [r.aggregate_qualification_score for r in a] == [r.aggregate_qualification_score for r in b]


def test_hash_helper_stable() -> None:
    payload = {"a": 1, "b": ["z", "y"], "c": {"k": True}}
    assert hash_qualification_payload(payload) == hash_qualification_payload(
        {"c": {"k": True}, "b": ["z", "y"], "a": 1}
    )


def test_not_ready_never_qualified_or_readonly_stage() -> None:
    for broker in ("OANDA", "COINBASE", "QUESTRADE", "BINANCE", "PLUGIN", "IBKR"):
        result = qualify_broker(broker, _oanda_env() if broker == "OANDA" else {}, timestamp="2026-08-01T12:00:00Z")
        if result.evidence.read_only_qualification == "NOT_READY":
            assert result.stage not in {"QUALIFIED", "READ_ONLY_READY"}
