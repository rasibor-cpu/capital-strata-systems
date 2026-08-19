"""MI-EXT-001 R2 recovery tests — TAI overlay, isolation, data quality, anti-lookahead."""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timezone
from typing import Any, Mapping

import pytest

from backend.intelligence.external_events.constants import TrustTier, UNAVAILABLE, UNKNOWN
from backend.intelligence.external_events.decision_integration import (
    build_external_event_intelligence,
    coerce_external_events,
)
from backend.intelligence.external_events.dedup import deduplicate_events
from backend.intelligence.external_events.freshness import evaluate_freshness, is_actionable_freshness
from backend.intelligence.external_events.hashing import sha256_text
from backend.intelligence.external_events.models import ExternalEvent
from backend.intelligence.external_events.catalogue import SourceCatalogue
from backend.trading.autonomous_opportunity_intelligence_engine import (
    AutonomousOpportunityIntelligenceEngine,
)
from backend.trading import autonomous_opportunity_intelligence_engine as aoi_module
from backend.trading.opportunity_ranking_engine import OpportunityRankingEngine
from backend.trading import opportunity_ranking_engine as ranking_module
from dashboard.mission_control.opportunity_ranking import build_opportunity_ranking
from dashboard.mission_control.safety import validate_no_execution_controls
from tests.test_tai002_technical_intelligence_integration import (
    FORBIDDEN_IMPORT_FRAGMENTS,
    _DenyGate,
    _StubOrchestrator,
    _StubTAI,
    _assert_advisory_safety,
    _candidate,
    _candles,
    _decision,
    _instrument,
    _tai_payload,
)

NOW = datetime(2026, 7, 30, 18, 30, tzinfo=timezone.utc)


def _event(**overrides: Any) -> ExternalEvent:
    base = dict(
        event_id="e1",
        source_id="us_federal_reserve",
        source_name="Federal Reserve publications",
        source_tier=TrustTier.TIER_1_OFFICIAL_PRIMARY,
        source_url="https://www.federalreserve.gov/",
        publisher="Federal Reserve",
        jurisdiction="US",
        published_at="2026-07-30T18:00:00Z",
        retrieved_at="2026-07-30T18:30:00Z",
        effective_at=UNAVAILABLE,
        title="FOMC monetary policy statement — policy rate held",
        normalized_summary="Official monetary policy statement",
        event_category="monetary_policy",
        affected_instruments=("BTCUSD", "USD"),
        affected_asset_classes=("CRYPTO", "FX"),
        raw_content_hash=sha256_text("raw"),
        normalized_content_hash=sha256_text("norm"),
        confidence=0.8,
        verification_status="VERIFIED",
        freshness_status="FRESH",
        licensing_usage_classification="PUBLIC_US_GOVERNMENT_WORK_INTERNAL_USE",
        advisory_only=True,
        execution_allowed=False,
        duplicate_count=1,
    )
    base.update(overrides)
    return ExternalEvent(**base)


class _EventUniverse:
    def __init__(self, events: list[Mapping[str, Any]] | None = None) -> None:
        instrument = _instrument()
        if events is not None:
            instrument["external_events"] = list(events)
        self.instrument = instrument

    def all_instruments(self) -> list[dict[str, Any]]:
        return [dict(self.instrument)]


def _analyze_with_events(events: list[Any], *, evaluation_time: str | None = None) -> dict[str, Any]:
    candidate = _candidate()
    candidate["external_events"] = [e.as_dict() if isinstance(e, ExternalEvent) else e for e in events]
    if evaluation_time is not None:
        candidate["evaluation_time"] = evaluation_time
        candidate["market_snapshot"]["timestamp"] = evaluation_time
    engine = AutonomousOpportunityIntelligenceEngine(
        technical_intelligence_engine=_StubTAI(_tai_payload(directional_score=0.9, confidence=0.9))
    )
    return engine.analyze(
        instrument=_instrument(),
        candidate=candidate,
        decision=_decision(),
    )


def test_valid_fresh_event_is_advisory_only() -> None:
    overlay = build_external_event_intelligence([_event()], instrument="BTCUSD", evaluation_time=NOW)
    assert overlay["advisory_only"] is True
    assert overlay["execution_allowed"] is False
    assert overlay["direct_execution_influence"] is False
    assert overlay["live_network_ingestion"] is False
    assert overlay["external_event_score"] == pytest.approx(0.8)
    assert overlay["event_freshness"] == "FRESH"
    assert overlay["event_provenance_count"] == 1


