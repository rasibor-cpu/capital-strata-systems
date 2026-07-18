"""Phase 174 — Executive Intelligence Engine tests."""

from __future__ import annotations

import json
from pathlib import Path

from backend.executive_intelligence.actions import generate_executive_actions
from backend.executive_intelligence.assembler import ExecutiveMorningBriefAssembler
from backend.executive_intelligence.archive import MorningBriefArchiveStore
from backend.executive_intelligence.constants import BRIEF_SCHEMA_VERSION, KPI_NAMES, SAFETY_LOCKS
from backend.executive_intelligence.retrieval import MorningBriefRetrieval
from backend.executive_intelligence.scoring import score_all_kpis
from backend.executive_intelligence.service import ExecutiveIntelligenceEngine
from backend.executive_intelligence.validator import validate_brief_for_final


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
            "brokers": {"OANDA": {"health": "GREEN"}, "Coinbase": {"health": "GREEN"}},
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
            "overnight_market_summary": {"note": "stub_existing_regime_evidence"},
        },
        "opportunities": [
            {"symbol": "EUR_USD", "confidence": 0.8, "expected_return": 1.2, "strategy_class": "FX_MOMENTUM"},
            {"symbol": "BTC_USD", "confidence": 0.7, "expected_return": 2.0, "strategy_class": "CRYPTO"},
        ],
        "committee": {
            "status": "OK",
            "overall_recommendation": "APPROVE",
            "vetoes": [],
        },
        "decision_confidence": {"confidence": 0.86},
        "learning": {
            "freshness": "AGING",
            "confidence": 0.7,
            "learning_summary": {"trade_count": 12, "optimality_rate": 0.66, "top_strategy": "FX_MOMENTUM"},
        },
        "risk": {"risk_level": "MEDIUM", "stability": 0.7},
        "alerts": {"count": 0},
        "explainability": {"why": "test"},
    }


def test_assembler_builds_five_panels_and_safety_locks() -> None:
    brief = ExecutiveMorningBriefAssembler().assemble(_good_evidence(), report_date="2026-07-18")
    assert brief["schema_version"] == BRIEF_SCHEMA_VERSION
    assert brief["advisory_only"] is True
    assert brief["execution_allowed"] is False
    assert brief["live_trading_blocked"] is True
    assert brief["broker_execution_armed"] is False
    panels = brief["panels"]
    for panel_id in (
        "executive_decision",
        "operational_health",
        "market_intelligence",
        "trading_intelligence",
        "learning",
    ):
        assert panel_id in panels
        assert panels[panel_id]["panel_id"] == panel_id
    assert panels["trading_intelligence"]["execution_action"] == "NO_EXECUTION"
    assert brief["report_id"]
    assert brief["report_date"] == "2026-07-18"


def test_kpi_scoring_includes_all_frozen_kpis() -> None:
    assembler = ExecutiveMorningBriefAssembler()
    evidence = _good_evidence()
    brief = assembler.assemble(evidence)
    kpis = brief["executive_kpis"]
    for name in KPI_NAMES:
        assert name in kpis
        kpi = kpis[name]
        assert "value" in kpi
        assert "confidence" in kpi
        assert "freshness" in kpi
        assert "producer" in kpi
        assert "validation" in kpi


def test_executive_actions_prioritized_and_advisory() -> None:
    evidence = _good_evidence()
    panels = ExecutiveMorningBriefAssembler().assemble(evidence)["panels"]
    kpis = score_all_kpis(evidence, panels)
    actions = generate_executive_actions(evidence=evidence, panels=panels, kpis=kpis)
    assert 1 <= len(actions) <= 5
    assert actions[0]["rank"] == 1
    for action in actions:
        assert action["advisory_only"] is True
        assert action["execution_allowed"] is False
        assert action["type"]


def test_validation_passes_for_good_evidence() -> None:
    engine = ExecutiveIntelligenceEngine(repo_root=Path.cwd(), archive_root=Path.cwd() / "_tmp_unused")
    result = engine.generate(evidence=_good_evidence(), report_date="2026-07-18", persist=False)
    assert result["validation"]["finalization_allowed"] is True
    assert result["brief"]["schema_version"] == BRIEF_SCHEMA_VERSION


def test_validation_fails_when_runtime_stale() -> None:
    evidence = _good_evidence()
    evidence["runtime_health"]["freshness"] = "STALE"
    evidence["runtime_health"]["heartbeat_age_seconds"] = 500
    brief = ExecutiveMorningBriefAssembler().assemble(evidence, report_date="2026-07-18")
    validation = validate_brief_for_final(brief, evidence=evidence)
    assert validation["finalization_allowed"] is False
    assert "runtime_stale_or_unavailable" in validation["blockers"]


def test_validation_fails_when_market_unavailable() -> None:
    evidence = _good_evidence()
    evidence["market"] = {}
    brief = ExecutiveMorningBriefAssembler().assemble(evidence, report_date="2026-07-18")
    validation = validate_brief_for_final(brief, evidence=evidence)
    assert validation["finalization_allowed"] is False
    assert "market_panel_unavailable" in validation["blockers"]


