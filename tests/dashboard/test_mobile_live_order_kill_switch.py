from __future__ import annotations

import dashboard.mobile.mobile_app as mobile_app
from backend.analytics.trade_outcome_repository import TradeOutcomeRepository
from backend.execution.canonical_trade_lifecycle import CanonicalTradeLifecycle


TRADER = {
    "user_id": "00017",
    "display_name": "CSS Trader",
    "role": "TRADER",
}


def test_mobile_live_order_kill_switch_blocks_live_orders(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls(
        {
            "mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED",
            "engine_mode": "BALANCED",
            "live_order_kill_switch": True,
        }
    )

    SUPER_USER = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
    }

    result = mobile_app.execute_mobile_trade_ticket(
        SUPER_USER,
        {
            "broker": "COINBASE",
            "asset_class": "CRYPTO",
            "symbol": "BTC-USD",
            "side": "BUY",
            "amount": "1.00",
            "qty": "1",
            "confirm": "MOBILE LIVE",
        },
    )
    status = mobile_app._system_status(SUPER_USER)

    assert result["ok"] is False
    assert result["status"] == "GLOBAL_LIVE_ORDER_KILL_SWITCH_ENGAGED"
    assert result["broker_response"]["live_order_sent"] is False
    assert status["live_order_kill_switch"] is True



def test_mobile_live_order_kill_switch_does_not_block_paper_tickets(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls(
        {
            "mobile_trading_mode": "MOBILE_PAPER_TRADING",
            "engine_mode": "SAFE",
            "live_order_kill_switch": True,
        }
    )
    def mock_eval(*args, **kwargs):
        return {"decision": {"final": "ALLOW"}, "reason": "approved"}
    
    from engine.execution.execution_gate import ExecutionGate
    monkeypatch.setattr(ExecutionGate, "evaluate_trade", mock_eval)
    import backend.intelligence.trade_decision_orchestrator as tdo

    outcome_repository = TradeOutcomeRepository(tmp_path / "trade_outcomes.json")
    outcome_repository.create_storage()
    trade_runtime_service = tdo.TradeRuntimeService
    monkeypatch.setattr(
        tdo,
        "TradeRuntimeService",
        lambda: trade_runtime_service(
            canonical_lifecycle=CanonicalTradeLifecycle(outcome_repository)
        ),
    )

    import uuid
    result = mobile_app.execute_mobile_trade_ticket(
        TRADER,
        {
            "broker": "CSS_PAPER",
            "asset_class": "CRYPTO",
            "symbol": f"BTC-KILL-{uuid.uuid4()}",
            "side": "BUY",

            "amount": "1000.00",
            "qty": "10",
        },

    )

    # Kill switch must not engage on paper. RR-001 may allow the ticket to
    # succeed when durable equity_peak is missing (peak defaults to equity);
    # either success or a non-kill-switch rejection is acceptable here.
    assert result["status"] != "GLOBAL_LIVE_ORDER_KILL_SWITCH_ENGAGED"
    if result.get("ok") is False:
        assert "KILL_SWITCH" not in str(result.get("status") or "").upper()


def test_controls_page_exposes_live_order_kill_switch(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls(
        {
            "runtime_mode": "live",
            "orders_enabled": True,
            "engine_mode": "BALANCED",
            "live_order_kill_switch": True,
        }
    )

    page = mobile_app._controls_page(
        {
            "user_id": "00000",
            "display_name": "CSS Administrator",
            "role": "SUPER_USER",
        }
    )

    assert "Live Order Kill Switch" in page
    assert "Kill Switch" in page
    assert "ENGAGED" in page