def test_stale_event_loses_directional_influence() -> None:
    overlay = build_external_event_intelligence(
        [_event(freshness_status="STALE", confidence=0.99)],
        instrument="BTCUSD",
        evaluation_time=NOW,
    )
    assert overlay["external_event_score"] == 0.0
    assert overlay["event_confidence"] == 0.0
    assert overlay["event_freshness"] == "STALE"
    assert "non_actionable_freshness" in overlay["event_reasons"]


def test_malformed_event_is_dropped_fail_closed() -> None:
    events = coerce_external_events([{"title": "broken"}, _event().as_dict()])
    assert len(events) == 1
    overlay = build_external_event_intelligence(events, instrument="BTCUSD", evaluation_time=NOW)
    assert overlay["event_provenance_count"] == 1


def test_missing_timestamp_is_not_actionable() -> None:
    status = evaluate_freshness(published_at=UNAVAILABLE, retrieved_at=UNAVAILABLE, now_utc=NOW)
    assert status == "UNKNOWN"
    assert is_actionable_freshness(status) is False
    overlay = build_external_event_intelligence(
        [_event(published_at=UNAVAILABLE, freshness_status="UNKNOWN", confidence=0.99)],
        evaluation_time=NOW,
    )
    assert overlay["external_event_score"] == 0.0


def test_future_timestamp_is_anti_lookahead() -> None:
    status = evaluate_freshness(published_at="2026-07-30T19:00:00Z", now_utc=NOW, category="monetary_policy")
    assert status == "FUTURE"
    overlay = build_external_event_intelligence(
        [_event(published_at="2026-07-30T19:00:00Z", freshness_status="FRESH", confidence=0.99)],
        instrument="BTCUSD",
        evaluation_time=NOW,
    )
    assert overlay["external_event_score"] == 0.0
    assert overlay["event_lookahead_excluded_count"] == 1
    assert overlay["event_freshness"] == "FUTURE"


def test_duplicate_events_do_not_amplify_conviction() -> None:
    first = _event(event_id="dup-1", confidence=0.7)
    second = _event(event_id="dup-2", confidence=0.7, retrieved_at="2026-07-30T18:31:00Z")
    overlay = build_external_event_intelligence([first, second], instrument="BTCUSD", evaluation_time=NOW)
    assert overlay["external_event_score"] == pytest.approx(0.7)
    assert overlay["external_event_score"] <= 0.7


def test_same_event_from_multiple_sources_does_not_sum_confidence() -> None:
    catalogue = SourceCatalogue.load()
    left = _event(event_id="a", source_id="us_federal_reserve", confidence=0.6)
    right = _event(
        event_id="b",
        source_id="us_bls",
        source_tier=TrustTier.TIER_1_OFFICIAL_PRIMARY,
        confidence=0.5,
    )
    merged = deduplicate_events([left, right], catalogue)
    overlay = build_external_event_intelligence(merged, instrument="BTCUSD", evaluation_time=NOW)
    assert overlay["external_event_score"] <= max(0.6, 0.5)
    assert overlay["event_provenance_count"] >= 1
    assert overlay["event_duplicate_count"] >= 1


def test_conflicting_events_fail_closed() -> None:
    overlay = build_external_event_intelligence(
        [_event(contradiction_status="CONFLICT", confidence=0.99, freshness_status="FRESH")],
        instrument="BTCUSD",
        evaluation_time=NOW,
    )
    assert overlay["external_event_score"] == 0.0
    assert overlay["event_conflict_state"] == "CONFLICT"


def test_low_confidence_source_cannot_influence_overlay() -> None:
    overlay = build_external_event_intelligence(
        [
            _event(
                source_id="global_yahoo_finance",
                source_tier=TrustTier.TIER_4_UNVERIFIED_SOCIAL,
                confidence=0.99,
            )
        ],
        evaluation_time=NOW,
    )
    assert overlay["external_event_score"] == 0.0
    assert "low_confidence_source_excluded" in overlay["event_reasons"]


def test_unsupported_event_category_does_not_invent_conviction() -> None:
    overlay = build_external_event_intelligence(
        [_event(event_category="unknown", confidence=None, freshness_status="FRESH")],
        evaluation_time=NOW,
    )
    assert overlay["external_event_score"] == 0.0


def test_empty_event_set_is_zero() -> None:
    overlay = build_external_event_intelligence([], evaluation_time=NOW)
    assert overlay["external_event_score"] == 0.0
    assert overlay["event_provenance_count"] == 0
    assert "empty_event_set" in overlay["event_reasons"]


