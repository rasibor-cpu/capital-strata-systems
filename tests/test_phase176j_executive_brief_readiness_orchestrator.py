"""Phase 176J — Executive Brief readiness orchestrator tests."""

from __future__ import annotations

import json
from pathlib import Path

from backend.executive_intelligence.freshness_policy import load_freshness_policy
from backend.executive_intelligence.orchestrator import ExecutiveBriefReadinessOrchestrator
from backend.executive_intelligence.readiness import (
    ExecutiveBriefReadinessEvaluator,
    readiness_audit_phrase,
)
from backend.executive_intelligence.service import ExecutiveIntelligenceEngine
from backend.executive_intelligence.constants import SAFETY_LOCKS


def _good_evidence() -> dict:
    return {
        "runtime_health": {
            "status": "HEALTHY",
            "runtime_health": "GREEN",
            "freshness": "FRESH",
            "heartbeat_age_seconds": 5,
            "runtime_id": "rt-test-001",
            "supervisor_id": "sup-test-001",
            "state_hash": "abc123",
        },
        "broker_health": {
            "health": "GREEN",
            "status": "GREEN",
            "freshness": "FRESH",
            "brokers": {"OANDA": {"health": "GREEN"}},
        },
        "portfolio": {
            "status": "OK",
            "freshness": "FRESH",
            "equity": 100000.0,
            "cash": 25000.0,
            "total_exposure": 0.4,
            "portfolio_health": 0.88,
            "capital_efficiency": 0.8,
        },
        "market": {
            "regime": "Risk-On",
            "regime_current": "Risk-On",
            "freshness": "FRESH",
            "confidence": 0.82,
            "overnight_market_summary": {"note": "stub"},
            "generated_at_utc": "2099-01-01T00:00:00Z",
        },
        "opportunities": [{"symbol": "EUR_USD", "confidence": 0.8}],
        "committee": {"status": "OK", "overall_recommendation": "APPROVE", "vetoes": [], "freshness": "FRESH"},
        "learning": {"freshness": "FRESH", "confidence": 0.7},
        "risk": {"risk_level": "MEDIUM", "stability": 0.7, "freshness": "FRESH"},
        "alerts": {"count": 0},
        "explainability": {"why": "test"},
    }


def _fast_policy(**gate_overrides: dict) -> dict:
    policy = load_freshness_policy(
        overrides={
            "retry_interval_seconds": 1,
            "max_wait_seconds": 3,
            "advisory_only": True,
        }
    )
    for gate_id, overlay in gate_overrides.items():
        policy["gates"][gate_id].update(overlay)
    return policy


def test_ready_path(tmp_path: Path) -> None:
    ev = ExecutiveBriefReadinessEvaluator(repo_root=tmp_path, policy=_fast_policy())
    result = ev.evaluate(evidence=_good_evidence())
    assert result["status"] == "READY"
    assert result["waiting_for"] == []
    for gate in result["gates"].values():
        assert gate["status"] == "READY"


def test_wait_path_stale_runtime() -> None:
    evidence = _good_evidence()
    evidence["runtime_health"]["freshness"] = "STALE"
    evidence["runtime_health"]["heartbeat_age_seconds"] = 500
    ev = ExecutiveBriefReadinessEvaluator(policy=_fast_policy())
    result = ev.evaluate(evidence=evidence)
    assert result["status"] == "WAITING"
    assert any("Runtime" in w for w in result["waiting_for"])
    assert result["gates"]["runtime_snapshot"]["status"] == "STALE"


def test_stale_broker_never_ready() -> None:
    evidence = _good_evidence()
    evidence["broker_health"]["freshness"] = "UNAVAILABLE"
    ev = ExecutiveBriefReadinessEvaluator(policy=_fast_policy())
    result = ev.evaluate(evidence=evidence)
    assert result["status"] == "WAITING"
    assert result["gates"]["broker_snapshot"]["status"] == "UNAVAILABLE"
    assert any("Broker" in w for w in result["waiting_for"])


def test_stale_portfolio_waiting() -> None:
    evidence = _good_evidence()
    evidence["portfolio"]["freshness"] = "STALE"
    ev = ExecutiveBriefReadinessEvaluator(policy=_fast_policy())
    result = ev.evaluate(evidence=evidence)
    assert result["status"] == "WAITING"
    assert result["gates"]["portfolio_snapshot"]["status"] == "STALE"


def test_freshness_expiry_by_age() -> None:
    evidence = _good_evidence()
    evidence["runtime_health"]["freshness"] = "FRESH"
    evidence["runtime_health"]["heartbeat_age_seconds"] = 999
    policy = _fast_policy(runtime_snapshot={"max_age_seconds": 90}, system_heartbeat={"max_age_seconds": 60})
    ev = ExecutiveBriefReadinessEvaluator(policy=policy)
    result = ev.evaluate(evidence=evidence)
    assert result["status"] == "WAITING"
    assert result["gates"]["system_heartbeat"]["status"] == "STALE"


