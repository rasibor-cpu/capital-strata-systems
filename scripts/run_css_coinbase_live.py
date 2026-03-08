from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.execution.coinbase_executor import CoinbaseExecutor
from backend.risk.portfolio_risk_governor import PortfolioRiskGovernor
from backend.risk.session_policy_loader import choose_session_policy
from backend.strategy.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "backend" / "state"
AUDIT_DIR = PROJECT_ROOT / "audit_logs"
SESSION_DIR = AUDIT_DIR / "sessions"

STATE_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)

POSITION_STATE_FILE = STATE_DIR / "spot_position.json"
SESSION_POLICY_FILE = STATE_DIR / "active_session_policy.json"
SESSION_SNAPSHOT_FILE = STATE_DIR / "active_risk_snapshot.json"
TRADES_LOG_FILE = AUDIT_DIR / "trades.jsonl"
RISK_DECISIONS_LOG_FILE = AUDIT_DIR / "risk_decisions.jsonl"


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None else str(value)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
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
            "opened_at": None,
            "mode": "paper",
        },
    )


def _save_position_state(state: Dict[str, Any]) -> None:
    _write_json(POSITION_STATE_FILE, state)


def _log_risk_decision(
    *,
    asset: str,
    size_usd: float,
    approved: bool,
    reason: str,
    snapshot: Dict[str, Any],
) -> None:
    _append_jsonl(
        RISK_DECISIONS_LOG_FILE,
        {
            "ts": _utc_now_iso(),
            "asset": asset,
            "size_usd": size_usd,
            "approved": approved,
            "reason": reason,
            "risk_snapshot": snapshot,
        },
    )


def _log_trade_event(
    *,
    event: str,
    asset: str,
    mode: str,
    mid_price: float,
    size_usd: float,
    quantity: float,
    notes: str,
) -> None:
    _append_jsonl(
        TRADES_LOG_FILE,
        {
            "ts": _utc_now_iso(),
            "event": event,
            "asset": asset,
            "mode": mode,
            "mid_price": mid_price,
            "size_usd": size_usd,
            "quantity": quantity,
            "notes": notes,
        },
    )


def _safe_mid_from_candles(candles: List[Dict[str, Any]]) -> Optional[float]:
    if not candles:
        return None

    last = candles[-1]

    if isinstance(last, dict):
        close = last.get("close")
        if close is not None:
            return float(close)
        if "high" in last and "low" in last:
            return (float(last["high"]) + float(last["low"])) / 2.0

    return None


def _load_assets_from_env() -> List[str]:
    raw = _env("CSS_PRODUCTS", "BTC-USD,ETH-USD")
    assets = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return assets or ["BTC-USD"]


def _session_capital_from_env() -> float:
    return _env_float("CSS_STARTING_CAPITAL_USD", 200.0)


def _session_trade_size_from_env(starting_capital: float) -> float:
    default_size = max(10.0, round(starting_capital * 0.10, 2))
    return _env_float("CSS_TRADE_SIZE_USD", default_size)


def _build_executor() -> CoinbaseExecutor:
    return CoinbaseExecutor(
        api_key_name=_env("COINBASE_API_KEY_NAME", ""),
        api_private_key_path=_env("COINBASE_API_PRIVATE_KEY_PATH", ""),
        paper_mode=_env_bool("CSS_PAPER_MODE", True),
    )


def _choose_and_lock_policy(starting_capital: float) -> Dict[str, Any]:
    policy = choose_session_policy(starting_capital)
    policy_dict = policy.to_dict()
    policy_dict["locked_at"] = _utc_now_iso()
    _write_json(SESSION_POLICY_FILE, policy_dict)
    return policy_dict


def _prime_governor_from_existing_position(
    governor: PortfolioRiskGovernor,
    position_state: Dict[str, Any],
) -> None:
    if (
        position_state.get("in_position")
        and position_state.get("asset")
        and float(position_state.get("size_usd", 0.0)) > 0
    ):
        asset = str(position_state["asset"])
        size_usd = float(position_state["size_usd"])
        governor.positions[asset] = size_usd


