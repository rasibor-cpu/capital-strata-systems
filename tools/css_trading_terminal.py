from __future__ import annotations

import json
import math
import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "backend" / "state"
AUDIT_DIR = PROJECT_ROOT / "audit_logs"

SPOT_POSITION_FILE = STATE_DIR / "spot_position.json"
TRADES_FILE = AUDIT_DIR / "trades.jsonl"
RUN_STATE_FILE = STATE_DIR / "run_state.json"
ACCOUNT_STATE_FILE = STATE_DIR / "account_state.json"

REFRESH_SECONDS = 30
EQUITY_CHART_WIDTH = 34
EQUITY_CHART_HEIGHT = 4
BAR_WIDTH = 18
MAX_TRADE_ROWS = 5
MAX_POSITION_ROWS = 5


@dataclass
class PositionRow:
    asset: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    instrument_class: str
    status: str


@dataclass
class TradeRow:
    ts: str
    asset: str
    side: str
    qty: float
    price: float
    gross_pnl: float
    fee: float
    net_pnl: float
    status: str


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return rows
    return rows


def _fmt_money(v: float) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.2f}"


def _fmt_num(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.2f}"
    if abs(v) >= 1:
        return f"{v:,.4f}"
    return f"{v:,.6f}"


def _fmt_pct(v: float) -> str:
    return f"{v:.2f}%"


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None

    s = str(value).strip()
    if not s:
        return None

    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _sort_ts(value: Any) -> datetime:
    dt = _parse_ts(value)
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ts_to_str(value: Any) -> str:
    dt = _parse_ts(value)
    if dt is None:
        return "-"
    try:
        return dt.astimezone().strftime("%m-%d %H:%M")
    except Exception:
        return dt.strftime("%m-%d %H:%M")


