"""DIP-003 — Capture + Decision Analytics deterministic tests."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.intelligence.decision_analytics import DecisionAnalyticsEngine
from backend.intelligence.trade_dna import (
    SCHEMA_VERSION,
    CanonicalCloseEventError,
    DurableCaptureStore,
    TradeDNACaptureService,
    TradeDNAValidationError,
    build_canonical_close_event,
    capture_completed_trade,
    project_trade_dna_from_close_event,
    serialize_canonical_close_event,
    deserialize_canonical_close_event,
    serialize_trade_dna,
    deserialize_trade_dna,
)
from backend.execution.paper_execution_economics import build_paper_execution_economics
from engine.execution.execution_gate import ExecutionGate


def _event(**overrides):
    base = dict(
        trade_id="T-DIP3-1",
        symbol="EUR_USD",
        side="buy",
        broker_name="css_paper",
        broker_mode="paper",
        entry_price=1.10,
        exit_price=1.12,
        quantity=1000.0,
        filled_quantity=1000.0,
        opened_at="2026-07-30T10:00:00+00:00",
        closed_at="2026-07-30T12:00:00+00:00",
        realized_pnl=20.0,
        session_id="S1",
        order_type="market",
        strategy_id="alpha",
        market_regime="trend",
        exit_reason="take_profit",
        scaled_notional=1000.0,
        requested_notional=1000.0,
        fill_kind="paper_synthetic_full_request_qty",
        gate_final="ALLOW",
        gate_reason="approved",
        source_event_ids=("trade:T-DIP3-1",),
    )
    base.update(overrides)
    return build_canonical_close_event(**base)


def test_canonical_close_event_round_trip_and_hash():
    event = _event()
    text = serialize_canonical_close_event(event)
    restored = deserialize_canonical_close_event(text)
    assert restored.event_id == event.event_id
    assert restored.content_hash == event.content_hash
    again = _event()
    assert again.content_hash == event.content_hash


def test_canonical_close_rejects_non_positive_prices():
    with pytest.raises(CanonicalCloseEventError):
        _event(entry_price=0)
    with pytest.raises(CanonicalCloseEventError):
        _event(exit_price=-1)


def test_trade_dna_generation_deterministic():
    event = _event()
    a = project_trade_dna_from_close_event(event)
    b = project_trade_dna_from_close_event(event)
    assert a.content_hash == b.content_hash
    assert a.identity.dna_id == b.identity.dna_id
    assert a.schema_version == SCHEMA_VERSION
    assert "profit" not in a.to_dict()


def test_capture_idempotent_and_duplicate_safe(tmp_path: Path):
    store = DurableCaptureStore(tmp_path / "capture")
    service = TradeDNACaptureService(store)
    event = _event()
    first = service.capture_close_event(event)
    second = service.capture_close_event(event)
    assert first["status"] == "captured"
    assert second["status"] == "idempotent_hit"
    assert first["dna"]["content_hash"] == second["dna"]["content_hash"]
    assert len(store.list_dna()) == 1
    assert store.get_close_event(event.trade_id) is not None


def test_duplicate_close_conflict(tmp_path: Path):
    store = DurableCaptureStore(tmp_path / "capture")
    service = TradeDNACaptureService(store)
    service.capture_close_event(_event(realized_pnl=20.0))
    with pytest.raises(CanonicalCloseEventError) as exc:
        service.capture_close_event(_event(realized_pnl=25.0))
    assert exc.value.code == "duplicate_close_event_conflict"


def test_crash_recovery_after_close_event_persisted(tmp_path: Path):
    root = tmp_path / "capture"
    store = DurableCaptureStore(root)
    event = _event()
    store.commit_close_event(event)
    # Simulate crash before DNA: reload store with close event only
    store2 = DurableCaptureStore(root)
    assert store2.get_close_event(event.trade_id) is not None
    assert store2.head_dna_for_trade(event.trade_id) is None
    service = TradeDNACaptureService(store2)
    repaired = service.recover_missing_dna()
    assert event.trade_id in repaired
    head = store2.head_dna_for_trade(event.trade_id)
    assert head is not None
    assert head.content_hash == project_trade_dna_from_close_event(event).content_hash


def test_evidence_graph_integrity(tmp_path: Path):
    store = DurableCaptureStore(tmp_path / "capture")
    result = TradeDNACaptureService(store).capture_close_event(_event())
    evidence = result["evidence"]
    assert list(evidence["trade_ids"]) == ["T-DIP3-1"]
    assert evidence["sample_size"] == 1
    assert evidence["confidence"] == 1.0
    assert evidence["evidence_version"]
    assert evidence["analysis_version"]
    assert evidence["generated_at"] == "2026-07-30T12:00:00+00:00"


def test_schema_compatibility_round_trip(tmp_path: Path):
    store = DurableCaptureStore(tmp_path / "capture")
    result = TradeDNACaptureService(store).capture_close_event(_event())
    text = serialize_trade_dna(deserialize_trade_dna(result["dna"]))
    restored = deserialize_trade_dna(text)
    assert restored.schema_version == SCHEMA_VERSION
    assert restored.content_hash == result["dna"]["content_hash"]


def test_analytics_correctness_and_determinism(tmp_path: Path):
    store = DurableCaptureStore(tmp_path / "capture")
    service = TradeDNACaptureService(store)
    service.capture_close_event(_event(trade_id="T1", realized_pnl=50.0, strategy_id="A"))
    service.capture_close_event(
        _event(
            trade_id="T2",
            realized_pnl=-10.0,
            strategy_id="B",
            exit_reason="stop",
            opened_at="2026-07-31T15:00:00+00:00",
            closed_at="2026-07-31T16:00:00+00:00",
        )
    )
    service.capture_close_event(
        _event(
            trade_id="T3",
            realized_pnl=5.0,
            strategy_id="A",
            side="sell",
            opened_at="2026-08-01T10:00:00+00:00",
            closed_at="2026-08-01T20:00:00+00:00",
        )
    )

    engine = DecisionAnalyticsEngine(
        dna_records=store.list_dna(),
        derived_metrics=store.list_derived(),
        generated_at="2026-08-02T00:00:00+00:00",
    )
    report1 = engine.full_report()
    report2 = DecisionAnalyticsEngine(
        dna_records=store.list_dna(),
        derived_metrics=store.list_derived(),
        generated_at="2026-08-02T00:00:00+00:00",
    ).full_report()
    assert report1 == report2
    assert report1["recommendations"] is False
    assert report1["capital_allocation"] is False
    assert report1["execution_allowed"] is False

    profits = engine.top_profit_contributors().to_dict()
    assert profits["rows"][0]["trade_id"] == "T1"
    assert profits["evidence"]["trade_ids"]
    losses = engine.largest_loss_contributors().to_dict()
    assert losses["rows"][0]["trade_id"] == "T2"
    strategies = engine.strategy_profitability().to_dict()
    assert any(r["strategy_id"] == "A" and r["profit"] == 55.0 for r in strategies["rows"])


def test_replay_determinism(tmp_path: Path):
    event = _event()
    store_a = DurableCaptureStore(tmp_path / "a")
    store_b = DurableCaptureStore(tmp_path / "b")
    ra = TradeDNACaptureService(store_a).capture_close_event(event)
    rb = TradeDNACaptureService(store_b).capture_close_event(event)
    assert ra["dna"]["content_hash"] == rb["dna"]["content_hash"]
    assert ra["close_event"]["content_hash"] == rb["close_event"]["content_hash"]
    assert ra["evidence"]["dna_ids"] == rb["evidence"]["dna_ids"]


def test_execution_gate_unaffected_regression():
    """DIP-003 must not alter ExecutionGate behaviour."""
    gate = ExecutionGate()
    # Smoke: class still importable and constructible (no DIP coupling).
    assert gate is not None
    assert "evaluate_trade" in dir(gate)


def test_capture_from_trade_record_helper(tmp_path: Path, monkeypatch):
    economics = build_paper_execution_economics(
        ticket={
            "ticket_id": "T-REC",
            "symbol": "EUR_USD",
            "side": "BUY",
            "qty": 1000.0,
            "amount": 1000.0,
            "asset_class": "FX",
            "engine_mode": "SAFE",
            "strategy_id": "mobile",
        },
        gate_decision={
            "decision": {"final": "ALLOW"},
            "reason": "approved",
            "debug": {"scaled_notional": 1000.0, "canonical_price": 1.1},
        },
        canonical_price=1.1,
        price_source="price",
    )
    trade_record = {
        "trade_id": "T-REC",
        "session_id": "S1",
        "broker_name": "css_paper",
        "broker_mode": "paper",
        "symbol": "EUR_USD",
        "direction": "buy",
        "order_type": "market",
        "quantity": "1000",
        "filled_quantity": "1000",
        "entry_price": "1.1",
        "opened_at": "2026-07-30T10:00:00+00:00",
        "raw_payload_json": json.dumps(
            {
                "strategy_id": "mobile",
                "asset_class": "FX",
                "execution_economics": economics,
                "execution_gate_summary": {"final": "ALLOW", "reason": "approved"},
            }
        ),
    }
    monkeypatch.setattr(
        "backend.intelligence.trade_dna.capture.default_capture_root",
        lambda: str(tmp_path / "cap"),
    )
    result = capture_completed_trade(
        trade_record,
        exit_price=Decimal("1.12"),
        realized_pnl=Decimal("20"),
        closed_at="2026-07-30T12:00:00+00:00",
    )
    assert result is not None
    assert result["status"] == "captured"
    assert result["dna"]["execution"]["entry_price"] == 1.1


# --- DIP-003 bounded hardening -------------------------------------------------

def test_warehouse_success_dna_failure_leaves_durable_outbox(tmp_path: Path):
    store = DurableCaptureStore(tmp_path / "cap")
    service = TradeDNACaptureService(store)
    event = _event()
    store.enqueue_pending_capture(event)

    def _boom(_record):
        raise RuntimeError("simulated_dna_write_failure")

    store.commit_dna = _boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        service._apply_dna_for_event(event)

    reloaded = DurableCaptureStore(tmp_path / "cap")
    outbox = reloaded.get_outbox(event.trade_id)
    assert outbox is not None
    assert outbox["status"] == "PENDING_DNA"
    assert outbox["close_event_hash"] == event.content_hash
    assert reloaded.head_dna_for_trade(event.trade_id) is None


def test_restart_and_recover_missing_dna_idempotent(tmp_path: Path):
    root = tmp_path / "cap"
    store = DurableCaptureStore(root)
    event = _event()
    store.enqueue_pending_capture(event)
    # Crash window: outbox durable, DNA absent
    restarted = TradeDNACaptureService(DurableCaptureStore(root))
    first = restarted.recover_pending_captures()
    second = restarted.recover_pending_captures()
    assert any(r["trade_id"] == event.trade_id for r in first)
    assert restarted.store.head_dna_for_trade(event.trade_id) is not None
    assert restarted.store.get_outbox(event.trade_id)["status"] == "COMPLETE"
    assert len(restarted.store.list_dna()) == 1
    # Second recovery finds nothing pending
    assert second == [] or all(
        r.get("status") in {"idempotent_hit", "recovered_complete", "captured"} or r.get("trade_id") != event.trade_id
        for r in second
    )
    assert len(TradeDNACaptureService(DurableCaptureStore(root)).store.list_dna()) == 1


def test_duplicate_close_one_dna_conflict_fail_closed(tmp_path: Path):
    store = DurableCaptureStore(tmp_path / "cap")
    service = TradeDNACaptureService(store)
    service.capture_close_event(_event(realized_pnl=20.0))
    with pytest.raises(CanonicalCloseEventError):
        service.capture_close_event(_event(realized_pnl=25.0))
    assert len(store.list_dna()) == 1
    assert store.get_outbox("T-DIP3-1")["status"] == "CONFLICT"
    assert store.list_conflicts()


def test_crash_after_outbox_before_dna(tmp_path: Path):
    root = tmp_path / "cap"
    event = _event()
    DurableCaptureStore(root).enqueue_pending_capture(event)
    service = TradeDNACaptureService(DurableCaptureStore(root))
    service.recover_pending_captures()
    assert service.store.get_outbox(event.trade_id)["status"] == "COMPLETE"
    assert service.store.head_dna_for_trade(event.trade_id).content_hash == project_trade_dna_from_close_event(event).content_hash


def test_crash_after_dna_before_reconciliation_complete(tmp_path: Path):
    root = tmp_path / "cap"
    store = DurableCaptureStore(root)
    service = TradeDNACaptureService(store)
    event = _event()
    store.enqueue_pending_capture(event)
    sealed = store.commit_close_event(event)
    dna = store.commit_dna(project_trade_dna_from_close_event(sealed))
    store.mark_outbox_dna_committed(event.trade_id)
    # No derived / not COMPLETE yet
    assert store.get_derived(dna.identity.dna_id) is None
    assert store.get_outbox(event.trade_id)["status"] == "DNA_COMMITTED"

    recovered = TradeDNACaptureService(DurableCaptureStore(root))
    results = recovered.recover_pending_captures()
    assert any(r["status"] == "recovered_complete" for r in results)
    assert recovered.store.get_outbox(event.trade_id)["status"] == "COMPLETE"
    assert recovered.store.get_derived(dna.identity.dna_id) is not None


def test_stable_event_id_and_hashes():
    a = _event()
    b = _event()
    assert a.event_id == b.event_id
    assert a.content_hash == b.content_hash
    assert project_trade_dna_from_close_event(a).content_hash == project_trade_dna_from_close_event(b).content_hash
    # Identity excludes wall clock / paths / randoms
    assert a.event_id.startswith("cce-")
    assert "artifacts" not in json.dumps(a.to_dict())


def test_unavailable_context_not_fabricated():
    event = _event(strategy_id="UNKNOWN", market_regime="UNAVAILABLE", exit_reason=None)
    assert event.strategy_id is None
    assert event.market_regime is None
    dna = project_trade_dna_from_close_event(event)
    assert dna.strategy.strategy_id is None
    assert dna.market.market_regime is None
    observed = _event(market_regime="OBSERVED_UNKNOWN")
    assert observed.market_regime == "OBSERVED_UNKNOWN"
    assert project_trade_dna_from_close_event(observed).market.market_regime == "OBSERVED_UNKNOWN"


def test_close_completes_when_advisory_capture_fails(tmp_path, monkeypatch):
    import backend.app.persistence.db as db_module
    from backend.app.persistence.services.trade_runtime_service import TradeRuntimeService
    from backend.execution.canonical_trade_lifecycle import CanonicalTradeLifecycle
    from backend.analytics.trade_outcome_repository import TradeOutcomeRepository

    db_path = tmp_path / "harden.db"
    db_module.close_connection()
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(db_module, "_CONNECTION", None)

    repo = TradeOutcomeRepository(tmp_path / "outcomes.json")
    repo.create_storage()
    service = TradeRuntimeService(canonical_lifecycle=CanonicalTradeLifecycle(repo))
    service.persistence.sessions.create_session(
        session_id="s-h",
        status="active",
        mode="paper",
        broker_name="css_paper",
        broker_mode="paper",
        started_at="2026-07-30T00:00:00+00:00",
    )
    service.open_trade(
        trade_id="H1",
        session_id="s-h",
        broker_name="css_paper",
        broker_mode="paper",
        symbol="EUR_USD",
        direction="buy",
        order_type="market",
        quantity=Decimal("1000"),
        filled_quantity=Decimal("1000"),
        entry_price=Decimal("1.10"),
        raw_payload_json=json.dumps({"asset_class": "FX", "strategy_id": "t"}),
        status="open",
    )

    def _fail(*_a, **_k):
        raise RuntimeError("capture_explodes")

    monkeypatch.setattr(
        "backend.intelligence.trade_dna.capture.capture_completed_trade",
        _fail,
    )
    monkeypatch.setattr(
        "backend.intelligence.trade_dna.capture.default_capture_root",
        lambda: str(tmp_path / "cap"),
    )
    service.close_trade("H1", exit_price=Decimal("1.20"), realized_pnl=Decimal("100"))
    trade = service.persistence.trades.get_trade("H1")
    assert trade["status"] == "closed"
    assert float(trade["realized_pnl"]) == 100.0
    outcomes = repo.load_outcomes()
    assert len(outcomes) == 1
    assert outcomes[0]["trade_id"] == "H1"


def test_capture_helper_pending_recovery_after_dna_failure(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "backend.intelligence.trade_dna.capture.default_capture_root",
        lambda: str(tmp_path / "cap"),
    )
    trade_record = {
        "trade_id": "T-PEND",
        "session_id": "S1",
        "broker_name": "css_paper",
        "broker_mode": "paper",
        "symbol": "EUR_USD",
        "direction": "buy",
        "order_type": "market",
        "quantity": "1000",
        "filled_quantity": "1000",
        "entry_price": "1.1",
        "opened_at": "2026-07-30T10:00:00+00:00",
        "raw_payload_json": "{}",
    }

    real_store_cls = DurableCaptureStore

    class FlakyStore(real_store_cls):
        def commit_dna(self, record):
            raise RuntimeError("disk_full")

    monkeypatch.setattr(
        "backend.intelligence.trade_dna.capture.DurableCaptureStore",
        FlakyStore,
    )
    result = capture_completed_trade(
        trade_record,
        exit_price=1.12,
        realized_pnl=5.0,
        closed_at="2026-07-30T12:00:00+00:00",
    )
    assert result is not None
    assert result["status"] == "pending_recovery"
    # Discoverable without logs
    store = real_store_cls(tmp_path / "cap")
    assert store.get_outbox("T-PEND")["status"] == "PENDING_DNA"
    # Recovery with healthy store class
    monkeypatch.setattr(
        "backend.intelligence.trade_dna.capture.DurableCaptureStore",
        real_store_cls,
    )
    service = TradeDNACaptureService(real_store_cls(tmp_path / "cap"))
    service.recover_pending_captures()
    assert service.store.head_dna_for_trade("T-PEND") is not None
    assert service.store.get_outbox("T-PEND")["status"] == "COMPLETE"
