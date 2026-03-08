from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.risk.portfolio_risk_governor import PortfolioRiskGovernor
from backend.risk.session_policy_loader import choose_session_policy
from backend.broker.coinbase_adapter import CoinbaseAdapter
from backend.strategies.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "backend" / "state"
AUDIT_DIR = PROJECT_ROOT / "audit_logs"

POSITION_STATE_FILE = STATE_DIR / "spot_position.json"
SESSION_POLICY_FILE = STATE_DIR / "active_session_policy.json"
SESSION_SNAPSHOT_FILE = STATE_DIR / "active_risk_snapshot.json"

TRADES_LOG_FILE = AUDIT_DIR / "trades.jsonl"
RISK_DECISIONS_LOG_FILE = AUDIT_DIR / "risk_decisions.jsonl"


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else str(v)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _load_position_state() -> Dict[str, Any]:
    return _read_json(
        POSITION_STATE_FILE,
        {
            "in_position": False,
            "asset": "",
            "entry_price": 0.0,
            "size_usd": 0.0,
            "quantity": 0.0,
        },
    )


def _save_position_state(state: Dict[str, Any]) -> None:
    _write_json(POSITION_STATE_FILE, state)


def _log_trade(event: str, payload: Dict[str, Any]) -> None:
    payload["event"] = event
    payload["ts"] = _utc_now_iso()
    _append_jsonl(TRADES_LOG_FILE, payload)


def _log_risk(payload: Dict[str, Any]) -> None:
    payload["ts"] = _utc_now_iso()
    _append_jsonl(RISK_DECISIONS_LOG_FILE, payload)


def _safe_mid(candle: Dict[str, Any]) -> float:
    return float(candle["close"])


def _assets() -> List[str]:
    raw = _env("CSS_PRODUCTS", "BTC-USD,ETH-USD")
    return [x.strip().upper() for x in raw.split(",") if x.strip()]


def main():

    scan_interval = int(_env_float("CSS_SCAN_INTERVAL_SECONDS", 20))
    candle_granularity = _env("CSS_CANDLE_GRANULARITY", "FIFTEEN_MINUTE")

    vwap_window = int(_env_float("CSS_VWAP_WINDOW", 20))
    epsilon_bps = _env_float("CSS_ENTRY_EPSILON_BPS", 12)
    take_profit_bps = _env_float("CSS_TAKE_PROFIT_BPS", 35)
    stop_loss_bps = _env_float("CSS_STOP_LOSS_BPS", 45)

    starting_capital = _env_float("CSS_STARTING_CAPITAL_USD", 200)
    trade_size_usd = _env_float("CSS_TRADE_SIZE_USD", 20)

    policy = choose_session_policy(starting_capital)
    policy_dict = policy.to_dict()

    _write_json(SESSION_POLICY_FILE, policy_dict)

    governor = PortfolioRiskGovernor(policy)

    adapter = CoinbaseAdapter(paper_mode=True)

    assets = _assets()

    print("\n=== CSS SESSION LOCKED ===")
    print(f"Policy: {policy_dict['policy_name']}")
    print(f"Capital: ${starting_capital}")
    print(f"Assets: {assets}")
    print("Coinbase adapter active\n")

    vwap_cfg = VWAPConfig(
        window=vwap_window,
        epsilon_bps=epsilon_bps,
        take_profit_bps=take_profit_bps,
        stop_loss_bps=stop_loss_bps,
    )

    while True:

        try:

            pos = _load_position_state()

            for asset in assets:

                candles = adapter.get_candles(asset, candle_granularity)

                if len(candles) < vwap_window:
                    print(f"{asset}: waiting for candles")
                    continue

                vwap = compute_vwap_from_candles(candles, vwap_window)
                mid = _safe_mid(candles[-1])

                spread = ((mid - vwap) / vwap) * 10000

                signal, reason = should_buy_mean_reversion(mid, vwap, spread, vwap_cfg)

                print(asset, "mid", mid, "vwap", vwap, "spread", round(spread, 2), "signal", signal)

                if pos["in_position"]:
                    continue

                if not signal:
                    continue

                approved, msg = governor.approve_trade(asset, trade_size_usd)

                _log_risk(
                    {
                        "asset": asset,
                        "size": trade_size_usd,
                        "approved": approved,
                        "reason": msg,
                    }
                )

                if not approved:
                    print("Risk block:", msg)
                    continue

                qty = trade_size_usd / mid

                governor.register_trade(asset, trade_size_usd)

                pos = {
                    "in_position": True,
                    "asset": asset,
                    "entry_price": mid,
                    "size_usd": trade_size_usd,
                    "quantity": qty,
                }

                _save_position_state(pos)

                _log_trade(
                    "ENTRY",
                    {
                        "asset": asset,
                        "price": mid,
                        "qty": qty,
                    },
                )

                print("TRADE ENTERED", asset, "price", mid)

            time.sleep(scan_interval)

        except KeyboardInterrupt:
            print("CSS stopped")
            break

        except Exception as e:
            print("Runner error:", e)
            time.sleep(scan_interval)


if __name__ == "__main__":
    main()