def _session_banner(policy_dict: Dict[str, Any], assets: List[str], trade_size_usd: float) -> None:
    print("\n=== CSS SESSION LOCKED ===")
    print(f"Policy: {policy_dict['policy_name']}")
    print(f"Starting capital: ${policy_dict['starting_capital']:.2f}")
    print(f"Max deploy pct: {policy_dict['max_capital_deployed_pct']:.2%}")
    print(f"Max asset pct: {policy_dict['max_asset_pct']:.2%}")
    print(f"Max concurrent trades: {policy_dict['max_concurrent_trades']}")
    print(f"Broker mode: {policy_dict['broker_mode']}")
    print(f"Strategy mode: {policy_dict['strategy_mode']}")
    print(f"Session expiry: {policy_dict['session_expiry_time']}")
    print(f"Tracked assets: {', '.join(assets)}")
    print(f"Configured trade size: ${trade_size_usd:.2f}")
    print("Policy changes require a fresh session.\n")


def main() -> None:
    scan_interval_seconds = int(_env_float("CSS_SCAN_INTERVAL_SECONDS", 20.0))
    candle_granularity = _env("CSS_CANDLE_GRANULARITY", "FIFTEEN_MINUTE")
    vwap_window = int(_env_float("CSS_VWAP_WINDOW", 20.0))
    epsilon_bps = _env_float("CSS_ENTRY_EPSILON_BPS", 12.0)
    take_profit_bps = _env_float("CSS_TAKE_PROFIT_BPS", 35.0)
    stop_loss_bps = _env_float("CSS_STOP_LOSS_BPS", 45.0)
    dev_force_allow = _env_bool("CSS_DEV_FORCE_ALLOW", False)

    starting_capital = _session_capital_from_env()
    trade_size_usd = _session_trade_size_from_env(starting_capital)
    assets = _load_assets_from_env()

    policy_dict = _choose_and_lock_policy(starting_capital)
    executor = _build_executor()

    from backend.risk.session_risk_policy import SessionRiskPolicy

    policy = SessionRiskPolicy(
        policy_name=str(policy_dict["policy_name"]),
        starting_capital=float(policy_dict["starting_capital"]),
        max_capital_deployed_pct=float(policy_dict["max_capital_deployed_pct"]),
        max_asset_pct=float(policy_dict["max_asset_pct"]),
        max_concurrent_trades=int(policy_dict["max_concurrent_trades"]),
        max_daily_loss_usd=float(policy_dict["max_daily_loss_usd"]),
        max_weekly_drawdown_usd=float(policy_dict["max_weekly_drawdown_usd"]),
        allowed_asset_classes=list(policy_dict["allowed_asset_classes"]),
        broker_mode=str(policy_dict["broker_mode"]),
        strategy_mode=str(policy_dict["strategy_mode"]),
        session_expiry_time=str(policy_dict["session_expiry_time"]),
        allow_live_trading=bool(policy_dict["allow_live_trading"]),
    )

    governor = PortfolioRiskGovernor(policy=policy)
    position_state = _load_position_state()
    _prime_governor_from_existing_position(governor, position_state)

    _session_banner(policy_dict, assets, trade_size_usd)

    vwap_cfg = VWAPConfig(
        window=vwap_window,
        epsilon_bps=epsilon_bps,
        take_profit_bps=take_profit_bps,
        stop_loss_bps=stop_loss_bps,
    )

    print("CSS live runner started. Press Ctrl+C to stop.\n")

    while True:
        try:
            current_position = _load_position_state()
            _write_json(SESSION_SNAPSHOT_FILE, governor.snapshot())

            for product_id in assets:
                candles = executor.get_candles(product_id, candle_granularity)
                if not candles or len(candles) < vwap_window:
                    print(f"[{product_id}] Waiting for enough candles...")
                    continue

                vwap = compute_vwap_from_candles(candles, vwap_window)
                mid = _safe_mid_from_candles(candles)
                if mid is None or vwap <= 0:
                    print(f"[{product_id}] Unable to compute valid mid/VWAP.")
                    continue

                spread_bps = ((mid - vwap) / vwap) * 10000.0
                buy_ok, buy_reason = should_buy_mean_reversion(mid, vwap, spread_bps, vwap_cfg)

                print(
                    f"[{product_id}] mid={mid:.4f} vwap={vwap:.4f} "
                    f"spread_bps={spread_bps:.2f} signal={buy_ok} reason={buy_reason}"
                )

                already_in_position = bool(current_position.get("in_position"))
                current_asset = str(current_position.get("asset", ""))

                if already_in_position and current_asset == product_id:
                    entry_price = float(current_position.get("entry_price", 0.0))
                    pnl_bps = ((mid - entry_price) / entry_price) * 10000.0 if entry_price > 0 else 0.0

                    if pnl_bps >= take_profit_bps:
                        governor.close_trade(product_id)
                        current_position.update(
                            {
                                "in_position": False,
                                "asset": "",
                                "entry_price": 0.0,
                                "size_usd": 0.0,
                                "quantity": 0.0,
                                "opened_at": None,
                            }
                        )
                        _save_position_state(current_position)
                        _write_json(SESSION_SNAPSHOT_FILE, governor.snapshot())
                        _log_trade_event(
                            event="TAKE_PROFIT_EXIT",
                            asset=product_id,
                            mode=policy.broker_mode,
                            mid_price=mid,
                            size_usd=0.0,
                            quantity=0.0,
                            notes=f"Exited at +{pnl_bps:.2f} bps",
                        )
                        print(f"[{product_id}] Take-profit exit triggered at {pnl_bps:.2f} bps.")
                        continue

                    if pnl_bps <= -stop_loss_bps:
                        governor.close_trade(product_id)
                        current_position.update(
                            {
                                "in_position": False,
                                "asset": "",
                                "entry_price": 0.0,
                                "size_usd": 0.0,
                                "quantity": 0.0,
                                "opened_at": None,
                            }
                        )
                        _save_position_state(current_position)
                        _write_json(SESSION_SNAPSHOT_FILE, governor.snapshot())
                        _log_trade_event(
                            event="STOP_LOSS_EXIT",
                            asset=product_id,
                            mode=policy.broker_mode,
                            mid_price=mid,
                            size_usd=0.0,
                            quantity=0.0,
                            notes=f"Exited at {pnl_bps:.2f} bps",
                        )
                        print(f"[{product_id}] Stop-loss exit triggered at {pnl_bps:.2f} bps.")
                        continue

                if already_in_position:
                    continue

                if not buy_ok and not dev_force_allow:
                    continue

                approved, approval_reason = governor.approve_trade(product_id, trade_size_usd)
                _log_risk_decision(
                    asset=product_id,
                    size_usd=trade_size_usd,
                    approved=approved,
                    reason=approval_reason,
                    snapshot=governor.snapshot(),
                )

                if not approved:
                    print(f"[{product_id}] Risk governor blocked trade: {approval_reason}")
                    continue

                quantity = round(trade_size_usd / mid, 10)

                if policy.broker_mode == "live":
                    print(
                        f"[{product_id}] LIVE mode selected, but order placement remains guarded. "
                        "Manual execution wiring can be enabled later."
                    )
                    note = "Risk-approved live candidate; execution intentionally guarded"
                else:
                    note = "Paper-mode entry registered"

                governor.register_trade(product_id, trade_size_usd)
                current_position.update(
                    {
                        "in_position": True,
                        "asset": product_id,
                        "entry_price": mid,
                        "size_usd": trade_size_usd,
                        "quantity": quantity,
                        "opened_at": _utc_now_iso(),
                        "mode": policy.broker_mode,
                    }
                )
                _save_position_state(current_position)
                _write_json(SESSION_SNAPSHOT_FILE, governor.snapshot())
                _log_trade_event(
                    event="ENTRY",
                    asset=product_id,
                    mode=policy.broker_mode,
                    mid_price=mid,
                    size_usd=trade_size_usd,
                    quantity=quantity,
                    notes=note if buy_ok else "DEV_FORCE_ALLOW entry",
                )
                print(f"[{product_id}] Entry registered. quantity={quantity} size_usd={trade_size_usd:.2f}")

            time.sleep(scan_interval_seconds)

        except KeyboardInterrupt:
            print("\nCSS runner stopped by user.")
            break
        except Exception as exc:
            print(f"\nRunner error: {exc}")
            time.sleep(scan_interval_seconds)


if __name__ == "__main__":
    main()