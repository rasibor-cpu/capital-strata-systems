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


def test_mobile_tradeable_symbols_route_returns_paper_tradeable_only(monkeypatch) -> None:
    import launcher.css_mobile_launcher as mod
    from types import SimpleNamespace

    class _StubUniverse:
        def tradeable_symbols(self, mode="paper", asset_class=None, broker=None):
            rows = [
                SimpleNamespace(
                    symbol="PAPER_OK",
                    display_name="Paper OK",
                    asset_class="FX",
                    broker="oanda",
                    paper_supported=True,
                    live_supported=False,
                    status="ACTIVE",
                )
            ]
            if mode == "live":
                rows.append(
                    SimpleNamespace(
                        symbol="LIVE_ONLY",
                        display_name="Live Only",
                        asset_class="CRYPTO",
                        broker="coinbase",
                        paper_supported=False,
                        live_supported=True,
                        status="ACTIVE",
                    )
                )
            return rows

    monkeypatch.setattr(mod, "InstrumentUniverse", _StubUniverse)

    response = client.get("/mobile/tradeable-symbols?mode=paper")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OK"
    assert payload["mode"] == "paper"
    assert payload["count"] == 1
    assert payload["symbols"][0]["symbol"] == "PAPER_OK"


def test_mobile_instrument_feed_route_returns_lists() -> None:
    response = client.get("/mobile/instruments")

    assert response.status_code == 200
    payload = response.json()
    assert "all_instruments" in payload
    assert "tradable_paper_instruments" in payload
    assert isinstance(payload["all_instruments"], list)


def test_trade_dropdown_renders_tradeable_symbols_only_on_server_fallback(monkeypatch) -> None:
    import launcher.css_mobile_launcher as mod

    monkeypatch.setattr(
        mod,
        "get_tradeable_symbols_feed",
        lambda **kwargs: {
            "status": "OK",
            "mode": "paper",
            "count": 1,
            "symbols": [
                {
                    "symbol": "PAPER_OK",
                    "display_name": "Paper OK",
                    "asset_class": "FX",
                    "broker": "oanda",
                    "paper_supported": True,
                    "live_supported": False,
                    "status": "ACTIVE",
                }
            ],
        },
    )
    monkeypatch.setattr(
        mod,
        "get_trade_tab_instrument_feed",
        lambda: {
            "all_instruments": [
                {
                    "symbol": "LIVE_ONLY",
                    "display_name": "Live Only",
                    "asset_class": "CRYPTO",
                    "broker": "coinbase",
                    "tradable": True,
                    "paper_supported": False,
                    "live_supported": True,
                    "status": "ACTIVE",
                }
            ],
            "asset_classes": ["CRYPTO"],
            "brokers": ["coinbase"],
            "instruments_by_asset_class": {},
            "instruments_by_broker": {},
            "tradable_paper_instruments": [],
        },
    )

    response = client.get("/mobile")
    assert response.status_code == 200
    assert "PAPER_OK | FX | ACTIVE" in response.text
    assert "LIVE_ONLY | CRYPTO | ACTIVE" not in response.text


def test_trade_dropdown_empty_state_when_no_tradeable_symbols(monkeypatch) -> None:
    import launcher.css_mobile_launcher as mod

    monkeypatch.setattr(
        mod,
        "get_tradeable_symbols_feed",
        lambda **kwargs: {
            "status": "OK",
            "mode": "paper",
            "count": 0,
            "symbols": [],
        },
    )

    response = client.get("/mobile")
    assert response.status_code == 200
    assert "NO TRADEABLE SYMBOLS AVAILABLE" in response.text


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
