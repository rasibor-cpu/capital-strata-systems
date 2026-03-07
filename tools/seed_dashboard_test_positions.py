from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "backend" / "state"
AUDIT_DIR = PROJECT_ROOT / "audit_logs"

SPOT_POSITION_FILE = STATE_DIR / "spot_position.json"
ACCOUNT_STATE_FILE = STATE_DIR / "account_state.json"
RUN_STATE_FILE = STATE_DIR / "run_state.json"
TRADES_FILE = AUDIT_DIR / "trades.jsonl"

DEFAULT_STARTING_CAPITAL = 200.0
DEFAULT_CASH_BUFFER = 65.0


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def _append_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_starting_capital(account_state: Dict[str, Any], run_state: Dict[str, Any]) -> float:
    for key in ("starting_capital", "starting_cash", "initial_cash", "cash_usd", "cash"):
        if key in account_state and account_state[key] is not None:
            try:
                return float(account_state[key])
            except Exception:
                pass

    for key in ("starting_capital", "starting_cash", "cash_usd", "cash"):
        if key in run_state and run_state[key] is not None:
            try:
                return float(run_state[key])
            except Exception:
                pass

    return DEFAULT_STARTING_CAPITAL


def _build_basket() -> List[Dict[str, float]]:
    return [
        {"asset": "BTC-USD", "notional": 40.0, "entry_price": 68000.0, "current_price": 68120.0},
        {"asset": "ETH-USD", "notional": 35.0, "entry_price": 1970.0, "current_price": 1982.0},
        {"asset": "SOL-USD", "notional": 25.0, "entry_price": 84.0, "current_price": 85.4},
        {"asset": "AVAX-USD", "notional": 20.0, "entry_price": 27.5, "current_price": 27.9},
        {"asset": "LINK-USD", "notional": 15.0, "entry_price": 18.2, "current_price": 18.45},
    ]


def _make_positions(basket: List[Dict[str, float]]) -> List[Dict[str, Any]]:
    positions: List[Dict[str, Any]] = []

    for item in basket:
        entry = float(item["entry_price"])
        current = float(item["current_price"])
        notional = float(item["notional"])
        qty = notional / entry if entry > 0 else 0.0
        market_value = qty * current
        unrealized = (current - entry) * qty
        unrealized_pct = ((current - entry) / entry) * 100.0 if entry > 0 else 0.0

        positions.append(
            {
                "asset": item["asset"],
                "symbol": item["asset"],
                "product_id": item["asset"],
                "side": "LONG",
                "quantity": round(qty, 10),
                "entry_price": round(entry, 8),
                "current_price": round(current, 8),
                "market_value": round(market_value, 8),
                "unrealized_pnl": round(unrealized, 8),
                "unrealized_pnl_pct": round(unrealized_pct, 8),
                "status": "OPEN",
            }
        )

    return positions


def _make_trade_rows(basket: List[Dict[str, float]]) -> List[Dict[str, Any]]:
    ts = _now_iso()
    trade_rows: List[Dict[str, Any]] = []

    for item in basket:
        entry = float(item["entry_price"])
        notional = float(item["notional"])
        qty = notional / entry if entry > 0 else 0.0

        trade_rows.append(
            {
                "ts": ts,
                "asset": item["asset"],
                "symbol": item["asset"],
                "side": "BUY",
                "quantity": round(qty, 10),
                "price": round(entry, 8),
                "realized_pnl": 0.0,
                "fee": 0.0,
                "status": "PAPER_OPEN",
                "source": "seed_dashboard_test_positions",
            }
        )

    return trade_rows


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    account_state = _read_json(ACCOUNT_STATE_FILE)
    run_state = _read_json(RUN_STATE_FILE)

    starting_capital = _extract_starting_capital(account_state, run_state)

    basket = _build_basket()
    total_notional = sum(float(x["notional"]) for x in basket)
    cash_buffer = DEFAULT_CASH_BUFFER

    if total_notional + cash_buffer > starting_capital:
        cash_buffer = max(0.0, starting_capital - total_notional)

    remaining_cash = starting_capital - total_notional
    if remaining_cash < 0:
        raise ValueError(
            f"Starting capital {_extract_starting_capital(account_state, run_state):.2f} "
            f"is too small for the seed basket {total_notional:.2f}."
        )

    positions = _make_positions(basket)
    trade_rows = _make_trade_rows(basket)

    spot_payload = {
        "positions": positions,
        "updated_at": _now_iso(),
        "source": "seed_dashboard_test_positions",
        "mode": "paper",
    }

    updated_account_state = dict(account_state)
    updated_account_state["starting_capital"] = round(starting_capital, 8)
    updated_account_state["starting_cash"] = round(starting_capital, 8)
    updated_account_state["cash"] = round(remaining_cash, 8)
    updated_account_state["cash_usd"] = round(remaining_cash, 8)
    updated_account_state["available_cash"] = round(remaining_cash, 8)
    updated_account_state["mode"] = "paper"
    updated_account_state["updated_at"] = _now_iso()

    updated_run_state = dict(run_state)
    updated_run_state["starting_capital"] = round(starting_capital, 8)
    updated_run_state["starting_cash"] = round(starting_capital, 8)
    updated_run_state["cash"] = round(remaining_cash, 8)
    updated_run_state["cash_usd"] = round(remaining_cash, 8)
    updated_run_state["available_cash"] = round(remaining_cash, 8)
    updated_run_state["mode"] = "paper"
    updated_run_state["updated_at"] = _now_iso()

    _write_json(SPOT_POSITION_FILE, spot_payload)
    _write_json(ACCOUNT_STATE_FILE, updated_account_state)
    _write_json(RUN_STATE_FILE, updated_run_state)
    _append_jsonl(TRADES_FILE, trade_rows)

    print("Paper dashboard seed completed.\n")
    print(f"Starting capital : ${starting_capital:,.2f}")
    print(f"Total notional   : ${total_notional:,.2f}")
    print(f"Remaining cash   : ${remaining_cash:,.2f}")
    print(f"Positions seeded : {len(positions)}")
    print("\nSeeded assets:")
    for p in positions:
        print(
            f"  {p['asset']:<8} qty={p['quantity']:.10f} "
            f"entry={p['entry_price']:.4f} current={p['current_price']:.4f}"
        )
    print("\nDashboard files updated:")
    print(f"  {SPOT_POSITION_FILE}")
    print(f"  {ACCOUNT_STATE_FILE}")
    print(f"  {RUN_STATE_FILE}")
    print(f"  {TRADES_FILE}")


if __name__ == "__main__":
    main()