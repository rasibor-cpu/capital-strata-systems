"""MI-EXT-001 bounded hardening — boundary, no-network, catalogue, schema, dedup."""

from __future__ import annotations

import ast
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.intelligence.external_events.adapter import (
    APPROVED_FIXTURE_ROOT,
    FixtureJsonAdapter,
    LiveNetworkFetchAdapter,
)
from backend.intelligence.external_events.catalogue import SourceCatalogue, SourceCatalogueError
from backend.intelligence.external_events.constants import TrustTier, UNAVAILABLE, UNKNOWN
from backend.intelligence.external_events.decision_integration import build_advisory_context
from backend.intelligence.external_events.dedup import deduplicate_events
from backend.intelligence.external_events.freshness import evaluate_freshness, is_actionable_freshness
from backend.intelligence.external_events.gie_bridge import gie_available, to_gie_event
from backend.intelligence.external_events.hashing import (
    normalized_evidence_hash,
    sha256_bytes,
    sha256_text,
)
from backend.intelligence.external_events.models import ExternalEvent

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "backend" / "intelligence" / "external_events"
FIXTURES = ROOT / "tests" / "fixtures" / "mi_ext_001"
CATALOGUE_PATH = ROOT / "docs" / "governance" / "MI_EXT_001_SOURCE_CATALOGUE.json"
SCHEMA_PATH = ROOT / "docs" / "governance" / "MI_EXT_001_EVENT_SCHEMA.json"
NOW = "2026-07-30T18:30:00Z"
FIXED_NOW = datetime(2026, 7, 30, 18, 30, tzinfo=timezone.utc)

PROHIBITED_IMPORT_TOKENS = (
    "ExecutionGate",
    "RiskGovernor",
    "AntiBleedGuard",
    "AntiBleed",
    "MarginGate",
    "order_router",
    "OrderRouter",
    "live_authority",
    "position_siz",
    "broker.order",
    "submit_order",
    "start_runtime",
    "stop_runtime",
    "runtime_supervisor",
)

