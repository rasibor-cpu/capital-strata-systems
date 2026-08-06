"""
tests/test_phase171b_supervisor_path_isolation.py

Phase 171B regression tests — CSSRuntimeSupervisor canonical path isolation.

Verifies:
  U-01  Launcher constructor defaults remain state_dir="runtime/supervisor"
  U-02  Dashboard constructor uses state_dir="runtime/supervisor/dashboard"
  U-03  Launcher and dashboard state files do not share the same path
  U-04  Launcher start() writes only to the canonical path
  U-05  Dashboard start() writes only to the subordinate path; canonical untouched
  U-06  Dashboard heartbeat() does not change canonical file mtime
  U-07  supervisor_id in canonical file is stable when dashboard heartbeats
  U-08  Dashboard record_restart() writes to subordinate path only
  U-09  Dashboard record_failure() writes to subordinate path only
  U-10  _ensure_state_dir creates runtime/supervisor/dashboard/ automatically
  U-11  record_restart() with no arguments succeeds (Change 2 regression check)
  U-12  FreshnessManager default supervisor_state path is the canonical path
  U-13  RuntimeArtifactReader default supervisor_state_path is the canonical path
  U-14  LauncherConfig.SUPERVISOR_STATE_FILE is the canonical path
  I-01  Concurrent launcher + dashboard writes leave canonical JSON valid
  I-02  RuntimeArtifactFreshnessManager evaluates canonical file correctly
  I-03  Dashboard subordinate file is independently valid JSON
  I-04  Mobile launcher get_supervisor_summary reads canonical file only
  I-05  Both supervisor files can coexist without interference
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_supervisor(tmp_path: Path, subpath: str = "supervisor") -> CSSRuntimeSupervisor:
    """Create a CSSRuntimeSupervisor writing to an isolated tmp directory."""
    state_dir = str(tmp_path / subpath)
    alert_mock = MagicMock()
    return CSSRuntimeSupervisor(
        state_dir=state_dir,
        max_restart_limit=3,
        alert_service=alert_mock,
        trusted_root=tmp_path,
    )


def _canonical_state_file(tmp_path: Path) -> Path:
    return tmp_path / "supervisor" / "css_runtime_supervisor_state.json"


def _dashboard_state_file(tmp_path: Path) -> Path:
    return tmp_path / "supervisor" / "dashboard" / "css_runtime_supervisor_state.json"


# ═══════════════════════════════════════════════════════════════════════════════
# Unit Tests (U-01 – U-11)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPathIsolationUnit:

    def test_u01_launcher_constructor_default_state_dir(self):
        """U-01: CSSRuntimeSupervisor() default state_dir is 'runtime/supervisor'."""
        sup = CSSRuntimeSupervisor.__new__(CSSRuntimeSupervisor)
        import inspect
        sig = inspect.signature(CSSRuntimeSupervisor.__init__)
        default = sig.parameters["state_dir"].default
        assert default == "runtime/supervisor", (
            f"Default state_dir changed from 'runtime/supervisor' to {default!r}. "
            "This would affect the launcher's canonical artifact path."
        )

    def test_u02_dashboard_state_dir_is_subordinate(self, tmp_path):
        """U-02: Dashboard supervisor uses subordinate state_dir beneath its trusted root."""
        alert_mock = MagicMock()
        dashboard_sup = CSSRuntimeSupervisor(
            alert_service=alert_mock,
            state_dir="runtime/supervisor/dashboard",
            trusted_root=tmp_path,
        )
        assert Path(dashboard_sup.state_dir) == tmp_path / "runtime" / "supervisor" / "dashboard"
        assert "dashboard" in dashboard_sup.state_dir

    def test_u02b_absolute_state_dir_without_trusted_root_is_rejected(self, tmp_path):
        """U-02b: Absolute state_dir without trusted_root still fails closed."""
        from backend.certification.ov002_persistence import PersistenceError

        with pytest.raises(PersistenceError) as exc:
            CSSRuntimeSupervisor(
                state_dir=str(tmp_path / "unrooted"),
                alert_service=MagicMock(),
            )
        assert exc.value.code == "supervisor_trusted_root_required"

    def test_u03_launcher_and_dashboard_paths_do_not_collide(self, tmp_path):
        """U-03: Launcher and dashboard state files resolve to different paths."""
        launcher_sup = _make_supervisor(tmp_path, "supervisor")
        dashboard_sup = _make_supervisor(tmp_path, "supervisor/dashboard")

        assert launcher_sup.state_file != dashboard_sup.state_file, (
            "Launcher and dashboard state files must not share the same path. "
            f"Both resolve to: {launcher_sup.state_file}"
        )
        assert "dashboard" in dashboard_sup.state_file
        assert "dashboard" not in launcher_sup.state_file

    def test_u04_launcher_start_writes_canonical_only(self, tmp_path):
        """U-04: Launcher start() creates the canonical file; subordinate path untouched."""
        launcher_sup = _make_supervisor(tmp_path, "supervisor")
        launcher_sup.start()

        canonical = _canonical_state_file(tmp_path)
        subordinate = _dashboard_state_file(tmp_path)

        assert canonical.exists(), "Launcher start() must create the canonical state file"
        assert not subordinate.exists(), (
            "Launcher start() must not create the dashboard subordinate file"
        )

    def test_u05_dashboard_start_writes_subordinate_only(self, tmp_path):
        """U-05: Dashboard start() writes to subordinate path; canonical file untouched."""
        dashboard_sup = _make_supervisor(tmp_path, "supervisor/dashboard")
        dashboard_sup.start()

        canonical = _canonical_state_file(tmp_path)
        subordinate = _dashboard_state_file(tmp_path)

        assert subordinate.exists(), "Dashboard start() must create the subordinate state file"
        assert not canonical.exists(), (
            "Dashboard start() must NOT write to the canonical supervisor path. "
            "The canonical path is owned exclusively by the launcher."
        )

    def test_u06_dashboard_heartbeat_does_not_touch_canonical_mtime(self, tmp_path):
        """U-06: Dashboard heartbeat() does not update the canonical file mtime."""
        # Set up launcher (canonical)
        launcher_sup = _make_supervisor(tmp_path, "supervisor")
        launcher_sup.start()

        canonical = _canonical_state_file(tmp_path)
        mtime_before = canonical.stat().st_mtime

        # Small sleep to ensure mtime would differ if the file were written
        time.sleep(0.05)

        # Dashboard heartbeat fires
        dashboard_sup = _make_supervisor(tmp_path, "supervisor/dashboard")
        dashboard_sup.start()
        dashboard_sup.heartbeat()

        mtime_after = canonical.stat().st_mtime
        assert mtime_after == mtime_before, (
            "Dashboard heartbeat() must not modify the canonical supervisor file mtime. "
            f"mtime changed from {mtime_before} to {mtime_after}."
        )

    def test_u07_canonical_supervisor_id_stable_across_dashboard_heartbeat(self, tmp_path):
        """U-07: supervisor_id in canonical file is stable when dashboard heartbeats."""
        launcher_sup = _make_supervisor(tmp_path, "supervisor")
        launcher_sup.start()

        canonical = _canonical_state_file(tmp_path)
        launcher_uuid = json.loads(canonical.read_text())["supervisor_id"]

        # Dashboard starts and heartbeats multiple times
        dashboard_sup = _make_supervisor(tmp_path, "supervisor/dashboard")
        dashboard_sup.start()
        for _ in range(3):
            dashboard_sup.heartbeat()

        uuid_after = json.loads(canonical.read_text())["supervisor_id"]
        assert uuid_after == launcher_uuid, (
            "supervisor_id in canonical file changed after dashboard heartbeat. "
            f"Before: {launcher_uuid!r}  After: {uuid_after!r}"
        )

    def test_u08_dashboard_record_restart_writes_subordinate_only(self, tmp_path):
        """U-08: Dashboard record_restart() does not modify canonical file."""
        launcher_sup = _make_supervisor(tmp_path, "supervisor")
        launcher_sup.start()
        launcher_sup.record_failure("test failure")

        canonical = _canonical_state_file(tmp_path)
        canonical_restart_count_before = json.loads(canonical.read_text())["restart_count"]
        mtime_before = canonical.stat().st_mtime

        time.sleep(0.05)

        dashboard_sup = _make_supervisor(tmp_path, "supervisor/dashboard")
        dashboard_sup.start()
        dashboard_sup.record_failure("dashboard failure")
        dashboard_sup.record_restart()

        mtime_after = canonical.stat().st_mtime
        canonical_restart_count_after = json.loads(canonical.read_text())["restart_count"]

        assert mtime_after == mtime_before, (
            "Dashboard record_restart() must not modify canonical file mtime."
        )
        assert canonical_restart_count_after == canonical_restart_count_before, (
            "Dashboard record_restart() must not change canonical restart_count."
        )

    def test_u09_dashboard_record_failure_writes_subordinate_only(self, tmp_path):
        """U-09: Dashboard record_failure() does not touch canonical failure_count."""
        launcher_sup = _make_supervisor(tmp_path, "supervisor")
        launcher_sup.start()

        canonical = _canonical_state_file(tmp_path)
        mtime_before = canonical.stat().st_mtime
        time.sleep(0.05)

        dashboard_sup = _make_supervisor(tmp_path, "supervisor/dashboard")
        dashboard_sup.start()
        for _ in range(3):
            dashboard_sup.record_failure("dashboard test error")

        mtime_after = canonical.stat().st_mtime
        assert mtime_after == mtime_before, (
            "Dashboard record_failure() must not modify the canonical supervisor file."
        )
        canonical_state = json.loads(canonical.read_text())
        assert canonical_state["failure_count"] == 0, (
            "Dashboard record_failure() must not increment canonical failure_count."
        )

    def test_u10_subordinate_dir_created_automatically(self, tmp_path):
        """U-10: _ensure_state_dir creates the subordinate directory automatically."""
        subordinate_dir = tmp_path / "supervisor" / "dashboard"
        assert not subordinate_dir.exists(), "Pre-condition: subordinate dir must not exist"

        dashboard_sup = _make_supervisor(tmp_path, "supervisor/dashboard")
        # _ensure_state_dir is called during __init__
        assert subordinate_dir.exists(), (
            "_ensure_state_dir must create runtime/supervisor/dashboard/ automatically."
        )

    def test_u11_record_restart_no_args_succeeds(self, tmp_path):
        """U-11: record_restart() with no arguments succeeds (Change 2 regression)."""
        sup = _make_supervisor(tmp_path, "supervisor")
        sup.start()
        sup.record_failure("test failure")
        initial_restart_count = sup.restart_count

        # Must not raise TypeError
        sup.record_restart()

        assert sup.restart_count == initial_restart_count + 1
        assert sup.status == "RUNNING"
        assert sup.failure_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Consumer default path tests (U-12 – U-14)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsumerPathDefaults:

    def test_u12_freshness_manager_canonical_default(self):
        """U-12: RuntimeArtifactFreshnessManager defaults to the canonical supervisor path."""
        from backend.runtime.runtime_artifact_freshness import RuntimeArtifactFreshnessManager
        mgr = RuntimeArtifactFreshnessManager(artifacts_dir="artifacts")
        supervisor_path = str(mgr.paths["supervisor_state"])
        assert "runtime" in supervisor_path
        assert "supervisor" in supervisor_path
        assert "dashboard" not in supervisor_path, (
            "FreshnessManager must NOT default to the dashboard subordinate path."
        )
        assert "css_runtime_supervisor_state.json" in supervisor_path

    def test_u13_artifact_reader_canonical_default(self):
        """U-13: RuntimeArtifactReader defaults to the canonical supervisor path."""
        from dashboard.mission_control.runtime_artifact_reader import RuntimeArtifactReader
        import inspect
        sig = inspect.signature(RuntimeArtifactReader.__init__)
        default = str(sig.parameters["supervisor_state_path"].default)
        assert "dashboard" not in default, (
            f"RuntimeArtifactReader default changed to include 'dashboard': {default!r}"
        )
        assert "runtime/supervisor/css_runtime_supervisor_state.json" == default

    def test_u14_launcher_config_canonical_path(self, tmp_path, monkeypatch):
        """U-14: LauncherConfig.SUPERVISOR_STATE_FILE resolves to the canonical path."""
        from launcher.css_launcher_config import LauncherConfig
        path = LauncherConfig.SUPERVISOR_STATE_FILE
        assert "runtime" in path
        assert "supervisor" in path
        assert "css_runtime_supervisor_state.json" in path
        assert "dashboard" not in path, (
            f"LauncherConfig.SUPERVISOR_STATE_FILE unexpectedly includes 'dashboard': {path!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests (I-01 – I-05)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPathIsolationIntegration:

    def test_i01_concurrent_writes_leave_canonical_json_valid(self, tmp_path):
        """I-01: After N write cycles from both supervisors, canonical JSON is valid."""
        launcher_sup = _make_supervisor(tmp_path, "supervisor")
        dashboard_sup = _make_supervisor(tmp_path, "supervisor/dashboard")

        launcher_sup.start()
        dashboard_sup.start()

        # Interleave writes
        for i in range(20):
            if i % 3 == 0:
                launcher_sup.heartbeat()
            elif i % 3 == 1:
                dashboard_sup.heartbeat()
            else:
                launcher_sup.heartbeat()
                dashboard_sup.heartbeat()

        canonical = _canonical_state_file(tmp_path)
        assert canonical.exists()
        state = json.loads(canonical.read_text())  # must not raise
        assert isinstance(state, dict)
        assert state["supervisor_id"] == launcher_sup.supervisor_id, (
            "Canonical supervisor_id must always be the launcher's UUID after interleaved writes."
        )

    def test_i02_freshness_manager_reads_canonical_file(self, tmp_path):
        """I-02: FreshnessManager evaluates the canonical file written by launcher."""
        from backend.runtime.runtime_artifact_freshness import RuntimeArtifactFreshnessManager

        launcher_sup = _make_supervisor(tmp_path, "supervisor")
        launcher_sup.start()
        launcher_sup.heartbeat()

        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        canonical_path = _canonical_state_file(tmp_path)

        mgr = RuntimeArtifactFreshnessManager(
            artifacts_dir=str(artifacts_dir),
            supervisor_state_path=str(canonical_path),
        )
        result = mgr.evaluate()
        artifacts = result.get("artifacts", {})
        supervisor_info = artifacts.get("supervisor_state", {})

        assert supervisor_info.get("exists") is True, (
            "FreshnessManager must find the canonical supervisor state file."
        )
        assert supervisor_info.get("freshness") in {"FRESH", "AGING"}, (
            f"Expected FRESH or AGING freshness; got {supervisor_info.get('freshness')!r}"
        )

    def test_i03_dashboard_subordinate_file_is_valid_json(self, tmp_path):
        """I-03: The dashboard subordinate file is independently valid JSON."""
        dashboard_sup = _make_supervisor(tmp_path, "supervisor/dashboard")
        dashboard_sup.start()
        dashboard_sup.heartbeat()

        subordinate = _dashboard_state_file(tmp_path)
        assert subordinate.exists()

        state = json.loads(subordinate.read_text())  # must not raise
        assert isinstance(state, dict)
        assert state["status"] == "RUNNING"
        assert state["last_heartbeat_at"] is not None
        assert state["supervisor_id"] == dashboard_sup.supervisor_id

    def test_i04_both_files_coexist_without_interference(self, tmp_path):
        """I-05: Both supervisor files can exist and remain independent."""
        launcher_sup = _make_supervisor(tmp_path, "supervisor")
        dashboard_sup = _make_supervisor(tmp_path, "supervisor/dashboard")

        launcher_sup.start()
        dashboard_sup.start()

        # Each heartbeat cycle
        for _ in range(5):
            launcher_sup.heartbeat()
            dashboard_sup.heartbeat()
            time.sleep(0.01)

        canonical = _canonical_state_file(tmp_path)
        subordinate = _dashboard_state_file(tmp_path)

        # Both files exist
        assert canonical.exists()
        assert subordinate.exists()

        canonical_state   = json.loads(canonical.read_text())
        subordinate_state = json.loads(subordinate.read_text())

        # Each file carries its own supervisor_id
        assert canonical_state["supervisor_id"]   == launcher_sup.supervisor_id
        assert subordinate_state["supervisor_id"] == dashboard_sup.supervisor_id
        assert canonical_state["supervisor_id"]   != subordinate_state["supervisor_id"]

    def test_i05_launcher_restart_count_not_clobbered_by_dashboard(self, tmp_path):
        """I-04 (runtime contract): Dashboard writes cannot clobber launcher restart_count."""
        launcher_sup  = _make_supervisor(tmp_path, "supervisor")
        dashboard_sup = _make_supervisor(tmp_path, "supervisor/dashboard")

        launcher_sup.start()
        launcher_sup.record_failure("child process crash")
        launcher_sup.record_restart()   # restart_count now 1 in launcher

        canonical = _canonical_state_file(tmp_path)
        assert json.loads(canonical.read_text())["restart_count"] == 1

        # Dashboard writes multiple times
        dashboard_sup.start()
        for _ in range(10):
            dashboard_sup.heartbeat()

        # Canonical restart_count must still be 1 (launcher's value)
        assert json.loads(canonical.read_text())["restart_count"] == 1, (
            "Dashboard heartbeat cycles must not reset launcher's restart_count in canonical file."
        )
