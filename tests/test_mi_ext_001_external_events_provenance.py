"""MI-EXT-001 offline tests — advisory-only external events / provenance."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.intelligence.external_events.adapter import AdapterError, ExternalSourceAdapter, FixtureJsonAdapter
from backend.intelligence.external_events.catalogue import SourceCatalogue, SourceCatalogueError
from backend.intelligence.external_events.classify import classify_event
from backend.intelligence.external_events.constants import (
    SCHEMA_VERSION,
    TrustTier,
    UNAVAILABLE,
    UNKNOWN,
)
from backend.intelligence.external_events.decision_integration import (
    build_advisory_context,
    profit_attribution_learning_contract,
)
from backend.intelligence.external_events.dedup import deduplicate_events, lower_tier_cannot_override
from backend.intelligence.external_events.freshness import evaluate_freshness, is_actionable_freshness
from backend.intelligence.external_events.gie_bridge import to_gie_event
from backend.intelligence.external_events.hashing import canonical_json_hash, normalize_title, sha256_text
from backend.intelligence.external_events.impact import assess_impact
from backend.intelligence.external_events.models import ExternalEvent
from backend.intelligence.external_events.pipeline import ExternalEventPipeline
from backend.intelligence.external_events.safety import event_cannot_enable_execution

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "mi_ext_001"
CATALOGUE_PATH = ROOT / "docs" / "governance" / "MI_EXT_001_SOURCE_CATALOGUE.json"
CHARTER = ROOT / "docs" / "governance" / "MI_EXT_001_EXTERNAL_EVENTS_AND_SOURCE_PROVENANCE_CHARTER.md"
SCHEMA = ROOT / "docs" / "governance" / "MI_EXT_001_EVENT_SCHEMA.json"

NOW = "2026-07-30T18:30:00Z"
FIXED_NOW_DT = datetime(2026, 7, 30, 18, 30, tzinfo=timezone.utc)

WAVE1 = {
    "us_federal_reserve": "us_federal_reserve.json",
    "us_bls": "us_bls.json",
    "us_sec_edgar": "us_sec_edgar.json",
    "ca_bank_of_canada": "ca_bank_of_canada.json",
    "ng_cbn": "ng_cbn.json",
    "ng_nbs": "ng_nbs.json",
    "ng_sec": "ng_sec.json",
    "ng_ngx": "ng_ngx.json",
    "crypto_coinbase_public_md": "crypto_coinbase_public_md.json",
}


def _catalogue() -> SourceCatalogue:
    return SourceCatalogue.load(CATALOGUE_PATH)


def _event(**overrides) -> ExternalEvent:
    base = dict(
        event_id="e1",
        source_id="us_federal_reserve",
        source_name="Federal Reserve publications",
        source_tier=TrustTier.TIER_1_OFFICIAL_PRIMARY,
        source_url="https://www.federalreserve.gov/",
        publisher="Federal Reserve",
        jurisdiction="US",
        published_at="2026-07-30T18:00:00Z",
        retrieved_at=NOW,
        effective_at=UNAVAILABLE,
        title="FOMC monetary policy statement — policy rate held",
        normalized_summary="Official monetary policy statement",
        event_category="monetary_policy",
        affected_instruments=("USD", "US_RATES"),
        affected_asset_classes=("FX", "RATES"),
        raw_content_hash=sha256_text("raw"),
        normalized_content_hash=sha256_text("norm"),
        confidence=None,
        verification_status="VERIFIED",
        freshness_status="FRESH",
        licensing_usage_classification="PUBLIC_US_GOVERNMENT_WORK_INTERNAL_USE",
        advisory_only=True,
        execution_allowed=False,
    )
    base.update(overrides)
    return ExternalEvent(**base)


def _wave1_adapters(catalogue: SourceCatalogue) -> list[FixtureJsonAdapter]:
    return [
        FixtureJsonAdapter(catalogue, source_id=sid, fixture_path=FIXTURES / fname)
        for sid, fname in WAVE1.items()
    ]


def test_governance_documents_exist():
    assert CHARTER.is_file()
    assert CATALOGUE_PATH.is_file()
    assert SCHEMA.is_file()
    text = CHARTER.read_text(encoding="utf-8")
    for heading in (
        "Executive summary",
        "Existing-layer audit",
        "Non-duplication decision",
        "Source tiers",
        "Source catalogue",
        "Provenance contract",
        "Deduplication",
        "Freshness",
        "Classification",
        "Impact assessment",
        "Decision-layer integration",
        "Adapter contract",
        "Security / licensing",
        "Observability",
        "Tests",
        "Current limitations",
        "Future controlled-online validations",
        "Explicit advisory-only statement",
    ):
        assert heading in text
    assert "advisory-only" in text.casefold()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["advisory_only"]["const"] is True
    assert schema["properties"]["execution_allowed"]["const"] is False


def test_source_registration_and_trust_tier_ordering():
    cat = _catalogue()
    sources = cat.all_sources()
    assert len(sources) >= 20
    assert cat.get("us_federal_reserve")["trust_tier"] == TrustTier.TIER_1_OFFICIAL_PRIMARY
    assert cat.get("global_reuters")["trust_tier"] == TrustTier.TIER_2_VERIFIED_INSTITUTIONAL
    assert cat.get("global_fox_business")["trust_tier"] == TrustTier.TIER_3_SECONDARY_NEWS
    assert cat.get("social_unverified_example")["trust_tier"] == TrustTier.TIER_4_UNVERIFIED_SOCIAL
    assert TrustTier.rank(TrustTier.TIER_1_OFFICIAL_PRIMARY) < TrustTier.rank(
        TrustTier.TIER_2_VERIFIED_INSTITUTIONAL
    )
    assert SourceCatalogue.higher_tier_wins(
        TrustTier.TIER_1_OFFICIAL_PRIMARY, TrustTier.TIER_3_SECONDARY_NEWS
    ) == TrustTier.TIER_1_OFFICIAL_PRIMARY
    with pytest.raises(SourceCatalogueError):
        cat.require_enabled("global_reuters")
    with pytest.raises(SourceCatalogueError):
        cat.require_enabled("social_unverified_example")
    with pytest.raises(SourceCatalogueError):
        cat.get("not_a_real_source")


def test_provenance_completeness_and_canonical_hashing():
    event = _event()
    payload = event.as_dict()
    required = json.loads(SCHEMA.read_text(encoding="utf-8"))["required"]
    for key in required:
        assert key in payload
    assert payload["confidence"] == UNKNOWN
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
    assert payload["schema_version"] == SCHEMA_VERSION
    assert canonical_json_hash({"a": 1, "b": 2}) == canonical_json_hash({"b": 2, "a": 1})
    assert normalize_title("  FOMC  Decision!! ") == "fomc decision"


def test_duplicate_merging_and_corroboration():
    cat = _catalogue()
    a = _event(event_id="a", source_id="us_federal_reserve")
    b = _event(
        event_id="b",
        source_id="us_bls",
        source_name="Bureau of Labor Statistics",
        source_tier=TrustTier.TIER_1_OFFICIAL_PRIMARY,
        publisher="BLS",
    )
    merged = deduplicate_events([a, b], cat)
    assert len(merged) == 1
    m = merged[0]
    assert m.duplicate_count == 2
    assert set(m.corroborating_source_ids) | {m.primary_source_id} == {
        "us_federal_reserve",
        "us_bls",
    }
    assert m.canonical_event_hash not in {UNAVAILABLE, UNKNOWN, ""}


def test_contradiction_and_lower_tier_cannot_override_tier1():
    tier1 = _event(
        source_id="us_federal_reserve",
        source_tier=TrustTier.TIER_1_OFFICIAL_PRIMARY,
        normalized_summary="Official statement; direction unknown",
    )
    tier3 = _event(
        event_id="t3",
        source_id="global_fox_business",
        source_name="Fox Business",
        source_tier=TrustTier.TIER_3_SECONDARY_NEWS,
        normalized_summary="Secondary note claims hawkish tightening",
        verification_status="UNVERIFIED",
    )
    winner = lower_tier_cannot_override(tier1, tier3)
    assert winner.source_id == "us_federal_reserve"
    cat = _catalogue()
    merged = deduplicate_events([tier1, tier3], cat)
    assert len(merged) == 1
    assert merged[0].source_tier == TrustTier.TIER_1_OFFICIAL_PRIMARY


def test_freshness_and_staleness():
    fresh = evaluate_freshness(
        published_at="2026-07-30T18:00:00Z",
        retrieved_at=NOW,
        now_utc=FIXED_NOW_DT,
        category="monetary_policy",
    )
    assert fresh == "FRESH"
    stale = evaluate_freshness(
        published_at="2026-07-20T18:00:00Z",
        retrieved_at=NOW,
        now_utc=FIXED_NOW_DT,
        category="exchange_outage",
    )
    assert stale in {"STALE", "EXPIRED"}
    assert is_actionable_freshness("FRESH")
    assert not is_actionable_freshness("STALE")
    assert (
        evaluate_freshness(published_at=UNAVAILABLE, retrieved_at=UNAVAILABLE, now_utc=FIXED_NOW_DT)
        == UNKNOWN
    )


def test_unsupported_source_rejection_and_licensing():
    cat = _catalogue()
    adapter = FixtureJsonAdapter(
        cat, source_id="global_bloomberg", fixture_path=FIXTURES / "us_bls.json"
    )
    result = adapter.run(now_utc_iso=NOW)
    assert result.events == []
    assert result.errors
    assert result.errors[0]["code"] == "unsupported_or_disabled"


def test_malformed_payload_handling():
    cat = _catalogue()
    adapter = FixtureJsonAdapter(cat, source_id="us_bls", fixture_path=FIXTURES / "malformed.json")
    result = adapter.run(now_utc_iso=NOW)
    assert result.events == []
    assert any(e["code"] == "malformed_payload" for e in result.errors)


class _TimeoutAdapter(ExternalSourceAdapter):
    source_id = "us_federal_reserve"

    def fetch(self):
        raise AdapterError("timeout", "simulated timeout")

    def normalize(self, payload, *, source, retrieved_at, raw_hash):
        return []


class _RateLimitAdapter(ExternalSourceAdapter):
    source_id = "us_bls"

    def fetch(self):
        raise AdapterError("rate_limited", "429")

    def normalize(self, payload, *, source, retrieved_at, raw_hash):
        return []


class _CrashAdapter(ExternalSourceAdapter):
    source_id = "ng_sec"

    def run(self, *, now_utc_iso=None):  # type: ignore[override]
        raise RuntimeError("boom")

    def fetch(self):
        return {}

    def normalize(self, payload, *, source, retrieved_at, raw_hash):
        return []


def test_source_timeout_and_rate_limit_handling():
    cat = _catalogue()
    t = _TimeoutAdapter(cat).run(now_utc_iso=NOW)
    assert t.events == []
    assert any(e["code"] == "timeout" for e in t.errors)
    r = _RateLimitAdapter(cat).run(now_utc_iso=NOW)
    assert r.events == []
    assert r.health is not None
    assert r.health.rate_limit_state == "LIMITED"


def test_event_classification_and_impact_assessment():
    assert classify_event("FOMC monetary policy statement") == "monetary_policy"
    assert classify_event("Consumer Price Index inflation release") == "inflation"
    assert classify_event("NGX exchange outage matching engine") == "exchange_outage"
    actionable = assess_impact(_event(freshness_status="FRESH"))
    assert actionable.impact_direction != ""
    assert actionable.execution_allowed is False
    stale = assess_impact(_event(freshness_status="STALE", event_id="stale"))
    assert stale.impact_direction == UNKNOWN
    assert "stale_or_non_actionable_freshness" in stale.impact_evidence


def test_wave1_fixture_pipeline_replay_determinism():
    cat = _catalogue()
    pipe = ExternalEventPipeline(cat, _wave1_adapters(cat))
    a = pipe.run(now_utc_iso=NOW)
    b = pipe.run(now_utc_iso=NOW)
    assert a.advisory_only is True
    assert a.execution_allowed is False
    assert len(a.events) >= 8
    assert [e.event_id for e in a.events] == [e.event_id for e in b.events]
    assert [e.normalized_content_hash for e in a.events] == [
        e.normalized_content_hash for e in b.events
    ]
    for event in a.events:
        assert event_cannot_enable_execution(event)
        assert event.advisory_only is True
        assert event.execution_allowed is False
        assert event.schema_version == SCHEMA_VERSION
        gie = to_gie_event(event)
        assert gie.event_id == event.event_id


def test_no_event_can_directly_enable_execution():
    with pytest.raises(ValueError):
        _event(execution_allowed=True)
    with pytest.raises(ValueError):
        _event(advisory_only=False)
    ctx = build_advisory_context([_event()])
    assert ctx.execution_allowed is False
    assert ctx.may_bypass_execution_gate is False
    assert ctx.may_submit_orders is False
    assert ctx.may_modify_risk_governor is False
    assert ctx.may_modify_anti_bleed is False
    learning = profit_attribution_learning_contract()
    assert learning["auto_allocation_authority"] is False
    assert learning["execution_allowed"] is False


def test_adapter_failures_do_not_crash_pipeline():
    cat = _catalogue()
    adapters = _wave1_adapters(cat) + [_CrashAdapter(cat), _TimeoutAdapter(cat)]
    result = ExternalEventPipeline(cat, adapters).run(now_utc_iso=NOW)
    assert result.execution_allowed is False
    assert any(e["code"] == "adapter_crash_contained" for e in result.errors)
    assert len(result.events) >= 1


def test_execution_authority_spoof_blocked_in_adapter_validation():
    cat = _catalogue()

    class SpoofAdapter(FixtureJsonAdapter):
        def normalize(self, payload, *, source, retrieved_at, raw_hash):
            events = super().normalize(
                payload, source=source, retrieved_at=retrieved_at, raw_hash=raw_hash
            )
            bad = []
            for ev in events:
                bad.append(
                    ExternalEvent.from_mapping(
                        {
                            **ev.as_dict(),
                            "source_id": "us_bls",
                            "confidence": UNKNOWN,
                        }
                    )
                )
            return bad

    adapter = SpoofAdapter(
        cat,
        source_id="us_federal_reserve",
        fixture_path=FIXTURES / "us_federal_reserve.json",
    )
    result = adapter.run(now_utc_iso=NOW)
    assert result.events == []
    assert any(e["code"] == "source_spoof" for e in result.errors)
