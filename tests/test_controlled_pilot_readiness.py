import json

from backend.runtime.controlled_pilot_readiness import evaluate_controlled_pilot_readiness


SAFE = {
    "verdict": "SAFE",
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
    "advisory_only": True,
    "not_observed": [],
    "unsafe": [],
}

BROKER_OK = {
    "status": "BROKER_RECONCILED",
    "safe_degradation_required": False,
}


def enrollment_file(tmp_path):
    path = tmp_path / "enrollment.json"
    path.write_text(json.dumps({
        "schema": "css.pilot_approver_enrollment.v1",
        "designations": {
            "PILOT_SPONSOR": {"holder_id": "robert-asibor"},
            "RELEASE_SECURITY_APPROVER": None,
        },
        "keys": [],
        "notes": "test",
    }), encoding="utf-8")
    return path


def baseline(tmp_path, **overrides):
    data = dict(
        safety_flags=SAFE,
        broker_reconciliation=BROKER_OK,
        pcnrass_passed=True,
        kill_switch_verified=True,
        full_regression_reconciled=True,
        security_review_passed=True,
        endurance_review_passed=True,
        release_candidate_frozen=True,
        independent_readiness_review_passed=True,
        enrollment_path=str(enrollment_file(tmp_path)),
    )
    data.update(overrides)
    return evaluate_controlled_pilot_readiness(**data)


def test_unenrolled_second_approver_blocks(tmp_path):
    result = baseline(tmp_path)
    assert not result.ready
    assert any(x.startswith("enrollment:") for x in result.blockers)


def test_missing_safety_flag_blocks(tmp_path):
    bad = dict(SAFE)
    bad.pop("broker_execution_armed")
    result = baseline(tmp_path, safety_flags=bad)
    assert not result.ready
    assert "safety_flags_not_fail_closed" in result.blockers


def test_broker_divergence_blocks(tmp_path):
    result = baseline(
        tmp_path,
        broker_reconciliation={
            "status": "BROKER_DIVERGED",
            "safe_degradation_required": True,
        },
    )
    assert not result.ready
    assert "broker_reconciliation_not_clean" in result.blockers


def test_any_required_governance_check_false_blocks(tmp_path):
    result = baseline(tmp_path, pcnrass_passed=False)
    assert not result.ready
    assert "pcnrass_passed" in result.blockers
