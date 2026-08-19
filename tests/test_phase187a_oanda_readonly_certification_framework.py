"""Phase 187A / 187A-R1 — offline tests for OANDA read-only certification framework."""

from __future__ import annotations

import pytest

from backend.app.market.oanda_readonly_certification.boundary import verify_execution_boundary
from backend.app.market.oanda_readonly_certification.contracts import (
    FRAMEWORK_VERSION,
    SCHEMA_VERSION,
    OandaReadOnlyCertification,
)
from backend.app.market.oanda_readonly_certification.evidence import (
    build_evidence_package,
    compute_evidence_hash,
    redact_diagnostics,
)
from backend.app.market.oanda_readonly_certification.fingerprint import (
    build_provider_fingerprint,
)
from backend.app.market.oanda_readonly_certification.framework import (
    OandaReadOnlyCertificationFramework,
)
from backend.app.market.oanda_readonly_certification.gates import READ_ONLY_GATES, evaluate_gates
from backend.app.market.oanda_readonly_certification.invalidation import (
    INVALIDATION_TRIGGERS,
    evaluate_invalidation,
)
from backend.app.market.oanda_readonly_certification.replay import (
    ReplayProtectionRegistry,
    evaluate_replay,
)
from backend.app.market.oanda_readonly_certification.state_machine import (
    CERTIFICATION_STATES,
    OandaReadOnlyStateMachine,
)


FULL_EVIDENCE = {
    "config_present": True,
    "config_validated": True,
    "dns_ok": True,
    "tls_ok": True,
    "auth_pending": True,
    "auth_ok": True,
    "account_ok": True,
    "account_scope_ok": True,
    "marketdata_ok": True,
    "read_only_certified": True,
}


def test_required_states_present() -> None:
    required = {
        "NOT_STARTED",
        "CONFIG_PRESENT",
        "CONFIG_VALIDATED",
        "DNS_OK",
        "TLS_OK",
        "AUTH_PENDING",
        "AUTH_OK",
        "ACCOUNT_OK",
        "ACCOUNT_SCOPE_OK",
        "MARKETDATA_OK",
        "READ_ONLY_CERTIFIED",
        "REVALIDATION_PENDING",
        "REVALIDATION_RUNNING",
        "REVALIDATED",
        "FAILED",
        "BLOCKED",
    }
    assert required.issubset(set(CERTIFICATION_STATES))


def test_happy_path_all_transitions() -> None:
    sm = OandaReadOnlyStateMachine()
    final, history = sm.run_to_completion(FULL_EVIDENCE)
    assert final == "READ_ONLY_CERTIFIED"
    forwards = [h.to_state for h in history if h.success]
    assert forwards == [
        "CONFIG_PRESENT",
        "CONFIG_VALIDATED",
        "DNS_OK",
        "TLS_OK",
        "AUTH_PENDING",
        "AUTH_OK",
        "ACCOUNT_OK",
        "ACCOUNT_SCOPE_OK",
        "MARKETDATA_OK",
        "READ_ONLY_CERTIFIED",
    ]


def test_missing_evidence_stalls() -> None:
    sm = OandaReadOnlyStateMachine()
    evidence = dict(FULL_EVIDENCE)
    evidence["dns_ok"] = False
    final, history = sm.run_to_completion(evidence)
    assert final == "CONFIG_VALIDATED"
    assert any("missing_evidence:dns_ok" in h.failure_reason for h in history)


def test_failed_path_explicit() -> None:
    sm = OandaReadOnlyStateMachine()
    final, history = sm.run_to_completion(FULL_EVIDENCE, failed=True, failure_reason="tls_handshake")
    assert final == "FAILED"
    assert history[0].failure_reason == "tls_handshake"


def test_blocked_path_explicit() -> None:
    sm = OandaReadOnlyStateMachine()
    final, _ = sm.run_to_completion({}, blocked=True, failure_reason="founder_hold")
    assert final == "BLOCKED"


