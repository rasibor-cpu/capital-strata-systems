"""Offline tests for the live-data shadow paper runner.

All market data here is injected through a fake fetcher. These synthetic prices
exist only to exercise control flow; they are never evidence of performance.
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.shadow_paper import controls
from backend.shadow_paper.controls import SafetyPreflightError, load_r14f
from backend.shadow_paper.evidence import summarize
from backend.shadow_paper.journal import EventJournal, JournalIntegrityError, read_journal
from backend.shadow_paper.market_data import (
    MAX_QUOTE_AGE_SECONDS,
    CoinbasePublicTicker,
    MarketQuote,
    validate_ticker,
)
from backend.shadow_paper.runner import (
    BAR_INTERVAL_SECONDS,
    JOURNAL_FILENAME,
    ShadowPaperRunner,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float = BAR_INTERVAL_SECONDS) -> None:
        self.now += timedelta(seconds=seconds)


class FakeFeed:
    """Deterministic test feed: steady uptrend unless overridden per call."""

    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.trade_ids: dict[str, int] = {}
        self.step = 0
        self.age_seconds = 2.0
        self.override = None  # callable(url) -> (status, body) or None
        self.repeat_trade_id = False
        self.trend = 0.0004

    def __call__(self, url: str, timeout: float):
        if self.override is not None:
            return self.override(url)
        key = "BTC" if "BTC" in url else "ETH"
        if not self.repeat_trade_id or key not in self.trade_ids:
            self.trade_ids[key] = self.trade_ids.get(key, 1000) + 1
            self.step += 1
        base = 60000.0 if key == "BTC" else 2500.0
        price = base * (1.0 + self.trend * self.step)
        traded_at = self.clock() - timedelta(seconds=self.age_seconds)
        return 200, {
            "price": f"{price:.2f}",
            "bid": f"{price - 0.5:.2f}",
            "ask": f"{price + 0.5:.2f}",
            "time": traded_at.isoformat().replace("+00:00", "Z"),
            "trade_id": self.trade_ids[key],
        }


@pytest.fixture(autouse=True)
def _no_broker_modules_loaded(monkeypatch):
    # Other tests in the same session may import broker modules; hide them so the
    # runner's own "no broker module" preflight evaluates this runner only.
    for name in controls.forbidden_modules_loaded():
        monkeypatch.delitem(sys.modules, name)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def feed(clock) -> FakeFeed:
    return FakeFeed(clock)


def make_runner(tmp_path: Path, clock: Clock, feed: FakeFeed, environ=None, **kwargs) -> ShadowPaperRunner:
    return ShadowPaperRunner(
        tmp_path / "evidence",
        operator_id="test-operator",
        ticker=CoinbasePublicTicker(fetcher=feed, clock=clock),
        clock=clock,
        commit_sha="test-sha",
        environ={} if environ is None else environ,
        repo_root=kwargs.pop("repo_root", tmp_path),
        **kwargs,
    )


def journal_records(runner: ShadowPaperRunner) -> list[dict]:
    return read_journal(runner.evidence_dir / JOURNAL_FILENAME)


def types(records: list[dict]) -> list[str]:
    return [r["type"] for r in records]


def run_cycles(runner: ShadowPaperRunner, clock: Clock, n: int) -> None:
    for _ in range(n):
        clock.advance()
        runner.run_cycle()


def run_until_open(runner: ShadowPaperRunner, clock: Clock, limit: int = 120) -> None:
    for _ in range(limit):
        clock.advance()
        runner.run_cycle()
        if runner.positions:
            return
    raise AssertionError("no paper position opened in test scenario")


# ---------------------------------------------------------------------------
# market data validation (stale / missing / invalid / unverifiable)
# ---------------------------------------------------------------------------

def _body(**overrides):
    body = {"price": "100.00", "bid": "99.99", "ask": "100.01", "time": "2026-10-14T12:00:00Z", "trade_id": 7}
    body.update(overrides)
    return body


def _validate(body, status=200, received=T0 + timedelta(seconds=1)):
    return validate_ticker(
        instrument="BTC-USD", url="https://example.invalid", http_status=status,
        body=body, received_at=received, fetch_latency_ms=10.0,
    )


def test_fresh_valid_quote_is_accepted_with_provenance():
    quote = _validate(_body())
    assert isinstance(quote, MarketQuote)
    assert quote.source == "COINBASE_EXCHANGE_PUBLIC_TICKER"
    assert quote.trade_id == 7 and quote.age_seconds == 1.0
    assert quote.exchange_time_utc == "2026-10-14T12:00:00Z"


@pytest.mark.parametrize(
    "body,status,received,reason",
    [
        (_body(), 200, T0 + timedelta(seconds=MAX_QUOTE_AGE_SECONDS + 1), "STALE_PRICE"),
        (_body(), 200, T0 - timedelta(seconds=30), "FUTURE_TIMESTAMP"),
        (_body(time=None), 200, T0, "MISSING_FIELD"),
        (_body(price=""), 200, T0, "MISSING_FIELD"),
        (_body(time="2026-10-14 12:00:00"), 200, T0, "UNVERIFIABLE_TIMESTAMP"),
        (_body(time="yesterday"), 200, T0, "UNVERIFIABLE_TIMESTAMP"),
        (_body(price="abc"), 200, T0, "INVALID_PRICE"),
        (_body(price="-5"), 200, T0, "INVALID_PRICE"),
        (_body(price="nan"), 200, T0, "INVALID_PRICE"),
        (_body(bid="101", ask="100"), 200, T0, "CROSSED_BOOK"),
        (_body(bid="90", ask="110", price="100"), 200, T0, "ABNORMAL_SPREAD"),
        (_body(price="105"), 200, T0, "TRADE_FAR_FROM_QUOTE"),
        (_body(trade_id="x"), 200, T0, "INVALID_TRADE_ID"),
        (_body(), 503, T0, "HTTP_STATUS"),
        ("not-json", 200, T0, "MALFORMED_BODY"),
    ],
)
def test_invalid_or_stale_quotes_are_rejected(body, status, received, reason):
    result = _validate(body, status=status, received=received)
    assert not isinstance(result, MarketQuote)
    assert result.reason == reason


def test_fetch_exception_becomes_rejection_not_crash(clock):
    def boom(url, timeout):
        raise ConnectionError("network down")

    result = CoinbasePublicTicker(fetcher=boom, clock=clock).fetch("BTC-USD")
    assert result.reason == "FETCH_ERROR"


def test_runner_never_feeds_a_stale_price_to_the_engine(tmp_path, clock, feed):
    runner = make_runner(tmp_path, clock, feed)
    runner.start()
    run_cycles(runner, clock, 3)
    bars_before = dict(runner.engine.bars_seen_by_instrument)

    feed.age_seconds = MAX_QUOTE_AGE_SECONDS + 30
    run_cycles(runner, clock, 2)

    assert runner.engine.bars_seen_by_instrument == bars_before
    tail = journal_records(runner)[-6:]
    assert "MARKET_TICK" not in types(tail) and "GATE_DECISION" not in types(tail)
    rejected = [r for r in tail if r["type"] == "MARKET_DATA_REJECTED"]
    assert len(rejected) == 4 and {r["payload"]["reason"] for r in rejected} == {"STALE_PRICE"}
    assert summarize(runner.evidence_dir / JOURNAL_FILENAME)["gates"]["decisions_on_stale_or_unknown_price"] == 0


# ---------------------------------------------------------------------------
# safety flags and required controls
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "environ",
    [
        {"COINBASE_ENABLE_LIVE_ORDERS": "true"},
        {"CSS_EXECUTION_ALLOWED": "1"},
        {"CSS_BROKER_EXECUTION_ARMED": "yes"},
        {"OANDA_ENV": "live"},
        {"CSS_LIVE_TRADING_BLOCKED": "false"},
        {"CSS_ADVISORY_ONLY": "0"},
        {"CSS_TEST_MODE": "1"},
        {"CSS_BASELINE_NOTIONAL_PCT": "0.5"},
        {"CSS_MIN_SIGNAL_STRENGTH": "0.1"},
    ],
)
def test_refuses_to_start_when_unsafe(tmp_path, clock, feed, environ):
    runner = make_runner(tmp_path, clock, feed, environ=environ)
    with pytest.raises(SafetyPreflightError):
        runner.start()
    recorded = types(journal_records(runner))
    assert recorded == ["RUN_STARTED", "SAFETY_PREFLIGHT_FAILED"]


def test_refuses_when_repo_env_file_enables_live_orders(tmp_path, clock, feed):
    (tmp_path / ".env").write_text("COINBASE_ENABLE_LIVE_ORDERS=true\n", encoding="utf-8")
    runner = make_runner(tmp_path, clock, feed)
    with pytest.raises(SafetyPreflightError) as exc:
        runner.start()
    assert any(".env" in f for f in exc.value.failures)


def test_refuses_when_broker_module_is_loaded(tmp_path, clock, feed, monkeypatch):
    monkeypatch.setitem(sys.modules, "engine.brokers.fake_broker", object())
    runner = make_runner(tmp_path, clock, feed)
    with pytest.raises(SafetyPreflightError) as exc:
        runner.start()
    assert any("engine.brokers.fake_broker" in f for f in exc.value.failures)


def test_preflight_passes_on_v1_controls_and_records_every_check(tmp_path, clock, feed):
    runner = make_runner(tmp_path, clock, feed)
    preflight = runner.start()
    assert preflight["passed"] is True
    assert set(preflight["checks"]) >= {
        "live_execution_flags", "test_mode", "threshold_overrides", "engine_constants",
        "anti_bleed_guard", "r7_unified_trade_gate", "r14f_profitability_gate",
        "regime_gate", "no_broker_modules", "min_signal_strength",
    }
    assert runner.engine.execution_gate.anti_bleed_guard.minimum_profitable_trade_size == 50.0
    assert controls.forbidden_modules_loaded() == []


def test_mid_run_live_flag_halts_runner(tmp_path, clock, feed):
    environ: dict[str, str] = {}
    runner = make_runner(tmp_path, clock, feed, environ=environ)
    runner.start()
    run_cycles(runner, clock, 1)
    environ["COINBASE_ENABLE_LIVE_ORDERS"] = "true"
    with pytest.raises(SafetyPreflightError):
        run_cycles(runner, clock, 1)
    assert types(journal_records(runner))[-1] == "SAFETY_HALT"


def test_weakened_anti_bleed_threshold_halts_runner(tmp_path, clock, feed):
    runner = make_runner(tmp_path, clock, feed)
    runner.start()
    runner.engine.execution_gate.anti_bleed_guard.minimum_profitable_trade_size = 10.0
    with pytest.raises(SafetyPreflightError) as exc:
        run_cycles(runner, clock, 1)
    assert any("minimum_profitable_trade_size" in f for f in exc.value.failures)


def test_unavailable_control_fails_closed(tmp_path, clock, feed):
    runner = make_runner(tmp_path, clock, feed)
    runner.start()
    del runner.engine.execution_gate.anti_bleed_guard
    with pytest.raises(SafetyPreflightError):
        run_cycles(runner, clock, 1)


def test_r14f_loaded_verbatim_from_dashboard_with_v1_thresholds():
    evaluator = load_r14f("SAFE")
    assert {m: evaluator.threshold_for_mode(m) for m in controls.EXPECTED_R14F_THRESHOLDS} == controls.EXPECTED_R14F_THRESHOLDS
    result = evaluator.evaluate(symbol="BTC-USD", asset_class="CRYPTO", sig=12.0, prob=0.5)
    assert result["threshold"] == pytest.approx(17.2)  # SAFE 17.5 with CRYPTO -0.30
    assert result["passed"] is False and result["composite"] == pytest.approx(14.5)


def test_runner_contains_no_order_submission_capability():
    sources = list((REPO_ROOT / "backend" / "shadow_paper").glob("*.py"))
    sources.append(REPO_ROOT / "scripts" / "css_shadow_paper_runner.py")
    forbidden_calls = {"submit_order", "place_order", "create_order", "market_order", "limit_order", "post"}
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for name in names:
                    assert not any(
                        name == p or name.startswith(p + ".") for p in controls.FORBIDDEN_MODULE_PREFIXES
                    ), f"{path.name} imports {name}"
            if isinstance(node, ast.Attribute) and node.attr in forbidden_calls:
                pytest.fail(f"{path.name} references .{node.attr}")


# ---------------------------------------------------------------------------
# gates: every stage recorded, all must pass, rejection never produces an order
# ---------------------------------------------------------------------------

def test_full_pipeline_records_gates_and_simulated_fills(tmp_path, clock, feed):
    runner = make_runner(tmp_path, clock, feed)
    runner.start()
    run_until_open(runner, clock)
    records = journal_records(runner)

    opened = [r for r in records if r["type"] == "PAPER_POSITION_OPENED"][-1]["payload"]
    decision = [r for r in records if r["type"] == "GATE_DECISION" and r["payload"]["final"] == "ENTRY_ALLOWED"][-1]
    assert [s["stage"] for s in decision["payload"]["stages"]] == list(
        __import__("backend.shadow_paper.evidence", fromlist=["x"]).REQUIRED_ENTRY_STAGES
    )
    assert all(s["passed"] for s in decision["payload"]["stages"])
    assert opened["notional"] >= 50.0
    fill = [r for r in records if r["type"] == "SIMULATED_FILL"][-1]["payload"]
    assert fill["fill_basis"] == "SIMULATED" and fill["reference_basis"] == "REAL_MARKET"
    assert fill["cost_basis"] == "ESTIMATED" and fill["reference_side"] == "ask"
    intent = [r for r in records if r["type"] == "PAPER_ORDER_INTENT"][-1]["payload"]
    assert intent["order_route"] == "NONE_SIMULATED_ONLY"

    summary = summarize(runner.evidence_dir / JOURNAL_FILENAME)
    assert summary["gates"]["opens_without_full_gate_pass"] == []
    assert summary["gates"]["opens_below_anti_bleed_minimum"] == []


def _warm(runner, clock, cycles=45):
    runner.start()
    run_cycles(runner, clock, cycles)


def test_r7_rejection_blocks_entry_before_execution_gate(tmp_path, clock, feed, monkeypatch):
    runner = make_runner(tmp_path, clock, feed)
    _warm(runner, clock, 1)

    from backend.governance.css_unified_trade_gate import GateDecision

    monkeypatch.setattr(runner.r7, "approve_trade", lambda **kw: GateDecision(False, "rejected: test", "SAFE", 0.0, {}))
    calls = []
    monkeypatch.setattr(runner.engine.execution_gate, "evaluate_trade", lambda **kw: calls.append(kw) or {})
    run_cycles(runner, clock, 60)

    records = journal_records(runner)
    assert "PAPER_ORDER_INTENT" not in types(records) and not runner.positions
    blocked = {r["payload"]["blocked_by"] for r in records if r["type"] == "GATE_DECISION"}
    assert "r7_unified_trade_gate" in blocked
    assert calls == []  # AntiBleed cooldown state is not touched by R7-rejected candidates


def test_r14f_rejection_blocks_entry(tmp_path, clock, feed, monkeypatch):
    runner = make_runner(tmp_path, clock, feed)
    _warm(runner, clock, 1)
    import dataclasses

    blocked = dataclasses.replace(runner.r14f, _allows=lambda *args: (False, 0.0, 17.2))
    monkeypatch.setattr(runner, "r14f", blocked)
    run_cycles(runner, clock, 60)
    records = journal_records(runner)
    assert "PAPER_ORDER_INTENT" not in types(records)
    assert "r14f_profitability_gate" in {r["payload"]["blocked_by"] for r in records if r["type"] == "GATE_DECISION"}


def test_execution_gate_block_prevents_order_and_records_reason(tmp_path, clock, feed, monkeypatch):
    runner = make_runner(tmp_path, clock, feed)
    _warm(runner, clock, 1)
    monkeypatch.setattr(
        runner.engine.execution_gate, "evaluate_trade",
        lambda **kw: {"decision": {"final": "BLOCK"}, "reason": "anti_bleed_guard:trade_size_too_small",
                      "debug": {"anti_bleed_guard": {"approved": False, "reason": "trade_size_too_small"}}},
    )
    run_cycles(runner, clock, 60)
    records = journal_records(runner)
    assert "PAPER_ORDER_INTENT" not in types(records)
    reasons = [r["payload"] for r in records if r["type"] == "GATE_DECISION" and r["payload"]["blocked_by"] == "anti_bleed_guard"]
    assert reasons, "AntiBleedGuard rejection must be journaled"


def test_portfolio_cap_blocks_second_concurrent_crypto_position(tmp_path, clock, feed):
    runner = make_runner(tmp_path, clock, feed)
    runner.start()
    run_cycles(runner, clock, 60)
    records = journal_records(runner)
    assert len(runner.positions) <= 1  # 8% notional each vs 10% CRYPTO class cap
    blocked = {r["payload"]["blocked_by"] for r in records if r["type"] == "GATE_DECISION"}
    assert "portfolio_capital_controller" in blocked


# ---------------------------------------------------------------------------
# journal integrity
# ---------------------------------------------------------------------------

def _journal(tmp_path, n=3) -> Path:
    path = tmp_path / "j.jsonl"
    journal = EventJournal(path, run_id="r", commit_sha="c")
    for i in range(n):
        journal.append("E", {"i": i}, dedupe_key=f"k{i}")
    return path


def test_journal_round_trip_verifies(tmp_path):
    path = _journal(tmp_path)
    records = read_journal(path)
    assert [r["seq"] for r in records] == [1, 2, 3]
    assert records[1]["prev_hash"] == records[0]["hash"]


@pytest.mark.parametrize("tamper", ["edit", "delete_middle", "truncate", "reorder", "blank"])
def test_tampered_journal_is_rejected(tmp_path, tamper):
    path = _journal(tmp_path)
    lines = path.read_text(encoding="ascii").splitlines(keepends=True)
    if tamper == "edit":
        record = json.loads(lines[1])
        record["payload"]["i"] = 99
        lines[1] = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    elif tamper == "delete_middle":
        del lines[1]
    elif tamper == "truncate":
        lines[-1] = lines[-1][:20]
    elif tamper == "reorder":
        lines[0], lines[1] = lines[1], lines[0]
    elif tamper == "blank":
        lines.insert(1, "\n")
    path.write_text("".join(lines), encoding="ascii")
    with pytest.raises(JournalIntegrityError):
        read_journal(path)


def test_runner_refuses_to_start_on_corrupt_journal(tmp_path, clock, feed):
    runner = make_runner(tmp_path, clock, feed)
    runner.start()
    run_cycles(runner, clock, 2)
    runner.stop("test")
    path = runner.evidence_dir / JOURNAL_FILENAME
    path.write_bytes(path.read_bytes()[:-5])

    second = make_runner(tmp_path, clock, feed)
    with pytest.raises(JournalIntegrityError):
        second.start()
    assert summarize(path)["journal_integrity"] == "FAIL"


# ---------------------------------------------------------------------------
# duplicate events
# ---------------------------------------------------------------------------

def test_duplicate_dedupe_key_is_not_written(tmp_path):
    path = tmp_path / "j.jsonl"
    journal = EventJournal(path, run_id="r", commit_sha="c")
    assert journal.append("E", {}, dedupe_key="same") is not None
    assert journal.append("E", {}, dedupe_key="same") is None
    assert len(read_journal(path)) == 1
    reopened = EventJournal(path, run_id="r2", commit_sha="c")
    assert reopened.append("E", {}, dedupe_key="same") is None


def test_duplicate_key_forced_into_file_is_detected(tmp_path):
    path = tmp_path / "j.jsonl"
    journal = EventJournal(path, run_id="r", commit_sha="c")
    journal.append("E", {}, dedupe_key="same")
    journal._dedupe_keys.clear()  # simulate a buggy second writer
    journal.append("E", {}, dedupe_key="same")
    with pytest.raises(JournalIntegrityError, match="duplicate dedupe_key"):
        read_journal(path)


def test_repeated_exchange_trade_is_not_processed_twice(tmp_path, clock, feed):
    runner = make_runner(tmp_path, clock, feed)
    runner.start()
    run_cycles(runner, clock, 2)
    bars = dict(runner.engine.bars_seen_by_instrument)
    feed.repeat_trade_id = True
    run_cycles(runner, clock, 1)
    assert runner.engine.bars_seen_by_instrument == bars
    assert types(journal_records(runner)).count("MARKET_DATA_DUPLICATE") >= 1


# ---------------------------------------------------------------------------
# restart reconciliation
# ---------------------------------------------------------------------------

def test_restart_restores_open_position_and_never_invents_a_close(tmp_path, clock, feed):
    first = make_runner(tmp_path, clock, feed)
    first.start()
    run_until_open(first, clock)
    open_ids = {p.position_id for p in first.positions.values()}
    first.stop("simulated_crash_recovery")

    feed.override = lambda url: (503, None)  # no fresh data after restart
    second = make_runner(tmp_path, clock, feed)
    second.start()
    assert {p.position_id for p in second.positions.values()} == open_ids
    run_cycles(second, clock, 3)

    records = journal_records(second)
    restart_index = max(i for i, r in enumerate(records) if r["type"] == "RUN_STARTED")
    after = records[restart_index:]
    assert "PAPER_POSITION_CLOSED" not in types(after)
    assert "RECONCILIATION_COMPLETED" in types(after) and "POSITION_RESTORED" in types(after)
    assert second.pending_marks == {p.instrument for p in second.positions.values()}


def test_entries_blocked_until_restored_position_has_a_fresh_mark(tmp_path, clock, feed):
    first = make_runner(tmp_path, clock, feed)
    first.start()
    run_until_open(first, clock)
    restored_instrument = next(iter(first.positions))
    first.stop("restart")

    second = make_runner(tmp_path, clock, feed)
    second.start()
    records_before = len(journal_records(second))
    clock.advance()
    second.run_cycle()
    new = journal_records(second)[records_before:]
    marked = [r for r in new if r["type"] == "POSITION_MARKED"]
    assert marked and marked[0]["payload"]["instrument"] == restored_instrument
    assert second.pending_marks == set()


def test_restart_carries_realized_pnl_and_ledger_reconciles(tmp_path, clock, feed):
    first = make_runner(tmp_path, clock, feed)
    first.start()
    run_cycles(first, clock, 140)
    realized = first.realized_net
    assert types(journal_records(first)).count("PAPER_POSITION_CLOSED") >= 1 and realized != 0.0
    first.stop("restart")

    second = make_runner(tmp_path, clock, feed)
    second.start()
    assert second.realized_net == pytest.approx(realized)
    run_cycles(second, clock, 2)
    summary = summarize(second.evidence_dir / JOURNAL_FILENAME)
    assert summary["journal_integrity"] == "PASS"
    assert summary["ledger"]["reconciliation_difference"] <= 0.01
    assert summary["ledger"]["restarts"] == 1
    assert summary["lifecycle"]["orphan_closes"] == [] and summary["lifecycle"]["duplicate_closes"] == []
    assert summary["lifecycle"]["arithmetic_errors"] == []
    assert summary["lifecycle"]["closes_without_real_tick"] == []


def test_restart_with_changed_config_is_refused(tmp_path, clock, feed):
    first = make_runner(tmp_path, clock, feed)
    first.start()
    first.stop("restart")
    second = make_runner(tmp_path, clock, feed, starting_equity=5000.0)
    with pytest.raises(SafetyPreflightError):
        second.start()


def test_cli_verify_reports_integrity(tmp_path, clock, feed):
    runner = make_runner(tmp_path, clock, feed)
    runner.start()
    run_cycles(runner, clock, 2)
    runner.stop("done")

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import css_shadow_paper_runner as cli
    finally:
        sys.path.pop(0)
    assert cli.main(["verify", "--evidence-dir", str(runner.evidence_dir)]) == 0
    path = runner.evidence_dir / JOURNAL_FILENAME
    path.write_text(path.read_text(encoding="ascii").replace('"cycle":1', '"cycle":7', 1), encoding="ascii")
    assert cli.main(["verify", "--evidence-dir", str(runner.evidence_dir)]) == 3


def test_feed_probe_journals_without_feeding_engine(tmp_path, clock, feed):
    runner = make_runner(tmp_path, clock, feed)
    runner.start()
    probe = runner.probe_feed()
    assert all(item["accepted"] for item in probe.values())
    assert runner.engine.bars_seen_by_instrument == {}
    feed.override = lambda url: (403, None)
    assert not any(item["accepted"] for item in runner.probe_feed().values())
    assert types(journal_records(runner)).count("FEED_PROBE") == 4


def test_preflight_only_start_is_not_counted_as_restart(tmp_path, clock, feed):
    preflight = make_runner(tmp_path, clock, feed)
    preflight.start()
    preflight.stop("preflight_only")
    runner = make_runner(tmp_path, clock, feed)
    runner.start()
    run_cycles(runner, clock, 2)
    ledger = summarize(runner.evidence_dir / JOURNAL_FILENAME)["ledger"]
    assert ledger["restarts"] == 0 and ledger["run_sessions_with_cycles"] == 1
    assert ledger["reconciliations_completed"] == ledger["starts_passing_preflight"] == 2
