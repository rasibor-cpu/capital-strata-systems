from __future__ import annotations

import dashboard.mobile.mobile_app as mobile_app


TRADER = {
    "user_id": "00017",
    "display_name": "CSS Trader",
    "role": "TRADER",
}


def test_mobile_live_order_kill_switch_blocks_live_orders(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    monkeypatch.setattr(mobile_app, "_mobile_live_orders_enabled", lambda: True)
    mobile_app.save_mobile_controls(
        {
            "runtime_mode": "live",
            "orders_enabled": True,
            "engine_mode": "BALANCED",
            "live_order_kill_switch": True,
        }
    )

    result = mobile_app.execute_mobile_trade_ticket(
        TRADER,
        {
            "broker": "COINBASE",
            "asset_class": "CRYPTO",
            "symbol": "BTC-USD",
            "side": "BUY",
            "amount": "1.00",
            "qty": "1",
            "confirm": "EXECUTE",
        },
    )
    status = mobile_app._system_status(TRADER)

    assert result["ok"] is False
    assert result["status"] == "GLOBAL_LIVE_ORDER_KILL_SWITCH_ENGAGED"
    assert result["broker_response"]["live_order_sent"] is False
    assert status["live_order_kill_switch"] is True
    assert status["live_orders_enabled"] is False


def test_mobile_live_order_kill_switch_does_not_block_paper_tickets(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls(
        {
            "runtime_mode": "paper",
            "orders_enabled": True,
            "engine_mode": "SAFE",
            "live_order_kill_switch": True,
        }
    )

    result = mobile_app.execute_mobile_trade_ticket(
        TRADER,
        {
            "broker": "CSS_PAPER",
            "asset_class": "CRYPTO",
            "symbol": "BTC-USD",
            "side": "BUY",
            "amount": "1.00",
            "qty": "1",
        },
    )

    assert result["ok"] is True
    assert result["status"] == "PAPER_TICKET_RECORDED"
    assert result["broker_response"]["live_order_sent"] is False


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