def test_no_skip_ahead() -> None:
    sm = OandaReadOnlyStateMachine()
    final, _ = sm.run_to_completion({"read_only_certified": True})
    assert final == "NOT_STARTED"


def test_gates_never_grant_execution() -> None:
    results = evaluate_gates(FULL_EVIDENCE)
    assert len(results) == len(READ_ONLY_GATES)
    assert all(r.passed for r in results)
    assert all(r.grants_execution is False for r in results)


def test_gate_failures() -> None:
    results = evaluate_gates({})
    assert all(not r.passed for r in results)


def test_schema_and_provider_versions() -> None:
    fw = OandaReadOnlyCertificationFramework()
    cert = fw.certify(
        FULL_EVIDENCE,
        timestamp="2026-07-31T12:00:00Z",
        diagnostics={"endpoint": "https://api-fxtrade.oanda.com"},
    )
    assert cert.schema_version == SCHEMA_VERSION
    assert cert.provider_version == FRAMEWORK_VERSION
    assert cert.execution_authority is False
    assert cert.certification_state == "READ_ONLY_CERTIFIED"
    assert cert.diagnostics["network_performed"] is False
    assert cert.diagnostics["authentication_performed"] is False
    assert cert.certification_generation == 1
    assert cert.certification_id
    assert cert.certification_timestamp == "2026-07-31T12:00:00Z"
    assert cert.connection is not None
    assert cert.connection.certification_generation == 1
    assert cert.authentication is not None
    assert cert.account is not None
    assert cert.market_data is not None


def test_execution_authority_cannot_be_true() -> None:
    with pytest.raises(ValueError):
        OandaReadOnlyCertification(execution_authority=True)


def test_framework_forbids_execution_methods() -> None:
    fw = OandaReadOnlyCertificationFramework()
    for name in (
        "place_order",
        "submit_order",
        "cancel_order",
        "modify_order",
        "arm_live_authority",
        "enable_execution",
        "authenticate",
        "connect",
        "fetch_market_data",
    ):
        with pytest.raises(AttributeError):
            getattr(fw, name)


