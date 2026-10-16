"""Closeout: the provider-matrix tool reports BLOCKED (never PASS) unless real bars were fetched fresh."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("css_market_data_matrix", REPO / "tools" / "css_market_data_matrix.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

H = 3600
NOW = datetime(2026, 10, 16, 9, 30, tzinfo=timezone.utc)


class Refused:
    """Every request fails the way a policy-denied proxy does."""

    def get(self, url, params=None, headers=None, timeout=10.0):
        raise ConnectionError("proxy CONNECT 403")


class Resp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code, self.headers = payload, status, {}

    def json(self):
        return self.payload


def test_static_matrix_has_no_network_and_no_pass_rows():
    report = tool.run(probe=False, env={"CSS_OPERATING_COUNTRY": "CA"}, now=NOW)
    assert report["providers"] == {} and report["orders_placed"] == 0
    assert {r["status"] for r in report["static"]} <= {"READY", "BLOCKED"}


def test_probe_with_network_refused_blocks_every_provider_with_reason():
    report = tool.run(probe=True, env={"CSS_OPERATING_COUNTRY": "CA"}, http=Refused(), now=NOW)
    rows = report["providers"]
    assert all(r["verdict"] == "BLOCKED" for r in rows.values())
    assert rows["coinbase"]["reason"].startswith("ConnectionError") or "proxy" in rows["coinbase"]["reason"]
    assert rows["binance"]["reason"] == "binance_jurisdiction_restricted:CA"
    assert rows["alpaca_stock"]["reason"] == "alpaca_credentials_missing"
    assert rows["oanda"]["reason"] == "oanda_practice_token_missing"
    assert rows["options"]["reason"] == "no_authorized_options_feed"


def test_probe_pass_requires_fresh_validated_bars():
    ts0 = int(NOW.timestamp()) // H * H - 5 * H
    fresh = [[ts0 + i * H, 99.0, 101.0, 100.0, 100.5, 3.0] for i in range(5)]

    class Coinbase:
        def get(self, url, params=None, headers=None, timeout=10.0):
            if url.endswith("/candles"):
                return Resp(list(reversed(fresh)))
            raise ConnectionError("not needed")

    row = tool.probe_provider("coinbase", granularity_s=H, now=NOW, http=Coinbase())
    assert row["verdict"] == "PASS" and row["bars"] == 5 and row["classification"] == "LIVE"
    later = datetime.fromtimestamp(NOW.timestamp() + 10 * H, tz=timezone.utc)
    stale = tool.probe_provider("coinbase", granularity_s=H, now=later, http=Coinbase())
    assert stale["verdict"] == "BLOCKED" and stale["reason"] == "data_stale"