def test_deterministic_rerun_and_hashing_stability() -> None:
    events = [_event()]
    first = build_external_event_intelligence(events, instrument="BTCUSD", evaluation_time=NOW)
    second = build_external_event_intelligence(events, instrument="BTCUSD", evaluation_time=NOW)
    assert first == second
    assert _event().normalized_content_hash == _event().normalized_content_hash


def test_ttl_boundary_behavior() -> None:
    fresh = evaluate_freshness(published_at="2026-07-30T18:00:00Z", now_utc=NOW, category="monetary_policy")
    aging = evaluate_freshness(published_at="2026-07-30T12:00:00Z", now_utc=NOW, category="monetary_policy")
    stale = evaluate_freshness(published_at="2026-07-28T18:00:00Z", now_utc=NOW, category="monetary_policy")
    assert fresh == "FRESH"
    assert aging == "AGING"
    assert stale == "STALE"
    assert is_actionable_freshness(fresh) is True
    assert is_actionable_freshness(stale) is False


def test_provenance_completeness_fields_present() -> None:
    event = _event()
    payload = event.as_dict()
    for key in (
        "source_id",
        "source_tier",
        "published_at",
        "retrieved_at",
        "event_id",
        "raw_content_hash",
        "normalized_content_hash",
        "canonical_event_hash",
        "advisory_only",
        "execution_allowed",
    ):
        assert key in payload
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False


def test_tai_overlay_attaches_without_changing_weighted_rank_from_events() -> None:
    none = _analyze_with_events([])
    favorable = _analyze_with_events([_event(confidence=0.95)])
    none_score = none["ranking_v2"]["weighted_score"]
    fav_score = favorable["ranking_v2"]["weighted_score"]
    assert none_score == pytest.approx(fav_score)
    overlay = favorable["external_event_intelligence"]
    _assert_advisory_safety(overlay)
    assert overlay["external_event_score"] == pytest.approx(0.95)
    assert overlay["execution_allowed"] is False


def test_stale_or_future_events_cannot_raise_rank() -> None:
    baseline = _analyze_with_events([])
    stale = _analyze_with_events([_event(freshness_status="STALE", confidence=0.99)])
    future = _analyze_with_events(
        [_event(published_at="2026-07-31T00:00:00Z", freshness_status="FRESH", confidence=0.99)],
        evaluation_time="2026-07-30T18:30:00+00:00",
    )
    assert stale["ranking_v2"]["weighted_score"] == pytest.approx(baseline["ranking_v2"]["weighted_score"])
    assert future["ranking_v2"]["weighted_score"] == pytest.approx(baseline["ranking_v2"]["weighted_score"])
    assert stale["external_event_intelligence"]["external_event_score"] == 0.0
    assert future["external_event_intelligence"]["external_event_score"] == 0.0


def test_anti_lookahead_integration_at_evaluation_time_t() -> None:
    evaluation_time = "2026-07-30T18:30:00+00:00"
    past_only = _analyze_with_events(
        [_event(published_at="2026-07-30T18:00:00Z", confidence=0.8)],
        evaluation_time=evaluation_time,
    )
    with_future = _analyze_with_events(
        [
            _event(event_id="past", published_at="2026-07-30T18:00:00Z", confidence=0.8),
            _event(event_id="future", published_at="2026-07-30T19:00:00Z", confidence=0.99),
        ],
        evaluation_time=evaluation_time,
    )
    assert past_only["external_event_intelligence"]["external_event_score"] == pytest.approx(
        with_future["external_event_intelligence"]["external_event_score"]
    )
    assert past_only["ranking_v2"]["weighted_score"] == pytest.approx(with_future["ranking_v2"]["weighted_score"])
    assert with_future["external_event_intelligence"]["event_lookahead_excluded_count"] == 1


def test_favorable_mi_ext_and_tai_cannot_override_unified_trade_gate_denial() -> None:
    gate = _DenyGate()
    ranking_engine = OpportunityRankingEngine(
        instrument_universe=_EventUniverse([_event(confidence=0.99).as_dict()]),
        intelligence_orchestrator=_StubOrchestrator(_decision(entry_decision="ALLOW", decision="ALLOW", confidence=0.99)),
        unified_trade_gate=gate,
        autonomous_intelligence_engine=AutonomousOpportunityIntelligenceEngine(
            technical_intelligence_engine=_StubTAI(_tai_payload(directional_score=1.0, confidence=1.0))
        ),
    )
    ranked = ranking_engine.rank_all()
    assert gate.calls == 1
    assert ranked[0]["action"] == "BLOCK"
    assert ranked[0]["diagnostics"]["gate"]["approved"] is False
    overlay = ranked[0]["diagnostics"]["intelligence"]["external_event_intelligence"]
    _assert_advisory_safety(overlay)
    assert overlay["execution_allowed"] is False
    assert "order" not in ranked[0]


