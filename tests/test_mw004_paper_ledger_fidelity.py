"""MW-004 / RR-003b — paper ledger execution fidelity."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

import backend.app.persistence.db as db_module
from backend.app.persistence.services.trade_runtime_service import TradeRuntimeService
from backend.execution.paper_execution_economics import (
    PaperExecutionEconomicsError,
    amount_traded,
    build_paper_execution_economics,
    merge_ticket_payload_with_economics,
    require_positive_execution_price,
)
from engine.execution.execution_gate import ExecutionGate
from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from engine.risk.margin_snapshot import MarginSnapshot, MarginState


@pytest.fixture
def trade_service(tmp_path, monkeypatch):
    db_path = tmp_path / "mw004.db"
    db_module.close_connection()
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(db_module, "_CONNECTION", None)
    service = TradeRuntimeService()
    service.persistence.sessions.create_session(
        session_id="s1",
        status="active",
        mode="paper",
        broker_name="css_paper",
        broker_mode="paper",
        started_at="2026-07-30T00:00:00+00:00",
    )
    return service


def _ticket(**overrides):
    base = {
        "ticket_id": "T1",
        "symbol": "EUR_USD",
        "side": "BUY",
        "qty": 1000.0,
        "amount": 1000.0,
        "asset_class": "FX",
        "engine_mode": "SAFE",
    }
    base.update(overrides)
    return base


def _allow_gate(*, scaled_notional=1000.0, price=1.10):
    return {
        "decision": {"final": "ALLOW"},
        "reason": "approved",
        "debug": {
            "canonical_price": price,
            "canonical_price_source": "price",
            "base_notional": 1000.0,
            "vol_scaled_notional": scaled_notional,
            "scaled_notional": scaled_notional,
        },
    }


def test_economics_persists_price_and_scaled_notional_distinct_from_qty():
    economics = build_paper_execution_economics(
        ticket=_ticket(qty=1000, amount=1000),
        gate_decision=_allow_gate(scaled_notional=500.0, price=1.10),
        canonical_price=1.10,
        price_source="price",
    )
    assert economics["status"] == "open"
    assert economics["entry_price"] == "1.1" or float(economics["entry_price"]) == 1.1
    assert float(economics["scaled_notional"]) == 500.0
    assert float(economics["requested_quantity"]) == 1000.0
    assert float(economics["filled_quantity"]) == 1000.0
    assert economics["quantity_contract"] == "requested_quantity_authoritative"
    assert economics["notional_contract"] == "scaled_notional_authoritative_for_risk"


def test_zero_and_negative_price_rejected():
    with pytest.raises(PaperExecutionEconomicsError):
        require_positive_execution_price(0)
    with pytest.raises(PaperExecutionEconomicsError):
        require_positive_execution_price(-1)
    with pytest.raises(PaperExecutionEconomicsError):
        build_paper_execution_economics(
            ticket=_ticket(),
            gate_decision=_allow_gate(price=0),
            canonical_price=0,
        )


def test_pending_when_gate_not_allow():
    economics = build_paper_execution_economics(
        ticket=_ticket(),
        gate_decision={"decision": {"final": "BLOCK"}, "reason": "x", "debug": {"scaled_notional": 100.0}},
        canonical_price=1.10,
    )
    assert economics["status"] == "pending"
    assert economics["filled_quantity"] == "0"
    assert float(economics["entry_price"]) == 1.1


def test_open_trade_rejects_zero_entry(trade_service):
    with pytest.raises(ValueError, match="execution_price_invalid"):
        trade_service.open_trade(
            trade_id="bad",
            session_id="s1",
            broker_name="css_paper",
            broker_mode="paper",
            symbol="EUR_USD",
            direction="buy",
            order_type="market",
            quantity=Decimal("1"),
            filled_quantity=Decimal("1"),
            entry_price=Decimal("0"),
        )


def test_open_trade_persists_economics_and_recovery(trade_service):
    economics = build_paper_execution_economics(
        ticket=_ticket(ticket_id="FX1", symbol="EUR_USD", qty=1000, amount=1100),
        gate_decision=_allow_gate(scaled_notional=550.0, price=1.10),
        canonical_price=1.10,
    )
    payload = merge_ticket_payload_with_economics(_ticket(ticket_id="FX1"), economics, gate_decision=_allow_gate(scaled_notional=550.0))
    trade_service.open_trade(
        trade_id="FX1",
        session_id="s1",
        broker_name="css_paper",
        broker_mode="paper",
        symbol="EUR_USD",
        direction="buy",
        order_type="market",
        quantity=Decimal(economics["requested_quantity"]),
        filled_quantity=Decimal(economics["filled_quantity"]),
        entry_price=Decimal(economics["entry_price"]),
        raw_payload_json=payload,
        status=economics["status"],
    )
    rows = trade_service.get_open_trades("s1")
    assert len(rows) == 1
    row = rows[0]
    assert float(row["entry_price"]) == 1.1
    assert float(row["quantity"]) == 1000.0
    assert float(row["filled_quantity"]) == 1000.0
    body = json.loads(row["raw_payload_json"])
    assert float(body["execution_economics"]["scaled_notional"]) == 550.0
    assert body["execution_economics"]["requested_quantity"] != body["execution_economics"]["scaled_notional"]


def test_crypto_path_economics():
    economics = build_paper_execution_economics(
        ticket=_ticket(symbol="BTC-USD", qty=0.01, amount=650.0, asset_class="CRYPTO"),
        gate_decision=_allow_gate(scaled_notional=325.0, price=65000.0),
        canonical_price=65000.0,
        price_source="last_price",
    )
    assert float(economics["entry_price"]) == 65000.0
    assert float(economics["requested_quantity"]) == 0.01
    assert float(economics["scaled_notional"]) == 325.0


def test_amount_traded_uses_positive_entry():
    assert float(amount_traded(entry_price=1.10, quantity=1000)) == 1100.0
    with pytest.raises(PaperExecutionEconomicsError):
        amount_traded(entry_price=0, quantity=1000)


def test_pending_persist_contract(trade_service):
    economics = build_paper_execution_economics(
        ticket=_ticket(ticket_id="P1"),
        gate_decision={"decision": {"final": "BLOCK"}, "reason": "blocked", "debug": {"scaled_notional": 100.0}},
        canonical_price=1.25,
    )
    trade_service.open_trade(
        trade_id="P1",
        session_id="s1",
        broker_name="css_paper",
        broker_mode="paper",
        symbol="EUR_USD",
        direction="buy",
        order_type="market",
        quantity=Decimal(economics["requested_quantity"]),
        filled_quantity=Decimal(economics["filled_quantity"]),
        entry_price=Decimal(economics["entry_price"]),
        raw_payload_json=merge_ticket_payload_with_economics(_ticket(ticket_id="P1"), economics),
        status="pending",
    )
    all_rows = trade_service.get_all_session_trades("s1")
    assert all_rows[0]["status"] == "pending"
    assert float(all_rows[0]["filled_quantity"]) == 0.0
    assert float(all_rows[0]["entry_price"]) == 1.25


def test_close_amount_traded_with_nonzero_entry(trade_service, tmp_path, monkeypatch):
    from backend.analytics.trade_outcome_repository import TradeOutcomeRepository
    from backend.execution.canonical_trade_lifecycle import CanonicalTradeLifecycle

    repo = TradeOutcomeRepository(tmp_path / "wh.json")
    repo.create_storage()
    service = TradeRuntimeService(canonical_lifecycle=CanonicalTradeLifecycle(repo))
    service.persistence.sessions.create_session(
        session_id="s2",
        status="active",
        mode="paper",
        broker_name="css_paper",
        broker_mode="paper",
        started_at="2026-07-30T00:00:00+00:00",
    )
    service.open_trade(
        trade_id="C1",
        session_id="s2",
        broker_name="css_paper",
        broker_mode="paper",
        symbol="EUR_USD",
        direction="buy",
        order_type="market",
        quantity=Decimal("1000"),
        filled_quantity=Decimal("1000"),
        entry_price=Decimal("1.10"),
        raw_payload_json='{"asset_class":"FX","strategy_id":"t","market_regime":"NORMAL"}',
    )
    service.close_trade("C1", exit_price=Decimal("1.20"), realized_pnl=Decimal("100"))
    # legacy ledger path records amount_traded; ensure no exception and trade closed
    closed = [t for t in service.get_all_session_trades("s2") if t["trade_id"] == "C1"][0]
    assert closed["status"] == "closed"
    assert float(closed["entry_price"]) == 1.1