def _instrument_class(asset: str) -> str:
    asset = str(asset or "UNKNOWN").upper().strip()

    if "-" in asset:
        base = asset.split("-")[0]
    elif "/" in asset:
        base = asset.split("/")[0]
    else:
        base = asset

    crypto = {
        "BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "AVAX", "MATIC",
        "DOT", "LINK", "LTC", "BCH", "ATOM", "NEAR", "ARB", "OP"
    }
    fx = {"EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}

    if base in crypto:
        return "CRYPTO"
    if asset.endswith("PERP") or asset.endswith("FUT") or asset.endswith("FUTURES"):
        return "FUTURES"
    if asset.endswith("OPT") or asset.endswith("OPTION") or asset.endswith("OPTIONS"):
        return "OPTIONS"
    if base in fx:
        return "FX"
    return "OTHER"


def _extract_positions(raw: Dict[str, Any]) -> List[PositionRow]:
    positions: List[PositionRow] = []

    possible_lists: List[Any] = []
    for key in ("positions", "open_positions", "holdings", "assets"):
        if isinstance(raw.get(key), list):
            possible_lists = raw.get(key, [])
            break

    if not possible_lists and raw and all(isinstance(v, dict) for v in raw.values()):
        possible_lists = list(raw.values())

    for item in possible_lists:
        if not isinstance(item, dict):
            continue

        asset = str(
            item.get("asset")
            or item.get("symbol")
            or item.get("product_id")
            or item.get("pair")
            or "UNKNOWN"
        ).upper()

        side = str(item.get("side") or item.get("position_side") or "LONG").upper()

        qty = _safe_float(
            item.get("quantity")
            or item.get("qty")
            or item.get("size")
            or item.get("units")
            or item.get("filled_size")
        )

        entry = _safe_float(
            item.get("entry_price")
            or item.get("avg_entry")
            or item.get("average_entry_price")
            or item.get("avg_price")
        )

        current = _safe_float(
            item.get("current_price")
            or item.get("mark_price")
            or item.get("last_price")
            or item.get("price")
        )

        market_value = _safe_float(item.get("market_value"))
        if market_value == 0.0 and qty and current:
            market_value = qty * current

        unreal = _safe_float(item.get("unrealized_pnl") or item.get("pnl_unrealized"))
        if unreal == 0.0 and qty and entry and current:
            if side == "SHORT":
                unreal = (entry - current) * qty
            else:
                unreal = (current - entry) * qty

        unreal_pct = _safe_float(item.get("unrealized_pnl_pct"))
        if unreal_pct == 0.0 and entry > 0 and current > 0:
            if side == "SHORT":
                unreal_pct = ((entry - current) / entry) * 100.0
            else:
                unreal_pct = ((current - entry) / entry) * 100.0

        status = str(item.get("status") or "OPEN").upper()

        if qty == 0 and market_value == 0 and unreal == 0 and entry == 0 and current == 0:
            continue

        positions.append(
            PositionRow(
                asset=asset,
                side=side,
                quantity=qty,
                entry_price=entry,
                current_price=current,
                market_value=market_value,
                unrealized_pnl=unreal,
                unrealized_pnl_pct=unreal_pct,
                instrument_class=_instrument_class(asset),
                status=status,
            )
        )

    positions.sort(key=lambda p: abs(p.market_value), reverse=True)
    return positions


def _extract_cash(account_state: Dict[str, Any], run_state: Dict[str, Any]) -> float:
    account_candidates = [
        account_state.get("cash_usd"),
        account_state.get("cash"),
        account_state.get("available_cash"),
        account_state.get("usd_balance"),
        account_state.get("balance"),
    ]
    for c in account_candidates:
        if c is not None:
            return _safe_float(c)

    run_candidates = [
        run_state.get("cash_usd"),
        run_state.get("cash"),
        run_state.get("available_cash"),
        run_state.get("starting_cash"),
    ]
    for c in run_candidates:
        if c is not None:
            return _safe_float(c)

    return 0.0


def _extract_starting_capital(
    account_state: Dict[str, Any],
    run_state: Dict[str, Any],
    trades: List[Dict[str, Any]],
    cash_now: float,
) -> float:
    candidates = [
        run_state.get("starting_cash"),
        run_state.get("starting_capital"),
        account_state.get("starting_cash"),
        account_state.get("starting_capital"),
        account_state.get("initial_cash"),
    ]
    for c in candidates:
        if c is not None:
            return _safe_float(c)

    realized_net = 0.0
    for t in trades:
        realized_net += _safe_float(t.get("realized_pnl") or t.get("pnl"))
        realized_net -= _safe_float(t.get("fee") or t.get("fees"))

    inferred = cash_now - realized_net
    return inferred if inferred > 0 else cash_now


def _normalize_trade(row: Dict[str, Any]) -> TradeRow:
    ts = _ts_to_str(row.get("ts") or row.get("timestamp") or row.get("time") or row.get("created_at"))
    asset = str(row.get("asset") or row.get("symbol") or row.get("product_id") or "UNKNOWN").upper()
    side = str(row.get("side") or row.get("action") or "-").upper()
    qty = _safe_float(row.get("quantity") or row.get("qty") or row.get("size") or row.get("filled_size"))
    price = _safe_float(row.get("price") or row.get("avg_price") or row.get("filled_price"))
    gross_pnl = _safe_float(row.get("realized_pnl") or row.get("pnl"))
    fee = _safe_float(row.get("fee") or row.get("fees"))
    net_pnl = gross_pnl - fee
    status = str(row.get("status") or row.get("result") or "OK").upper()

    return TradeRow(
        ts=ts,
        asset=asset,
        side=side,
        qty=qty,
        price=price,
        gross_pnl=gross_pnl,
        fee=fee,
        net_pnl=net_pnl,
        status=status,
    )


def _realized_gross(trades: List[Dict[str, Any]]) -> float:
    return sum(_safe_float(t.get("realized_pnl") or t.get("pnl")) for t in trades)


def _total_fees(trades: List[Dict[str, Any]]) -> float:
    return sum(_safe_float(t.get("fee") or t.get("fees")) for t in trades)


def _wins_losses(trades: List[Dict[str, Any]]) -> Tuple[int, int, List[float], List[float]]:
    wins = 0
    losses = 0
    win_vals: List[float] = []
    loss_vals: List[float] = []

    for t in trades:
        pnl = _safe_float(t.get("realized_pnl") or t.get("pnl"))
        fee = _safe_float(t.get("fee") or t.get("fees"))
        net = pnl - fee
        if net > 0:
            wins += 1
            win_vals.append(net)
        elif net < 0:
            losses += 1
            loss_vals.append(abs(net))

    return wins, losses, win_vals, loss_vals


def _profit_factor(win_vals: List[float], loss_vals: List[float]) -> float:
    gross_profit = sum(win_vals)
    gross_loss = sum(loss_vals)
    if gross_loss <= 0:
        return gross_profit if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _expectancy(trades: List[Dict[str, Any]]) -> float:
    closed: List[float] = []
    for t in trades:
        pnl = _safe_float(t.get("realized_pnl") or t.get("pnl"))
        fee = _safe_float(t.get("fee") or t.get("fees"))
        net = pnl - fee
        if net != 0:
            closed.append(net)
    if not closed:
        return 0.0
    return sum(closed) / len(closed)


def _equity_series(
    starting_capital: float,
    trades: List[Dict[str, Any]],
    positions: List[PositionRow],
    cash_now: float,
) -> List[float]:
    base = starting_capital if starting_capital > 0 else cash_now
    series = [base]
    equity = base

    sorted_trades = sorted(
        trades,
        key=lambda x: _sort_ts(x.get("ts") or x.get("timestamp") or x.get("time") or x.get("created_at")),
    )

    for t in sorted_trades:
        equity += _safe_float(t.get("realized_pnl") or t.get("pnl"))
        equity -= _safe_float(t.get("fee") or t.get("fees"))
        series.append(equity)

    live_equity = cash_now + sum(p.market_value for p in positions)
    if live_equity > 0:
        series.append(live_equity)

    return series


def _max_drawdown_pct(equity: List[float]) -> float:
    if not equity:
        return 0.0

    peak = equity[0]
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            dd = ((peak - value) / peak) * 100.0
            max_dd = max(max_dd, dd)
    return max_dd


def _ascii_line_chart(values: List[float], width: int = EQUITY_CHART_WIDTH, height: int = EQUITY_CHART_HEIGHT) -> List[str]:
    if not values:
        return ["(no equity data)"]

    if len(values) == 1:
        values = [values[0], values[0]]

    if len(values) > width:
        step = len(values) / width
        sampled: List[float] = []
        i = 0.0
        while int(i) < len(values) and len(sampled) < width:
            sampled.append(values[int(i)])
            i += step
        values = sampled

    vmin = min(values)
    vmax = max(values)

    if math.isclose(vmin, vmax, rel_tol=1e-12, abs_tol=1e-12):
        return [f"(flat {_fmt_money(values[-1])})"]

    grid = [[" " for _ in range(len(values))] for _ in range(height)]

    for x, val in enumerate(values):
        y = int(round((val - vmin) / (vmax - vmin) * (height - 1)))
        y = max(0, min(height - 1, y))
        grid[height - 1 - y][x] = "•"

    lines: List[str] = []
    for idx, row in enumerate(grid):
        if idx == 0:
            label = f"{_fmt_money(vmax):>10} ┤ "
        elif idx == height - 1:
            label = f"{_fmt_money(vmin):>10} ┤ "
        else:
            label = f"{'':>10} │ "
        lines.append(label + "".join(row))

    lines.append(f"{'':>10} └" + "─" * (len(values) + 1))
    return lines


def _bar(label: str, value: int, total: int, width: int = BAR_WIDTH) -> str:
    filled = 0 if total <= 0 else int(round((value / total) * width))
    return f"{label:<5}[{'█' * filled}{' ' * (width - filled)}] {value}"


def _fit(text: str, width: int) -> str:
    text = str(text)
    if len(text) <= width:
        return text.ljust(width)
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def _table(headers: List[str], rows: List[List[str]], widths: List[int]) -> List[str]:
    out = [
        " | ".join(_fit(h, w) for h, w in zip(headers, widths)),
        "-+-".join("-" * w for w in widths),
    ]
    for row in rows:
        out.append(" | ".join(_fit(c, w) for c, w in zip(row, widths)))
    return out


def _system_health(max_dd: float, realized_net: float, unrealized: float, wins: int, losses: int) -> str:
    total = wins + losses
    win_rate = (wins / total * 100.0) if total else 0.0
    combined = realized_net + unrealized

    if max_dd >= 15:
        return "DEFENSIVE"
    if max_dd >= 8:
        return "CAUTION"
    if combined < 0 and win_rate < 45 and total >= 6:
        return "WEAK"
    return "NORMAL"


def _terminal_width(default: int = 160) -> int:
    try:
        return shutil.get_terminal_size((default, 40)).columns
    except Exception:
        return default


def _realized_by_class(trades: List[Dict[str, Any]]) -> Dict[str, float]:
    out = {
        "CRYPTO": 0.0,
        "FX": 0.0,
        "FUTURES": 0.0,
        "OPTIONS": 0.0,
        "OTHER": 0.0,
    }
    for t in trades:
        asset = str(t.get("asset") or t.get("symbol") or t.get("product_id") or "UNKNOWN").upper()
        cls = _instrument_class(asset)
        pnl = _safe_float(t.get("realized_pnl") or t.get("pnl"))
        fee = _safe_float(t.get("fee") or t.get("fees"))
        out[cls] = out.get(cls, 0.0) + pnl - fee
    return out


def _class_rollup(
    positions: List[PositionRow],
    trades: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    realized_map = _realized_by_class(trades)
    rollup: Dict[str, Dict[str, float]] = {
        "CRYPTO": {"value": 0.0, "unrealized": 0.0, "realized": 0.0, "combined": 0.0, "count": 0},
        "FX": {"value": 0.0, "unrealized": 0.0, "realized": 0.0, "combined": 0.0, "count": 0},
        "FUTURES": {"value": 0.0, "unrealized": 0.0, "realized": 0.0, "combined": 0.0, "count": 0},
        "OPTIONS": {"value": 0.0, "unrealized": 0.0, "realized": 0.0, "combined": 0.0, "count": 0},
        "OTHER": {"value": 0.0, "unrealized": 0.0, "realized": 0.0, "combined": 0.0, "count": 0},
    }

    for cls, realized in realized_map.items():
        rollup[cls]["realized"] = realized

    for p in positions:
        bucket = rollup[p.instrument_class]
        bucket["value"] += p.market_value
        bucket["unrealized"] += p.unrealized_pnl
        bucket["count"] += 1

    for cls in rollup:
        rollup[cls]["combined"] = rollup[cls]["realized"] + rollup[cls]["unrealized"]

    return rollup


def _render() -> str:
    spot_state = _read_json(SPOT_POSITION_FILE)
    run_state = _read_json(RUN_STATE_FILE)
    account_state = _read_json(ACCOUNT_STATE_FILE)
    trades_raw = _read_jsonl(TRADES_FILE)

    positions = _extract_positions(spot_state)
    cash_now = _extract_cash(account_state, run_state)
    starting_capital = _extract_starting_capital(account_state, run_state, trades_raw, cash_now)

    realized_gross = _realized_gross(trades_raw)
    fees = _total_fees(trades_raw)
    realized_net = realized_gross - fees
    unrealized = sum(p.unrealized_pnl for p in positions)
    combined_all_assets = realized_net + unrealized
    market_value = sum(p.market_value for p in positions)
    exposure = sum(abs(p.market_value) for p in positions)
    rollup = _class_rollup(positions, trades_raw)

    live_equity = cash_now + market_value if (cash_now or market_value) else starting_capital + combined_all_assets

    wins, losses, win_vals, loss_vals = _wins_losses(trades_raw)
    total_trades = wins + losses
    avg_win = (sum(win_vals) / len(win_vals)) if win_vals else 0.0
    avg_loss = (sum(loss_vals) / len(loss_vals)) if loss_vals else 0.0
    pf = _profit_factor(win_vals, loss_vals)
    expectancy = _expectancy(trades_raw)
    equity = _equity_series(starting_capital, trades_raw, positions, cash_now)
    max_dd = _max_drawdown_pct(equity)
    exposure_pct = (exposure / live_equity * 100.0) if live_equity > 0 else 0.0
    invested_pct = (market_value / live_equity * 100.0) if live_equity > 0 else 0.0
    return_pct = ((live_equity - starting_capital) / starting_capital * 100.0) if starting_capital > 0 else 0.0
    health = _system_health(max_dd, realized_net, unrealized, wins, losses)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    width = _terminal_width()
    hr = "-" * min(width, 160)

    lines: List[str] = []
    lines.append("=" * min(width, 160))
    lines.append("CAPITAL STRATA SYSTEMS — PROFESSIONAL PORTFOLIO + ANALYTICS TERMINAL")
    lines.append(f"Updated: {now_str} | Refresh: {REFRESH_SECONDS}s")
    lines.append("=" * min(width, 160))

    lines.append("RUNNING BALANCE / PORTFOLIO SUMMARY")
    lines.append(hr)
    bal_left = [
        f"Start Cap   : {_fmt_money(starting_capital)}",
        f"Run Balance : {_fmt_money(cash_now)}",
        f"Port Equity : {_fmt_money(live_equity)}",
        f"Open Exp    : {_fmt_money(exposure)}",
        f"Comb P&L All: {_fmt_money(combined_all_assets)} ({_fmt_pct(return_pct)})",
    ]
    bal_right = [
        f"Open Pos    : {len(positions)}",
        f"Mkt Value   : {_fmt_money(market_value)}",
        f"Invested %  : {_fmt_pct(invested_pct)}",
        f"Exposure %  : {_fmt_pct(exposure_pct)}",
        f"Health      : {health}",
    ]
    for i in range(max(len(bal_left), len(bal_right))):
        left = bal_left[i] if i < len(bal_left) else ""
        right = bal_right[i] if i < len(bal_right) else ""
        lines.append(f"{left:<42} {right}")

    lines.append("INSTRUMENT SUMMARY")
    lines.append(hr)
    class_rows: List[List[str]] = []
    total_value = 0.0
    total_unreal = 0.0
    total_realized = 0.0
    total_combined = 0.0

    for cls in ["CRYPTO", "FX", "FUTURES", "OPTIONS", "OTHER"]:
        bucket = rollup[cls]
        total_value += bucket["value"]
        total_unreal += bucket["unrealized"]
        total_realized += bucket["realized"]
        total_combined += bucket["combined"]
        class_rows.append([
            cls,
            str(int(bucket["count"])),
            _fmt_money(bucket["unrealized"]),
            _fmt_money(bucket["realized"]),
            _fmt_money(bucket["combined"]),
        ])

    class_rows.append([
        "TOTAL",
        str(len(positions)),
        _fmt_money(total_unreal),
        _fmt_money(total_realized),
        _fmt_money(total_combined),
    ])
    lines.extend(
        _table(
            headers=["CLASS", "CNT", "UNREAL", "REALIZED", "COMBINED"],
            rows=class_rows,
            widths=[10, 5, 13, 13, 13],
        )
    )

    lines.append("PROFESSIONAL PORTFOLIO DASHBOARD")
    lines.append(hr)
    summary_left = [
        f"Cash       : {_fmt_money(cash_now)}",
        f"Mkt Value  : {_fmt_money(market_value)}",
        f"Live Equity: {_fmt_money(live_equity)}",
        f"Net P&L    : {_fmt_money(combined_all_assets)}",
    ]
    summary_right = [
        f"Realized N : {_fmt_money(realized_net)}",
        f"Unrealized : {_fmt_money(unrealized)}",
        f"Fees       : {_fmt_money(fees)}",
        f"PF / Exp   : {pf:.2f} / {_fmt_money(expectancy)}",
    ]
    for i in range(max(len(summary_left), len(summary_right))):
        left = summary_left[i] if i < len(summary_left) else ""
        right = summary_right[i] if i < len(summary_right) else ""
        lines.append(f"{left:<42} {right}")

    lines.append("ACTIVE POSITIONS / ANALYTICS")
    lines.append(hr)
    pos_rows: List[List[str]] = []
    for p in positions[:MAX_POSITION_ROWS]:
        pos_rows.append([
            p.asset,
            p.instrument_class,
            _fmt_money(p.market_value),
            _fmt_money(p.unrealized_pnl),
            _fmt_pct(p.unrealized_pnl_pct),
        ])
    if pos_rows:
        lines.extend(
            _table(
                headers=["ASSET", "CLASS", "VALUE", "UPNL", "UPNL%"],
                rows=pos_rows,
                widths=[10, 9, 12, 12, 8],
            )
        )
    else:
        lines.append("(no open positions)")

    lines.append("PERFORMANCE SNAPSHOT")
    lines.append(hr)
    lines.append(
        f"Trades:{total_trades}  Wins:{wins}  Losses:{losses}  "
        f"AvgWin:{_fmt_money(avg_win)}  AvgLoss:{_fmt_money(avg_loss)}  MaxDD:{_fmt_pct(max_dd)}"
    )

    lines.append("NET P&L PER TRADE")
    lines.append(hr)
    if trades_raw:
        sorted_trades = sorted(
            trades_raw,
            key=lambda x: _sort_ts(x.get("ts") or x.get("timestamp") or x.get("time") or x.get("created_at")),
        )
        trade_rows = [_normalize_trade(t) for t in sorted_trades[-MAX_TRADE_ROWS:]]
        out_rows: List[List[str]] = []
        for t in trade_rows:
            out_rows.append([
                t.ts,
                t.asset,
                _fmt_money(t.net_pnl),
                t.status,
            ])
        lines.extend(
            _table(
                headers=["TIME", "ASSET", "NET P&L", "STATUS"],
                rows=out_rows,
                widths=[11, 10, 12, 8],
            )
        )
    else:
        lines.append("(no trade history)")

    lines.append("EQUITY / W-L")
    lines.append(hr)
    lines.extend(_ascii_line_chart(equity, width=EQUITY_CHART_WIDTH, height=EQUITY_CHART_HEIGHT))
    lines.append(f"{_bar('W', wins, max(total_trades, 1), width=BAR_WIDTH)}  {_bar('L', losses, max(total_trades, 1), width=BAR_WIDTH)}")
    lines.append("")
    lines.append("Press Ctrl+C to stop.")

    return "\n".join(lines)


def main() -> None:
    while True:
        try:
            _clear()
            print(_render())
            time.sleep(REFRESH_SECONDS)
        except KeyboardInterrupt:
            print("\nCSS Trading Terminal stopped.")
            break
        except Exception as exc:
            _clear()
            print("CSS Trading Terminal encountered an error.\n")
            print(f"Error: {exc}\n")
            print("Waiting 30 seconds before retry...")
            time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    main()