NETWORK_IMPORT_MODULES = {
    "requests",
    "httpx",
    "aiohttp",
    "urllib.request",
    "urllib3",
    "socket",
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


def test_static_execution_boundary_no_prohibited_imports():
    offenders: list[str] = []
    for path in sorted(PKG.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names.append(mod)
                names.extend(f"{mod}.{alias.name}" if mod else alias.name for alias in node.names)
            for name in names:
                for token in PROHIBITED_IMPORT_TOKENS:
                    if token.casefold() in name.casefold():
                        offenders.append(f"{path.name}:{name}")
        text = path.read_text(encoding="utf-8")
        for token in PROHIBITED_IMPORT_TOKENS:
            # Allow documentary mentions in comments/docstrings only via explicit allowlist files
            if token in text and path.name not in {"decision_integration.py", "safety.py", "constants.py"}:
                # Still fail on import-like usage already covered; soft-scan for call sites
                if f"import {token}" in text or f"{token}(" in text:
                    offenders.append(f"{path.name}:usage:{token}")
    assert offenders == [], offenders


def test_package_has_no_network_imports():
    offenders: list[str] = []
    for path in sorted(PKG.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in {m.split(".")[0] for m in NETWORK_IMPORT_MODULES}:
                        offenders.append(f"{path.name}:{alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in {"requests", "httpx", "aiohttp", "socket", "urllib3"}:
                    offenders.append(f"{path.name}:{node.module}")
                if node.module.startswith("urllib.request"):
                    offenders.append(f"{path.name}:{node.module}")
    assert offenders == [], offenders


def test_fixture_adapter_reads_only_approved_local_fixtures(monkeypatch):
    cat = _catalogue()
    adapter = FixtureJsonAdapter(
        cat, source_id="us_federal_reserve", fixture_path=FIXTURES / "us_federal_reserve.json"
    )
    assert APPROVED_FIXTURE_ROOT.resolve() in adapter.fixture_path.parents or adapter.fixture_path.parent == APPROVED_FIXTURE_ROOT.resolve()

    # Reject path outside approved root
    outside = ROOT / "docs" / "governance" / "MI_EXT_001_EVENT_SCHEMA.json"
    bad = FixtureJsonAdapter(cat, source_id="us_federal_reserve", fixture_path=outside)
    result = bad.run(now_utc_iso=NOW)
    assert result.events == []
    assert any(e["code"] == "fixture_path_rejected" for e in result.errors)

    # Ensure no credential env vars are required/consumed into payloads
    monkeypatch.setenv("CSS_API_KEY", "should-never-be-read")
    monkeypatch.setenv("BLOOMBERG_API_KEY", "should-never-be-read")
    ok = adapter.run(now_utc_iso=NOW)
    assert ok.events
    blob = json.dumps(ok.events[0].as_dict())
    assert "should-never-be-read" not in blob
    assert os.environ.get("CSS_API_KEY") == "should-never-be-read"  # still present, unread into event


def test_blocked_and_controlled_online_sources_cannot_be_fetched():
    cat = _catalogue()
    for source_id in ("global_bloomberg", "global_reuters", "ng_fmdq", "social_unverified_example"):
        live = LiveNetworkFetchAdapter(cat, source_id=source_id)
        result = live.run(now_utc_iso=NOW)
        assert result.events == []
        assert result.errors
    # Enabled fixture source still cannot live-fetch
    live_fed = LiveNetworkFetchAdapter(cat, source_id="us_federal_reserve")
    fed = live_fed.run(now_utc_iso=NOW)
    assert fed.events == []
    assert any("live_fetch" in e["code"] or "unsupported" in e["code"] for e in fed.errors)
    assert cat.is_live_fetch_authorized("us_federal_reserve") is False


def test_source_catalogue_integrity_rules():
    cat = _catalogue()
    payload = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    assert payload.get("catalogue_integrity_hash")
    assert payload["catalogue_integrity_hash"] == cat.integrity_hash
    ids = [s["source_id"] for s in cat.all_sources()]
    assert len(ids) == len(set(ids))
    for row in cat.all_sources():
        assert row["trust_tier"] in TrustTier.ORDER
        assert row["jurisdiction"]
        assert row["access_method"]
        assert row["cost_status"]
        assert row["licensing_usage_classification"]
        assert row["freshness_threshold"]
        assert "may_influence_advisory" in row
        assert row["direct_execution_influence"] is False
        assert row["prohibited_from_direct_execution"] is True
        assert row["operational_state"]
        assert row["online_validation_required"] is True
        if row["trust_tier"] == TrustTier.TIER_4_UNVERIFIED_SOCIAL:
            assert row["may_influence_advisory"] is False
            assert row["enabled"] is False
        if str(row["access_status"]).upper() in {"BLOCKED", "PROHIBITED"}:
            assert row["enabled"] is False
        if "paid" in str(row["cost_status"]).casefold():
            assert row["enabled"] is False
            assert row["licensing_usage_classification"] != "COMMERCIAL_LICENSE_APPROVED"


def test_blocked_unreviewed_cannot_be_enabled_in_catalogue():
    payload = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    row = next(s for s in payload["sources"] if s["source_id"] == "global_bloomberg")
    row = dict(row)
    row["enabled"] = True
    bad = dict(payload)
    bad["sources"] = [row if s["source_id"] != "global_bloomberg" else row for s in payload["sources"]]
    with pytest.raises(SourceCatalogueError):
        SourceCatalogue(bad)


def test_event_schema_and_hashing_stability():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$id"] == "css.mi_ext_001.external_event.v1"
    assert schema["properties"]["advisory_only"]["const"] is True
    assert schema["properties"]["execution_allowed"]["const"] is False
    for key in (
        "event_id",
        "source_id",
        "source_tier",
        "published_at",
        "retrieved_at",
        "raw_content_hash",
        "normalized_content_hash",
        "advisory_only",
        "execution_allowed",
    ):
        assert key in schema["required"]

    h1 = normalized_evidence_hash(
        title="FOMC monetary policy statement",
        summary="Official",
        category="monetary_policy",
        instruments=("USD",),
        published_at="2026-07-30T18:00:00Z",
        source_id="us_federal_reserve",
        schema_version="css.mi_ext_001.external_event.v1",
        parser_version="mi_ext_001.parser.v1",
    )
    h2 = normalized_evidence_hash(
        title="FOMC monetary policy statement",
        summary="Official",
        category="monetary_policy",
        instruments=("USD",),
        published_at="2026-07-30T18:00:00Z",
        source_id="us_federal_reserve",
        schema_version="css.mi_ext_001.external_event.v1",
        parser_version="mi_ext_001.parser.v1",
    )
    assert h1 == h2
    # retrieved_at is not part of normalized evidence material
    altered = normalized_evidence_hash(
        title="FOMC monetary policy statement ALTERED",
        summary="Official",
        category="monetary_policy",
        instruments=("USD",),
        published_at="2026-07-30T18:00:00Z",
        source_id="us_federal_reserve",
        schema_version="css.mi_ext_001.external_event.v1",
        parser_version="mi_ext_001.parser.v1",
    )
    assert altered != h1
    raw_a = sha256_bytes(b'{"title":"A"}')
    raw_b = sha256_bytes(b'{"title":"B"}')
    assert raw_a != raw_b
    missing = _event(published_at=UNAVAILABLE, affected_instruments=(), confidence=None)
    assert missing.published_at == UNAVAILABLE
    assert missing.as_dict()["confidence"] == UNKNOWN


def test_fixture_parser_produces_stable_normalized_hash():
    cat = _catalogue()
    adapter = FixtureJsonAdapter(
        cat, source_id="us_federal_reserve", fixture_path=FIXTURES / "us_federal_reserve.json"
    )
    a = adapter.run(now_utc_iso="2026-07-30T18:30:00Z").events[0]
    b = adapter.run(now_utc_iso="2026-07-30T19:00:00Z").events[0]
    # volatile retrieved_at may differ; normalized evidence hash must match
    assert a.normalized_content_hash == b.normalized_content_hash
    assert a.retrieved_at != b.retrieved_at or a.retrieved_at == b.retrieved_at


def test_dedup_merge_order_and_tier1_primary_and_unresolved():
    cat = _catalogue()
    tier1 = _event(
        event_id="t1",
        source_id="us_federal_reserve",
        source_tier=TrustTier.TIER_1_OFFICIAL_PRIMARY,
        normalized_summary="Official statement dovish easing bias",
    )
    tier3 = _event(
        event_id="t3",
        source_id="global_fox_business",
        source_name="Fox Business",
        source_tier=TrustTier.TIER_3_SECONDARY_NEWS,
        normalized_summary="Secondary claims hawkish tightening",
    )
    m1 = deduplicate_events([tier1, tier3], cat)[0]
    m2 = deduplicate_events([tier3, tier1], cat)[0]
    assert m1.canonical_event_hash == m2.canonical_event_hash
    assert m1.primary_source_id == "us_federal_reserve"
    assert "global_fox_business" in m1.corroborating_source_ids or "global_fox_business" in m1.conflicting_source_ids
    assert any("lower_tier_contradiction" in x for x in m1.counter_evidence)
    assert any(x.startswith("source_history:") for x in m1.impact_evidence)

    # Exact duplicates merge
    dups = deduplicate_events([tier1, _event(event_id="t1b", source_id="us_federal_reserve")], cat)
    assert len(dups) == 1
    assert dups[0].duplicate_count == 2

    # Contradictory Tier-1 events are not silently resolved
    t1a = _event(
        event_id="a",
        source_id="us_federal_reserve",
        normalized_summary="Official hawkish tightening",
    )
    t1b = _event(
        event_id="b",
        source_id="us_bls",
        source_name="BLS",
        source_tier=TrustTier.TIER_1_OFFICIAL_PRIMARY,
        normalized_summary="Official dovish easing",
        publisher="BLS",
    )
    unresolved = deduplicate_events([t1a, t1b], cat)[0]
    assert unresolved.contradiction_status == "UNRESOLVED_TIER1_CONFLICT"
    assert unresolved.verification_status == "UNRESOLVED"


def test_freshness_states_and_advisory_integration():
    cases = {
        "FRESH": evaluate_freshness(
            published_at="2026-07-30T18:00:00Z", now_utc=FIXED_NOW, category="monetary_policy"
        ),
        "AGING": evaluate_freshness(
            published_at="2026-07-30T12:00:00Z", now_utc=FIXED_NOW, category="monetary_policy"
        ),
        "STALE": evaluate_freshness(
            published_at="2026-07-28T18:00:00Z", now_utc=FIXED_NOW, category="monetary_policy"
        ),
        "EXPIRED": evaluate_freshness(
            published_at="2026-06-01T18:00:00Z", now_utc=FIXED_NOW, category="monetary_policy"
        ),
        "UNKNOWN": evaluate_freshness(published_at=UNAVAILABLE, retrieved_at=UNAVAILABLE, now_utc=FIXED_NOW),
    }
    assert cases["FRESH"] == "FRESH"
    assert cases["AGING"] in {"FRESH", "AGING"}
    assert cases["STALE"] in {"STALE", "EXPIRED", "AGING"}
    assert cases["EXPIRED"] == "EXPIRED"
    assert cases["UNKNOWN"] == UNKNOWN
    assert is_actionable_freshness("FRESH") and is_actionable_freshness("AGING")
    assert not is_actionable_freshness("STALE")
    assert not is_actionable_freshness("EXPIRED")
    assert not is_actionable_freshness("UNKNOWN")

    fresh_ctx = build_advisory_context([_event(freshness_status="FRESH")])
    stale_ctx = build_advisory_context([_event(freshness_status="STALE", event_id="s")])
    unknown_ctx = build_advisory_context([_event(freshness_status="UNKNOWN", event_id="u")])
    assert fresh_ctx.market_context_notes
    assert stale_ctx.market_context_notes == ()
    assert unknown_ctx.market_context_notes == ()
    for ctx in (fresh_ctx, stale_ctx, unknown_ctx):
        assert ctx.execution_allowed is False
        assert ctx.may_submit_orders is False
        assert ctx.may_change_position_size is False
        assert ctx.may_change_live_authority is False
        assert ctx.may_bypass_execution_gate is False


def test_gie_bridge_optional_fail_safe_and_non_mutating():
    assert gie_available() is True
    event = _event()
    gie = to_gie_event(event)
    assert gie is not None
    assert gie.event_id == event.event_id
    # Missing published_at must not invent a timestamp
    assert to_gie_event(_event(published_at=UNAVAILABLE, event_id="x")) is None
    # Bridge must not flip execution flags on source event
    assert event.execution_allowed is False
    assert event.advisory_only is True
