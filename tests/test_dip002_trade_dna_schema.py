"""DIP-002 — Trade DNA canonical schema deterministic tests."""

from __future__ import annotations

import json

import pytest

from backend.intelligence.trade_dna import (
    SCHEMA_VERSION,
    AppendOnlyDNAStore,
    BrokerFacts,
    DerivedTradeMetrics,
    EvidenceCustodyFacts,
    EvidenceGraphError,
    ExecutionFacts,
    MarketFacts,
    OutcomeFacts,
    RevisionFacts,
    TimingFacts,
    TradeDNARecord,
    TradeDNAValidationError,
    TradeIdentityFacts,
    VolatilityFacts,
    assert_not_embedded_in_facts,
    build_advisory_conclusion,
    build_evidence_graph,
    compute_content_hash,
    deserialize_trade_dna,
    serialize_trade_dna,
    validate_trade_dna,
    verify_content_hash,
)
from backend.intelligence.trade_dna.schema import MetadataFacts


def _build(**kwargs) -> TradeDNARecord:
    """Build a hashed valid DNA record with optional section replacements."""
    base = {
        "identity": TradeIdentityFacts(
            trade_id="T-100",
            dna_id="dna-100",
            instrument="EUR_USD",
            asset_class="FX",
            side="BUY",
            session_id="S-1",
        ),
        "execution": ExecutionFacts(
            entry_price=1.10,
            exit_price=1.12,
            requested_quantity=1000.0,
            filled_quantity=1000.0,
            fees=0.5,
            execution_result="CLOSED",
        ),
        "market": MarketFacts(symbol="EUR_USD", market_regime="trend"),
        "broker": BrokerFacts(broker_name="css_paper", broker_mode="paper", practice=True),
        "volatility": VolatilityFacts(atr=0.0012),
        "timing": TimingFacts(
            opened_at="2026-07-30T10:00:00+00:00",
            closed_at="2026-07-30T12:00:00+00:00",
            decision_at="2026-07-30T09:59:50+00:00",
            executed_at="2026-07-30T10:00:00+00:00",
        ),
        "outcome": OutcomeFacts(status="closed", exit_reason="take_profit", win_loss="win"),
        "evidence_custody": EvidenceCustodyFacts(
            source_event_ids=("evt-close-1",),
            writer="dip002_test",
            captured_at="2026-07-30T12:00:01+00:00",
        ),
        "revision": RevisionFacts(revision=1, created_at="2026-07-30T12:00:01+00:00"),
    }
    base.update(kwargs)
    return TradeDNARecord(**base).with_content_hash()


def test_serialization_round_trip():
    record = _build()
    text = serialize_trade_dna(record)
    restored = deserialize_trade_dna(text)
    assert restored.identity.trade_id == "T-100"
    assert restored.identity.dna_id == "dna-100"
    assert restored.schema_version == SCHEMA_VERSION
    assert restored.content_hash == record.content_hash
    assert verify_content_hash(restored.to_dict())


def test_content_hash_stable_and_sensitive():
    a = _build()
    b = _build()
    assert a.content_hash == b.content_hash
    mutated = _build(execution=ExecutionFacts(entry_price=1.11, exit_price=1.12, fees=0.5))
    assert mutated.content_hash != a.content_hash


def test_schema_version_present():
    record = _build()
    assert record.schema_version == SCHEMA_VERSION
    payload = json.loads(serialize_trade_dna(record))
    assert payload["schema_version"] == SCHEMA_VERSION


def test_append_only_revisions_never_overwrite():
    store = AppendOnlyDNAStore()
    first = store.commit(_build())
    assert store.get(first.identity.dna_id) is first

    with pytest.raises(TradeDNAValidationError) as exc:
        store.commit(_build())  # same dna_id
    assert exc.value.code == "dna_id_already_committed"

    second = store.supersede(
        first.identity.dna_id,
        _build(
            execution=ExecutionFacts(
                entry_price=1.10,
                exit_price=1.13,
                requested_quantity=1000.0,
                filled_quantity=1000.0,
                fees=0.5,
                execution_result="CLOSED",
            )
        ),
        reason="corrected_exit_price",
        created_at="2026-07-30T13:00:00+00:00",
    )
    assert second.revision.revision == 2
    assert second.revision.supersedes_dna_id == first.identity.dna_id
    assert second.identity.dna_id != first.identity.dna_id
    # Prior immutable
    assert store.get(first.identity.dna_id).execution.exit_price == 1.12
    assert store.get(second.identity.dna_id).execution.exit_price == 1.13
    chain = store.list_for_trade("T-100")
    assert len(chain) == 2


