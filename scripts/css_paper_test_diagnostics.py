from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

TRADE_LOG_PATH = ARTIFACTS_DIR / "css_extended_paper_test_trades.jsonl"
SUMMARY_PATH = ARTIFACTS_DIR / "css_extended_paper_test_summary.json"
INTELLIGENCE_LOG_PATH = ARTIFACTS_DIR / "css_trade_intelligence_log.jsonl"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def pct(value: float) -> str:
    return f"{value:.2%}"


def print_header(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def summarize_summary(summary: Dict[str, Any]) -> None:
    print_header("CSS PAPER TEST SUMMARY")

    if not summary:
        print("Summary file not found or unreadable.")
        return

    config = summary.get("config", {}) if isinstance(summary.get("config"), dict) else {}

    print(f"Timestamp UTC        : {summary.get('timestamp_utc', 'N/A')}")
    print(f"Cycle No             : {summary.get('cycle_no', 'N/A')}")
    print(f"Open Positions       : {summary.get('open_positions', 'N/A')}")
    print(f"Closed Trades        : {summary.get('closed_trades', 'N/A')}")
    print(f"Wins                 : {summary.get('wins', 'N/A')}")
    print(f"Losses               : {summary.get('losses', 'N/A')}")
    print(f"Win Rate             : {summary.get('win_rate', 'N/A')}")
    print(f"Realized PnL USD     : {summary.get('realized_pnl_usd', 'N/A')}")
    print(f"Gross Profit USD     : {summary.get('gross_profit_usd', 'N/A')}")
    print(f"Gross Loss USD       : {summary.get('gross_loss_usd', 'N/A')}")
    print(f"Starting Capital USD : {summary.get('starting_capital_usd', 'N/A')}")
    print(f"Estimated Equity USD : {summary.get('estimated_equity_usd', 'N/A')}")

    print()
    print("ACTIVE CONFIG")
    print("-" * 70)
    for k in sorted(config.keys()):
        print(f"{k:22}: {config[k]}")


def summarize_trade_log(rows: List[Dict[str, Any]]) -> None:
    print_header("TRADE LOG ANALYSIS")

    if not rows:
        print("No trade log rows found yet.")
        return

    opens = [r for r in rows if str(r.get("event", "")).upper() == "OPEN"]
    closes = [r for r in rows if str(r.get("event", "")).upper() == "CLOSE"]

    exit_reason_counter = Counter(str(r.get("exit_reason", "UNKNOWN")).upper() for r in closes)
    regime_counter = Counter(str(r.get("regime", "UNKNOWN")).upper() for r in rows if r.get("regime") is not None)
    symbol_counter = Counter(str(r.get("symbol", "")).upper() for r in rows if r.get("symbol"))

    pnl_values = [safe_float(r.get("pnl_usd")) for r in closes]
    pnl_pct_values = [safe_float(r.get("pnl_pct")) for r in closes if r.get("pnl_pct") is not None]
    hold_minutes_values = [safe_float(r.get("hold_minutes")) for r in closes if r.get("hold_minutes") is not None]
    cycles_held_values = [safe_float(r.get("cycles_held")) for r in closes if r.get("cycles_held") is not None]

    print(f"Open events  : {len(opens)}")
    print(f"Close events : {len(closes)}")
    print(f"Symbols seen : {len(symbol_counter)}")

    if closes:
        wins = sum(1 for x in pnl_values if x > 0)
        losses = sum(1 for x in pnl_values if x < 0)
        flats = sum(1 for x in pnl_values if x == 0)
        total = len(closes)

        print(f"Wins         : {wins}")
        print(f"Losses       : {losses}")
        print(f"Flat closes  : {flats}")
        print(f"Win rate     : {pct(wins / total) if total else '0.00%'}")
        print(f"Avg pnl_usd  : {sum(pnl_values) / total:.4f}")
        print(f"Net pnl_usd  : {sum(pnl_values):.4f}")

        if pnl_pct_values:
            print(f"Avg pnl_pct  : {sum(pnl_pct_values) / len(pnl_pct_values):.6f}")

        if hold_minutes_values:
            print(f"Avg hold min : {sum(hold_minutes_values) / len(hold_minutes_values):.2f}")

        if cycles_held_values:
            print(f"Avg hold cyc : {sum(cycles_held_values) / len(cycles_held_values):.2f}")

    print()
    print("EXIT REASONS")
    print("-" * 70)
    if exit_reason_counter:
        for reason, count in exit_reason_counter.most_common():
            print(f"{reason:25} {count}")
    else:
        print("No CLOSE events yet.")

    print()
    print("REGIME COUNTS")
    print("-" * 70)
    if regime_counter:
        for regime, count in regime_counter.most_common():
            print(f"{regime:25} {count}")
    else:
        print("No regime data yet.")

    print()
    print("TOP SYMBOLS")
    print("-" * 70)
    if symbol_counter:
        for symbol, count in symbol_counter.most_common(10):
            print(f"{symbol:15} {count}")
    else:
        print("No symbol data yet.")

    print()
    print("RECENT TRADE EVENTS")
    print("-" * 70)
    for row in rows[-10:]:
        event = str(row.get("event", "")).upper()
        symbol = str(row.get("symbol", ""))
        timestamp = str(row.get("timestamp_utc", ""))
        if event == "OPEN":
            print(
                f"{timestamp} | OPEN  | {symbol:10} | "
                f"trade={safe_float(row.get('trade_score')):.4f} | "
                f"pressure={safe_float(row.get('pressure_score')):.4f} | "
                f"accel={safe_float(row.get('pressure_acceleration')):.4f} | "
                f"regime={str(row.get('regime', ''))}"
            )
        elif event == "CLOSE":
            print(
                f"{timestamp} | CLOSE | {symbol:10} | "
                f"pnl_usd={safe_float(row.get('pnl_usd')):.4f} | "
                f"reason={str(row.get('exit_reason', 'UNKNOWN'))} | "
                f"held={safe_float(row.get('cycles_held')):.0f}"
            )
        else:
            print(f"{timestamp} | {event:5} | {symbol:10}")


def summarize_intelligence_log(rows: List[Dict[str, Any]]) -> None:
    print_header("TRADE INTELLIGENCE LOG ANALYSIS")

    if not rows:
        print("No intelligence log rows found yet.")
        return

    opens = [r for r in rows if str(r.get("event", "")).upper() == "OPEN"]
    closes = [r for r in rows if str(r.get("event", "")).upper() == "CLOSE"]

    open_scores = [safe_float(r.get("score")) for r in opens if r.get("score") is not None]
    open_vwap_dist = [safe_float(r.get("distance_to_vwap_pct")) for r in opens if r.get("distance_to_vwap_pct") is not None]
    open_spreads = [safe_float(r.get("spread_pct")) for r in opens if r.get("spread_pct") is not None]
    close_pnl_pct = [safe_float(r.get("pnl_pct")) for r in closes if r.get("pnl_pct") is not None]

    print(f"Open events  : {len(opens)}")
    print(f"Close events : {len(closes)}")

    if open_scores:
        print(f"Avg open score           : {sum(open_scores) / len(open_scores):.4f}")
    if open_vwap_dist:
        print(f"Avg distance_to_vwap_pct : {sum(open_vwap_dist) / len(open_vwap_dist):.6f}")
    if open_spreads:
        print(f"Avg spread_pct           : {sum(open_spreads) / len(open_spreads):.6f}")
    if close_pnl_pct:
        print(f"Avg close pnl_pct        : {sum(close_pnl_pct) / len(close_pnl_pct):.6f}")

    regime_counter = Counter(str(r.get("regime", "UNKNOWN")).upper() for r in rows if r.get("regime") is not None)

    print()
    print("INTELLIGENCE REGIMES")
    print("-" * 70)
    for regime, count in regime_counter.most_common():
        print(f"{regime:25} {count}")


def compare_log_consistency(
    trade_rows: List[Dict[str, Any]],
    intelligence_rows: List[Dict[str, Any]],
) -> None:
    print_header("LOG CONSISTENCY CHECK")

    trade_open_count = sum(1 for r in trade_rows if str(r.get("event", "")).upper() == "OPEN")
    trade_close_count = sum(1 for r in trade_rows if str(r.get("event", "")).upper() == "CLOSE")

    intel_open_count = sum(1 for r in intelligence_rows if str(r.get("event", "")).upper() == "OPEN")
    intel_close_count = sum(1 for r in intelligence_rows if str(r.get("event", "")).upper() == "CLOSE")

    print(f"Trade log opens         : {trade_open_count}")
    print(f"Trade log closes        : {trade_close_count}")
    print(f"Intelligence log opens  : {intel_open_count}")
    print(f"Intelligence log closes : {intel_close_count}")

    if trade_open_count != intel_open_count or trade_close_count != intel_close_count:
        print("Warning: log counts differ. This may be normal during transition runs.")
    else:
        print("Counts look aligned.")


def symbol_pnl_breakdown(rows: List[Dict[str, Any]]) -> None:
    print_header("SYMBOL PNL BREAKDOWN")

    closes = [r for r in rows if str(r.get("event", "")).upper() == "CLOSE"]
    if not closes:
        print("No CLOSE events yet.")
        return

    by_symbol: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "net_pnl": 0.0})

    for r in closes:
        symbol = str(r.get("symbol", "UNKNOWN")).upper()
        pnl = safe_float(r.get("pnl_usd"))
        by_symbol[symbol]["count"] += 1
        by_symbol[symbol]["net_pnl"] += pnl
        if pnl > 0:
            by_symbol[symbol]["wins"] += 1
        elif pnl < 0:
            by_symbol[symbol]["losses"] += 1

    ranked = sorted(by_symbol.items(), key=lambda kv: kv[1]["net_pnl"], reverse=True)

    for symbol, stats in ranked[:15]:
        count = int(stats["count"])
        wins = int(stats["wins"])
        win_rate = (wins / count) if count else 0.0
        print(
            f"{symbol:12} trades={count:3d} "
            f"wins={wins:3d} "
            f"losses={int(stats['losses']):3d} "
            f"win_rate={pct(win_rate):>8} "
            f"net_pnl={stats['net_pnl']:.4f}"
        )


def main() -> None:
    summary = load_json(SUMMARY_PATH)
    trade_rows = load_jsonl(TRADE_LOG_PATH)
    intelligence_rows = load_jsonl(INTELLIGENCE_LOG_PATH)

    summarize_summary(summary)
    summarize_trade_log(trade_rows)
    summarize_intelligence_log(intelligence_rows)
    compare_log_consistency(trade_rows, intelligence_rows)
    symbol_pnl_breakdown(trade_rows)

    print()
    print("=" * 70)
    print("FILES")
    print("=" * 70)
    print(f"Summary            : {SUMMARY_PATH}")
    print(f"Trade log          : {TRADE_LOG_PATH}")
    print(f"Intelligence log   : {INTELLIGENCE_LOG_PATH}")


if __name__ == "__main__":
    main()