def test_advisory_broker_unavailable_still_not_ready() -> None:
    evidence = _good_evidence()
    evidence["broker_health"] = {}  # explicit empty — never load from disk
    policy = _fast_policy()
    policy["advisory_only"] = True
    ev = ExecutiveBriefReadinessEvaluator(policy=policy)
    result = ev.evaluate(evidence=evidence)
    assert result["gates"]["broker_snapshot"]["status"] == "UNAVAILABLE"
    assert result["status"] != "READY"


def test_timeout_path_archives_fail_closed(tmp_path: Path) -> None:
    evidence = _good_evidence()
    evidence["runtime_health"]["freshness"] = "STALE"
    evidence["runtime_health"]["heartbeat_age_seconds"] = 999
    sleeps: list[float] = []
    clock = {"t": 0.0}

    def sleep_fn(sec: float) -> None:
        sleeps.append(sec)
        clock["t"] += sec

    engine = ExecutiveIntelligenceEngine(
        repo_root=tmp_path,
        archive_root=tmp_path / "morning_briefings",
        freshness_policy=_fast_policy(),
    )
    orch = ExecutiveBriefReadinessOrchestrator(
        repo_root=tmp_path,
        archive_root=tmp_path / "morning_briefings",
        policy=_fast_policy(),
        sleep_fn=sleep_fn,
        time_fn=lambda: clock["t"],
    )
    result = orch.run(
        evidence=evidence,
        report_date="2026-07-19",
        wait=True,
        persist=True,
        created_reason="test_timeout",
        generate_fn=engine._generate_once,
    )
    assert result["ready"] is False
    assert result["status"] == "FAILED"
    assert result["readiness"]["orchestration_status"] == "FAILED"
    assert sleeps  # retried
    session = json.loads(
        (tmp_path / "morning_briefings" / "readiness" / "latest_session.json").read_text(encoding="utf-8")
    )
    assert session["attempt"] >= 2
    brief = result.get("brief") or {}
    assert brief.get("report_status") == "FAILED"
    assert result["validation"].get("finalization_allowed") is False


def test_retry_recovery_then_generate(tmp_path: Path) -> None:
    evidence = _good_evidence()
    evidence["runtime_health"]["freshness"] = "STALE"
    evidence["runtime_health"]["heartbeat_age_seconds"] = 500
    clock = {"t": 0.0}
    flips = {"n": 0}

    def sleep_fn(sec: float) -> None:
        clock["t"] += sec
        flips["n"] += 1
        # Recover after first wait.
        evidence["runtime_health"]["freshness"] = "FRESH"
        evidence["runtime_health"]["heartbeat_age_seconds"] = 5

    engine = ExecutiveIntelligenceEngine(
        repo_root=tmp_path,
        archive_root=tmp_path / "morning_briefings",
        freshness_policy=_fast_policy(),
    )
    orch = ExecutiveBriefReadinessOrchestrator(
        repo_root=tmp_path,
        archive_root=tmp_path / "morning_briefings",
        policy=_fast_policy(),
        sleep_fn=sleep_fn,
        time_fn=lambda: clock["t"],
    )
    result = orch.run(
        evidence=evidence,
        report_date="2026-07-19",
        wait=True,
        persist=True,
        created_reason="test_recovery",
        generate_fn=engine._generate_once,
    )
    assert result["ready"] is True
    assert result["readiness"]["retries"] >= 1
    assert "Generated after waiting" in result["readiness"]["audit_phrase"] or "Readiness achieved" in result["readiness"]["audit_phrase"]
    brief = result["brief"]
    assert brief.get("report_status") == "FINAL"
    assert brief.get("readiness_audit")
    manifest_paths = list((tmp_path / "morning_briefings").rglob("manifest.json"))
    assert manifest_paths
    # version manifest includes readiness
    version_manifests = [p for p in manifest_paths if p.parent.name.startswith("v")]
    assert version_manifests
    man = json.loads(version_manifests[0].read_text(encoding="utf-8"))
    assert man.get("readiness_audit")
    assert man.get("readiness")


def test_immediate_ready_audit_phrase() -> None:
    assert readiness_audit_phrase(attempts=1, waited_seconds=0, status="READY") == "Generated immediately"


def test_engine_generate_with_injected_evidence_skips_wait_by_default(tmp_path: Path) -> None:
    engine = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=tmp_path / "mb")
    result = engine.generate(
        evidence=_good_evidence(),
        report_date="2026-07-19",
        persist=True,
        created_reason="test",
    )
    assert result["brief"]["report_status"] == "FINAL"
    assert result.get("readiness") in (None, {}) or result.get("ready") is not False