def test_invalid_missing_required_fields():
    with pytest.raises(TradeDNAValidationError) as exc:
        validate_trade_dna(
            TradeDNARecord(
                identity=TradeIdentityFacts(trade_id="", dna_id="dna-x"),
            ).with_content_hash()
        )
    assert exc.value.code == "missing_required_field"

    with pytest.raises(TradeDNAValidationError) as exc2:
        validate_trade_dna(
            TradeDNARecord(
                identity=TradeIdentityFacts(trade_id="T1", dna_id=""),
            ).with_content_hash()
        )
    assert exc2.value.code == "missing_required_field"


def test_invalid_prices():
    with pytest.raises(TradeDNAValidationError) as exc:
        validate_trade_dna(
            _build(execution=ExecutionFacts(entry_price=0.0, exit_price=1.1))
        )
    assert exc.value.code == "non_positive_price"

    with pytest.raises(TradeDNAValidationError) as exc2:
        validate_trade_dna(
            _build(execution=ExecutionFacts(entry_price=-1.0, exit_price=1.1))
        )
    assert exc2.value.code == "non_positive_price"


def test_invalid_timestamps():
    with pytest.raises(TradeDNAValidationError) as exc:
        validate_trade_dna(
            _build(
                timing=TimingFacts(
                    opened_at="2026-07-30T12:00:00+00:00",
                    closed_at="2026-07-30T10:00:00+00:00",
                )
            )
        )
    assert exc.value.code == "timestamp_order"

    with pytest.raises(TradeDNAValidationError) as exc2:
        validate_trade_dna(
            _build(timing=TimingFacts(opened_at="not-a-timestamp"))
        )
    assert exc2.value.code == "invalid_timestamp"


def test_instrument_consistency():
    with pytest.raises(TradeDNAValidationError) as exc:
        validate_trade_dna(
            _build(
                identity=TradeIdentityFacts(
                    trade_id="T-100",
                    dna_id="dna-100",
                    instrument="EUR_USD",
                ),
                market=MarketFacts(symbol="GBP_USD"),
            )
        )
    assert exc.value.code == "instrument_inconsistency"


def test_content_hash_mismatch_detected():
    record = _build()
    payload = record.to_dict()
    payload["content_hash"] = "0" * 64
    with pytest.raises(TradeDNAValidationError) as exc:
        validate_trade_dna(payload)
    assert exc.value.code == "content_hash_mismatch"


def test_derived_and_advisory_separated_from_facts():
    record = _build()
    payload = record.to_dict()
    assert_not_embedded_in_facts(payload)
    assert "profit" not in payload
    assert "mae" not in payload
    assert "advisory" not in payload

    derived = DerivedTradeMetrics(
        dna_id=record.identity.dna_id,
        trade_id=record.identity.trade_id,
        profit=20.0,
        mae=-5.0,
        mfe=25.0,
        holding_period_seconds=7200.0,
    )
    assert derived.layer == "derived"
    assert derived.dna_id == record.identity.dna_id

    with pytest.raises(ValueError):
        assert_not_embedded_in_facts({**payload, "profit": 1.0})


def test_evidence_graph_required_for_advisory():
    with pytest.raises(EvidenceGraphError):
        build_evidence_graph(trade_ids=[], confidence=0.5)

    evidence = build_evidence_graph(
        trade_ids=["T-100"],
        dna_ids=["dna-100"],
        sample_size=1,
        confidence=0.8,
        generated_at="2026-07-30T14:00:00+00:00",
    )
    assert evidence.sample_size == 1
    assert evidence.evidence_version
    assert evidence.analysis_version

    advisory = build_advisory_conclusion(
        recommendation_id="rec-1",
        kind="research_exits",
        summary="Review exit quality for EUR_USD trend cohort",
        evidence=evidence,
        confidence_score=0.8,
        opportunity_ranking=0.4,
    )
    locked = advisory.to_dict()
    assert locked["advisory_only"] is True
    assert locked["execution_allowed"] is False
    assert locked["live_trading_blocked"] is True
    assert locked["capital_movement"] is False


def test_backward_compatible_unknown_extension_fields():
    # Unknown category keys are ignored; v1 content_hash seals known fields only.
    record = _build()
    payload = record.to_dict()
    payload["market"]["future_field_v2"] = "ignored"
    restored = deserialize_trade_dna(payload)
    assert restored.market.symbol == "EUR_USD"
    assert restored.content_hash == record.content_hash
    assert "future_field_v2" not in restored.to_dict()["market"]

    # Official extension point is metadata.extensions (part of the sealed body).
    extended = _build(metadata=MetadataFacts(extensions={"research_tag": "alpha"}))
    restored2 = deserialize_trade_dna(serialize_trade_dna(extended))
    assert restored2.metadata.extensions["research_tag"] == "alpha"


def test_unsupported_schema_version_fail_closed():
    record = _build()
    payload = record.to_dict()
    payload["schema_version"] = "css.trade_dna.v999"
    payload["content_hash"] = compute_content_hash(payload)
    with pytest.raises(TradeDNAValidationError) as exc:
        deserialize_trade_dna(payload)
    assert exc.value.code == "unsupported_schema_version"
