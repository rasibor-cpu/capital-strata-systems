from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.institutional_hardening.broker_confidence import BrokerConfidenceInput, score_broker_confidence
from backend.institutional_hardening.config_governance import ConfigChangeRecord
from backend.institutional_hardening.incident_drill import run_incident_drill
from backend.institutional_hardening.live_mode_gate import LiveModeGuardrailInput, evaluate_live_mode_guardrail
from backend.institutional_hardening.mobile_certification import certify_mobile_flows, REQUIRED_MOBILE_FLOWS
from backend.institutional_hardening.operator_approval import OperatorApproval, validate_operator_approval, append_operator_approval_audit
from backend.institutional_hardening.order_intent_simulator import OrderIntent, simulate_order_intent
from backend.institutional_hardening.performance_budget import assess_performance_budget
from backend.institutional_hardening.recovery_drill import evaluate_recovery_drill
from backend.institutional_hardening.release_integrity import build_release_manifest, write_release_manifest
from backend.institutional_hardening.retention_policy import redact_export, archive_rotation_required

NOW = datetime(2026, 9, 14, tzinfo=timezone.utc)


def approval():
    return OperatorApproval("A1", "00000", "SUPER_USER", NOW, NOW + timedelta(hours=1), "RESTRICTED_LIVE_REVIEW")


def test_operator_approval_is_expiring_scoped_and_role_gated():
    ok, reason = validate_operator_approval(approval(), required_scope="RESTRICTED_LIVE_REVIEW", now_utc=NOW)
    assert ok is True and reason == "OPERATOR_APPROVAL_VALID"
    ok, reason = validate_operator_approval(approval(), required_scope="OTHER", now_utc=NOW)
    assert ok is False and reason == "OPERATOR_APPROVAL_SCOPE_MISMATCH"


def test_live_mode_guardrail_never_arms_execution():
    payload = evaluate_live_mode_guardrail(
        LiveModeGuardrailInput(approval(), True, True, True, True, True),
        now_utc=NOW,
    )
    assert payload["status"] == "READY_FOR_HUMAN_REVIEW"
    assert payload["execution_allowed"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["live_trading_authorized"] is False


def test_broker_confidence_degrades_below_threshold():
    result = score_broker_confidence(BrokerConfidenceInput(
        Decimal("1"), Decimal("1"), Decimal("0.2"), Decimal("1")
    ))
    assert result.status == "DEGRADED"
    assert result.safe_degradation_required is True


def test_order_intent_is_simulation_only():
    payload = simulate_order_intent(
        OrderIntent("Questrade", "AAPL", "BUY", Decimal("2"), Decimal("100"), Decimal("1"), Decimal("2")),
        capability_allowed=True,
        governance_allowed=True,
    )
    assert payload["simulation_status"] == "SIMULATED"
    assert payload["submitted_to_broker"] is False
    assert payload["execution_route"] is None
    assert payload["execution_allowed"] is False


@pytest.mark.parametrize("scenario", ["broker-disconnect", "reconciliation-divergence", "risk-breach", "kill-switch", "session-lock"])
def test_incident_drills_are_fail_closed(scenario):
    result = run_incident_drill(scenario)
    assert result["execution_allowed"] is False
    assert result["money_movement_allowed"] is False


def test_retention_export_redacts_sensitive_keys():
    value = {"token": "secret", "nested": {"api_key": "secret", "safe": 1}}
    out = redact_export(value)
    assert out["token"] == "REDACTED"
    assert out["nested"]["api_key"] == "REDACTED"
    assert out["nested"]["safe"] == 1


def test_performance_budget_emits_stale_warning_when_slow():
    out = assess_performance_budget(metric="dashboard_snapshot", elapsed_ms=150, payload_bytes=100)
    assert out["status"] == "BUDGET_EXCEEDED"
    assert out["stale_state_warning"] is True


def test_configuration_change_diff_and_rollback_reference():
    record = ConfigChangeRecord("C1", "engineer", "approver", NOW, "tag:v1", {"risk": 1}, {"risk": 2})
    assert record.diff() == {"risk": {"before": 1, "after": 2}}
    assert record.rollback_reference == "tag:v1"


def test_recovery_drill_fails_closed_on_corrupt_artifact():
    out = evaluate_recovery_drill(restart_ok=True, session_restored=True, artifact_integrity_ok=False, stale_state_explicit=True)
    assert out["status"] == "FAIL_CLOSED"
    assert out["execution_allowed"] is False


def test_mobile_certification_requires_every_critical_flow():
    results = {name: True for name in REQUIRED_MOBILE_FLOWS}
    assert certify_mobile_flows(results)["status"] == "PASS"
    results["no_frontend_broker_calls"] = False
    assert certify_mobile_flows(results)["status"] == "FAIL"


def test_release_manifest_hashes_files(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text("alpha", encoding="utf-8")
    result = build_release_manifest([a], validation_commands=["python -m pytest -q"])
    assert len(result["files"][0]["sha256"]) == 64
    assert len(result["manifest_sha256"]) == 64


def test_operator_approval_audit_is_jsonl_and_scoped(tmp_path):
    path = tmp_path / "approval.jsonl"
    event = append_operator_approval_audit(path, approval(), required_scope="RESTRICTED_LIVE_REVIEW", now_utc=NOW)
    assert event["valid"] is True
    assert "RESTRICTED_LIVE_REVIEW" in path.read_text(encoding="utf-8")


def test_archive_rotation_guardrail():
    assert archive_rotation_required(2_000_000_000) is True
    assert archive_rotation_required(1) is False


def test_release_manifest_writer_is_atomic_shape(tmp_path):
    src = tmp_path / "source.txt"
    src.write_text("content", encoding="utf-8")
    out = tmp_path / "release_manifest.json"
    payload = write_release_manifest(out, [src], validation_commands=["python -m pytest -q"])
    assert out.exists()
    assert payload["manifest_sha256"] in out.read_text(encoding="utf-8")