def test_credential_redaction() -> None:
    redacted = redact_diagnostics(
        {
            "endpoint": "https://api-fxtrade.oanda.com",
            "api_key": "SECRET_VALUE",
            "token": "abc",
            "account_balance": 12345.0,
            "nested": {"password": "x", "ok": True},
        }
    )
    assert redacted["endpoint"] == "https://api-fxtrade.oanda.com"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["account_balance"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["ok"] is True


def test_evidence_hashing_deterministic() -> None:
    a = build_evidence_package(
        timestamp="2026-07-31T12:00:00Z",
        certification_state="READ_ONLY_CERTIFIED",
        endpoint="https://api-fxtrade.oanda.com",
        connection_diagnostics={"dns": "ok", "token": "LEAK"},
        lineage_generation=1,
        certification_id="orc-test",
    )
    b = build_evidence_package(
        timestamp="2026-07-31T12:00:00Z",
        certification_state="READ_ONLY_CERTIFIED",
        endpoint="https://api-fxtrade.oanda.com",
        connection_diagnostics={"dns": "ok", "token": "DIFFERENT_LEAK"},
        lineage_generation=1,
        certification_id="orc-test",
    )
    assert a.evidence_hash == b.evidence_hash
    assert a.current_evidence_hash == a.evidence_hash
    assert a.connection_diagnostics["token"] == "[REDACTED]"
    body = a.as_dict()
    body.pop("evidence_hash")
    body.pop("current_evidence_hash")
    assert compute_evidence_hash(body) == a.evidence_hash
    assert "SECRET" not in str(a.as_dict())
    assert "LEAK" not in str(a.as_dict())


def test_ast_execution_boundary() -> None:
    report = verify_execution_boundary()
    assert report["ok"] is True
    assert report["grants_execution"] is False
    assert report["violations"] == []


def test_incomplete_certification_diagnostics() -> None:
    fw = OandaReadOnlyCertificationFramework()
    cert = fw.certify({"config_present": True}, timestamp="2026-07-31T12:00:00Z")
    assert cert.certification_state == "CONFIG_PRESENT"
    assert cert.failure_reason.startswith("missing_evidence:")
    assert cert.evidence_hash


def test_generation_increments_only_on_revalidation() -> None:
    fw = OandaReadOnlyCertificationFramework()
    fp = build_provider_fingerprint(endpoint="https://api-fxtrade.oanda.com")
    c1 = fw.certify(FULL_EVIDENCE, timestamp="2026-07-31T12:00:00Z", fingerprint=fp)
    assert c1.certification_generation == 1
    assert fw.generation == 1
    # Stay certified without revalidation — generation must not bump.
    c1b = fw.certify(FULL_EVIDENCE, timestamp="2026-07-31T12:01:00Z", fingerprint=fp)
    assert c1b.certification_state == "READ_ONLY_CERTIFIED"
    assert fw.generation == 1
    inv = fw.invalidate(
        current_fingerprint=fp,
        explicit_triggers=("endpoint_change",),
        timestamp="2026-07-31T12:02:00Z",
    )
    assert inv.certification_state == "REVALIDATION_PENDING"
    assert fw.generation == 1
    running = fw.begin_revalidation(timestamp="2026-07-31T12:03:00Z", fingerprint=fp)
    assert running.certification_state == "REVALIDATION_RUNNING"
    c2 = fw.complete_revalidation(
        FULL_EVIDENCE,
        timestamp="2026-07-31T12:04:00Z",
        fingerprint=fp,
        diagnostics={"endpoint": fp.endpoint, "nonce": "reval-1"},
    )
    assert c2.certification_state in {"REVALIDATED", "READ_ONLY_CERTIFIED"}
    assert c2.certification_generation == 2
    assert c2.parent_certification_id == c1.certification_id
    assert fw.generation == 2


def test_provider_fingerprint_stability_and_invalidation() -> None:
    a = build_provider_fingerprint(endpoint="https://api-fxtrade.oanda.com", api_version="v3")
    b = build_provider_fingerprint(endpoint="https://api-fxtrade.oanda.com", api_version="v3")
    assert a.fingerprint_hash() == b.fingerprint_hash()
    c = build_provider_fingerprint(endpoint="https://api-fxpractice.oanda.com", api_version="v3")
    assert a.fingerprint_hash() != c.fingerprint_hash()
    inv = evaluate_invalidation(prior_fingerprint=a, current_fingerprint=c)
    assert inv.invalidated is True
    assert inv.target_state == "REVALIDATION_PENDING"
    assert "endpoint_change" in inv.triggers
    assert inv.target_state != "READ_ONLY_CERTIFIED"


def test_invalidation_never_lands_on_certified() -> None:
    prior = build_provider_fingerprint(provider_version="187A.1")
    current = build_provider_fingerprint(provider_version="187A.2")
    for trigger in INVALIDATION_TRIGGERS:
        # certificate/credential rotation via flags; others via explicit list
        kwargs: dict = {"prior_fingerprint": prior, "current_fingerprint": current}
        if trigger == "certificate_rotation":
            kwargs = {
                "prior_fingerprint": prior,
                "current_fingerprint": prior,
                "certificate_rotated": True,
            }
        elif trigger == "credential_rotation":
            kwargs = {
                "prior_fingerprint": prior,
                "current_fingerprint": prior,
                "credential_rotated": True,
            }
        else:
            kwargs["explicit_triggers"] = (trigger,)
            kwargs["current_fingerprint"] = prior
        result = evaluate_invalidation(**kwargs)
        assert result.invalidated is True
        assert result.target_state == "REVALIDATION_PENDING"


def test_revalidation_state_transitions() -> None:
    sm = OandaReadOnlyStateMachine(initial_state="READ_ONLY_CERTIFIED")
    tr = sm.invalidate_to_revalidation_pending("endpoint_change")
    assert tr.to_state == "REVALIDATION_PENDING"
    assert sm.state == "REVALIDATION_PENDING"
    # Must not jump to certified
    stalled, _ = sm.run_to_completion({"read_only_certified": True})
    assert stalled == "REVALIDATION_PENDING"
    final, history = sm.run_to_completion(
        {
            "revalidation_start": True,
            "revalidation_complete": True,
            "read_only_certified": True,
        }
    )
    assert [h.to_state for h in history if h.success] == [
        "REVALIDATION_RUNNING",
        "REVALIDATED",
        "READ_ONLY_CERTIFIED",
    ]
    assert final == "READ_ONLY_CERTIFIED"


def test_evidence_lineage_fields() -> None:
    pkg = build_evidence_package(
        timestamp="2026-07-31T12:00:00Z",
        certification_state="READ_ONLY_CERTIFIED",
        parent_certification_id="orc-parent",
        previous_evidence_hash="abc",
        lineage_generation=2,
        certification_id="orc-child",
        provider_fingerprint_hash="fp",
    )
    assert pkg.parent_certification_id == "orc-parent"
    assert pkg.previous_evidence_hash == "abc"
    assert pkg.current_evidence_hash == pkg.evidence_hash
    assert pkg.lineage_generation == 2
    # Immutability
    with pytest.raises(Exception):
        pkg.lineage_generation = 3  # type: ignore[misc]


def test_replay_protection() -> None:
    reg = ReplayProtectionRegistry()
    fp = build_provider_fingerprint(endpoint="https://api-fxtrade.oanda.com")
    reg.lock_fingerprint(fp)
    reg.register_accepted("hash-one", 1)

    reused = evaluate_replay(
        registry=reg,
        evidence_hash="hash-one",
        fingerprint=fp,
        certification_generation=2,
        schema_version=SCHEMA_VERSION,
    )
    assert reused.accepted is False
    assert "reused_evidence_hash" in reused.reason

    bad_fp = evaluate_replay(
        registry=reg,
        evidence_hash="hash-two",
        fingerprint=build_provider_fingerprint(endpoint="https://other.example"),
        certification_generation=2,
        schema_version=SCHEMA_VERSION,
    )
    assert bad_fp.accepted is False
    assert "mismatched_provider_fingerprint" in bad_fp.reason

    stale = evaluate_replay(
        registry=reg,
        evidence_hash="hash-three",
        fingerprint=fp,
        certification_generation=0,
        schema_version=SCHEMA_VERSION,
    )
    assert stale.accepted is False
    assert "stale_certification_generation" in stale.reason

    downgrade = evaluate_replay(
        registry=reg,
        evidence_hash="hash-four",
        fingerprint=fp,
        certification_generation=2,
        schema_version="187A.1",
    )
    assert downgrade.accepted is False
    assert "downgraded_schema_version" in downgrade.reason

    ok = evaluate_replay(
        registry=reg,
        evidence_hash="hash-five",
        fingerprint=fp,
        certification_generation=2,
        schema_version=SCHEMA_VERSION,
    )
    assert ok.accepted is True


def test_fingerprint_change_forces_revalidation_pending() -> None:
    fw = OandaReadOnlyCertificationFramework()
    fp1 = build_provider_fingerprint(endpoint="https://api-fxtrade.oanda.com")
    fw.certify(FULL_EVIDENCE, timestamp="2026-07-31T12:00:00Z", fingerprint=fp1)
    fp2 = build_provider_fingerprint(endpoint="https://api-fxpractice.oanda.com")
    out = fw.certify(FULL_EVIDENCE, timestamp="2026-07-31T12:05:00Z", fingerprint=fp2)
    assert out.certification_state == "REVALIDATION_PENDING"
    assert out.certification_generation == 1
    assert "invalidation" in out.failure_reason