def test_archive_immutability_and_versioning(tmp_path: Path) -> None:
    archive_root = tmp_path / "morning_briefings"
    engine = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=archive_root)
    first = engine.generate(evidence=_good_evidence(), report_date="2026-07-18", persist=True)
    assert first["archive"]["status"] == "FINAL"
    assert first["archive"]["version"] == "v001"
    first_path = Path(first["archive"]["path"])
    first_bytes = first_path.read_bytes()

    second = engine.generate(
        evidence=_good_evidence(),
        report_date="2026-07-18",
        persist=True,
        created_reason="manual_regen",
    )
    assert second["archive"]["status"] == "FINAL"
    assert second["archive"]["version"] == "v002"
    # Prior FINAL bytes unchanged
    assert first_path.read_bytes() == first_bytes
    assert first_path.exists()

    retrieval = MorningBriefRetrieval(archive_root)
    current = retrieval.by_date("2026-07-18")
    assert current is not None
    assert current["report_version"] == "v002"
    versions = retrieval.versions("2026-07-18")
    assert len(versions) == 2
    manifest = retrieval.manifest()
    assert "2026-07-18" in manifest["available_dates"]
    assert manifest["current_version_by_date"]["2026-07-18"] == "v002"
    latest = retrieval.latest()
    assert latest is not None
    assert latest["report_id"] == second["brief"]["report_id"]


def test_failed_generation_does_not_update_latest(tmp_path: Path) -> None:
    archive_root = tmp_path / "morning_briefings"
    engine = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=archive_root)
    ok = engine.generate(evidence=_good_evidence(), report_date="2026-07-17", persist=True)
    assert ok["archive"]["status"] == "FINAL"
    latest_before = (archive_root / "latest.json").read_text(encoding="utf-8")

    bad = _good_evidence()
    bad["runtime_health"]["freshness"] = "STALE"
    bad["runtime_health"]["heartbeat_age_seconds"] = 999
    failed = engine.generate(evidence=bad, report_date="2026-07-18", persist=True)
    assert failed["archive"]["status"] == "FAILED"
    assert (archive_root / "latest.json").read_text(encoding="utf-8") == latest_before


def test_historical_retrieval_previous_next_range(tmp_path: Path) -> None:
    archive_root = tmp_path / "morning_briefings"
    engine = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=archive_root)
    engine.generate(evidence=_good_evidence(), report_date="2026-07-15", persist=True)
    engine.generate(evidence=_good_evidence(), report_date="2026-07-16", persist=True)
    engine.generate(evidence=_good_evidence(), report_date="2026-07-17", persist=True)

    retrieval = MorningBriefRetrieval(archive_root)
    prev = retrieval.previous("2026-07-16")
    nxt = retrieval.next("2026-07-16")
    assert prev is not None and prev["report_date"] == "2026-07-15"
    assert nxt is not None and nxt["report_date"] == "2026-07-17"
    items = retrieval.list_summaries(date_from="2026-07-15", date_to="2026-07-16")
    assert [i["report_date"] for i in items] == ["2026-07-15", "2026-07-16"]
    stub = retrieval.compare_stub("2026-07-15", "2026-07-17")
    assert stub["stub"] is True
    assert stub["from_present"] is True
    assert stub["to_present"] is True


def test_report_integrity_fields(tmp_path: Path) -> None:
    archive_root = tmp_path / "morning_briefings"
    engine = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=archive_root)
    result = engine.generate(evidence=_good_evidence(), report_date="2026-07-18", persist=True)
    brief = result["brief"]
    assert brief["report_hash"]
    assert brief["schema_version"] == BRIEF_SCHEMA_VERSION
    assert brief["archive_version"]
    assert brief["runtime_id"] == "rt-test-001"
    assert brief["supervisor_id"] == "sup-test-001"
    assert brief["generated_at_utc"]
    assert brief["report_id"]
    for key, value in SAFETY_LOCKS.items():
        assert brief[key] is value
    # JSON + MD written
    path = Path(result["archive"]["path"])
    assert path.with_suffix(".md").exists() or (path.parent / "executive_morning_brief.md").exists()
    md_path = path.parent / "executive_morning_brief.md"
    assert "Highest Priority Today" in md_path.read_text(encoding="utf-8")
    assert "advisory" in md_path.read_text(encoding="utf-8").lower()


def test_refuse_silent_overwrite(tmp_path: Path) -> None:
    store = MorningBriefArchiveStore(tmp_path / "morning_briefings")
    engine_brief = ExecutiveMorningBriefAssembler().assemble(_good_evidence(), report_date="2026-07-18")
    validation = validate_brief_for_final(engine_brief, evidence=_good_evidence())
    assert validation["finalization_allowed"] is True
    first = store.publish(engine_brief, validation)
    # Manually create conflicting dir then ensure next version is v002 not overwrite
    second_brief = ExecutiveMorningBriefAssembler().assemble(_good_evidence(), report_date="2026-07-18")
    second = store.publish(second_brief, validate_brief_for_final(second_brief, evidence=_good_evidence()))
    assert first["version"] == "v001"
    assert second["version"] == "v002"
    assert (tmp_path / "morning_briefings" / "2026" / "07" / "2026-07-18" / "v001").is_dir()
    assert (tmp_path / "morning_briefings" / "2026" / "07" / "2026-07-18" / "v002").is_dir()


def test_sanitizer_redacts_secrets() -> None:
    from backend.executive_intelligence.sanitizer import sanitize_payload, contains_secrets

    dirty = {"api_key": "super-secret", "health": "GREEN"}
    clean = sanitize_payload(dirty)
    assert clean["api_key"] == "REDACTED"
    assert clean["health"] == "GREEN"
    has, _ = contains_secrets({"token_value": "abc"})
    assert has is True