def test_engine_forced_wait_uses_orchestrator(tmp_path: Path) -> None:
    evidence = _good_evidence()
    engine = ExecutiveIntelligenceEngine(
        repo_root=tmp_path,
        archive_root=tmp_path / "mb",
        freshness_policy=_fast_policy(),
    )
    clock = {"t": 0.0}

    # Patch orchestrator indirectly via wait_for_readiness True with short policy
    from backend.executive_intelligence import orchestrator as orch_mod

    original = orch_mod.ExecutiveBriefReadinessOrchestrator

    class FastOrch(original):  # type: ignore[valid-type,misc]
        def __init__(self, *a, **k):
            k.setdefault("sleep_fn", lambda s: clock.__setitem__("t", clock["t"] + s))
            k.setdefault("time_fn", lambda: clock["t"])
            k["policy"] = _fast_policy()
            super().__init__(*a, **k)

    orch_mod.ExecutiveBriefReadinessOrchestrator = FastOrch  # type: ignore[misc]
    try:
        result = engine.generate(
            evidence=evidence,
            report_date="2026-07-19",
            persist=True,
            wait_for_readiness=True,
            created_reason="test_forced_wait",
        )
        assert result.get("ready") is True
        assert result["brief"]["report_status"] == "FINAL"
        assert "readiness_audit" in result["brief"]
    finally:
        orch_mod.ExecutiveBriefReadinessOrchestrator = original  # type: ignore[misc]


def test_ui_home_exposes_waiting_labels(tmp_path: Path, monkeypatch) -> None:
    from backend.reports_center.service import ReportsCenterService

    svc = ReportsCenterService(repo_root=tmp_path)
    # Force readiness WAITING via evaluator monkeypatch
    from backend.executive_intelligence import service as eng_svc

    class StubEngine:
        def __init__(self, *a, **k):
            pass

        def readiness(self, evidence=None):
            return {
                "status": "WAITING",
                "waiting_for": ["Waiting for Runtime", "Waiting for Portfolio", "Waiting for Broker", "Waiting for Market"],
                "waiting_labels": ["Waiting for Runtime", "Waiting for Portfolio", "Waiting for Broker", "Waiting for Market"],
                "reason": "waiting_for:runtime_snapshot",
                **SAFETY_LOCKS,
            }

    monkeypatch.setattr(eng_svc, "ExecutiveIntelligenceEngine", StubEngine)
    home = svc.home(role="SUPER_USER", user_id="00000")
    assert home["executive_brief_readiness"]["status"] == "WAITING"
    labels = home["executive_brief_readiness"]["waiting_labels"]
    assert "Waiting for Runtime" in labels
    assert "Waiting for Portfolio" in labels
    assert "Waiting for Broker" in labels
    assert "Waiting for Market" in labels


def test_mc_reports_page_shows_waiting_copy() -> None:
    from dashboard.mission_control.pages.reports_center import _library_panel

    html = _library_panel(
        {
            "recent_reports": [],
            "report_generation_failures": [],
            "latest_daily_executive_brief": {"status": "UNAVAILABLE"},
            "executive_brief_readiness": {
                "status": "WAITING",
                "waiting_labels": [
                    "Waiting for Runtime",
                    "Waiting for Portfolio",
                    "Waiting for Broker",
                    "Waiting for Market",
                ],
                "reason": "waiting_for:runtime_snapshot",
            },
        }
    )
    assert "Waiting for Runtime" in html
    assert "Waiting for Portfolio" in html
    assert "Waiting for Broker" in html
    assert "Waiting for Market" in html
    assert "Executive Brief readiness" in html


def test_safety_locks_unchanged_on_readiness() -> None:
    result = ExecutiveBriefReadinessEvaluator(policy=_fast_policy()).evaluate(evidence=_good_evidence())
    for key, expected in SAFETY_LOCKS.items():
        assert result[key] is expected


def test_policy_loaded_from_json_not_scheduler_constants() -> None:
    policy = load_freshness_policy()
    assert policy["gates"]["runtime_snapshot"]["max_age_seconds"] == 90
    assert policy["gates"]["portfolio_snapshot"]["max_age_seconds"] == 120
    assert policy["gates"]["market_snapshot"]["max_age_seconds"] == 300
    assert policy["gates"]["learning_snapshot"]["max_age_seconds"] == 1800
    assert policy["gates"]["broker_snapshot"]["max_age_seconds"] == 300
    assert policy["gates"]["system_heartbeat"]["max_age_seconds"] == 60
    assert policy["retry_interval_seconds"] == 60
    assert policy["max_wait_seconds"] == 1800
