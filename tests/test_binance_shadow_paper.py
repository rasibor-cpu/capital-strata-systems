"""Offline tests: Binance public market data through the shadow paper runner.

Synthetic prices come from an in-memory fake fetcher and only exercise control flow.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import pytest

from backend.shadow_paper import controls
from backend.shadow_paper.binance_market_data import (
    PUBLIC_DATA_BASE_URL,
    SOURCE_NAME,
    BinancePublicTicker,
)
from backend.shadow_paper.controls import SafetyPreflightError
from backend.shadow_paper.evidence import REQUIRED_ENTRY_STAGES, summarize
from backend.shadow_paper.journal import read_journal
from backend.shadow_paper.market_data import MAX_QUOTE_AGE_SECONDS, MarketQuote
from backend.shadow_paper.runner import BAR_INTERVAL_SECONDS, JOURNAL_FILENAME, ShadowPaperRunner

T0 = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


class FakeBinancePublic:
    def __init__(self, clock: Clock):
        self.clock = clock
        self.step = 0
        self.trade_ids = {"BTCUSDT": 5000, "ETHUSDT": 7000}
        self.age_seconds = 1.0
        self.status = 200
        self.urls: list[str] = []

    def __call__(self, url, timeout):
        self.urls.append(url)
        if self.status != 200:
            return self.status, {"code": 0, "msg": "restricted"}
        symbol = "BTCUSDT" if "BTCUSDT" in url else "ETHUSDT"
        base = 60000.0 if symbol == "BTCUSDT" else 2500.0
        if "/trades" in url:
            self.step += 1
            self.trade_ids[symbol] += 1
        price = base * (1.0 + 0.0004 * self.step)
        if "/trades" in url:
            ms = int((self.clock() - timedelta(seconds=self.age_seconds)).timestamp() * 1000)
            return 200, [{"id": self.trade_ids[symbol], "price": f"{price:.2f}", "qty": "0.01", "time": ms}]
        return 200, {"symbol": symbol, "bidPrice": f"{price - 0.01:.2f}", "askPrice": f"{price + 0.01:.2f}"}


@pytest.fixture(autouse=True)
def _hide_broker_modules(monkeypatch):
    for name in controls.forbidden_modules_loaded():
        monkeypatch.delitem(sys.modules, name)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def fake(clock):
    return FakeBinancePublic(clock)


def ticker(fake, clock):
    return BinancePublicTicker(fetcher=fake, clock=clock)


def test_valid_binance_quote_has_provenance(fake, clock):
    quote = ticker(fake, clock).fetch("BTCUSDT")
    assert isinstance(quote, MarketQuote)
    assert quote.source == SOURCE_NAME and quote.instrument == "BTCUSDT"
    assert quote.bid < quote.ask and quote.age_seconds == pytest.approx(1.0, abs=0.01)
    assert all(u.startswith(PUBLIC_DATA_BASE_URL) for u in fake.urls)


def test_http_451_is_restricted_location_with_no_fallback(fake, clock):
    fake.status = 451
    result = ticker(fake, clock).fetch("ETHUSDT")
    assert result.reason == "RESTRICTED_LOCATION"
    assert len(fake.urls) == 2 and all(u.startswith(PUBLIC_DATA_BASE_URL) for u in fake.urls)


def test_stale_and_unsupported_quotes_rejected(fake, clock):
    fake.age_seconds = MAX_QUOTE_AGE_SECONDS + 5
    assert ticker(fake, clock).fetch("BTCUSDT").reason == "STALE_PRICE"
    assert ticker(fake, clock).fetch("BTC-USD").reason == "UNSUPPORTED_INSTRUMENT"


def test_malformed_and_mismatched_responses_rejected(clock):
    def wrong_symbol(url, timeout):
        if "/trades" in url:
            return 200, [{"id": 1, "price": "1", "time": int(clock().timestamp() * 1000)}]
        return 200, {"symbol": "XRPUSDT", "bidPrice": "1", "askPrice": "1"}

    assert BinancePublicTicker(fetcher=wrong_symbol, clock=clock).fetch("BTCUSDT").reason == "MALFORMED_BODY"
    assert BinancePublicTicker(fetcher=lambda u, t: (200, []), clock=clock).fetch("BTCUSDT").reason == "MALFORMED_BODY"


def test_only_public_market_data_host_allowed():
    with pytest.raises(ValueError):
        BinancePublicTicker(base_url="https://api.binance.com")


def make_runner(tmp_path, fake, clock, **kw):
    return ShadowPaperRunner(
        tmp_path / "ev", operator_id="op", ticker=ticker(fake, clock), clock=clock,
        commit_sha="test", environ={}, repo_root=tmp_path, **kw,
    )


def test_runner_uses_binance_symbols_and_records_source(tmp_path, fake, clock):
    runner = make_runner(tmp_path, fake, clock)
    runner.start()
    config = read_journal(runner.evidence_dir / JOURNAL_FILENAME)[0]["payload"]["config"]
    assert config["instruments"] == ["BTCUSDT", "ETHUSDT"]
    assert config["market_data_source"] == SOURCE_NAME


def test_binance_prices_go_through_every_gate_before_a_simulated_fill(tmp_path, fake, clock):
    runner = make_runner(tmp_path, fake, clock)
    runner.start()
    for _ in range(120):
        clock.now += timedelta(seconds=BAR_INTERVAL_SECONDS)
        runner.run_cycle()
        if runner.positions:
            break
    assert runner.positions, "expected a simulated paper position in the trend scenario"
    records = read_journal(runner.evidence_dir / JOURNAL_FILENAME)
    allowed = [r for r in records if r["type"] == "GATE_DECISION" and r["payload"]["final"] == "ENTRY_ALLOWED"][-1]
    assert [s["stage"] for s in allowed["payload"]["stages"]] == list(REQUIRED_ENTRY_STAGES)
    fill = [r for r in records if r["type"] == "SIMULATED_FILL"][-1]["payload"]
    assert fill["fill_basis"] == "SIMULATED" and fill["reference_basis"] == "REAL_MARKET"
    summary = summarize(runner.evidence_dir / JOURNAL_FILENAME)
    assert summary["gates"]["opens_without_full_gate_pass"] == []
    assert summary["gates"]["opens_below_anti_bleed_minimum"] == []


def test_runner_refuses_when_authenticated_binance_client_is_loaded(tmp_path, fake, clock, monkeypatch):
    monkeypatch.setitem(sys.modules, "backend.binance_readonly.client", object())
    runner = make_runner(tmp_path, fake, clock)
    with pytest.raises(SafetyPreflightError) as exc:
        runner.start()
    assert any("backend.binance_readonly" in f for f in exc.value.failures)


def test_runner_rejects_instruments_from_another_source(tmp_path, fake, clock):
    with pytest.raises(ValueError):
        make_runner(tmp_path, fake, clock, instruments=("BTC-USD",))


def test_default_source_is_still_coinbase(tmp_path):
    runner = ShadowPaperRunner(tmp_path / "ev", operator_id="op", commit_sha="t", environ={}, repo_root=tmp_path)
    assert runner.instruments == ("BTC-USD", "ETH-USD")