def test_mission_control_exposes_mi_ext_without_execution_authority() -> None:
    projected = build_opportunity_ranking(
        {
            "runtime": {"source": "test", "runtime_status": "ONLINE"},
            "institutional_sources": {
                "opportunity_intelligence": {
                    "opportunities": [
                        {
                            "symbol": "BTC-USD",
                            "external_event_intelligence": build_external_event_intelligence(
                                [_event()],
                                instrument="BTCUSD",
                                evaluation_time=NOW,
                            ),
                        }
                    ]
                }
            },
        }
    )
    observed = projected["opportunities"][0]["external_event_intelligence"]
    _assert_advisory_safety(observed)
    assert observed["execution_authority"] == "NONE"
    assert observed["live_network_ingestion"] is False
    ok, reasons = validate_no_execution_controls(observed)
    assert ok, reasons


def test_fixture_only_catalogue_refuses_live_network_ingestion() -> None:
    from backend.intelligence.external_events.adapter import FixtureJsonAdapter, LiveNetworkFetchAdapter
    from backend.intelligence.external_events.pipeline import ExternalEventPipeline
    from pathlib import Path

    catalogue = SourceCatalogue.load()
    assert catalogue._payload["live_network_ingestion"] is False
    enabled = [row for row in catalogue.all_sources() if row["enabled"]]
    assert enabled
    assert all(str(row["access_status"]).upper() == "FIXTURE_ONLY" for row in enabled)
    assert catalogue.is_live_fetch_authorized("us_federal_reserve") is False

    live = LiveNetworkFetchAdapter(catalogue, source_id="us_federal_reserve")
    live_result = live.run(now_utc_iso="2026-07-30T18:30:00Z")
    assert live_result.events == []
    assert live_result.errors

    fixture_root = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "mi_ext_001"
    fixture = FixtureJsonAdapter(
        catalogue,
        source_id="us_federal_reserve",
        fixture_path=fixture_root / "us_federal_reserve.json",
    )
    fixture_result = fixture.run(now_utc_iso="2026-07-30T18:30:00Z")
    assert fixture_result.events
    assert all(event.advisory_only and not event.execution_allowed for event in fixture_result.events)

    pipeline = ExternalEventPipeline(catalogue, [fixture])
    piped = pipeline.run(now_utc_iso="2026-07-30T18:30:00Z")
    assert piped.advisory_only is True
    assert piped.execution_allowed is False
    assert piped.events


def test_repeated_ingestion_cannot_increase_conviction() -> None:
    event = _event(confidence=0.72)
    once = build_external_event_intelligence([event], instrument="BTCUSD", evaluation_time=NOW)
    repeated = build_external_event_intelligence(
        [event, _event(event_id="repeat-2", confidence=0.72), _event(event_id="repeat-3", confidence=0.72)],
        instrument="BTCUSD",
        evaluation_time=NOW,
    )
    catalogue = SourceCatalogue.load()
    merged = deduplicate_events(
        [event, _event(event_id="repeat-2", confidence=0.72), _event(event_id="repeat-3", confidence=0.72)],
        catalogue,
    )
    after_dedup = build_external_event_intelligence(merged, instrument="BTCUSD", evaluation_time=NOW)
    assert once["external_event_score"] == pytest.approx(0.72)
    assert repeated["external_event_score"] == pytest.approx(once["external_event_score"])
    assert after_dedup["external_event_score"] == pytest.approx(once["external_event_score"])
    assert after_dedup["event_duplicate_count"] >= 3
    assert after_dedup["external_event_score"] <= 0.72


def test_package_and_seams_have_no_execution_or_broker_capability() -> None:
    from backend.intelligence import external_events as ext_pkg
    from backend.intelligence.external_events import decision_integration as overlay_module

    for module in (ext_pkg, overlay_module, aoi_module):
        source = inspect.getsource(module) if module is not ext_pkg else inspect.getsource(overlay_module)
        for token in ("place_order(", "submit_order(", "cancel_order(", "approve_trade(", "authorize_execution("):
            assert token not in source
        tree = ast.parse(source)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        joined = " ".join(imported)
        for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
            assert fragment not in joined

    ranking_source = inspect.getsource(ranking_module)
    assert "CSSUnifiedTradeGate" in ranking_source
    for token in ("AntiBleedGuard", "CapitalAllocationGovernor", "KillSwitch", "place_order", "submit_order"):
        assert token not in ranking_source
