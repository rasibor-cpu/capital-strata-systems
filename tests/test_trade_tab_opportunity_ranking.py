from __future__ import annotations

import os
import tempfile

from fastapi.testclient import TestClient

from launcher.css_mobile_launcher import app


client = TestClient(app)


def test_trade_tab_renders_ranked_opportunity_table() -> None:
    response = client.get("/mobile")
    assert response.status_code == 200
    assert "Ranked Opportunities" in response.text
    assert "Rank" in response.text
    assert "Action" in response.text
    assert "Score" in response.text


def test_opportunity_feed_routes_return_payloads() -> None:
    response = client.get("/mobile/opportunities")
    assert response.status_code == 200
    payload = response.json()
    assert "all_opportunities" in payload
    assert "top_opportunities" in payload

    top_response = client.get("/mobile/opportunities/top")
    assert top_response.status_code == 200
    assert "top_opportunities" in top_response.json()

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


def test_feed_fail_closed_behavior(monkeypatch) -> None:
    import launcher.css_mobile_launcher as mod

    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(mod, "OpportunityRankingEngine", _boom)
    payload = mod.get_opportunity_feed()

    assert payload["all_opportunities"] == []
    assert payload["top_opportunities"] == []
