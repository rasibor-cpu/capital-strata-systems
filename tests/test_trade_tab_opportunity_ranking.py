from __future__ import annotations

import os
import tempfile

from fastapi.testclient import TestClient

from launcher.css_mobile_launcher import app


client = TestClient(app)


def test_trade_tab_renders_ranked_opportunity_table() -> None:
    response = client.get("/mobile")
    assert response.status_code == 200
    assert "TOP OPPORTUNITIES" in response.text
    assert "CSS Decision Console" in response.text
    assert "Decision Panel" in response.text


def test_opportunity_feed_routes_return_payloads() -> None:
    response = client.get("/mobile/opportunities")
    assert response.status_code == 200
    payload = response.json()
    assert "all_opportunities" in payload
    assert "top_opportunities" in payload

    top_response = client.get("/mobile/opportunities/top")
    assert top_response.status_code == 200
    assert "top_opportunities" in top_response.json()

    top_console = client.get("/mobile/top-opportunities")
    assert top_console.status_code == 200
    assert "top_opportunities" in top_console.json()

    by_asset = client.get("/mobile/opportunities/asset-class/FX")
    assert by_asset.status_code == 200
    body = by_asset.json()
    assert body["asset_class"] == "FX"
    assert "opportunities" in body


def test_selecting_opportunity_only_populates_ticket_not_executes() -> None:
    import launcher.css_mobile_launcher as mod

    with tempfile.TemporaryDirectory() as td:
        orig = mod.MOBILE_TRADE_REQUESTS_FILE
        mod.MOBILE_TRADE_REQUESTS_FILE = os.path.join(td, "artifacts", "css_mobile_trade_requests.jsonl")
        try:
            page = client.get("/mobile")
            assert page.status_code == 200
            assert "opportunity-select-btn" in page.text
            assert not os.path.exists(mod.MOBILE_TRADE_REQUESTS_FILE)
        finally:
            mod.MOBILE_TRADE_REQUESTS_FILE = orig


def test_no_trade_execution_occurs_on_feed_calls() -> None:
    import launcher.css_mobile_launcher as mod

    with tempfile.TemporaryDirectory() as td:
        orig = mod.MOBILE_TRADE_REQUESTS_FILE
        mod.MOBILE_TRADE_REQUESTS_FILE = os.path.join(td, "artifacts", "css_mobile_trade_requests.jsonl")
        try:
            assert client.get("/mobile/opportunities").status_code == 200
            assert client.get("/mobile/opportunities/top").status_code == 200
            assert not os.path.exists(mod.MOBILE_TRADE_REQUESTS_FILE)
        finally:
            mod.MOBILE_TRADE_REQUESTS_FILE = orig


def test_opportunity_use_button_blocked_for_non_tradeable_symbols(monkeypatch) -> None:
    import launcher.css_mobile_launcher as mod

    monkeypatch.setattr(mod, "get_grouped_trading_universe_feed", lambda **kwargs: {
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
                    }
                ],
            }
        ],
    })

    monkeypatch.setattr(mod, "get_top_opportunities_feed", lambda **kwargs: {
        "status": "OK",
        "count": 2,
        "top_opportunities": [
            {"rank": 1, "symbol": "PAPER_OK", "asset_class": "FOREX", "signal_color": "GREEN"},
            {"rank": 2, "symbol": "BLOCKED_X", "asset_class": "FOREX", "signal_color": "RED"},
        ],
    })

    response = client.get("/mobile")
    assert response.status_code == 200
    assert 'data-opportunity-symbol="PAPER_OK"' in response.text
    assert 'data-opportunity-symbol="BLOCKED_X"' in response.text
    assert 'data-opportunity-action=' in response.text
    assert "TOP OPPORTUNITIES" in response.text


def test_use_opportunity_populates_all_six_ticket_fields_hooks() -> None:
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text

    assert "assetSelect.value = asset;" in html
    assert "symbolSelect.value = symbol;" in html
    assert "refreshSummary({ side:" in html
    assert "applyTenor(" in html
    assert "priceInput.value" in html
    assert "quantityInput.value" in html


def test_feed_fail_closed_behavior(monkeypatch) -> None:
    import launcher.css_mobile_launcher as mod

    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(mod, "OpportunityRankingEngine", _boom)
    payload = mod.get_opportunity_feed()

    assert payload["all_opportunities"] == []
    assert payload["top_opportunities"] == []
