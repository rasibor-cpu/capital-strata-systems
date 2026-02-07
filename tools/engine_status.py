"""
tools.engine_status — REA Capital Trading Engine (V1 Freeze)

One-glance cockpit + selectable reporting.

Supports:
- Period: today | week | month | ytd | custom (start/end)
- Output: screen | file | printer
- Content: summary fields + optional transaction details

Usage examples:
  python -m tools.engine_status --mode TEST --period today
  python -m tools.engine_status --mode TEST --period week --details
  python -m tools.engine_status --mode TEST --period custom --start 2026-02-01 --end 2026-02-07
  python -m tools.engine_status --mode TEST --period today --out file --path reporting_store\\today_status.txt
  python -m tools.engine_status --mode TEST --period today --out printer

Notes:
- Reads JSONL ledger written by append_pnl_event().
- Fail-soft: missing ledger => prints "no trades yet" cleanly.
- Printer: uses Windows Notepad default printer (notepad /p).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Ledger location (V1)
# -----------------------------

def _ledger_path_for_mode(mode: str) -> Path:
    m = (mode or "TEST").upper().strip()
    return Path("pnl_ledger_live.jsonl") if m == "LIVE" else Path("pnl_ledger_test.jsonl")


# -----------------------------
# Time helpers (UTC)
# -----------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_day_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _start_of_week_utc(d: date) -> datetime:
    # Monday = 0
    start = d - timedelta(days=d.weekday())
    return _start_of_day_utc(start)


def _start_of_month_utc(d: date) -> datetime:
    return datetime(d.year, d.month, 1, tzinfo=timezone.utc)


def _start_of_year_utc(d: date) -> datetime:
    return datetime(d.year, 1, 1, tzinfo=timezone.utc)


def _parse_yyyy_mm_dd(s: str) -> date:
    parts = s.strip().split("-")
    if len(parts) != 3:
        raise ValueError("Date must be YYYY-MM-DD")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    return date(y, m, d)


def _parse_ts_utc(row: Dict) -> Optional[datetime]:
    ts = row.get("timestamp_utc") or row.get("timestamp")
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


# -----------------------------
# Summaries
# -----------------------------

@dataclass
class Summary:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    pnl: float = 0.0
    fees: float = 0.0

    @property
    def win_rate(self) -> float:
        return (self.wins / self.trades * 100.0) if self.trades else 0.0


def _row_pnl(row: Dict) -> float:
    try:
        return float(row.get("pnl", 0.0))
    except Exception:
        return 0.0


def _row_fees(row: Dict) -> float:
    try:
        return float(row.get("fees", 0.0))
    except Exception:
        return 0.0


def _read_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    rows: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _summarize(rows: List[Dict], start_dt: datetime, end_dt: datetime) -> Tuple[Summary, List[Dict]]:
    s = Summary()
    selected: List[Dict] = []

    for r in rows:
        dt = _parse_ts_utc(r)
        if dt is None:
            continue
        if not (start_dt <= dt < end_dt):
            continue

        selected.append(r)
        s.trades += 1
        pnl = _row_pnl(r)
        fees = _row_fees(r)
        s.pnl += pnl
        s.fees += fees

        if pnl > 0:
            s.wins += 1
        elif pnl < 0:
            s.losses += 1

    return s, selected


def _fmt_money(x: float) -> str:
    return f"{x:,.2f}"


def _safe_str(x) -> str:
    return "" if x is None else str(x)


def _render_summary_text(
    mode: str,
    period_label: str,
    start_dt: datetime,
    end_dt: datetime,
    ledger_path: Path,
    s: Summary,
    include_details: bool,
    selected_rows: List[Dict],
    fields: List[str],
) -> str:
    lines: List[str] = []
    lines.append(f"=== ENGINE STATUS ({mode.upper()}) ===")
    lines.append(f"Period: {period_label}")
    lines.append(f"UTC Window: {start_dt.isoformat()}  ->  {end_dt.isoformat()}")
    lines.append(f"Ledger: {ledger_path.as_posix()}")
    lines.append("")

    if s.trades == 0:
        lines.append("No trades recorded for this period.")
        lines.append("")
        return "\n".join(lines)

    # Field map
    field_map = {
        "trades": f"{s.trades}",
        "wins": f"{s.wins}",
        "losses": f"{s.losses}",
        "win_rate": f"{s.win_rate:,.2f}%",
        "pnl": _fmt_money(s.pnl),
        "fees": _fmt_money(s.fees),
    }

    # Print selected fields in a stable order
    order = ["trades", "wins", "losses", "win_rate", "pnl", "fees"]
    want = set([f.strip().lower() for f in fields if f.strip()]) if fields else set(order)
    for key in order:
        if key in want:
            label = key.replace("_", " ").title()
            lines.append(f"{label:<10}: {field_map[key]}")
    lines.append("")

    if include_details:
        lines.append("--- TRANSACTION DETAILS ---")
        cumulative = 0.0
        for i, r in enumerate(selected_rows, start=1):
            pnl = _row_pnl(r)
            cumulative += pnl

            lines.append(f"Trade #{i}")
            lines.append(f"UTRN:           {_safe_str(r.get('trade_id') or r.get('utrn'))}")
            lines.append(f"Trade Type:     {_safe_str(r.get('trade_type'))}")
            lines.append(f"Symbol:         {_safe_str(r.get('symbol'))}")
            lines.append(f"Side:           {_safe_str(r.get('side'))}")
            lines.append(f"Execution Date: {_safe_str(r.get('execution_date'))}")
            lines.append(f"Value Date:     {_safe_str(r.get('value_date'))}")
            lines.append(f"Amount:         {_safe_str(r.get('amount'))} {_safe_str(r.get('currency'))}")
            lines.append(f"FX Rate:        {_safe_str(r.get('fx_rate'))}")
            lines.append(f"Exchange Text:  {_safe_str(r.get('exchange_rate_text'))}")
            lines.append(f"Entry Px:       {_safe_str(r.get('entry_px'))}")
            lines.append(f"Exit Px:        {_safe_str(r.get('exit_px'))}")
            lines.append(f"Fees:           {_safe_str(r.get('fees'))}")
            lines.append(f"Trade P&L:      {_fmt_money(pnl)}")
            lines.append(f"Cumulative P&L: {_fmt_money(cumulative)}")
            lines.append("")
    return "\n".join(lines)


# -----------------------------
# Output destinations
# -----------------------------

def _ensure_parent_dir(path: Path) -> None:
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _write_text(path: Path, text: str) -> None:
    _ensure_parent_dir(path)
    path.write_text(text, encoding="utf-8")


def _print_to_default_printer_via_notepad(text_file: Path) -> None:
    # Windows default printer print via Notepad (simple, robust).
    # This spawns a print job to the default printer.
    subprocess.run(["notepad", "/p", str(text_file)], check=False)


# -----------------------------
# Period window resolver
# -----------------------------

def _resolve_window(period: str, start: Optional[str], end: Optional[str]) -> Tuple[str, datetime, datetime]:
    p = (period or "today").lower().strip()
    now = _utc_now()
    today = now.date()

    if p == "today":
        start_dt = _start_of_day_utc(today)
        end_dt = start_dt + timedelta(days=1)
        return "today", start_dt, end_dt

    if p == "week":
        start_dt = _start_of_week_utc(today)
        end_dt = start_dt + timedelta(days=7)
        return "week (Mon-Sun)", start_dt, end_dt

    if p == "month":
        start_dt = _start_of_month_utc(today)
        # next month start
        if today.month == 12:
            end_dt = datetime(today.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_dt = datetime(today.year, today.month + 1, 1, tzinfo=timezone.utc)
        return "month (MTD)", start_dt, end_dt

    if p in ("ytd", "year"):
        start_dt = _start_of_year_utc(today)
        end_dt = datetime(today.year + 1, 1, 1, tzinfo=timezone.utc)
        return "year-to-date", start_dt, end_dt

    if p == "custom":
        if not start or not end:
            raise ValueError("custom period requires --start YYYY-MM-DD and --end YYYY-MM-DD")
        sd = _parse_yyyy_mm_dd(start)
        ed = _parse_yyyy_mm_dd(end)
        if ed < sd:
            raise ValueError("--end must be >= --start")
        start_dt = _start_of_day_utc(sd)
        end_dt = _start_of_day_utc(ed) + timedelta(days=1)  # inclusive end date
        return f"custom ({start}..{end})", start_dt, end_dt

    raise ValueError("period must be one of: today, week, month, ytd, custom")


def main() -> int:
    ap = argparse.ArgumentParser(prog="engine_status")
    ap.add_argument("--mode", choices=["TEST", "LIVE"], default="TEST")
    ap.add_argument("--period", choices=["today", "week", "month", "ytd", "custom"], default="today")
    ap.add_argument("--start", default=None, help="custom start date YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="custom end date YYYY-MM-DD (inclusive)")
    ap.add_argument("--details", action="store_true", help="include transaction-level details")
    ap.add_argument(
        "--fields",
        default="trades,wins,losses,win_rate,pnl,fees",
        help="comma list: trades,wins,losses,win_rate,pnl,fees",
    )
    ap.add_argument("--out", choices=["screen", "file", "printer"], default="screen")
    ap.add_argument("--path", default=None, help="output file path when --out=file (or temp path for printer)")
    args = ap.parse_args()

    mode = args.mode.upper().strip()
    ledger_path = _ledger_path_for_mode(mode)
    rows = _read_jsonl(ledger_path)

    try:
        period_label, start_dt, end_dt = _resolve_window(args.period, args.start, args.end)
    except Exception as e:
        print(f"FATAL: {e}")
        return 2

    fields = [x.strip() for x in (args.fields or "").split(",") if x.strip()]
    summary, selected_rows = _summarize(rows, start_dt, end_dt)

    text = _render_summary_text(
        mode=mode,
        period_label=period_label,
        start_dt=start_dt,
        end_dt=end_dt,
        ledger_path=ledger_path,
        s=summary,
        include_details=bool(args.details),
        selected_rows=selected_rows,
        fields=fields,
    )

    out = args.out.lower().strip()

    if out == "screen":
        print(text)
        return 0

    if out == "file":
        if not args.path:
            print("FATAL: --out=file requires --path")
            return 2
        out_path = Path(args.path)
        _write_text(out_path, text)
        print(f"WROTE: {out_path.resolve()}")
        return 0

    # printer
    # If user provided a path, use it. Otherwise create a temp file in reporting_store.
    if args.path:
        tmp = Path(args.path)
    else:
        tmp = Path("reporting_store") / f"engine_status_{mode.lower()}_{args.period}.txt"

    _write_text(tmp, text)
    print(f"PRINTING (default printer): {tmp.resolve()}")
    _print_to_default_printer_via_notepad(tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
