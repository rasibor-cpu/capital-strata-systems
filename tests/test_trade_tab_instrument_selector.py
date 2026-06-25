from __future__ import annotations

import json
import os
import tempfile

from fastapi.testclient import TestClient

from launcher.css_mobile_launcher import app


client = TestClient(app)


def test_trade_tab_renders_instrument_selector() -> None:
    response = client.get("/mobile")

    assert response.status_code == 200
    assert "Instrument Universe Selector" in response.text
    assert "All Asset Classes" in response.text
    assert "All Brokers" in response.text
    assert 'class="instrument-select"' in response.text


def test_mobile_instrument_feed_route_returns_lists() -> None:
    response = client.get("/mobile/instruments")

    assert response.status_code == 200
    payload = response.json()
    assert "all_instruments" in payload
    assert "tradable_paper_instruments" in payload
    assert isinstance(payload["all_instruments"], list)


def test_selector_page_load_does_not_execute_trade_request() -> None:
    import launcher.css_mobile_launcher as mod

    with tempfile.TemporaryDirectory() as td:
        orig = mod.MOBILE_TRADE_REQUESTS_FILE
        mod.MOBILE_TRADE_REQUESTS_FILE = os.path.join(td, "artifacts", "css_mobile_trade_requests.jsonl")
        try:
            response = client.get("/mobile")
            assert response.status_code == 200
            assert not os.path.exists(mod.MOBILE_TRADE_REQUESTS_FILE)
        finally:
            mod.MOBILE_TRADE_REQUESTS_FILE = orig


def test_trade_submission_remains_paper_only_and_gate_safe() -> None:
    live_mode = client.post(
        "/mobile/trade/paper",
        headers={"Accept": "application/json"},
        data={
            "symbol": "EUR_USD",
            "asset_class": "FX",
            "side": "BUY",
            "quantity": "1",
            "broker_mode": "live",
        },
    )
    assert live_mode.status_code == 400

    broker_exec = client.post(
        "/mobile/trade/paper",
        headers={"Accept": "application/json"},
        data={
            "symbol": "EUR_USD",
            "asset_class": "FX",
            "side": "BUY",
            "quantity": "1",
            "broker_execution_allowed": "true",
        },
    )
    assert broker_exec.status_code == 400
