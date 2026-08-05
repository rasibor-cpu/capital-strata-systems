"""OV002-R1-R1 adversarial repairs — deterministic offline tests (no CSS runtime)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.certification.ov002_continuity import (
    STATE_INVALIDATED,
    STATE_NOT_CERTIFIED,
    STATE_RUNNING,
    ContinuityError,
    build_process_identity_record,
    default_identity_probe,
    evaluate_final_certification,
    freeze_process_identity,
    load_critical_event_ledger,
    persist_attempt_state,
    reconcile_process_identity_live,
    reject_historical_attempt2_as_pass,
    reject_legacy_certification_authority,
    transition_attempt_state,
    validate_process_identity,
    write_attempt_state,
)
from backend.certification.ov002_endurance_monitor import _load_alerts_since
from backend.certification.ov002_endurance_monitor import reconcile_supervisor_and_alerts
from backend.certification.ov002_endurance_monitor import run_monitor_loop
from backend.certification.ov002_persistence import (
    PersistenceError,
    WriterLockError,
    acquire_writer_lock,
    atomic_write_json,
    locked_atomic_write_json,
    strict_json_loads,
)
from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor
from backend.validation.endurance_validation import (
    OV002_AUTHORITATIVE as ENDURANCE_OV002_AUTH,
    PHASE181_AUTHORITATIVE as ENDURANCE_P181_AUTH,
    EnduranceValidationResult,
)
from launcher.css_runtime_launcher import (
    discover_canonical_runtime_processes,
    duplicate_canonical_runtime_owners,
)
import scripts.run_48h_paper_marathon as marathon


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _strong_identity(pid: int, role: str = "launcher") -> dict:
    return {
        "pid": pid,
        "parent_pid": 1,
        "creation_time": "2026-08-01T00:00:00+00:00",
        "executable_path": sys.executable,
        "command_line": f"{sys.executable} {role}",
        "service_role": role,
        "repo_root": "c:/repo",
    }


def _frozen_observed_tree(record: dict, *, service_record: dict | None = None) -> tuple[dict, dict]:
    supervisor_record = dict(record, service_role="supervisor")
    services = {"CSS Runtime": service_record} if service_record is not None else {}
    frozen = {
        "attempt_id": "OV002-A",
        "baseline_commit": "abc123",
        "repo_root": "c:/repo",
        "launcher": record,
        "supervisor": supervisor_record,
        "managed_services": services,
        "launcher_pid": record["pid"],
        "supervisor_pid": supervisor_record["pid"],
    }
    observed = {
        "process_identity": {
            "attempt_id": "OV002-A",
            "baseline_commit": "abc123",
            "repo_root": "c:/repo",
            "launcher_pid": record["pid"],
            "supervisor_pid": supervisor_record["pid"],
            "launcher": record,
            "supervisor": supervisor_record,
            "managed_services": services,
        },
        "duplicate_discovery": {"ok": True, "owners": []},
    }
    return frozen, observed


def _tree_with_services(launcher: dict, services: dict[str, dict]) -> tuple[dict, dict]:
    supervisor_record = dict(launcher, service_role="supervisor")
    frozen = {
        "attempt_id": "OV002-A",
        "baseline_commit": "abc123",
        "repo_root": "c:/repo",
        "launcher": launcher,
        "supervisor": supervisor_record,
        "managed_services": dict(services),
        "launcher_pid": launcher["pid"],
        "supervisor_pid": supervisor_record["pid"],
    }
    observed = {
        "process_identity": {
            "attempt_id": "OV002-A",
            "baseline_commit": "abc123",
            "repo_root": "c:/repo",
            "launcher_pid": launcher["pid"],
            "supervisor_pid": supervisor_record["pid"],
            "launcher": launcher,
            "supervisor": supervisor_record,
            "managed_services": dict(services),
        },
        "duplicate_discovery": {"ok": True, "owners": []},
    }
    return frozen, observed


def test_torn_write_cannot_become_valid_evidence(tmp_path: Path) -> None:
    dest = tmp_path / "RUN_STATUS.json"
    dest.write_text('{"status": "RUNNING", "run_id":', encoding="utf-8")
    with pytest.raises(PersistenceError) as exc:
        from backend.certification.ov002_persistence import read_json_object

        read_json_object(dest)
    assert exc.value.code == "json_malformed"


def test_atomic_replace_failure_fails_closed(tmp_path: Path) -> None:
    dest = tmp_path / "ATTEMPT_STATE.json"
    with patch("backend.certification.ov002_persistence.os.replace", side_effect=OSError("boom")):
        with pytest.raises(PersistenceError) as exc:
            atomic_write_json(dest, {"attempt_state": "RUNNING"})
    assert exc.value.code == "atomic_replace_failed"
    assert not dest.exists()
    assert list(tmp_path.glob(".ATTEMPT_STATE.json.*.tmp")) == []


def test_invalidated_cannot_be_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "ATTEMPT_STATE.json"
    persist_attempt_state(
        path,
        target_state=STATE_INVALIDATED,
        attempt_id="OV002-A",
        baseline_commit="abc123",
    )
    with pytest.raises(ContinuityError) as exc:
        persist_attempt_state(
            path,
            target_state=STATE_RUNNING,
            attempt_id="OV002-A",
            baseline_commit="abc123",
        )
    assert exc.value.code in {"invalidated_terminal", "illegal_attempt_transition", "terminal_state_immutable"}
    assert json.loads(path.read_text(encoding="utf-8"))["attempt_state"] == STATE_INVALIDATED


def test_invalidated_same_binding_replay_is_idempotent_non_writing(tmp_path: Path) -> None:
    path = tmp_path / "ATTEMPT_STATE.json"
    first = persist_attempt_state(
        path,
        target_state=STATE_INVALIDATED,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        reason="first_reason",
    )
    before = path.read_text(encoding="utf-8")
    before_mtime = path.stat().st_mtime_ns
    time.sleep(0.01)
    second = persist_attempt_state(
        path,
        target_state=STATE_INVALIDATED,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        reason="conflicting_second_reason",
    )
    assert second == first
    assert path.read_text(encoding="utf-8") == before
    assert path.stat().st_mtime_ns == before_mtime


def test_malformed_existing_attempt_state_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "ATTEMPT_STATE.json"
    path.write_text(json.dumps({"attempt_state": "WEIRD", "attempt_id": "A", "baseline_commit": "c"}), encoding="utf-8")
    with pytest.raises(ContinuityError) as exc:
        persist_attempt_state(path, target_state=STATE_RUNNING, attempt_id="A", baseline_commit="c")
    assert exc.value.code == "unknown_attempt_state"


def test_attempt_id_and_commit_mismatch_block_update(tmp_path: Path) -> None:
    path = tmp_path / "ATTEMPT_STATE.json"
    persist_attempt_state(path, target_state=STATE_RUNNING, attempt_id="A1", baseline_commit="c1")
    with pytest.raises(ContinuityError) as exc1:
        persist_attempt_state(path, target_state=STATE_INVALIDATED, attempt_id="A2", baseline_commit="c1")
    assert exc1.value.code == "attempt_id_mismatch"
    with pytest.raises(ContinuityError) as exc2:
        persist_attempt_state(path, target_state=STATE_INVALIDATED, attempt_id="A1", baseline_commit="c2")
    assert exc2.value.code == "baseline_commit_mismatch"


def test_pid_only_operational_freeze_rejected() -> None:
    supervisor_state = {
        "supervisor_id": "s",
        "started_at": "2026-08-01T00:00:00+00:00",
        "process_generation": 0,
        "process_identity": {
            "launcher_pid": 10,
            "supervisor_pid": 10,
            "managed_services": {"CSS Runtime": {"pid": 20}},
        },
    }
    with pytest.raises(ContinuityError) as exc:
        freeze_process_identity(
            supervisor_state,
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            require_live_fields=True,
            probe=lambda _pid: None,
        )
    assert exc.value.code == "identity_probe_unavailable"


def test_dead_pid_complete_forged_fields_rejected() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=10)
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=proc.pid,
            role="launcher",
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            parent_pid=1,
            creation_time="2026-08-01T00:00:00+00:00",
            executable_path=sys.executable,
            executable_sha256="0" * 64,
            command_line=f"{sys.executable} forged",
            require_live_fields=True,
        )
    assert exc.value.code == "identity_probe_unavailable"


def test_live_pid_forged_duplicate_fields_rejected() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        live = build_process_identity_record(
            pid=proc.pid,
            role="launcher",
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            require_live_fields=True,
        )
        assert live["pid"] == proc.pid
        forged = {
            "parent_pid": int(live["parent_pid"]) + 999,
            "creation_time": "2026-08-01T00:00:00+00:00",
            "executable_path": str(Path(sys.executable).with_name("forged-python.exe")),
            "executable_sha256": "0" * 64,
            "command_line": f"{sys.executable} forged command",
        }
        for field, value in forged.items():
            kwargs = {
                "pid": proc.pid,
                "role": "launcher",
                "attempt_id": "OV002-A",
                "baseline_commit": "abc123",
                "repo_root": "c:/repo",
                "require_live_fields": True,
                field: value,
            }
            with pytest.raises(ContinuityError) as exc:
                build_process_identity_record(**kwargs)
            assert exc.value.code == "identity_supplied_field_mismatch"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_process_disappearance_during_live_inspection_rejected() -> None:
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=os.getpid(),
            role="launcher",
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            require_live_fields=True,
            probe=lambda _pid: None,
        )
    assert exc.value.code == "identity_probe_unavailable"


def test_final_reconciliation_rejects_matching_json_for_dead_pid() -> None:
    record = build_process_identity_record(
        pid=999999,
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        parent_pid=1,
        creation_time="2026-08-01T00:00:00+00:00",
        executable_path=sys.executable,
        executable_sha256="0" * 64,
        command_line=f"{sys.executable} forged",
    )
    frozen, observed = _frozen_observed_tree(record)

    reasons = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        probe=lambda _pid: None,
    )

    assert any("live_probe_failed:identity_probe_unavailable" in reason for reason in reasons)


def test_final_reconciliation_probe_exception_fails_closed() -> None:
    record = build_process_identity_record(
        pid=os.getpid(),
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        parent_pid=1,
        creation_time="2026-08-01T00:00:00+00:00",
        executable_path=sys.executable,
        executable_sha256="0" * 64,
        command_line=f"{sys.executable} forged",
    )
    frozen, observed = _frozen_observed_tree(record)

    def _raise(_pid: int) -> dict:
        raise RuntimeError("probe boom")

    reasons = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        probe=_raise,
    )

    assert any("live_probe_exception:RuntimeError" in reason for reason in reasons)


def test_final_reconciliation_rejects_live_field_mismatches() -> None:
    base_live = {
        "pid": 4242,
        "parent_pid": 10,
        "creation_time": "2026-08-01T00:00:00+00:00",
        "executable_path": sys.executable,
        "executable_sha256": "1" * 64,
        "command_line": f"{sys.executable} stable",
    }
    record = build_process_identity_record(
        pid=4242,
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        probe=lambda _pid: base_live,
        require_live_fields=True,
    )
    frozen, observed = _frozen_observed_tree(record)

    mismatches = (
        {"parent_pid": 11},
        {"creation_time": "2026-08-01T00:00:01+00:00"},
        {"executable_path": str(Path(sys.executable).with_name("other-python.exe"))},
        {"executable_sha256": "2" * 64},
        {"command_line": f"{sys.executable} changed"},
    )
    for delta in mismatches:
        live = dict(base_live, **delta)
        reasons = reconcile_process_identity_live(
            frozen=frozen,
            observed_supervisor_state=observed,
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            probe=lambda _pid, payload=live: payload,
        )
        assert reasons


def test_final_reconciliation_accepts_valid_stable_live_process() -> None:
    record = build_process_identity_record(
        pid=os.getpid(),
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        require_live_fields=True,
    )
    frozen, observed = _frozen_observed_tree(record)

    reasons = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
    )

    assert reasons == []


def test_final_reconciliation_dead_service_fails_entire_tree() -> None:
    launcher = build_process_identity_record(
        pid=os.getpid(),
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        require_live_fields=True,
    )
    service = build_process_identity_record(
        pid=999999,
        role="CSS Runtime",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        parent_pid=1,
        creation_time="2026-08-01T00:00:00+00:00",
        executable_path=sys.executable,
        executable_sha256="0" * 64,
        command_line=f"{sys.executable} forged",
    )
    frozen, observed = _frozen_observed_tree(launcher, service_record=service)

    reasons = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        probe=lambda pid: None if int(pid) == 999999 else default_identity_probe(pid),
    )

    assert any("process_identity_service:CSS Runtime_live_probe_failed" in reason for reason in reasons)


def test_final_reconciliation_rejects_unexpected_observed_service() -> None:
    launcher = build_process_identity_record(
        pid=os.getpid(),
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        require_live_fields=True,
    )
    unexpected = dict(launcher, service_role="Unexpected")
    frozen, observed = _tree_with_services(launcher, {})
    observed["process_identity"]["managed_services"] = {"Unexpected": unexpected}

    reasons = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
    )

    assert "process_identity_unexpected_service:Unexpected" in reasons


def test_final_reconciliation_rejects_added_missing_renamed_and_case_changed_services() -> None:
    launcher = build_process_identity_record(
        pid=os.getpid(),
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        require_live_fields=True,
    )
    service_a = dict(launcher, service_role="A")
    service_b = dict(launcher, service_role="B")
    frozen, observed = _tree_with_services(launcher, {"A": service_a})
    observed["process_identity"]["managed_services"] = {"A": service_a, "B": service_b}
    added = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
    )
    assert "process_identity_unexpected_service:B" in added

    frozen, observed = _tree_with_services(launcher, {"A": service_a, "B": service_b})
    observed["process_identity"]["managed_services"] = {"A": service_a}
    missing = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
    )
    assert "process_identity_missing_service:B" in missing

    frozen, observed = _tree_with_services(launcher, {"A": service_a})
    observed["process_identity"]["managed_services"] = {"RenamedA": service_a}
    renamed = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
    )
    assert "process_identity_missing_service:A" in renamed
    assert "process_identity_unexpected_service:RenamedA" in renamed

    frozen, observed = _tree_with_services(launcher, {"A": service_a})
    observed["process_identity"]["managed_services"] = {"a": service_a}
    case_changed = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
    )
    assert "process_identity_missing_service:A" in case_changed
    assert "process_identity_unexpected_service:a" in case_changed


def test_final_reconciliation_accepts_exact_service_set_in_different_order() -> None:
    launcher = build_process_identity_record(
        pid=os.getpid(),
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        require_live_fields=True,
    )
    service_a = dict(launcher, service_role="A")
    service_b = dict(launcher, service_role="B")
    frozen, observed = _tree_with_services(launcher, {"A": service_a, "B": service_b})
    observed["process_identity"]["managed_services"] = {"B": service_b, "A": service_a}

    reasons = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
    )

    assert reasons == []


def test_final_reconciliation_unexpected_services_are_sorted_and_not_live_probed() -> None:
    launcher = build_process_identity_record(
        pid=os.getpid(),
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        require_live_fields=True,
    )
    frozen, observed = _tree_with_services(launcher, {})
    observed["process_identity"]["managed_services"] = {
        "Zulu": {"pid": 999999},
        "Alpha": {"pid": 999998},
    }
    probed: list[int] = []

    def _probe(pid: int) -> dict | None:
        probed.append(int(pid))
        return default_identity_probe(pid)

    reasons = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        probe=_probe,
    )

    unexpected = [reason for reason in reasons if reason.startswith("process_identity_unexpected_service:")]
    assert unexpected == [
        "process_identity_unexpected_service:Alpha",
        "process_identity_unexpected_service:Zulu",
    ]
    assert 999998 not in probed
    assert 999999 not in probed


def test_final_reconciliation_malformed_managed_services_fail_closed() -> None:
    launcher = build_process_identity_record(
        pid=os.getpid(),
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        require_live_fields=True,
    )
    frozen, observed = _tree_with_services(launcher, {})
    observed["process_identity"]["managed_services"] = None
    reasons = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
    )
    assert "process_identity_managed_services_malformed:observed" in reasons

    frozen["managed_services"] = {" ": launcher, 7: launcher, "NestedBad": ["not", "object"]}
    observed["process_identity"]["managed_services"] = {}
    malformed = reconcile_process_identity_live(
        frozen=frozen,
        observed_supervisor_state=observed,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
    )
    assert "process_identity_managed_service_name_malformed:frozen:blank" in malformed
    assert "process_identity_managed_service_name_malformed:frozen:7" in malformed
    assert "process_identity_managed_service_malformed:frozen:NestedBad" in malformed


def test_duplicate_service_key_strict_json_rejected() -> None:
    raw = '{"managed_services":{"CSS Runtime":{"pid":1},"CSS Runtime":{"pid":2}}}'
    with pytest.raises(PersistenceError) as exc:
        strict_json_loads(raw, source="process_identity")
    assert exc.value.code == "json_duplicate_key"


def test_monitor_reconciliation_consumes_unexpected_service_reason() -> None:
    launcher = build_process_identity_record(
        pid=os.getpid(),
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        require_live_fields=True,
    )
    frozen, observed = _tree_with_services(launcher, {})
    observed["process_identity"]["managed_services"] = {"Unexpected": dict(launcher, service_role="Unexpected")}
    supervisor_state = {
        "status": "RUNNING",
        "started_at": "2026-08-01T00:00:00+00:00",
        "last_heartbeat_at": "2026-08-01T00:01:00+00:00",
        "restart_count": 0,
        "restart_attempt_count": 0,
        "max_restart_limit": 3,
        "process_generation": 0,
        "restart_limit_exhausted": False,
        "process_identity": observed["process_identity"],
        "duplicate_discovery": {"ok": True, "owners": []},
    }

    result = reconcile_supervisor_and_alerts(
        supervisor_state=supervisor_state,
        alerts=[],
        run_meta={
            "run_id": "OV002-A",
            "frozen_sha": "abc123",
            "start_utc": "2026-08-01T00:00:00+00:00",
            "process_identity_freeze": frozen,
        },
        now=datetime(2026, 8, 1, 0, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert "process_identity_unexpected_service:Unexpected" in result["reasons"]


def test_monitor_reconciliation_cannot_rely_only_on_matching_json() -> None:
    record = build_process_identity_record(
        pid=999999,
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        parent_pid=1,
        creation_time="2026-08-01T00:00:00+00:00",
        executable_path=sys.executable,
        executable_sha256="0" * 64,
        command_line=f"{sys.executable} forged",
    )
    frozen, observed = _frozen_observed_tree(record)
    supervisor_state = {
        "status": "RUNNING",
        "started_at": "2026-08-01T00:00:00+00:00",
        "last_heartbeat_at": "2026-08-01T00:01:00+00:00",
        "restart_count": 0,
        "restart_attempt_count": 0,
        "max_restart_limit": 3,
        "process_generation": 0,
        "restart_limit_exhausted": False,
        "process_identity": observed["process_identity"],
        "duplicate_discovery": {"ok": True, "owners": []},
    }

    result = reconcile_supervisor_and_alerts(
        supervisor_state=supervisor_state,
        alerts=[],
        run_meta={
            "run_id": "OV002-A",
            "frozen_sha": "abc123",
            "start_utc": "2026-08-01T00:00:00+00:00",
            "process_identity_freeze": frozen,
        },
        now=datetime(2026, 8, 1, 0, 1, tzinfo=timezone.utc),
        process_identity_probe=lambda _pid: None,
    )

    assert result["ok"] is False
    assert any("live_probe_failed:identity_probe_unavailable" in reason for reason in result["reasons"])


def test_missing_required_live_field_rejected() -> None:
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=10,
            role="launcher",
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            parent_pid=1,
            creation_time="2026-08-01T00:00:00+00:00",
            executable_path=sys.executable,
            command_line=None,
            require_live_fields=True,
        )
    assert exc.value.code == "identity_probe_unavailable"


def test_more_than_1000_newer_alerts_cannot_hide_older_critical(tmp_path: Path) -> None:
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    start = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    # Older in-window critical
    (alerts / "alert_0000_old_critical.json").write_text(
        json.dumps(
            {
                "alert_id": "old-critical",
                "severity": "CRITICAL",
                "timestamp": _iso(start + timedelta(minutes=1)),
                "message": "ENGINE_HEARTBEAT_LOST",
                "metadata": {"event_type": "ENGINE_HEARTBEAT_LOST"},
            }
        ),
        encoding="utf-8",
    )
    # 1001 newer INFO alerts
    for i in range(1, 1002):
        (alerts / f"alert_{i:04d}_new.json").write_text(
            json.dumps(
                {
                    "alert_id": f"new-{i}",
                    "severity": "INFO",
                    "timestamp": _iso(start + timedelta(minutes=2 + i)),
                    "message": "noise",
                }
            ),
            encoding="utf-8",
        )
    # now must cover the newest alert timestamps (avoid future_skew fail-closed)
    payload = _load_alerts_since(alerts, _iso(start), now=start + timedelta(days=2))
    assert payload["scan_complete"] is True
    assert payload["ok"] is True
    ids = {a.get("alert_id") for a in payload["alerts"]}
    assert "old-critical" in ids
    assert len(payload["alerts"]) >= 1002


def test_malformed_alert_prevents_complete_reconciliation(tmp_path: Path) -> None:
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    (alerts / "bad.json").write_text("{not-json", encoding="utf-8")
    (alerts / "good.json").write_text(
        json.dumps({"alert_id": "g1", "severity": "INFO", "timestamp": _iso(start + timedelta(seconds=1))}),
        encoding="utf-8",
    )
    payload = _load_alerts_since(alerts, _iso(start), now=start + timedelta(hours=1))
    assert payload["ok"] is False
    assert payload["scan_complete"] is False
    assert any("alert_malformed" in e for e in payload["errors"])


def test_duplicate_key_critical_alert_rejected(tmp_path: Path) -> None:
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    (alerts / "dup.json").write_text(
        '{"alert_id":"dup","severity":"CRITICAL","severity":"INFO",'
        '"timestamp":"2026-08-01T00:01:00+00:00","message":"ENGINE_HEARTBEAT_LOST"}',
        encoding="utf-8",
    )
    payload = _load_alerts_since(alerts, _iso(start), now=start + timedelta(hours=1))
    assert payload["ok"] is False
    assert payload["scan_complete"] is False
    assert any("alert_malformed:dup.json" == e for e in payload["errors"])


def test_duplicate_key_invalidation_cannot_disappear(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "INVALIDATION.json").write_text(
        '{"invalidated":true,"invalidated":false,"reasons":[]}',
        encoding="utf-8",
    )
    result = run_monitor_loop(pkg, once=True)
    assert result["status"] == "INVALIDATED"
    assert any("invalidation_evidence_invalid" in r for r in result["invalidation"]["reasons"])


def test_malformed_invalidation_and_status_block_eligibility(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "INVALIDATION.json").write_text("{broken", encoding="utf-8")
    (pkg / "RUN_STATUS.json").write_text('{"status":"RUNNING"}', encoding="utf-8")
    result = run_monitor_loop(pkg, once=True)
    assert result["status"] == "INVALIDATED"
    assert any("invalidation_evidence_invalid" in r for r in result["invalidation"]["reasons"])

    pkg2 = tmp_path / "pkg2"
    pkg2.mkdir()
    (pkg2 / "RUN_STATUS.json").write_text('{"status":"RUNNING","status":"INVALIDATED"}', encoding="utf-8")
    result2 = run_monitor_loop(pkg2, once=True)
    assert result2["status"] == "INVALIDATED"
    assert any("run_status_evidence_invalid" in r for r in result2["invalidation"]["reasons"])


def test_missing_run_meta_half_initialized_package_fails_closed(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    persist_attempt_state(
        pkg / "ATTEMPT_STATE.json",
        target_state=STATE_RUNNING,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        expected_root=pkg,
    )
    result = run_monitor_loop(pkg, once=True)
    assert result["status"] == "INVALIDATED"
    assert "run_meta_missing" in result["invalidation"]["reasons"]


def test_duplicate_nested_authority_state_and_ledger_keys_rejected() -> None:
    with pytest.raises(PersistenceError) as auth_exc:
        strict_json_loads('{"authority":{"ov002_authoritative":false,"ov002_authoritative":true}}')
    assert auth_exc.value.code == "json_duplicate_key"
    with pytest.raises(PersistenceError) as state_exc:
        strict_json_loads('{"attempt_state":"INVALIDATED","attempt_state":"RUNNING"}')
    assert state_exc.value.code == "json_duplicate_key"
    with pytest.raises(PersistenceError) as ledger_exc:
        strict_json_loads('{"sequence":1,"sequence":2,"digest":"x"}')
    assert ledger_exc.value.code == "json_duplicate_key"


def test_truncated_ledger_prevents_eligibility(tmp_path: Path) -> None:
    ledger = tmp_path / "CRITICAL_EVENTS.jsonl"
    ledger.write_text('{"sequence":1,"alert_id":"x"}', encoding="utf-8")  # no trailing newline
    loaded = load_critical_event_ledger(ledger)
    assert loaded["ok"] is False
    assert loaded["complete"] is False
    assert any("truncated" in e for e in loaded["errors"])
    result = evaluate_final_certification(
        run_meta={"run_id": "A", "frozen_sha": "c"},
        run_status={"status": "COMPLETE"},
        invalidation=None,
        reconciliation_ok=True,
        reconciliation_reasons=[],
        alert_errors=[],
        expected_run_id="A",
        expected_commit="c",
        critical_ledger=loaded,
        critical_alerts=[],
    )
    assert result.eligible is False
    assert "critical_ledger_incomplete" in result.reasons or any("truncated" in r for r in result.reasons)


def test_alert_count_sequence_digest_mismatch_blocks_eligibility() -> None:
    events = [
        {
            "sequence": 1,
            "alert_id": "a1",
            "code": "ENGINE_HEARTBEAT_LOST",
            "timestamp": "2026-08-01T00:00:00+00:00",
            "severity": "CRITICAL",
            "attempt_id": "A",
            "baseline_commit": "c",
        }
    ]
    from backend.certification.ov002_continuity import critical_alert_digest, reconcile_critical_ledger_with_alerts

    ledger = {
        "ok": True,
        "complete": True,
        "events": events,
        "count": 2,  # wrong
        "sequence": 1,
        "digest": "deadbeef",
        "errors": [],
        "attempt_id": "A",
        "baseline_commit": "c",
    }
    recon = reconcile_critical_ledger_with_alerts(
        ledger=ledger,
        critical_alerts=events,
        expected_attempt_id="A",
        expected_commit="c",
    )
    assert recon["ok"] is False
    assert "critical_ledger_count_mismatch" in recon["reasons"]
    assert "critical_ledger_digest_mismatch" in recon["reasons"]


def test_same_pid_different_creation_time_fails() -> None:
    frozen = {
        "launcher": {
            "pid": 10,
            "parent_pid": 1,
            "creation_time": "2026-08-01T00:00:00+00:00",
            "executable_path": "abc",
            "command_identity": "def",
            "repo_root": "c:/repo",
            "service_role": "launcher",
            "attempt_id": "A",
            "baseline_commit": "c",
            "schema_version": "css.ov002.process_identity.v2",
        },
        "supervisor": {
            "pid": 10,
            "parent_pid": 1,
            "creation_time": "2026-08-01T00:00:00+00:00",
            "executable_path": "abc",
            "command_identity": "def",
            "repo_root": "c:/repo",
            "service_role": "supervisor",
            "attempt_id": "A",
            "baseline_commit": "c",
            "schema_version": "css.ov002.process_identity.v2",
        },
        "managed_services": {},
        "launcher_pid": 10,
        "supervisor_pid": 10,
    }
    observed = {
        "process_identity": {
            "launcher_pid": 10,
            "supervisor_pid": 10,
            "launcher": {
                "pid": 10,
                "parent_pid": 1,
                "creation_time": "2026-08-01T01:00:00+00:00",
                "executable_path": "abc",
                "command_identity": "def",
                "repo_root": "c:/repo",
                "service_role": "launcher",
                "attempt_id": "A",
                "baseline_commit": "c",
                "schema_version": "css.ov002.process_identity.v2",
            },
            "supervisor": {
                "pid": 10,
                "parent_pid": 1,
                "creation_time": "2026-08-01T00:00:00+00:00",
                "executable_path": "abc",
                "command_identity": "def",
                "repo_root": "c:/repo",
                "service_role": "supervisor",
                "attempt_id": "A",
                "baseline_commit": "c",
                "schema_version": "css.ov002.process_identity.v2",
            },
            "managed_services": {},
        },
        "duplicate_discovery": {"ok": True, "owners": []},
    }
    reasons = validate_process_identity(frozen=frozen, observed_supervisor_state=observed)
    assert any("creation_time_mismatch" in r for r in reasons)


@pytest.mark.parametrize(
    "field,value",
    [
        ("parent_pid", 99),
        ("executable_path", "zzz"),
        ("command_identity", "zzz"),
        ("repo_root", "d:/other"),
        ("service_role", "wrong"),
    ],
)
def test_identity_field_mismatches_fail(field: str, value: object) -> None:
    base = {
        "pid": 10,
        "parent_pid": 1,
        "creation_time": "2026-08-01T00:00:00+00:00",
        "executable_path": "abc",
        "command_identity": "def",
        "repo_root": "c:/repo",
        "service_role": "launcher",
        "attempt_id": "A",
        "baseline_commit": "c",
        "schema_version": "css.ov002.process_identity.v2",
    }
    observed_rec = dict(base)
    observed_rec[field] = value
    frozen = {
        "launcher": base,
        "supervisor": dict(base, service_role="supervisor"),
        "managed_services": {},
        "launcher_pid": 10,
        "supervisor_pid": 10,
    }
    observed = {
        "process_identity": {
            "launcher_pid": 10,
            "supervisor_pid": 10,
            "launcher": observed_rec,
            "supervisor": dict(base, service_role="supervisor"),
            "managed_services": {},
        },
        "duplicate_discovery": {"ok": True, "owners": []},
    }
    reasons = validate_process_identity(frozen=frozen, observed_supervisor_state=observed)
    assert any(field in r and "mismatch" in r for r in reasons)


def test_missing_required_identity_fails() -> None:
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=1,
            role="launcher",
            attempt_id="A",
            baseline_commit="c",
            repo_root="c:/repo",
            require_live_fields=True,
            probe=lambda _pid: None,
        )
    assert exc.value.code == "identity_probe_unavailable"


def test_malformed_pid_and_timestamp_fail_without_uncaught_exception() -> None:
    with pytest.raises(ContinuityError):
        build_process_identity_record(
            pid="not-a-pid",
            role="launcher",
            attempt_id="A",
            baseline_commit="c",
            repo_root="c:/repo",
        )
    with pytest.raises(ContinuityError):
        build_process_identity_record(
            pid=1,
            role="launcher",
            attempt_id="A",
            baseline_commit="c",
            repo_root="c:/repo",
            creation_time="not-a-time",
        )


def test_duplicate_discovery_exception_fails_closed() -> None:
    with patch(
        "launcher.css_runtime_launcher.subprocess.run",
        side_effect=RuntimeError("boom"),
    ):
        result = discover_canonical_runtime_processes(repo_root="C:/rasib/source/capital-strata-systems")
    assert result["ok"] is False
    assert result["error_code"] == "discovery_exception"
    assert result["processes"] == []
    dup = duplicate_canonical_runtime_owners(repo_root="C:/rasib/source/capital-strata-systems")
    # should also fail closed when discovery fails — call with patched discover
    with patch(
        "launcher.css_runtime_launcher.discover_canonical_runtime_processes",
        return_value={"ok": False, "processes": [], "error_code": "discovery_exception"},
    ):
        dup2 = duplicate_canonical_runtime_owners()
    assert dup2["ok"] is False
    assert dup2.get("error_code") == "discovery_exception"


def test_mid_run_discovery_failure_invalidates_via_supervisor_field() -> None:
    frozen = freeze_process_identity(
        {
            "supervisor_id": "s",
            "started_at": "2026-08-01T00:00:00+00:00",
            "process_generation": 0,
            "process_identity": {
                "launcher_pid": 1,
                "supervisor_pid": 1,
                "managed_services": {},
            },
            "failure_history_path": "x",
        },
        attempt_id="A",
        baseline_commit="c",
        repo_root="c:/repo",
        probe=lambda _pid: {
            "pid": 1,
            "parent_pid": 0,
            "creation_time": "2026-08-01T00:00:00+00:00",
            "executable_path": "c:/py.exe",
            "command_line": "python launcher",
        },
    )
    observed = {
        "process_identity": {
            "launcher_pid": 1,
            "supervisor_pid": 1,
            "launcher": frozen["launcher"],
            "supervisor": frozen["supervisor"],
            "managed_services": {},
            "schema_version": "css.ov002.process_identity.v2",
        },
        "duplicate_discovery": {"ok": False, "owners": [], "error_code": "discovery_exception"},
    }
    reasons = validate_process_identity(frozen=frozen, observed_supervisor_state=observed)
    assert "duplicate_discovery_failed" in reasons


def test_concurrent_and_stale_writer_lock_fail_closed(tmp_path: Path) -> None:
    lock_path = tmp_path / "x.json.writer.lock"
    lock1 = acquire_writer_lock(lock_path, attempt_id="A", writer_role="monitor", lease_seconds=60)
    with pytest.raises(WriterLockError) as held:
        acquire_writer_lock(lock_path, attempt_id="A", writer_role="supervisor", lease_seconds=60)
    assert held.value.code == "writer_lock_held"
    lock1.release()

    # Stale lock: write expired lease file then fail closed (no steal)
    stale = {
        "schema_version": "css.ov002.writer_lock.v1",
        "attempt_id": "A",
        "writer_role": "monitor",
        "lease_until_epoch": 1.0,
        "pid": 1,
    }
    lock_path.write_text(json.dumps(stale), encoding="utf-8")
    with pytest.raises(WriterLockError) as stale_exc:
        acquire_writer_lock(lock_path, attempt_id="A", writer_role="monitor", lease_seconds=60, now_epoch=100.0)
    assert stale_exc.value.code == "writer_lock_stale"


def test_outside_root_and_symlink_paths_rejected(tmp_path: Path) -> None:
    root = tmp_path / "attempt"
    root.mkdir()
    outside = tmp_path / "outside.json"
    with pytest.raises(PersistenceError) as outside_exc:
        atomic_write_json(outside, {"x": 1}, expected_root=root)
    assert outside_exc.value.code == "path_outside_expected_root"
    link = root / "link.json"
    target = tmp_path / "target.json"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        return
    with pytest.raises(PersistenceError) as link_exc:
        atomic_write_json(link, {"x": 1}, expected_root=root)
    assert link_exc.value.code == "path_reparse_or_symlink"


def test_rooted_supervisor_state_guards(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    with pytest.raises(PersistenceError) as no_root_ctor:
        CSSRuntimeSupervisor(state_dir=str(root / "absolute_without_root"))
    assert no_root_ctor.value.code == "supervisor_trusted_root_required"

    sup = CSSRuntimeSupervisor(state_dir=str(root / "supervisor"), trusted_root=root)
    sup.start()
    assert Path(sup.state_file).is_file()
    assert Path(sup.state_dir).is_relative_to(root)
    with pytest.raises(PersistenceError):
        CSSRuntimeSupervisor(state_dir=str(tmp_path / "outside" / "supervisor"), trusted_root=root)
    relative = CSSRuntimeSupervisor(state_dir="relative_supervisor", trusted_root=root)
    assert Path(relative.state_dir).is_relative_to(root)
    assert Path(relative.trusted_root).resolve() == root.resolve()
    sup.trusted_root = None
    with pytest.raises(PersistenceError) as no_root:
        sup._persist_state()
    assert no_root.value.code == "supervisor_trusted_root_missing"


def test_supervisor_symlink_parent_rejected(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        return
    with pytest.raises(PersistenceError) as exc:
        CSSRuntimeSupervisor(state_dir=str(link / "supervisor"), trusted_root=root)
    assert exc.value.code == "path_reparse_or_symlink"


def test_wrong_owner_lock_release_rejected(tmp_path: Path) -> None:
    root = tmp_path / "attempt"
    root.mkdir()
    lock_path = root / "x.json.writer.lock"
    lock = acquire_writer_lock(lock_path, attempt_id="A", writer_role="monitor", expected_root=root)
    try:
        lock.release()
        lock_path.write_text(
            json.dumps(
                {
                    "schema_version": "css.ov002.writer_lock.v1",
                    "attempt_id": "B",
                    "writer_role": "other",
                    "lease_until_epoch": time.time() + 60,
                }
            ),
            encoding="utf-8",
        )
        lock.released = False
        with pytest.raises(WriterLockError) as exc:
            lock.release()
        assert exc.value.code == "writer_lock_wrong_owner"
    finally:
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def test_malformed_run_meta_deterministic_invalidation(tmp_path: Path) -> None:
    from backend.certification.ov002_endurance_monitor import run_monitor_loop

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "snapshots").mkdir()
    (pkg / "checkpoints").mkdir()
    (pkg / "resources").mkdir()
    (pkg / "brokers").mkdir()
    (pkg / "RUN_META.json").write_text("{broken", encoding="utf-8")
    result = run_monitor_loop(pkg, once=True, target_hours=1.0)
    assert result["status"] == "INVALIDATED"
    reasons = (result.get("invalidation") or {}).get("reasons") or []
    assert any("run_meta" in str(r) for r in reasons)


def test_legacy_pass_go_certified_grants_no_ov002_or_phase181_credit() -> None:
    assert marathon.OV002_AUTHORITATIVE is False
    assert marathon.PHASE181_AUTHORITATIVE is False
    assert ENDURANCE_OV002_AUTH is False
    assert ENDURANCE_P181_AUTH is False

    legacy = {
        "source": "run_48h_paper_marathon",
        "go_no_go": "GO",
        "status": "PASS",
        "certification_status": "CERTIFIED",
    }
    reasons = reject_legacy_certification_authority(legacy)
    assert "legacy_certification_non_authoritative_ov002" in reasons
    assert "legacy_certification_non_authoritative_phase181" in reasons

    result = evaluate_final_certification(
        run_meta={"run_id": "A", "frozen_sha": "c"},
        run_status={"status": "COMPLETE"},
        invalidation=None,
        reconciliation_ok=True,
        reconciliation_reasons=[],
        alert_errors=[],
        expected_run_id="A",
        expected_commit="c",
        legacy_authority_payload=legacy,
    )
    assert result.eligible is False
    assert result.certification == STATE_NOT_CERTIFIED
    assert result.to_dict()["phase181"] == STATE_NOT_CERTIFIED

    endurance = EnduranceValidationResult(
        status="PASS",
        readiness_score=100.0,
        go_no_go="GO",
        critical_findings=(),
        warnings=(),
        informational_findings=(),
        recommended_actions=(),
        metrics={},
    )
    payload = endurance.to_dict()
    assert payload["ov002_authoritative"] is False
    assert payload["phase181_authoritative"] is False


def test_legacy_config_duplicate_keys_fail_closed(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text(
        '{"system":{"mode":"paper","mode":"live"},"oanda":{"environment":"practice"}}',
        encoding="utf-8",
    )
    with pytest.raises(marathon.MarathonExecutionPrepError):
        marathon._load_config(config)


def test_historical_attempt2_remains_invalidated() -> None:
    result = reject_historical_attempt2_as_pass(
        {"restart_count": 8, "heartbeat_lost_count": 2, "status": "PASS"}
    )
    assert result.attempt_state == STATE_INVALIDATED
    assert result.eligible is False
    assert result.certification == STATE_NOT_CERTIFIED


def test_illegal_transition_from_invalidated() -> None:
    with pytest.raises(ContinuityError):
        transition_attempt_state(STATE_INVALIDATED, STATE_RUNNING)


def test_not_certified_terminal_transition_is_immutable() -> None:
    with pytest.raises(ContinuityError) as exc:
        transition_attempt_state(STATE_NOT_CERTIFIED, STATE_INVALIDATED)
    assert exc.value.code == "terminal_state_immutable"
