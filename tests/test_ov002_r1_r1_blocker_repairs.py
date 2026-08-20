"""OV002-R1-R1 adversarial repairs — deterministic offline tests (no CSS runtime)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.certification.ov002_continuity import (
    PROCESS_IDENTITY_SCHEMA,
    STATE_INVALIDATED,
    STATE_NOT_CERTIFIED,
    STATE_RUNNING,
    ContinuityError,
    MAX_CANONICAL_PROCESS_PID,
    _build_authoritative_process_identity_reconciliation,
    build_process_identity_record,
    build_process_identity_reconciliation_result,
    canonical_process_pid,
    canonical_process_pid_error,
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
    DISCOVERY_SCHEMA,
    discover_canonical_runtime_processes,
    duplicate_canonical_runtime_owners,
)
import scripts.run_48h_paper_marathon as marathon


class DerivedPid(int):
    pass


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
        "schema_version": PROCESS_IDENTITY_SCHEMA,
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
            "schema_version": PROCESS_IDENTITY_SCHEMA,
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
        "schema_version": PROCESS_IDENTITY_SCHEMA,
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
            "schema_version": PROCESS_IDENTITY_SCHEMA,
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
    assert result["error_code"] == "discovery_enumeration_exception"
    assert result["processes"] == []
    # should also fail closed when discovery fails — call with patched discover
    with patch(
        "launcher.css_runtime_launcher.discover_canonical_runtime_processes",
        return_value={
            "ok": False,
            "processes": [],
            "error_code": "discovery_enumeration_exception",
        },
    ):
        dup2 = duplicate_canonical_runtime_owners()
    assert dup2["ok"] is False
    assert dup2.get("error_code") == "discovery_enumeration_exception"


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
                "parent_pid": 2,
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


# ═══════════════════════════════════════════════════════════════════════════════
# R6 — continuity-evidence fail-closed repairs (B1, H1, H2, M1–M4, L2/L3)
# ═══════════════════════════════════════════════════════════════════════════════


_R6_LIVE = {
    "parent_pid": 4,
    "creation_time": "2026-08-01T00:00:00+00:00",
    "executable_path": sys.executable,
    "executable_sha256": "1" * 64,
    "command_line": f"{sys.executable} -m launcher.css_runtime_launcher",
}


def _r6_probe(pid: int) -> dict:
    """Deterministic complete live payload — keeps R6 tests offline and fast."""
    return dict(_R6_LIVE, pid=int(pid))


def _r6_live_record(role: str = "launcher") -> dict:
    return build_process_identity_record(
        pid=os.getpid(),
        role=role,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        require_live_fields=True,
        probe=_r6_probe,
    )


def _r6_freeze(**overrides) -> dict:
    launcher = _r6_live_record("launcher")
    freeze = {
        "schema_version": PROCESS_IDENTITY_SCHEMA,
        "attempt_id": "OV002-A",
        "baseline_commit": "abc123",
        "repo_root": "c:/repo",
        "launcher": launcher,
        "supervisor": dict(launcher, service_role="supervisor"),
        "managed_services": {},
        "launcher_pid": launcher["pid"],
        "supervisor_pid": launcher["pid"],
    }
    freeze.update(overrides)
    return freeze


def _r6_supervisor_state(now: datetime, freeze: dict, **overrides) -> dict:
    state = {
        "status": "RUNNING",
        "started_at": _iso(now - timedelta(minutes=1)),
        "last_heartbeat_at": _iso(now),
        "restart_count": 0,
        "restart_attempt_count": 0,
        "max_restart_limit": 3,
        "process_generation": 0,
        "restart_limit_exhausted": False,
        "failure_history": [],
        "process_identity": {
            "schema_version": PROCESS_IDENTITY_SCHEMA,
            "attempt_id": freeze["attempt_id"],
            "baseline_commit": freeze["baseline_commit"],
            "repo_root": freeze["repo_root"],
            "launcher_pid": freeze["launcher_pid"],
            "supervisor_pid": freeze["supervisor_pid"],
            "launcher": freeze["launcher"],
            "supervisor": freeze["supervisor"],
            "managed_services": dict(freeze.get("managed_services") or {}),
        },
        "duplicate_discovery": {"ok": True, "owners": []},
    }
    state.update(overrides)
    return state


# ─── B1: missing / malformed process_identity_freeze fails closed ─────────────

@pytest.mark.parametrize(
    "freeze_value,expected_reason",
    [
        (None, "process_identity_freeze_missing"),
        ("not-a-mapping", "process_identity_freeze_malformed"),
        ([], "process_identity_freeze_malformed"),
        ({}, "process_identity_freeze_empty"),
    ],
)
def test_r6_missing_or_malformed_freeze_is_reconciled_not_skipped(
    freeze_value: object, expected_reason: str
) -> None:
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    freeze = _r6_freeze()
    run_meta = {"run_id": "OV002-A", "frozen_sha": "abc123", "start_utc": _iso(now)}
    if freeze_value is not None:
        run_meta["process_identity_freeze"] = freeze_value

    result = reconcile_supervisor_and_alerts(
        supervisor_state=_r6_supervisor_state(now, freeze, restart_count=1),
        alerts=[],
        run_meta=run_meta,
        now=now,
    )

    assert result["ok"] is False
    assert expected_reason in result["reasons"]
    # Reconciliation is not skipped: unrelated supervisor faults are still detected.
    assert "unexpected_supervisor_restart_observed" in result["reasons"]


@pytest.mark.parametrize(
    "mutation,expected_reason",
    [
        ({"launcher": None}, "process_identity_freeze_launcher_missing"),
        ({"supervisor": None}, "process_identity_freeze_supervisor_missing"),
        ({"launcher": "junk"}, "process_identity_freeze_launcher_malformed"),
        ({"supervisor": {}}, "process_identity_freeze_supervisor_empty"),
        ({"launcher": {"service_role": "launcher"}}, "process_identity_freeze_launcher_pid_missing"),
        ({"managed_services": []}, "process_identity_freeze_managed_services_malformed"),
    ],
)
def test_r6_structurally_invalid_freeze_reasons(mutation: dict, expected_reason: str) -> None:
    from backend.certification.ov002_continuity import validate_process_identity_freeze

    freeze = _r6_freeze()
    freeze.update(mutation)
    assert expected_reason in validate_process_identity_freeze(freeze)


def test_r6_preflight_before_freeze_does_not_require_freeze() -> None:
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    freeze = _r6_freeze()
    result = reconcile_supervisor_and_alerts(
        supervisor_state=_r6_supervisor_state(now, freeze),
        alerts=[],
        run_meta={"start_utc": _iso(now)},
        now=now,
        require_process_identity_freeze=False,
        process_identity_probe=_r6_probe,
    )
    assert result["ok"] is True
    assert result["reasons"] == []


def test_r6_freeze_validates_persisted_evidence_from_package_root(tmp_path: Path) -> None:
    from backend.certification.ov002_continuity import (
        load_process_identity_evidence,
        validate_process_identity_freeze,
    )

    freeze = _r6_freeze()
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    assert validate_process_identity_freeze(freeze, package_root=pkg) == [
        "process_identity_evidence_missing"
    ]

    (pkg / "PROCESS_IDENTITY.json").write_text(json.dumps(freeze), encoding="utf-8")
    assert validate_process_identity_freeze(freeze, package_root=pkg) == []

    evidence, reasons = load_process_identity_evidence(pkg)
    assert reasons == []
    assert evidence is not None and evidence["attempt_id"] == "OV002-A"

    (pkg / "PROCESS_IDENTITY.json").write_text('{"attempt_id":"A","attempt_id":"B"}', encoding="utf-8")
    blocked = validate_process_identity_freeze(freeze, package_root=pkg)
    assert any("process_identity_evidence_invalid" in reason for reason in blocked)


def test_r6_evidence_must_be_bound_to_same_attempt_and_commit() -> None:
    from backend.certification.ov002_continuity import validate_process_identity_evidence

    freeze = _r6_freeze()
    assert validate_process_identity_evidence(
        freeze, freeze=freeze, expected_attempt_id="OV002-A", expected_commit="abc123"
    ) == []

    wrong_attempt = dict(freeze, attempt_id="OV002-B")
    assert "process_identity_evidence_attempt_id_mismatch" in validate_process_identity_evidence(
        wrong_attempt, expected_attempt_id="OV002-A"
    )
    wrong_commit = dict(freeze, baseline_commit="def456")
    assert "process_identity_evidence_baseline_commit_mismatch" in validate_process_identity_evidence(
        wrong_commit, expected_commit="abc123"
    )
    wrong_pid = dict(freeze, launcher=dict(freeze["launcher"], pid=999999))
    assert "process_identity_evidence_launcher_pid_mismatch" in validate_process_identity_evidence(
        wrong_pid, freeze=freeze
    )
    extra_service = dict(freeze, managed_services={"Extra": dict(freeze["launcher"], service_role="Extra")})
    assert "process_identity_evidence_managed_services_mismatch" in validate_process_identity_evidence(
        extra_service, freeze=freeze
    )


def _r6_final_certification(**overrides):
    auto_reconciliation = overrides.pop("auto_reconciliation", True)
    kwargs = {
        "run_meta": {"run_id": "OV002-A", "frozen_sha": "abc123"},
        "run_status": {"status": "COMPLETE"},
        "invalidation": None,
        "reconciliation_ok": True,
        "reconciliation_reasons": [],
        "alert_errors": [],
        "expected_run_id": "OV002-A",
        "expected_commit": "abc123",
    }
    kwargs.update(overrides)
    freeze = kwargs.get("process_identity_freeze")
    evidence = kwargs.get("process_identity_evidence")
    if (
        auto_reconciliation
        and "process_identity_reconciliation" not in kwargs
        and isinstance(freeze, dict)
        and isinstance(evidence, dict)
        and kwargs.get("expected_run_id")
        and kwargs.get("expected_commit")
    ):
        kwargs["process_identity_reconciliation"] = _build_authoritative_process_identity_reconciliation(
            expected_run_id=str(kwargs["expected_run_id"]),
            expected_commit=str(kwargs["expected_commit"]),
            freeze=freeze,
            evidence=evidence,
            reasons=list(kwargs.get("process_identity_reasons") or []),
        )
    return evaluate_final_certification(**kwargs)


def test_r6_final_certification_requires_continuity_evidence() -> None:
    freeze = _r6_freeze()

    missing_freeze = _r6_final_certification(process_identity_evidence=freeze)
    assert missing_freeze.eligible is False
    assert missing_freeze.certification == STATE_NOT_CERTIFIED
    assert "process_identity_freeze_missing" in missing_freeze.reasons

    missing_evidence = _r6_final_certification(process_identity_freeze=freeze)
    assert missing_evidence.eligible is False
    assert "process_identity_evidence_missing" in missing_evidence.reasons

    empty_freeze = _r6_final_certification(
        process_identity_freeze={}, process_identity_evidence=freeze
    )
    assert empty_freeze.eligible is False
    assert "process_identity_freeze_empty" in empty_freeze.reasons

    live_reasons = _r6_final_certification(
        process_identity_freeze=freeze,
        process_identity_evidence=freeze,
        process_identity_reasons=["process_identity_launcher_live_probe_failed:identity_probe_unavailable"],
    )
    assert live_reasons.eligible is False
    assert (
        "process_identity_launcher_live_probe_failed:identity_probe_unavailable"
        in live_reasons.reasons
    )

    complete = _r6_final_certification(
        process_identity_freeze=freeze,
        process_identity_evidence=freeze,
        process_identity_reasons=[],
    )
    assert complete.eligible is True
    assert complete.certification == STATE_NOT_CERTIFIED


def test_r6_final_certification_reads_freeze_from_run_meta() -> None:
    freeze = _r6_freeze()
    reconciliation = _build_authoritative_process_identity_reconciliation(
        expected_run_id="OV002-A",
        expected_commit="abc123",
        freeze=freeze,
        evidence=freeze,
        reasons=[],
    )
    result = _r6_final_certification(
        run_meta={"run_id": "OV002-A", "frozen_sha": "abc123", "process_identity_freeze": freeze},
        process_identity_evidence=freeze,
        process_identity_reconciliation=reconciliation,
    )
    assert result.eligible is True


def test_r6_final_certification_rejects_evidence_from_other_attempt() -> None:
    freeze = _r6_freeze()
    other = dict(freeze, attempt_id="OV002-OTHER")
    result = _r6_final_certification(
        process_identity_freeze=freeze,
        process_identity_evidence=other,
    )
    assert result.eligible is False
    assert "process_identity_evidence_attempt_id_mismatch" in result.reasons


def test_r6_r1_empty_managed_service_record_cannot_reach_final_eligibility() -> None:
    freeze = _r6_freeze(managed_services={"CSS Runtime": {}})
    result = _r6_final_certification(
        process_identity_freeze=freeze,
        process_identity_evidence=dict(freeze),
    )
    assert result.eligible is False
    assert "process_identity_freeze_service:CSS Runtime_empty" in result.reasons


def test_r6_r1_independent_expected_bindings_are_mandatory() -> None:
    freeze = _r6_freeze()
    missing_both = _r6_final_certification(
        process_identity_freeze=freeze,
        process_identity_evidence=freeze,
        expected_run_id=None,
        expected_commit=None,
    )
    assert missing_both.eligible is False
    assert "expected_run_id_missing" in missing_both.reasons
    assert "expected_commit_missing" in missing_both.reasons

    missing_commit = _r6_final_certification(
        process_identity_freeze=freeze,
        process_identity_evidence=freeze,
        expected_commit=None,
    )
    assert missing_commit.eligible is False
    assert "expected_commit_missing" in missing_commit.reasons


def test_r6_r1_matching_mutable_metadata_cannot_self_authorize() -> None:
    freeze = _r6_freeze(attempt_id="MUTABLE", baseline_commit="MUTABLE")
    result = _r6_final_certification(
        run_meta={"run_id": "MUTABLE", "frozen_sha": "MUTABLE"},
        process_identity_freeze=freeze,
        process_identity_evidence=dict(freeze),
        expected_run_id=None,
        expected_commit=None,
    )
    assert result.eligible is False
    assert "expected_run_id_missing" in result.reasons
    assert "expected_commit_missing" in result.reasons


def test_r6_r1_structured_reconciliation_required_and_digest_bound() -> None:
    freeze = _r6_freeze()
    missing = _r6_final_certification(
        process_identity_freeze=freeze,
        process_identity_evidence=freeze,
        process_identity_reconciliation=None,
        auto_reconciliation=False,
    )
    assert missing.eligible is False
    assert "process_identity_reconciliation_result_missing" in missing.reasons

    malformed = _r6_final_certification(
        process_identity_freeze=freeze,
        process_identity_evidence=freeze,
        process_identity_reconciliation=True,
        auto_reconciliation=False,
    )
    assert malformed.eligible is False
    assert "process_identity_reconciliation_result_malformed" in malformed.reasons

    mapping = build_process_identity_reconciliation_result(
        expected_run_id="OV002-A",
        expected_commit="abc123",
        freeze=freeze,
        evidence=freeze,
        reasons=[],
    )
    mapping_result = _r6_final_certification(
        process_identity_freeze=freeze,
        process_identity_evidence=freeze,
        process_identity_reconciliation=mapping,
        auto_reconciliation=False,
    )
    assert mapping_result.eligible is False
    assert "process_identity_reconciliation_result_not_authoritative" in mapping_result.reasons

    reconciliation = _build_authoritative_process_identity_reconciliation(
        expected_run_id="OV002-A",
        expected_commit="abc123",
        freeze=freeze,
        evidence=freeze,
        reasons=[],
    )
    forged_freeze = dict(freeze, repo_root="c:/other")
    mismatch = _r6_final_certification(
        process_identity_freeze=forged_freeze,
        process_identity_evidence=freeze,
        process_identity_reconciliation=reconciliation,
        auto_reconciliation=False,
    )
    assert mismatch.eligible is False
    assert "process_identity_reconciliation_freeze_digest_mismatch" in mismatch.reasons

    round_trip = json.loads(json.dumps(asdict(reconciliation)))
    copied = _r6_final_certification(
        process_identity_freeze=freeze,
        process_identity_evidence=freeze,
        process_identity_reconciliation=round_trip,
        auto_reconciliation=False,
    )
    assert copied.eligible is False
    assert "process_identity_reconciliation_result_not_authoritative" in copied.reasons


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("pid", 1, None),
        ("pid", 0, "pid_out_of_range"),
        ("pid", -1, "pid_out_of_range"),
        ("pid", MAX_CANONICAL_PROCESS_PID, None),
        ("pid", MAX_CANONICAL_PROCESS_PID + 1, "pid_out_of_range"),
        ("pid", True, "pid_malformed"),
        ("pid", False, "pid_malformed"),
        ("pid", DerivedPid(1), "pid_malformed"),
        ("pid", 1.0, "pid_malformed"),
        ("pid", "1", "pid_malformed"),
        ("pid", Decimal("1"), "pid_malformed"),
        ("pid", None, "pid_malformed"),
        ("pid", object(), "pid_malformed"),
        ("pid", [1], "pid_malformed"),
        ("pid", {"pid": 1}, "pid_malformed"),
        ("pid", (1,), "pid_malformed"),
        ("parent_pid", 1, None),
        ("parent_pid", 0, "parent_pid_out_of_range"),
        ("parent_pid", -1, "parent_pid_out_of_range"),
        ("parent_pid", MAX_CANONICAL_PROCESS_PID, None),
        ("parent_pid", MAX_CANONICAL_PROCESS_PID + 1, "parent_pid_out_of_range"),
        ("parent_pid", True, "parent_pid_malformed"),
        ("parent_pid", False, "parent_pid_malformed"),
        ("parent_pid", DerivedPid(1), "parent_pid_malformed"),
        ("parent_pid", 1.0, "parent_pid_malformed"),
        ("parent_pid", "1", "parent_pid_malformed"),
        ("parent_pid", Decimal("1"), "parent_pid_malformed"),
        ("parent_pid", None, "parent_pid_malformed"),
        ("parent_pid", object(), "parent_pid_malformed"),
        ("parent_pid", [1], "parent_pid_malformed"),
        ("parent_pid", {"pid": 1}, "parent_pid_malformed"),
        ("parent_pid", (1,), "parent_pid_malformed"),
    ],
)
@pytest.mark.parametrize("role", ["launcher", "supervisor", "CSS Runtime"])
def test_r6_r2_identity_pid_boundary_matrix(field: str, value: object, reason: str | None, role: str) -> None:
    from backend.certification.ov002_continuity import validate_process_identity_freeze

    freeze = _r6_freeze(managed_services={"CSS Runtime": _r6_live_record("CSS Runtime")})
    record_key = role if role in {"launcher", "supervisor"} else "CSS Runtime"
    if role in {"launcher", "supervisor"}:
        freeze[role] = dict(freeze[role], **{field: value})
        if field == "pid":
            freeze[f"{role}_pid"] = value
    else:
        services = dict(freeze["managed_services"])
        services[record_key] = dict(services[record_key], **{field: value})
        freeze["managed_services"] = services

    reasons = validate_process_identity_freeze(freeze)
    if reason is None:
        assert not any("pid_" in item for item in reasons)
    else:
        label = "service:CSS Runtime" if role == "CSS Runtime" else role
        assert f"process_identity_freeze_{label}_{reason}" in reasons


def test_r6_r3_canonical_pid_accepts_only_builtin_int() -> None:
    assert canonical_process_pid_error(1) is None
    accepted = canonical_process_pid(MAX_CANONICAL_PROCESS_PID)
    assert accepted == MAX_CANONICAL_PROCESS_PID
    assert type(accepted) is int

    for value in (
        True,
        False,
        DerivedPid(1),
        1.0,
        "1",
        Decimal("1"),
        None,
        object(),
        [1],
        {"pid": 1},
        (1,),
        0,
        -1,
        MAX_CANONICAL_PROCESS_PID + 1,
    ):
        assert canonical_process_pid(value) is None
        assert canonical_process_pid_error(value) in {"malformed", "out_of_range"}


@pytest.mark.parametrize(
    "value",
    ["1", 1.0, DerivedPid(1), Decimal("1"), [], {"pid": 1}, (1,)],
)
def test_r6_r4_build_process_identity_record_rejects_malformed_parent_pid(value: object) -> None:
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=1,
            parent_pid=value,
            role="launcher",
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            creation_time="2026-08-01T00:00:00+00:00",
            executable_path=sys.executable,
            command_line=f"{sys.executable} launcher",
        )
    assert exc.value.code == "launcher_parent_pid_malformed"


def test_r6_r4_build_process_identity_record_distinguishes_omitted_and_valid_parent_pid() -> None:
    omitted = build_process_identity_record(
        pid=1,
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        creation_time="2026-08-01T00:00:00+00:00",
        executable_path=sys.executable,
        command_line=f"{sys.executable} launcher",
    )
    assert omitted["parent_pid"] is None

    valid = build_process_identity_record(
        pid=1,
        parent_pid=2,
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        creation_time="2026-08-01T00:00:00+00:00",
        executable_path=sys.executable,
        command_line=f"{sys.executable} launcher",
    )
    assert valid["parent_pid"] == 2
    assert type(valid["parent_pid"]) is int


def _r6_supervisor_identity_input(*, parent_field: str | None = None, parent_value: object = None) -> dict:
    identity = {
        "launcher_pid": 1,
        "supervisor_pid": 2,
        "launcher_parent_pid": 3,
        "supervisor_parent_pid": 3,
        "launcher_creation_time": "2026-08-01T00:00:00+00:00",
        "supervisor_creation_time": "2026-08-01T00:00:00+00:00",
        "launcher_executable_path": sys.executable,
        "supervisor_executable_path": sys.executable,
        "launcher_command_line": f"{sys.executable} launcher",
        "supervisor_command_line": f"{sys.executable} supervisor",
        "managed_services": {
            "CSS Runtime": {
                "pid": 4,
                "parent_pid": 3,
                "creation_time": "2026-08-01T00:00:00+00:00",
                "executable_path": sys.executable,
                "command_line": f"{sys.executable} runtime",
            }
        },
    }
    if parent_field == "launcher":
        identity["launcher_parent_pid"] = parent_value
    elif parent_field == "supervisor":
        identity["supervisor_parent_pid"] = parent_value
    elif parent_field == "service":
        identity["managed_services"]["CSS Runtime"]["parent_pid"] = parent_value
    elif parent_field == "omitted_launcher":
        identity.pop("launcher_parent_pid")
    elif parent_field == "omitted_supervisor":
        identity.pop("supervisor_parent_pid")
    elif parent_field == "omitted_service":
        identity["managed_services"]["CSS Runtime"].pop("parent_pid")
    return {"process_identity": identity}


@pytest.mark.parametrize("value", ["3", 3.0, DerivedPid(3)])
@pytest.mark.parametrize("parent_field", ["launcher", "supervisor", "service"])
def test_r6_r4_freeze_process_identity_rejects_precoerced_parent_pid_paths(
    parent_field: str,
    value: object,
) -> None:
    with pytest.raises(ContinuityError) as exc:
        freeze_process_identity(
            _r6_supervisor_identity_input(parent_field=parent_field, parent_value=value),
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
        )
    assert exc.value.code in {
        "launcher_parent_pid_malformed",
        "supervisor_parent_pid_malformed",
        "CSS_Runtime_parent_pid_malformed",
    }


@pytest.mark.parametrize("parent_field", ["omitted_launcher", "omitted_supervisor", "omitted_service"])
def test_r6_r4_freeze_process_identity_allows_genuinely_omitted_parent_pid(parent_field: str) -> None:
    frozen = freeze_process_identity(
        _r6_supervisor_identity_input(parent_field=parent_field),
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
    )
    if parent_field == "omitted_launcher":
        assert frozen["launcher"]["parent_pid"] is None
    elif parent_field == "omitted_supervisor":
        assert frozen["supervisor"]["parent_pid"] is None
    else:
        assert frozen["managed_services"]["CSS Runtime"]["parent_pid"] is None


def test_r6_r4_freeze_process_identity_keeps_valid_parent_pid_builtin_int() -> None:
    frozen = freeze_process_identity(
        _r6_supervisor_identity_input(),
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
    )
    assert frozen["launcher"]["parent_pid"] == 3
    assert type(frozen["launcher"]["parent_pid"]) is int
    assert frozen["supervisor"]["parent_pid"] == 3
    assert type(frozen["supervisor"]["parent_pid"]) is int
    assert frozen["managed_services"]["CSS Runtime"]["parent_pid"] == 3
    assert type(frozen["managed_services"]["CSS Runtime"]["parent_pid"]) is int


def test_r6_r4_supervisor_identity_construction_rejects_malformed_parent_pid(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    sup = CSSRuntimeSupervisor(state_dir=str(root / "supervisor"), trusted_root=root)
    with pytest.raises(PersistenceError) as exc:
        sup.record_process_tree(
            launcher_pid=1,
            supervisor_pid=2,
            launcher_parent_pid="3",
            managed_services={},
            repo_root=str(root),
        )
    assert exc.value.code == "process_identity_parent_pid_malformed"


def test_r6_r4_supervisor_managed_service_parent_pid_failure_is_persisted(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    sup = CSSRuntimeSupervisor(state_dir=str(root / "supervisor"), trusted_root=root)
    sup.record_process_tree(
        launcher_pid=1,
        supervisor_pid=2,
        launcher_parent_pid=3,
        supervisor_parent_pid=3,
        managed_services={
            "CSS Runtime": {
                "pid": 4,
                "parent_pid": "3",
                "creation_time": "2026-08-01T00:00:00+00:00",
                "executable_path": sys.executable,
                "command_line": f"{sys.executable} runtime",
            }
        },
        repo_root=str(root),
    )
    status = sup.get_status()
    assert "CSS_Runtime_parent_pid_malformed" in status["process_identity"]["process_identity_error"]


def test_r6_r5_supplied_parent_pid_string_fails_before_live_equality_comparison() -> None:
    # Function: build_process_identity_record
    # Inputs: supplied parent_pid="3"; live probe parent_pid=3.
    # Current defect: _same_int coerces "3" and accepts the supplied malformed evidence.
    # Expected: canonical validation rejects the supplied parent PID before equality comparison.
    live = {
        "pid": 1,
        "parent_pid": 3,
        "creation_time": "2026-08-01T00:00:00+00:00",
        "executable_path": sys.executable,
        "executable_sha256": "1" * 64,
        "command_line": f"{sys.executable} launcher",
    }
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=1,
            parent_pid="3",
            role="launcher",
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            require_live_fields=True,
            probe=lambda _pid: live,
        )
    assert exc.value.code == "launcher_parent_pid_malformed"


def test_r6_r5_managed_service_string_pid_fails_instead_of_disappearing() -> None:
    # Function: freeze_process_identity
    # Inputs: managed service {"pid": "4"}.
    # Current defect: malformed service PID is treated as absent and the service is dropped.
    # Expected: supplied malformed service PID raises deterministic continuity failure.
    state = _r6_supervisor_identity_input()
    state["process_identity"]["managed_services"]["CSS Runtime"]["pid"] = "4"

    with pytest.raises(ContinuityError) as exc:
        freeze_process_identity(
            state,
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
        )
    assert exc.value.code == "process_identity_service_pid_malformed"
    assert "CSS Runtime" in str(exc.value)


def test_r6_r2_negative_pid_exploit_cannot_reach_final_eligibility() -> None:
    freeze = _r6_freeze()
    freeze["launcher"] = dict(freeze["launcher"], pid=-1, parent_pid=0)
    freeze["supervisor"] = dict(freeze["supervisor"], pid=-1, parent_pid=0)
    freeze["launcher_pid"] = -1
    freeze["supervisor_pid"] = -1
    result = _r6_final_certification(
        process_identity_freeze=freeze,
        process_identity_evidence=dict(freeze),
    )
    assert result.eligible is False
    assert "process_identity_freeze_launcher_pid_out_of_range" in result.reasons
    assert "process_identity_freeze_launcher_parent_pid_out_of_range" in result.reasons


# ─── H1: empty / incomplete live probe fails closed ───────────────────────────

def test_r6_empty_live_probe_mapping_fails_closed() -> None:
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=os.getpid(),
            role="launcher",
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            require_live_fields=True,
            probe=lambda _pid: {},
        )
    assert exc.value.code == "identity_probe_empty"


@pytest.mark.parametrize(
    "dropped",
    ["pid", "parent_pid", "creation_time", "executable_path", "executable_sha256", "command_line"],
)
def test_r6_incomplete_live_probe_fails_closed(dropped: str) -> None:
    complete = {
        "pid": os.getpid(),
        "parent_pid": 1,
        "creation_time": "2026-08-01T00:00:00+00:00",
        "executable_path": sys.executable,
        "executable_sha256": "1" * 64,
        "command_line": f"{sys.executable} launcher",
    }
    partial = {key: value for key, value in complete.items() if key != dropped}
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=os.getpid(),
            role="launcher",
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            require_live_fields=True,
            probe=lambda _pid: partial,
        )
    assert exc.value.code == "identity_probe_incomplete"
    assert dropped in str(exc.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pid", str(os.getpid())),
        ("pid", True),
        ("parent_pid", "1"),
        ("parent_pid", False),
        ("creation_time", ["2026-08-01T00:00:00+00:00"]),
        ("executable_path", [sys.executable]),
        ("executable_sha256", "A" * 64),
        ("command_line", [f"{sys.executable} launcher"]),
    ],
)
def test_r6_r1_live_probe_field_types_are_strict(field: str, value: object) -> None:
    complete = {
        "pid": os.getpid(),
        "parent_pid": 1,
        "creation_time": "2026-08-01T00:00:00+00:00",
        "executable_path": sys.executable,
        "executable_sha256": "1" * 64,
        "command_line": f"{sys.executable} launcher",
    }
    forged = dict(complete, **{field: value})
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=os.getpid(),
            role="launcher",
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            require_live_fields=True,
            probe=lambda _pid: forged,
        )
    assert exc.value.code == "identity_probe_field_malformed"


def test_r6_caller_cannot_backfill_missing_live_fields() -> None:
    partial = {
        "pid": os.getpid(),
        "parent_pid": 1,
        "creation_time": "2026-08-01T00:00:00+00:00",
        "executable_path": sys.executable,
        "command_line": f"{sys.executable} launcher",
    }
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=os.getpid(),
            role="launcher",
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            executable_sha256="0" * 64,
            require_live_fields=True,
            probe=lambda _pid: partial,
        )
    assert exc.value.code == "identity_probe_incomplete"


def test_r6_live_values_remain_authoritative_over_supplied() -> None:
    live = {
        "pid": os.getpid(),
        "parent_pid": 11,
        "creation_time": "2026-08-01T00:00:00+00:00",
        "executable_path": sys.executable,
        "executable_sha256": "1" * 64,
        "command_line": f"{sys.executable} launcher",
    }
    record = build_process_identity_record(
        pid=os.getpid(),
        role="launcher",
        attempt_id="OV002-A",
        baseline_commit="abc123",
        repo_root="c:/repo",
        require_live_fields=True,
        probe=lambda _pid: live,
    )
    assert record["parent_pid"] == 11
    assert record["executable_sha256"] == "1" * 64

    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=os.getpid(),
            role="launcher",
            attempt_id="OV002-A",
            baseline_commit="abc123",
            repo_root="c:/repo",
            parent_pid=12,
            require_live_fields=True,
            probe=lambda _pid: live,
        )
    assert exc.value.code == "identity_supplied_field_mismatch"


# ─── H2: discovery cannot report empty success ────────────────────────────────

def test_r6_discovery_empty_output_and_missing_self_fail_closed() -> None:
    from types import SimpleNamespace

    def _run(stdout: str):
        return lambda *_a, **_k: SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    with patch("launcher.css_runtime_launcher.subprocess.run", _run("")):
        empty = discover_canonical_runtime_processes(current_pid=4242)
    assert empty["ok"] is False
    assert empty["error_code"] == "discovery_empty_output"

    with patch("launcher.css_runtime_launcher.subprocess.run", _run("[]")):
        unanchored = discover_canonical_runtime_processes(current_pid=4242)
    assert unanchored["ok"] is False
    assert unanchored["error_code"] == "discovery_envelope_malformed"

    envelope = json.dumps(
        {
            "schema_version": DISCOVERY_SCHEMA,
            "ok": True,
            "anchor_pid": 4242,
            "self_observed": True,
            "processes": [],
            "error_code": None,
            "error_type": None,
        }
    )
    with patch("launcher.css_runtime_launcher.subprocess.run", _run(envelope)):
        anchored = discover_canonical_runtime_processes(current_pid=4242)
        owners = duplicate_canonical_runtime_owners(current_pid=4242)
    assert anchored["ok"] is True
    assert anchored["processes"] == []
    assert owners["ok"] is True
    assert owners["owners"] == []

    failed_envelope = json.dumps(
        {
            "schema_version": DISCOVERY_SCHEMA,
            "ok": False,
            "anchor_pid": 4242,
            "self_observed": True,
            "processes": [],
            "error_code": None,
            "error_type": None,
        }
    )
    with patch("launcher.css_runtime_launcher.subprocess.run", _run(failed_envelope)):
        failed = discover_canonical_runtime_processes(current_pid=4242)
    assert failed["ok"] is False
    assert failed["error_code"] == "discovery_reported_failure"


# ─── M2: supervisor failure-history persistence fails closed ──────────────────

def test_r6_history_persist_failure_is_visible_and_reconciled(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    sup = CSSRuntimeSupervisor(state_dir=str(root / "supervisor"), trusted_root=root)
    sup.start()

    with patch(
        "backend.runtime.css_runtime_supervisor.atomic_append_jsonl",
        side_effect=PersistenceError("jsonl_append_failed", "C:/secret/path/token=abc"),
    ):
        sup.record_failure("boom")

    status = sup.get_status()
    assert status["last_history_persist_error"] == "jsonl_append_failed"
    assert status["history_persist_degraded"] is True
    assert "C:/secret" not in json.dumps(status)
    assert "token=abc" not in json.dumps(status)

    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    freeze = _r6_freeze()
    result = reconcile_supervisor_and_alerts(
        supervisor_state=_r6_supervisor_state(
            now, freeze, last_history_persist_error="jsonl_append_failed"
        ),
        alerts=[],
        run_meta={
            "run_id": "OV002-A",
            "frozen_sha": "abc123",
            "start_utc": _iso(now),
            "process_identity_freeze": freeze,
        },
        now=now,
        process_identity_probe=_r6_probe,
    )
    assert result["ok"] is False
    assert "supervisor_history_persist_failed" in result["reasons"]


# ─── M3: blocked invalidation persistence cannot read back as clean ───────────

def test_r6_blocked_invalidation_marker_blocks_clean_running(tmp_path: Path) -> None:
    from backend.certification.ov002_endurance_monitor import (
        INVALIDATION_BLOCKED_FILENAME,
        _existing_invalidation,
        _write_invalidated_status,
    )

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    atomic_write_json(
        pkg / "RUN_STATUS.json",
        {"status": "RUNNING", "run_id": "OV002-A"},
        expected_root=pkg,
    )
    # Simulate a stale writer lock that must not be silently stolen.
    (pkg / "INVALIDATION.json.writer.lock").write_text(
        json.dumps(
            {
                "schema_version": "css.ov002.writer_lock.v1",
                "attempt_id": "OV002-A",
                "writer_role": "other",
                "lease_until_epoch": time.time() + 600,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(PersistenceError):
        _write_invalidated_status(
            pkg,
            run_id="OV002-A",
            frozen_sha="abc123",
            invalidation={"invalidated": True, "reasons": ["engine_heartbeat_lost"]},
        )

    marker = pkg / INVALIDATION_BLOCKED_FILENAME
    assert marker.is_file()
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["invalidated"] is True
    assert payload["durable_invalidation_written"] is False

    existing = _existing_invalidation(pkg)
    assert existing is not None
    assert existing["invalidated"] is True
    assert "invalidation_persist_blocked" in existing["reasons"]

    result = run_monitor_loop(pkg, once=True)
    assert result["status"] == "INVALIDATED"
    assert "invalidation_persist_blocked" in result["invalidation"]["reasons"]


# ─── M4: identity failure is not misread as controlled shutdown ───────────────

def test_r6_identity_verification_failure_recorded_distinctly(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    sup = CSSRuntimeSupervisor(state_dir=str(root / "supervisor"), trusted_root=root)
    sup.start()
    sup.record_identity_verification_failure(
        "strong_process_identity_unavailable", detail_code="RuntimeError"
    )
    sup.stop()

    status = sup.get_status()
    event_types = [item.get("event_type") for item in status["failure_history"]]
    assert "identity_verification_failed" in event_types
    assert "controlled_shutdown" in event_types
    assert status["identity_verification_failed"] is True

    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    freeze = _r6_freeze()
    result = reconcile_supervisor_and_alerts(
        supervisor_state=_r6_supervisor_state(
            now,
            freeze,
            failure_history=[
                {"event_type": "identity_verification_failed", "reason": "strong_process_identity_unavailable"},
                {"event_type": "controlled_shutdown", "reason": "shutdown_requested"},
            ],
        ),
        alerts=[],
        run_meta={
            "run_id": "OV002-A",
            "frozen_sha": "abc123",
            "start_utc": _iso(now),
            "process_identity_freeze": freeze,
        },
        now=now,
        process_identity_probe=_r6_probe,
    )
    assert result["ok"] is False
    assert "identity_verification_failed" in result["reasons"]
    assert any(
        event.get("event_type") == "identity_verification_failed" for event in result["events"]
    )


def test_r6_identity_failure_flag_alone_blocks_reconciliation() -> None:
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    freeze = _r6_freeze()
    result = reconcile_supervisor_and_alerts(
        supervisor_state=_r6_supervisor_state(now, freeze, identity_verification_failed=True),
        alerts=[],
        run_meta={
            "run_id": "OV002-A",
            "frozen_sha": "abc123",
            "start_utc": _iso(now),
            "process_identity_freeze": freeze,
        },
        now=now,
        process_identity_probe=_r6_probe,
    )
    assert result["ok"] is False
    assert "identity_verification_failed" in result["reasons"]


# ─── M1: expected identity comes from durable evidence, not mutable run meta ──

def test_r6_expected_identity_read_from_attempt_state_not_run_meta(tmp_path: Path) -> None:
    from backend.certification.ov002_endurance_monitor import (
        _load_independent_continuity_evidence,
    )

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    freeze = _r6_freeze()

    attempt_id, commit, evidence, reasons = _load_independent_continuity_evidence(pkg)
    assert attempt_id is None and commit is None and evidence is None
    assert "attempt_state_evidence_missing" in reasons
    assert "process_identity_evidence_missing" in reasons

    persist_attempt_state(
        pkg / "ATTEMPT_STATE.json",
        target_state=STATE_RUNNING,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        expected_root=pkg,
    )
    atomic_write_json(pkg / "PROCESS_IDENTITY.json", freeze, expected_root=pkg)

    attempt_id, commit, evidence, reasons = _load_independent_continuity_evidence(pkg)
    assert attempt_id == "OV002-A"
    assert commit == "abc123"
    assert evidence is not None
    assert reasons == []

    # A tampered in-memory run meta cannot satisfy the durable expectation.
    tampered = _r6_final_certification(
        run_meta={"run_id": "OV002-TAMPERED", "frozen_sha": "deadbeef"},
        expected_run_id=attempt_id,
        expected_commit=commit,
        process_identity_freeze=freeze,
        process_identity_evidence=evidence,
        process_identity_reasons=[],
    )
    assert tampered.eligible is False
    assert "attempt_id_mismatch" in tampered.reasons
    assert "commit_mismatch" in tampered.reasons


def test_r6_attempt_state_malformed_blocks_final_certification(tmp_path: Path) -> None:
    from backend.certification.ov002_endurance_monitor import (
        _load_independent_continuity_evidence,
    )

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "ATTEMPT_STATE.json").write_text('{"attempt_id":"A","attempt_id":"B"}', encoding="utf-8")
    _attempt_id, _commit, _evidence, reasons = _load_independent_continuity_evidence(pkg)
    assert any("attempt_state_evidence_invalid" in reason for reason in reasons)

    result = _r6_final_certification(
        process_identity_freeze=_r6_freeze(),
        process_identity_evidence=_r6_freeze(),
        process_identity_reasons=reasons,
    )
    assert result.eligible is False
    assert any("attempt_state_evidence_invalid" in reason for reason in result.reasons)


# ─── L2/L3: legacy outputs remain explicitly non-authoritative ────────────────

def test_r6_legacy_marathon_output_is_labelled_non_authoritative() -> None:
    assert marathon.NON_AUTHORITATIVE_MARKER == "NON_AUTHORITATIVE_FOR_OV002_PHASE181"
    assert marathon.LEGACY_LABEL == "LEGACY NON-AUTHORITATIVE"
    source = Path(marathon.__file__).read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("print(") and "CERTIFIED" in stripped:
            assert "LEGACY_LABEL" in stripped or "NON_AUTHORITATIVE_MARKER" in stripped


def test_r6_legacy_payload_never_grants_ov002_credit() -> None:
    from backend.validation.endurance_validation import (
        NON_AUTHORITATIVE_MARKER as ENDURANCE_MARKER,
    )

    freeze = _r6_freeze()
    legacy_payloads = [
        {"status": "PASS", "go_no_go": "GO", "certification_status": "CERTIFIED"},
        {"certification_status": "PHASE181_CERTIFIED"},
        {"summary": "LEGACY NON-AUTHORITATIVE CERTIFIED GO"},
    ]
    for payload in legacy_payloads:
        reasons = reject_legacy_certification_authority(payload)
        assert "legacy_certification_non_authoritative_ov002" in reasons
        assert "legacy_certification_non_authoritative_phase181" in reasons

        result = _r6_final_certification(
            legacy_authority_payload=payload,
            process_identity_freeze=freeze,
            process_identity_evidence=freeze,
            process_identity_reasons=[],
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
    ).to_dict()
    assert endurance["ov002_authoritative"] is False
    assert endurance["phase181_authoritative"] is False
    assert endurance["non_authoritative_marker"] == ENDURANCE_MARKER


# ─── R21: R20 blocker remediation regressions ─────────────────────────────────


def test_r21_initialize_run_refuses_existing_invalidation_json(tmp_path: Path) -> None:
    from backend.certification.ov002_endurance_monitor import initialize_run

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    atomic_write_json(
        pkg / "INVALIDATION.json",
        {
            "invalidated": True,
            "reasons": ["engine_heartbeat_lost"],
            "observed_at_utc": _iso(datetime.now(timezone.utc)),
        },
        expected_root=tmp_path,
    )
    before = (pkg / "INVALIDATION.json").read_text(encoding="utf-8")
    result = initialize_run(output_dir=pkg)
    assert result["ok"] is False
    assert result["status"] == "INVALIDATED"
    assert result["reason"] == "existing_invalidation_refused"
    assert (pkg / "INVALIDATION.json").read_text(encoding="utf-8") == before
    if (pkg / "ATTEMPT_STATE.json").exists():
        attempt = json.loads((pkg / "ATTEMPT_STATE.json").read_text(encoding="utf-8"))
        assert attempt.get("attempt_state") != STATE_RUNNING


def test_r21_initialize_run_refuses_attempt_state_invalidated_without_invalidation_json(
    tmp_path: Path,
) -> None:
    from backend.certification.ov002_endurance_monitor import (
        _existing_invalidation,
        initialize_run,
    )

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    persist_attempt_state(
        pkg / "ATTEMPT_STATE.json",
        target_state=STATE_INVALIDATED,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        expected_root=tmp_path,
    )
    existing = _existing_invalidation(pkg)
    assert existing is not None
    assert "attempt_state_invalidated" in (existing.get("reasons") or [])
    result = initialize_run(output_dir=pkg)
    assert result["ok"] is False
    assert result["status"] == "INVALIDATED"
    attempt = json.loads((pkg / "ATTEMPT_STATE.json").read_text(encoding="utf-8"))
    assert attempt["attempt_state"] == STATE_INVALIDATED


def test_r21_initialize_run_does_not_rewrite_invalidated_attempt_state_to_running(
    tmp_path: Path,
) -> None:
    from backend.certification.ov002_endurance_monitor import initialize_run

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    persist_attempt_state(
        pkg / "ATTEMPT_STATE.json",
        target_state=STATE_INVALIDATED,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        expected_root=tmp_path,
    )
    initialize_run(output_dir=pkg)
    attempt = json.loads((pkg / "ATTEMPT_STATE.json").read_text(encoding="utf-8"))
    assert attempt["attempt_state"] == STATE_INVALIDATED
    if (pkg / "RUN_STATUS.json").exists():
        status = json.loads((pkg / "RUN_STATUS.json").read_text(encoding="utf-8"))
        assert status.get("status") != "RUNNING"


def test_r21_final_certification_rejects_persisted_attempt_state_invalidated() -> None:
    result = evaluate_final_certification(
        run_meta={"run_id": "A", "frozen_sha": "c"},
        run_status={"status": "COMPLETE"},
        invalidation=None,
        reconciliation_ok=True,
        reconciliation_reasons=[],
        alert_errors=[],
        expected_run_id="A",
        expected_commit="c",
        require_process_identity_continuity=False,
        persisted_attempt_state={
            "attempt_state": STATE_INVALIDATED,
            "attempt_id": "A",
            "baseline_commit": "c",
        },
    )
    assert result.eligible is False
    assert result.attempt_state == STATE_INVALIDATED
    assert "persisted_attempt_state_invalidated" in result.reasons


def test_r21_invalidation_sticky_across_restart(tmp_path: Path) -> None:
    from backend.certification.ov002_endurance_monitor import (
        _existing_invalidation,
        run_monitor_loop,
    )

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "snapshots").mkdir()
    persist_attempt_state(
        pkg / "ATTEMPT_STATE.json",
        target_state=STATE_INVALIDATED,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        expected_root=tmp_path,
    )
    atomic_write_json(
        pkg / "RUN_META.json",
        {"run_id": "OV002-A", "frozen_sha": "abc123", "start_epoch": time.time()},
        expected_root=tmp_path,
    )
    assert _existing_invalidation(pkg) is not None
    resumed = run_monitor_loop(pkg, once=True, target_hours=1.0)
    assert resumed["status"] == "INVALIDATED"


def test_r21_failed_invalidation_write_leaves_non_resumable_attempt_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.certification import ov002_endurance_monitor as mon

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    persist_attempt_state(
        pkg / "ATTEMPT_STATE.json",
        target_state=STATE_RUNNING,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        expected_root=tmp_path,
    )

    def _fail_critical(path, payload, *, attempt_id, expected_root=None):
        raise PersistenceError("atomic_replace_failed", str(path))

    monkeypatch.setattr(mon, "_write_json_critical", _fail_critical)
    with pytest.raises(PersistenceError):
        mon._write_invalidated_status(
            pkg,
            run_id="OV002-A",
            frozen_sha="abc123",
            invalidation={"invalidated": True, "reasons": ["x"], "events": []},
        )
    attempt = json.loads((pkg / "ATTEMPT_STATE.json").read_text(encoding="utf-8"))
    assert attempt["attempt_state"] == STATE_INVALIDATED
    assert mon._existing_invalidation(pkg) is not None
    refused = mon.initialize_run(output_dir=pkg)
    assert refused["ok"] is False
    assert refused["status"] == "INVALIDATED"


def test_r21_failed_blocked_markers_still_refuse_resume_via_attempt_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.certification import ov002_endurance_monitor as mon

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    persist_attempt_state(
        pkg / "ATTEMPT_STATE.json",
        target_state=STATE_RUNNING,
        attempt_id="OV002-A",
        baseline_commit="abc123",
        expected_root=tmp_path,
    )

    def _fail_critical(path, payload, *, attempt_id, expected_root=None):
        raise PersistenceError("atomic_replace_failed", str(path))

    monkeypatch.setattr(mon, "_write_json_critical", _fail_critical)
    monkeypatch.setattr(mon, "_write_invalidation_blocked_marker", lambda *a, **k: False)
    monkeypatch.setattr(mon, "_write_uncertain_invalidation_marker", lambda *a, **k: False)
    with pytest.raises(PersistenceError):
        mon._write_invalidated_status(
            pkg,
            run_id="OV002-A",
            frozen_sha="abc123",
            invalidation={"invalidated": True, "reasons": ["y"], "events": []},
        )
    assert (
        json.loads((pkg / "ATTEMPT_STATE.json").read_text(encoding="utf-8"))["attempt_state"]
        == STATE_INVALIDATED
    )
    assert mon.initialize_run(output_dir=pkg)["ok"] is False


def test_r21_dual_persist_uses_uncertain_marker_when_attempt_state_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.certification import ov002_endurance_monitor as mon

    pkg = tmp_path / "pkg"
    pkg.mkdir()

    def _fail_critical(path, payload, *, attempt_id, expected_root=None):
        raise PersistenceError("atomic_replace_failed", str(path))

    monkeypatch.setattr(mon, "_write_json_critical", _fail_critical)
    monkeypatch.setattr(
        mon,
        "_force_attempt_state_invalidated",
        lambda *a, **k: (False, "writer_lock_failed"),
    )
    monkeypatch.setattr(mon, "_write_invalidation_blocked_marker", lambda *a, **k: False)

    uncertain_written = {"ok": False}

    def _uncertain(*_a, **_k):
        uncertain_written["ok"] = True
        atomic_write_json(
            pkg / "INVALIDATION_UNCERTAIN.json",
            {
                "invalidated": True,
                "invalidation_uncertain": True,
                "reasons": ["invalidation_persist_uncertain"],
            },
            expected_root=tmp_path,
        )
        return True

    monkeypatch.setattr(mon, "_write_uncertain_invalidation_marker", _uncertain)
    with pytest.raises(PersistenceError):
        mon._write_invalidated_status(
            pkg,
            run_id="OV002-A",
            frozen_sha="abc123",
            invalidation={"invalidated": True, "reasons": ["z"], "events": []},
        )
    assert uncertain_written["ok"] is True
    assert mon._existing_invalidation(pkg) is not None
    assert mon.initialize_run(output_dir=pkg)["ok"] is False


def test_r21_malformed_uncertain_continuity_cannot_become_valid_by_initialization(
    tmp_path: Path,
) -> None:
    from backend.certification.ov002_endurance_monitor import initialize_run

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "INVALIDATION.json").write_text("{broken", encoding="utf-8")
    result = initialize_run(output_dir=pkg)
    assert result["ok"] is False
    assert result["status"] == "INVALIDATED"
