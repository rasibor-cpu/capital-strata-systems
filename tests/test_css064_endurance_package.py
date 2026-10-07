import json

from backend.certification.css064_endurance_package import (
    DISPOSITION_CANDIDATE, DISPOSITION_NOT_CERTIFIABLE, DISPOSITION_OBSERVATION, PREFLIGHT_FILE,
    build_final_manifest, build_preflight, observe_safety_flags,
)

SHA = "c" * 40
SAFE = {"/api/runtime-mode": {"execution_allowed": False, "advisory_only": True},
        "/api/v1/live-execution-authority": {"data": {"live_trading_blocked": True,
                                                      "broker_execution_armed": False}}}


def clean_git(_root):
    return {"head": SHA, "dirty_paths": []}


def preflight(**kw):
    args = dict(repo_root=".", expected_sha=SHA, operator_id="ops-1", target_hours=72,
                flag_payloads=SAFE, platform_name="nt", git=clean_git)
    args.update(kw)
    return build_preflight(**args)


def test_preflight_certifying_only_when_all_checks_pass():
    assert preflight()["certifying"]
    assert not preflight(platform_name="posix")["certifying"]
    assert not preflight(expected_sha="d" * 40)["certifying"]
    assert not preflight(git=lambda _r: {"head": SHA, "dirty_paths": [" M x.py"]})["certifying"]
    assert not preflight(target_hours=19.7)["certifying"]
    assert not preflight(operator_id=" ")["certifying"]


def test_missing_flag_is_not_assumed_safe():
    result = observe_safety_flags({"/api/runtime-mode": {"execution_allowed": False}})
    assert not result["ok"]
    assert "advisory_only:not_observed" in result["failures"]
    assert "broker_execution_armed:not_observed" in result["failures"]


def test_unsafe_or_non_boolean_or_conflicting_flags_fail():
    for bad in ({"execution_allowed": True}, {"execution_allowed": "false"}, {"execution_allowed": 0}):
        payloads = {**SAFE, "/extra": bad}
        assert not observe_safety_flags(payloads)["ok"]


def test_preflight_records_hash_and_identity():
    result = preflight()
    assert len(result["host"]["python_executable_sha256"]) == 64
    assert result["operator_id"] == "ops-1" and result["expected_sha"] == SHA


def _package(tmp_path, status="COMPLETE", pre=True):
    if pre:
        (tmp_path / PREFLIGHT_FILE).write_text(json.dumps(preflight()))
    (tmp_path / "RUN_STATUS.json").write_text(json.dumps({"status": status}))
    (tmp_path / "RUN_META.json").write_text(json.dumps({"run_start_utc": "2026-10-08T00:00:00+00:00"}))
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "snapshots" / "s1.json").write_text("{}")
    return tmp_path


def test_clean_complete_run_is_only_a_candidate(tmp_path):
    manifest = build_final_manifest(package_dir=_package(tmp_path), repo_root=".", flag_payloads=SAFE, git=clean_git)
    assert manifest["disposition"] == DISPOSITION_CANDIDATE and not manifest["blockers"]
    assert {f["path"] for f in manifest["files"]} >= {"snapshots/s1.json", "RUN_STATUS.json", PREFLIGHT_FILE}
    assert len(manifest["manifest_sha256"]) == 64


def test_invalidation_incomplete_or_changed_head_not_certifiable(tmp_path):
    pkg = _package(tmp_path)
    (pkg / "INVALIDATION.json").write_text("{}")
    assert build_final_manifest(package_dir=pkg, repo_root=".", flag_payloads=SAFE,
                                git=clean_git)["disposition"] == DISPOSITION_NOT_CERTIFIABLE


def test_running_status_and_head_change_block(tmp_path):
    pkg = _package(tmp_path, status="RUNNING")
    manifest = build_final_manifest(package_dir=pkg, repo_root=".", flag_payloads=SAFE,
                                    git=lambda _r: {"head": "e" * 40, "dirty_paths": []})
    assert manifest["disposition"] == DISPOSITION_NOT_CERTIFIABLE
    assert "head_changed_during_run" in manifest["blockers"]
    assert "monitor_status:RUNNING" in manifest["blockers"]


def test_no_preflight_is_observation_only(tmp_path):
    manifest = build_final_manifest(package_dir=_package(tmp_path, pre=False), repo_root=".",
                                    flag_payloads=SAFE, git=clean_git)
    assert manifest["disposition"] == DISPOSITION_OBSERVATION


def test_final_flag_drift_blocks(tmp_path):
    unsafe = {**SAFE, "/api/runtime-mode": {"execution_allowed": True, "advisory_only": True}}
    manifest = build_final_manifest(package_dir=_package(tmp_path), repo_root=".", flag_payloads=unsafe, git=clean_git)
    assert manifest["disposition"] == DISPOSITION_NOT_CERTIFIABLE
