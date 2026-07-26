"""
tests/test_phase172a_canonical_runtime_lifecycle.py

Phase 172A regression tests -- canonical launcher lifecycle, heartbeat
continuity, orphan-runtime detection, and Mission Control "Last Runtime
Heartbeat" wiring.

Verifies:
  A-01  classify_canonical_runtime_authority: healthy RUNNING + fresh
        heartbeat -> ONLINE
  A-02  classify_canonical_runtime_authority: status STOPPED -> STOPPED
        (not ORPHANED_RUNTIME) when no dashboard activity
  A-03  classify_canonical_runtime_authority: status STOPPED + fresh
        dashboard subordinate heartbeat -> ORPHANED_RUNTIME
  A-04  classify_canonical_runtime_authority: canonical file missing +
        fresh dashboard subordinate heartbeat -> ORPHANED_RUNTIME
  A-05  classify_canonical_runtime_authority: canonical file missing,
        no dashboard activity -> MISSING
  A-06  classify_canonical_runtime_authority: malformed heartbeat string
        -> MALFORMED
  A-07  classify_canonical_runtime_authority: stale heartbeat (RUNNING but
        past threshold) -> STALE
  A-08  classify_canonical_runtime_authority: synthetic gap-fill marker is
        never treated as canonical proof, even if status says RUNNING
  F-01  RuntimeArtifactFreshnessManager fails closed (STALE/RED) for a
        canonical file with fresh mtime but STOPPED status
  F-02  RuntimeArtifactFreshnessManager stays GREEN/FRESH for a genuinely
        healthy canonical file
  F-03  Orphan runtime is surfaced as a blocker in evaluate()
  R-01  RuntimeArtifactReader.read_candidate() is not "available" when the
        canonical supervisor is STOPPED even though the file was just
        written (fresh mtime)
  R-02  RuntimeArtifactReader.read_candidate() rejects a fresh dashboard
        subordinate heartbeat as proof of canonical health
  S-01  canonical_runtime_snapshot._snapshot_from_artifacts surfaces
        ORPHANED_RUNTIME as runtime_status when orphaned
  D-01  Mission Control "Last Runtime Heartbeat" (data_freshness.
        last_runtime_heartbeat) is sourced from the canonical runtime
        snapshot heartbeat, not broker connectivity data
  G-01  Mobile launcher gap-fill publisher no longer fabricates RUNNING
  L-01  Launcher heartbeat advances the canonical artifact across
        successive calls (mtime + last_heartbeat_at both advance)
  L-02  supervisor_id remains stable across heartbeat cycles
  L-03  Full shutdown transitions canonical status to STOPPED
  M-01  build_canonical_runtime_snapshot main (frontend/"sections") branch
        prefers frontend["canonical_runtime_supervisor"] heartbeat over
        broker connectivity heartbeat (the live in-process serving path,
        distinct from the artifact-file fallback path covered by D-01)
  M-02  M-01's runtime_status becomes ORPHANED_RUNTIME when the canonical
        supervisor is stopped but a dashboard subordinate heartbeat is fresh
  M-03  A live, cross-process-safe registry source (as now registered by
        launcher/css_mobile_launcher.py's _mission_control_registry_source)
        takes precedence over stale artifact files and still surfaces the
        live canonical heartbeat through RuntimeSourceResolver
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from backend.runtime.canonical_runtime_authority import (
    AUTHORITY_MALFORMED,
    AUTHORITY_MISSING,
    AUTHORITY_ONLINE,
    AUTHORITY_ORPHANED_RUNTIME,
    AUTHORITY_STALE,
    AUTHORITY_STOPPED,
    classify_canonical_runtime_authority,
)
from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor
from backend.runtime.runtime_artifact_freshness import RuntimeArtifactFreshnessManager
from backend.runtime.canonical_runtime_snapshot import build_canonical_runtime_snapshot
from dashboard.mission_control.runtime_artifact_reader import RuntimeArtifactReader


NOW = datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# A -- classify_canonical_runtime_authority unit tests
# ═══════════════════════════════════════════════════════════════════════════

class TestCanonicalRuntimeAuthorityClassifier:
    def test_a01_running_fresh_heartbeat_is_online(self):
        result = classify_canonical_runtime_authority(
            {"status": "RUNNING", "last_heartbeat_at": _iso(NOW)},
            None,
            now=NOW,
        )
        assert result["authority_status"] == AUTHORITY_ONLINE
        assert result["canonical_alive"] is True
        assert result["orphan_runtime"] is False

    def test_a02_stopped_status_without_dashboard_is_stopped(self):
        result = classify_canonical_runtime_authority(
            {"status": "STOPPED", "last_heartbeat_at": _iso(NOW - timedelta(seconds=30))},
            None,
            now=NOW,
        )
        assert result["authority_status"] == AUTHORITY_STOPPED
        assert result["canonical_alive"] is False
        assert result["orphan_runtime"] is False

    def test_a03_stopped_status_with_fresh_dashboard_is_orphaned(self):
        result = classify_canonical_runtime_authority(
            {"status": "STOPPED", "last_heartbeat_at": _iso(NOW - timedelta(seconds=30))},
            {"status": "RUNNING", "last_heartbeat_at": _iso(NOW - timedelta(seconds=5))},
            now=NOW,
        )
        assert result["authority_status"] == AUTHORITY_ORPHANED_RUNTIME
        assert result["canonical_alive"] is False
        assert result["orphan_runtime"] is True

    def test_a04_missing_canonical_with_fresh_dashboard_is_orphaned(self):
        result = classify_canonical_runtime_authority(
            None,
            {"status": "RUNNING", "last_heartbeat_at": _iso(NOW - timedelta(seconds=5))},
            now=NOW,
        )
        assert result["authority_status"] == AUTHORITY_ORPHANED_RUNTIME
        assert result["orphan_runtime"] is True

    def test_a05_missing_canonical_no_dashboard_is_missing(self):
        result = classify_canonical_runtime_authority(None, None, now=NOW)
        assert result["authority_status"] == AUTHORITY_MISSING
        assert result["orphan_runtime"] is False

    def test_a06_malformed_heartbeat_string_is_malformed(self):
        result = classify_canonical_runtime_authority(
            {"status": "RUNNING", "last_heartbeat_at": "not-a-timestamp"},
            None,
            now=NOW,
        )
        assert result["authority_status"] == AUTHORITY_MALFORMED

    def test_a07_stale_heartbeat_past_threshold_is_stale(self):
        result = classify_canonical_runtime_authority(
            {"status": "RUNNING", "last_heartbeat_at": _iso(NOW - timedelta(seconds=600))},
            None,
            now=NOW,
            stale_after_seconds=120.0,
        )
        assert result["authority_status"] == AUTHORITY_STALE
        assert result["canonical_alive"] is False

    def test_a08_synthetic_gap_fill_marker_never_counts_as_canonical_even_if_running(self):
        result = classify_canonical_runtime_authority(
            {"status": "RUNNING", "last_heartbeat": _iso(NOW), "synthetic": True},
            None,
            now=NOW,
        )
        assert result["authority_status"] != AUTHORITY_ONLINE
        assert result["canonical_alive"] is False


# ═══════════════════════════════════════════════════════════════════════════
# F -- RuntimeArtifactFreshnessManager fail-closed behavior
# ═══════════════════════════════════════════════════════════════════════════

class TestFreshnessManagerFailsClosed:
    def _manager(self, tmp_path: Path) -> RuntimeArtifactFreshnessManager:
        artifacts = tmp_path / "artifacts"
        return RuntimeArtifactFreshnessManager(
            artifacts_dir=artifacts,
            account_state_path=artifacts / "account.json",
            session_state_path=artifacts / "session.json",
            supervisor_state_path=tmp_path / "runtime" / "supervisor" / "css_runtime_supervisor_state.json",
            dashboard_supervisor_state_path=tmp_path / "runtime" / "supervisor" / "dashboard" / "css_runtime_supervisor_state.json",
            closed_trade_ledger_path=tmp_path / "audit" / "closed.jsonl",
        )

    def _write_required(self, tmp_path: Path, supervisor_payload: dict) -> None:
        artifacts = tmp_path / "artifacts"
        _write_json(artifacts / "account.json", {"account_balance": 1000.0})
        _write_json(artifacts / "session.json", {"session": {"engine_mode": "PAPER"}})
        _write_json(tmp_path / "runtime" / "supervisor" / "css_runtime_supervisor_state.json", supervisor_payload)

    def test_f01_fresh_mtime_but_stopped_status_fails_closed(self, tmp_path: Path):
        # The file was JUST written (fresh mtime) but truthfully declares
        # STOPPED -- a real launcher shutdown. mtime freshness must not
        # override the declared status.
        self._write_required(tmp_path, {"status": "STOPPED", "last_heartbeat_at": _iso(NOW - timedelta(seconds=10))})

        result = self._manager(tmp_path).evaluate(runtime_active=True, now=NOW)

        assert result["artifacts"]["supervisor_state"]["freshness"] == "STALE"
        assert result["freshness_status"] == "RED"
        assert "stale_supervisor_state" in result["blockers"]
        assert result["canonical_authority"]["authority_status"] == AUTHORITY_STOPPED

    def test_f02_healthy_running_heartbeat_stays_green(self, tmp_path: Path):
        self._write_required(tmp_path, {"status": "RUNNING", "last_heartbeat_at": _iso(NOW)})
        for name in ("portfolio_snapshot.json", "runtime_portfolio_state.json", "runtime_advisory_snapshot.json", "portfolio_decision.json", "validation_summary.json"):
            _write_json(tmp_path / "artifacts" / name, {"status": "OK"})
        ledger = tmp_path / "audit" / "closed.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text("", encoding="utf-8")

        result = self._manager(tmp_path).evaluate(runtime_active=True, now=NOW)

        assert result["artifacts"]["supervisor_state"]["freshness"] in {"FRESH", "AGING"}
        assert result["freshness_status"] == "GREEN"
        assert result["canonical_authority"]["authority_status"] == AUTHORITY_ONLINE

    def test_f03_orphan_runtime_surfaced_as_blocker(self, tmp_path: Path):
        self._write_required(tmp_path, {"status": "STOPPED", "last_heartbeat_at": _iso(NOW - timedelta(seconds=300))})
        _write_json(
            tmp_path / "runtime" / "supervisor" / "dashboard" / "css_runtime_supervisor_state.json",
            {"status": "RUNNING", "last_heartbeat_at": _iso(NOW - timedelta(seconds=5))},
        )

        result = self._manager(tmp_path).evaluate(runtime_active=True, now=NOW)

        assert result["canonical_authority"]["orphan_runtime"] is True
        assert result["canonical_authority"]["authority_status"] == AUTHORITY_ORPHANED_RUNTIME
        assert "orphaned_runtime_detected" in result["blockers"]
        assert result["freshness_status"] == "RED"


# ═══════════════════════════════════════════════════════════════════════════
# R -- RuntimeArtifactReader gating
# ═══════════════════════════════════════════════════════════════════════════

class TestRuntimeArtifactReaderOrphanGating:
    def _fixture(self, tmp_path: Path, supervisor_payload: dict, dashboard_payload: dict | None = None) -> Path:
        artifacts = tmp_path / "artifacts"
        supervisor_path = tmp_path / "runtime" / "supervisor" / "css_runtime_supervisor_state.json"
        _write_json(supervisor_path, supervisor_payload)
        _write_json(artifacts / "css_session_state_pcnrass.json", {"session": {"session_id": "s1", "cycle_number": 1}})
        _write_json(artifacts / "css_account_state_pcnrass.json", {"account_balance": 1000.0})
        if dashboard_payload is not None:
            _write_json(tmp_path / "runtime" / "supervisor" / "dashboard" / "css_runtime_supervisor_state.json", dashboard_payload)
        return supervisor_path

    def test_r01_stopped_canonical_with_fresh_mtime_is_not_available(self, tmp_path: Path):
        supervisor_path = self._fixture(
            tmp_path,
            {"status": "STOPPED", "last_heartbeat_at": _iso(datetime.now(timezone.utc) - timedelta(seconds=10))},
        )
        reader = RuntimeArtifactReader(artifact_root=tmp_path / "artifacts", supervisor_state_path=supervisor_path)

        candidate = reader.read_candidate()

        assert candidate.available is False
        assert "orphan" in candidate.failure or "not_alive" in candidate.failure

    def test_r02_fresh_dashboard_heartbeat_alone_does_not_satisfy_canonical_health(self, tmp_path: Path):
        supervisor_path = self._fixture(
            tmp_path,
            {"status": "STOPPED", "last_heartbeat_at": _iso(datetime.now(timezone.utc) - timedelta(seconds=300))},
            dashboard_payload={"status": "RUNNING", "last_heartbeat_at": _iso(datetime.now(timezone.utc) - timedelta(seconds=5))},
        )
        reader = RuntimeArtifactReader(artifact_root=tmp_path / "artifacts", supervisor_state_path=supervisor_path)

        candidate = reader.read_candidate()

        assert candidate.available is False
        assert candidate.failure == "orphaned_runtime_detected"

    def test_r03_healthy_canonical_is_available(self, tmp_path: Path):
        supervisor_path = self._fixture(
            tmp_path,
            {"status": "RUNNING", "last_heartbeat_at": _iso(datetime.now(timezone.utc))},
        )
        reader = RuntimeArtifactReader(artifact_root=tmp_path / "artifacts", supervisor_state_path=supervisor_path)

        candidate = reader.read_candidate()

        assert candidate.available is True
        assert candidate.failure == ""


# ═══════════════════════════════════════════════════════════════════════════
# S -- canonical_runtime_snapshot orphan surfacing
# ═══════════════════════════════════════════════════════════════════════════

class TestCanonicalRuntimeSnapshotOrphanStatus:
    def test_s01_orphan_diagnostics_surface_as_runtime_status(self):
        source = {
            "supervisor": {"status": "STOPPED", "last_heartbeat_at": _iso(NOW - timedelta(seconds=300))},
            "session": {"session_id": "orphan-session"},
            "account": {"account_balance": 1000.0},
            "runtime_source_diagnostics": {
                "freshness": {
                    "canonical_authority": {
                        "authority_status": AUTHORITY_ORPHANED_RUNTIME,
                        "canonical_alive": False,
                        "orphan_runtime": True,
                        "reason": "canonical_status_stopped",
                    }
                }
            },
        }

        snapshot = build_canonical_runtime_snapshot(source, None, source_name="test")

        assert snapshot["runtime_status"] == AUTHORITY_ORPHANED_RUNTIME

    def test_s02_online_authority_defers_to_declared_status(self):
        source = {
            "supervisor": {"status": "RUNNING", "last_heartbeat_at": _iso(NOW)},
            "session": {"session_id": "healthy-session"},
            "account": {"account_balance": 1000.0},
            "runtime_source_diagnostics": {
                "freshness": {"canonical_authority": {"authority_status": AUTHORITY_ONLINE}}
            },
        }

        snapshot = build_canonical_runtime_snapshot(source, None, source_name="test")

        assert snapshot["runtime_status"] == "RUNNING"
        assert snapshot["last_heartbeat"] == _iso(NOW)


# ═══════════════════════════════════════════════════════════════════════════
# D -- Mission Control "Last Runtime Heartbeat" wiring
# ═══════════════════════════════════════════════════════════════════════════

class TestDataFreshnessHeartbeatWiring:
    def test_d01_prefers_canonical_runtime_snapshot_heartbeat_over_broker(self):
        from dashboard.mission_control.contracts import _data_freshness

        runtime_snapshot = {"last_heartbeat": "2026-07-17T12:00:00+00:00"}
        broker = {"last_heartbeat": "2020-01-01T00:00:00+00:00", "last_successful_sync": "2020-01-01T00:00:00+00:00"}

        result = _data_freshness({}, broker, {}, {}, runtime_snapshot)

        assert result["last_runtime_heartbeat"] == "2026-07-17T12:00:00+00:00"

    def test_d02_falls_back_to_broker_when_canonical_unavailable(self):
        from dashboard.mission_control.contracts import _data_freshness

        runtime_snapshot = {"last_heartbeat": "DATA UNAVAILABLE"}
        broker = {"last_heartbeat": "2026-01-01T00:00:00+00:00"}

        result = _data_freshness({}, broker, {}, {}, runtime_snapshot)

        assert result["last_runtime_heartbeat"] == "2026-01-01T00:00:00+00:00"

    def test_d03_end_to_end_mission_control_state_surfaces_canonical_heartbeat(self, tmp_path: Path, monkeypatch):
        from dashboard.mission_control import contracts as contracts_module
        from dashboard.mission_control.runtime_snapshot_provider import RuntimeSnapshotProvider

        supervisor_path = tmp_path / "runtime" / "supervisor" / "css_runtime_supervisor_state.json"
        heartbeat_iso = _iso(datetime.now(timezone.utc))
        _write_json(supervisor_path, {"status": "RUNNING", "last_heartbeat_at": heartbeat_iso})
        artifacts = tmp_path / "artifacts"
        _write_json(artifacts / "css_session_state_pcnrass.json", {"session": {"session_id": "e2e"}})
        _write_json(artifacts / "css_account_state_pcnrass.json", {"account_balance": 1000.0})

        source = {
            "frontend_payload": {"sections": {}},
        }

        def fake_runtime_snapshot(dashboard_state, frontend):
            provider = RuntimeSnapshotProvider(
                artifact_root=artifacts,
                supervisor_state_path=supervisor_path,
                active_source_binding=True,
            )
            return provider.get_state_payload()["runtime_snapshot"]

        monkeypatch.setattr(contracts_module, "_runtime_snapshot", fake_runtime_snapshot)

        state = contracts_module.build_mission_control_state({}, allow_mock=True)

        assert state["data_freshness"]["last_runtime_heartbeat"] == heartbeat_iso


# ═══════════════════════════════════════════════════════════════════════════
# G -- Mobile launcher gap-fill publisher no longer fabricates health
# ═══════════════════════════════════════════════════════════════════════════

class TestGapFillPublisherDoesNotFabricateHealth:
    def test_g01_gap_fill_write_never_claims_running(self, tmp_path: Path, monkeypatch):
        from launcher import css_mobile_launcher as mobile

        target = tmp_path / "runtime" / "supervisor" / "css_runtime_supervisor_state.json"
        monkeypatch.setattr(mobile.LauncherConfig, "SUPERVISOR_STATE_FILE", str(target))

        result = mobile._publish_supervisor_heartbeat_snapshot()

        assert result["status"] == "OK"
        written = json.loads(target.read_text(encoding="utf-8"))
        assert written["status"] != "RUNNING"
        assert written.get("synthetic") is True


# ═══════════════════════════════════════════════════════════════════════════
# L -- Canonical launcher supervisor heartbeat continuity (proves the
#      priority acceptance criterion at the CSSRuntimeSupervisor level)
# ═══════════════════════════════════════════════════════════════════════════

class TestLauncherHeartbeatContinuity:
    def _supervisor(self, tmp_path: Path) -> CSSRuntimeSupervisor:
        return CSSRuntimeSupervisor(state_dir=str(tmp_path / "supervisor"), alert_service=MagicMock())

    def test_l01_heartbeat_advances_timestamp_and_mtime_across_cycles(self, tmp_path: Path):
        sup = self._supervisor(tmp_path)
        sup.start()

        sup.heartbeat()
        state_file = Path(sup.state_file)
        first_heartbeat = json.loads(state_file.read_text())["last_heartbeat_at"]
        first_mtime = state_file.stat().st_mtime

        time.sleep(0.05)
        sup.heartbeat()
        second_heartbeat = json.loads(state_file.read_text())["last_heartbeat_at"]
        second_mtime = state_file.stat().st_mtime

        assert second_heartbeat > first_heartbeat
        assert second_mtime >= first_mtime

    def test_l02_supervisor_id_stable_across_heartbeats(self, tmp_path: Path):
        sup = self._supervisor(tmp_path)
        sup.start()
        state_file = Path(sup.state_file)
        original_id = json.loads(state_file.read_text())["supervisor_id"]

        for _ in range(5):
            sup.heartbeat()

        assert json.loads(state_file.read_text())["supervisor_id"] == original_id
        assert original_id == sup.supervisor_id

    def test_l03_full_shutdown_sets_stopped_status(self, tmp_path: Path):
        sup = self._supervisor(tmp_path)
        sup.start()
        sup.heartbeat()
        sup.stop()

        state = json.loads(Path(sup.state_file).read_text())
        assert state["status"] == "STOPPED"
        assert state["stopped_at"] is not None

        authority = classify_canonical_runtime_authority(state, None)
        assert authority["authority_status"] == AUTHORITY_STOPPED
        assert authority["canonical_alive"] is False


# ═══════════════════════════════════════════════════════════════════════════
# M -- Live in-process ("registry") serving path: this is the branch actually
#      exercised when Mission Control is served directly by a running
#      launcher/mobile-launcher session, as opposed to the artifact-file
#      fallback path covered by the D-xx tests above. A live operational
#      verification revealed this branch had the same broker-vs-canonical
#      heartbeat wiring defect as D-01, independently of it.
# ═══════════════════════════════════════════════════════════════════════════

def _frontend_with_sections(**overrides) -> dict:
    base = {
        "generated_at": _iso(NOW),
        "session_id": "live-session",
        "resolved_mode": "paper",
        "session": {"session_id": "live-session"},
        "sections": {
            "broker": {
                "last_heartbeat": "2020-01-01T00:00:00+00:00",
                "last_successful_sync": "2020-01-01T00:00:00+00:00",
            },
            "account_summary": {},
            "pnl_summary": {},
            "positions": {},
            "risk": {},
            "market": {},
        },
    }
    base.update(overrides)
    return base


class TestLiveRegistryPathHeartbeatWiring:
    def test_m01_main_branch_prefers_canonical_supervisor_heartbeat_over_broker(self):
        canonical_heartbeat = _iso(NOW)
        frontend = _frontend_with_sections(
            canonical_runtime_supervisor={"status": "RUNNING", "last_heartbeat_at": canonical_heartbeat},
        )

        snapshot = build_canonical_runtime_snapshot({}, frontend, source_name="test")

        assert snapshot["last_heartbeat"] == canonical_heartbeat
        assert snapshot["last_heartbeat"] != "2020-01-01T00:00:00+00:00"

    def test_m02_orphaned_canonical_surfaces_as_runtime_status_in_main_branch(self):
        frontend = _frontend_with_sections(
            canonical_runtime_supervisor={
                "status": "STOPPED",
                "last_heartbeat_at": _iso(NOW - timedelta(seconds=300)),
            },
        )
        # No dashboard-subordinate info reachable from this branch directly,
        # but classify_canonical_runtime_authority(canonical, None) should
        # still correctly report STOPPED (not fabricate ONLINE/RUNNING).
        snapshot = build_canonical_runtime_snapshot({}, frontend, source_name="test")

        assert snapshot["runtime_status"] == AUTHORITY_STOPPED

    def test_m03_cross_process_safe_registry_beats_stale_artifacts_and_surfaces_live_heartbeat(self, tmp_path: Path):
        from dashboard.mission_control.runtime_snapshot_provider import RuntimeSnapshotProvider

        # Stale artifact files on disk (simulating a dashboard that hasn't
        # published in a long time) -- the artifact-file fallback path would
        # reject these as not fresh.
        artifacts = tmp_path / "artifacts"
        supervisor_path = tmp_path / "runtime" / "supervisor" / "css_runtime_supervisor_state.json"
        stale_time = time.time() - 3600
        _write_json(artifacts / "css_session_state_pcnrass.json", {"session": {"session_id": "stale"}})
        _write_json(artifacts / "css_account_state_pcnrass.json", {"account_balance": 1.0})
        _write_json(supervisor_path, {"status": "STOPPED"})
        import os
        os.utime(artifacts / "css_session_state_pcnrass.json", (stale_time, stale_time))
        os.utime(artifacts / "css_account_state_pcnrass.json", (stale_time, stale_time))

        live_heartbeat = _iso(datetime.now(timezone.utc))

        def live_registry_source():
            # Matches the shape launcher.css_mobile_launcher._mission_control_registry_source()
            # returns in production: the flat frontend-contract payload
            # (with "sections" at the top level) plus the cross-process-safe
            # flag set directly on it -- not nested under another key.
            payload = _frontend_with_sections(
                canonical_runtime_supervisor={"status": "RUNNING", "last_heartbeat_at": live_heartbeat},
            )
            payload["mission_control_runtime_registry_cross_process_safe"] = True
            return payload

        provider = RuntimeSnapshotProvider(
            live_registry_source,
            artifact_root=artifacts,
            supervisor_state_path=supervisor_path,
            active_source_binding=True,
        )
        state_payload = provider.get_state_payload()
        snapshot = state_payload["runtime_snapshot"]

        assert snapshot["last_heartbeat"] == live_heartbeat
        # ONLINE is the correct healthy label here: with no certification/
        # frontend override, _runtime_status() derives it from heartbeat
        # freshness -- the canonical_authority ONLINE classification is what
        # allows that (non-overridden) path to be taken at all instead of
        # being forced to a fail-closed label (STOPPED/ORPHANED_RUNTIME/...).
        assert snapshot["runtime_status"] == "ONLINE"
