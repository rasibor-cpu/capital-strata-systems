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
    assert "CSS Decision Console" in response.text
    assert "Canonical Trading Universe" in response.text
    assert "Portfolio Summary" in response.text
    assert 'id="decision-instrument-select"' in response.text
    assert "PAPER MODE" in response.text or "LIVE MODE" in response.text
    assert "optgroup" in response.text


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


def test_mobile_trading_universe_grouped_route_returns_groups() -> None:
    response = client.get("/mobile/trading-universe/grouped")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OK"
    groups = payload["groups"]
    labels = {row["group"] for row in groups}
    assert {"CRYPTO", "FOREX", "INDICES", "FUTURES", "OPTIONS"}.issubset(labels)


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
        "get_grouped_trading_universe_feed",
        lambda **kwargs: {
            "status": "OK",
            "mode": "paper",
            "count": 1,
            "groups": [
                {
                    "group": "FOREX",
                    "label": "Forex",
                    "instruments": [
                        {
                            "instrument_id": "FOREX:PAPER_OK",
                            "symbol": "PAPER_OK",
                            "display_name": "Paper OK",
                            "asset_class": "FOREX",
                            "broker": "oanda",
                            "paper_supported": True,
                            "live_supported": False,
                            "enabled": True,
                            "selectable": True,
                            "status": "ACTIVE",
                        }
                    ],
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
    assert "PAPER_OK" in response.text
    assert "UNAVAILABLE" in response.text or "Select canonical instrument" in response.text


def test_trade_dropdown_empty_state_when_no_tradeable_symbols(monkeypatch) -> None:
    import launcher.css_mobile_launcher as mod

    monkeypatch.setattr(
        mod,
        "get_grouped_trading_universe_feed",
        lambda **kwargs: {
            "status": "OK",
            "mode": "paper",
            "count": 0,
            "groups": [
                {"group": "CRYPTO", "label": "Crypto", "instruments": []},
                {"group": "FOREX", "label": "Forex", "instruments": []},
                {"group": "INDICES", "label": "Indices", "instruments": []},
                {"group": "FUTURES", "label": "Futures", "instruments": []},
                {"group": "OPTIONS", "label": "Options", "instruments": []},
            ],
        },
    )

    response = client.get("/mobile")
    assert response.status_code == 200
    assert "Select canonical instrument" in response.text


def test_search_and_favorites_hooks_present() -> None:
    response = client.get("/mobile")

    assert response.status_code == 200
    assert "trade-search-input" in response.text
    assert "toggle-favorite-btn" in response.text
    assert "css_trade_favorites" in response.text


def test_trade_ticket_field_order_and_presence() -> None:
    response = client.get("/mobile")
    assert response.status_code == 200

    html = response.text
    asset_idx = html.find('id="trade-asset-class"')
    symbol_idx = html.find('id="trade-symbol"')
    side_idx = html.find('id="trade-side"')
    tenor_idx = html.find('id="trade-tenor"')
    price_idx = html.find('id="trade-price"')
    qty_idx = html.find('id="trade-quantity"')

    assert -1 not in {asset_idx, symbol_idx, side_idx, tenor_idx, price_idx, qty_idx}
    assert asset_idx < symbol_idx < side_idx < tenor_idx < price_idx < qty_idx


def test_asset_class_dropdown_is_first_selector_and_has_expected_options() -> None:
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text

    assert 'id="trade-asset-class"' in html
    for value in ("CRYPTO", "FOREX", "INDICES", "FUTURES", "OPTIONS"):
        assert f'value="{value}"' in html


def test_symbol_dropdown_is_second_and_prepopulated() -> None:
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text
    assert 'id="trade-symbol"' in html
    assert "NO TRADEABLE SYMBOLS AVAILABLE" in html or "<option value=\"" in html


def test_side_dropdown_contains_buy_sell() -> None:
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text
    assert 'id="trade-side"' in html
    assert '<option value="BUY"' in html
    assert '<option value="SELL"' in html


def test_tenor_visibility_and_price_quantity_prefill_hooks_present() -> None:
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text

    assert 'id="trade-tenor-wrap"' in html
    assert 'id="trade-tenor"' in html
    assert "NEXT_MONTH" in html or "FRONT" in html
    assert 'id="trade-price"' in html
    assert 'id="trade-price-status"' in html
    assert 'id="trade-quantity"' in html


def test_decision_panel_displays_tenor_metadata_fields() -> None:
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text

    assert 'id="dp-tenor-source"' in html
    assert 'id="dp-default-tenor"' in html
    assert 'id="dp-contract-metadata-status"' in html


def test_symbol_filter_and_selection_update_hooks_present() -> None:
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text
    assert "rowsForAsset" in html
    assert "assetSelect.addEventListener(\"change\"" in html
    assert "symbolSelect.addEventListener(\"change\"" in html
    assert "panel.tenor_options" in html
    assert "panel.default_tenor" in html


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
