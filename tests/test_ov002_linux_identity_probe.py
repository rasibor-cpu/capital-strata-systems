"""Linux /proc identity probe for OV-002 (issue #116).

The probe must return a complete, kernel-sourced identity for a live process and
return None (fail closed upstream) whenever identity cannot be established.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time

import pytest

from backend.certification import ov002_continuity
from backend.certification.ov002_continuity import (
    ContinuityError,
    build_process_identity_record,
    default_identity_probe,
)
from backend.validation.endurance_evidence import CanonicalEnduranceEvidence

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux /proc probe")


def test_probe_returns_complete_kernel_identity_for_current_process() -> None:
    live = default_identity_probe(os.getpid())
    assert live is not None
    assert live["pid"] == os.getpid()
    assert live["parent_pid"] == os.getppid()
    exe = os.path.realpath(sys.executable)
    assert live["executable_path"] == exe
    with open(exe, "rb") as fh:
        assert live["executable_sha256"] == hashlib.sha256(fh.read()).hexdigest()
    assert live["creation_time"].endswith("+00:00")
    # Stable across reads: the same process always yields the same identity.
    assert default_identity_probe(os.getpid()) == live


def test_strict_record_builds_from_probe_and_rejects_tampered_supplied_fields() -> None:
    record = build_process_identity_record(
        pid=os.getpid(), role="launcher", attempt_id="A", baseline_commit="c", repo_root="/r",
        require_live_fields=True,
    )
    assert record["creation_time"] and record["executable_sha256"] and record["command_sha256"]
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=os.getpid(), role="launcher", attempt_id="A", baseline_commit="c", repo_root="/r",
            creation_time="2001-01-01T00:00:00+00:00", require_live_fields=True,
        )
    assert exc.value.code == "identity_supplied_field_mismatch"


def test_probe_fails_closed_for_missing_and_exited_processes() -> None:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=30)
    assert default_identity_probe(child.pid) is None
    with pytest.raises(ContinuityError) as exc:
        build_process_identity_record(
            pid=child.pid, role="launcher", attempt_id="A", baseline_commit="c", repo_root="/r",
            require_live_fields=True,
        )
    assert exc.value.code == "identity_probe_unavailable"


def test_probe_rejects_deleted_executable_and_pid_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    real_readlink = os.readlink
    monkeypatch.setattr(ov002_continuity.os, "readlink",
                        lambda p: real_readlink(p) + " (deleted)" if str(p).endswith("/exe") else real_readlink(p))
    assert default_identity_probe(os.getpid()) is None
    monkeypatch.setattr(ov002_continuity.os, "readlink", real_readlink)

    reads = iter([(1, 100), (1, 200)])  # start time changes between reads: PID reused
    monkeypatch.setattr(ov002_continuity, "_linux_proc_stat", lambda _pid: next(reads))
    assert default_identity_probe(os.getpid()) is None


def test_linux_boot_time_is_available_and_stable() -> None:
    first = CanonicalEnduranceEvidence.get_host_boot_time()
    time.sleep(0.05)
    second = CanonicalEnduranceEvidence.get_host_boot_time()
    assert first > 0.0
    assert abs(first - second) < 2.0
    assert first <= time.time()
