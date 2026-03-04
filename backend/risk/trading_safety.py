from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else str(v).strip()


def _env_upper(name: str, default: str) -> str:
    return _env(name, default).upper()


def _as_int(s: str, default: int) -> int:
    try:
        return int(str(s).strip())
    except Exception:
        return default


def _as_float(s: str, default: float) -> float:
    try:
        return float(str(s).strip())
    except Exception:
        return default


@dataclass
class SafetyConfig:
    trade_mode: str
    armed: bool
    max_live_quote: float
    max_orders_per_session: int
    order_cooldown_seconds: int
    kill_switch_file: Path
    state_file: Path


class TradingSafety:
    """
    Safety Layer:
    1) Kill switch file (hard block LIVE orders)
    2) Circuit breaker (max orders per session, cooldown, max quote notional)
    3) Persistent runtime state in audit_logs/runtime_safety_state.json
    """

    def __init__(self) -> None:
        trade_mode = _env_upper("TRADE_MODE", "DRY_RUN")
        armed = _env_upper("LIVE_TRADING_ARMED", "NO") == "YES"
        max_live_quote = _as_float(_env("MAX_LIVE_QUOTE", "5.0"), 5.0)
        max_orders_per_session = _as_int(_env("MAX_ORDERS_PER_SESSION", "3"), 3)
        order_cooldown_seconds = _as_int(_env("ORDER_COOLDOWN_SECONDS", "30"), 30)

        kill_switch_file = Path(_env("KILL_SWITCH_FILE", "tools/KILL_SWITCH.flag")).resolve()
        state_file = Path("audit_logs/runtime_safety_state.json").resolve()

        self.cfg = SafetyConfig(
            trade_mode=trade_mode,
            armed=armed,
            max_live_quote=max_live_quote,
            max_orders_per_session=max_orders_per_session,
            order_cooldown_seconds=order_cooldown_seconds,
            kill_switch_file=kill_switch_file,
            state_file=state_file,
        )

        self._state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        self.cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.cfg.state_file.exists():
            s = {
                "created_utc": _utc_iso(),
                "session_orders": 0,
                "last_order_epoch": 0.0,
                "last_order_utc": None,
                "last_block_reason": None,
            }
            self._save_state(s)
            return s

        try:
            return json.loads(self.cfg.state_file.read_text(encoding="utf-8"))
        except Exception:
            s = {
                "created_utc": _utc_iso(),
                "session_orders": 0,
                "last_order_epoch": 0.0,
                "last_order_utc": None,
                "last_block_reason": "state_reset_corrupt",
            }
            self._save_state(s)
            return s

    def _save_state(self, s: Dict[str, Any]) -> None:
        self.cfg.state_file.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_order_sent(self) -> None:
        self._state["session_orders"] = int(self._state.get("session_orders", 0)) + 1
        self._state["last_order_epoch"] = time.time()
        self._state["last_order_utc"] = _utc_iso()
        self._save_state(self._state)

    def record_block(self, reason: str) -> None:
        self._state["last_block_reason"] = reason
        self._save_state(self._state)

    def kill_switch_active(self) -> bool:
        return self.cfg.kill_switch_file.exists()

    def can_send_order(self, quote_size: Optional[str]) -> Tuple[bool, str]:
        # Kill switch always wins
        if self.kill_switch_active():
            return False, f"KILL_SWITCH_ACTIVE ({self.cfg.kill_switch_file})"

        # LIVE requires arming
        if self.cfg.trade_mode == "LIVE" and not self.cfg.armed:
            return False, "LIVE_MODE_NOT_ARMED"

        # Non-live modes: always allow (execution module will still dry-run)
        if self.cfg.trade_mode != "LIVE":
            return True, "NON_LIVE_MODE_OK"

        # Max orders per session
        if int(self._state.get("session_orders", 0)) >= self.cfg.max_orders_per_session:
            return False, f"MAX_ORDERS_PER_SESSION_EXCEEDED ({self.cfg.max_orders_per_session})"

        # Cooldown
        last_epoch = float(self._state.get("last_order_epoch", 0.0) or 0.0)
        if last_epoch > 0:
            since = time.time() - last_epoch
            if since < self.cfg.order_cooldown_seconds:
                remain = int(self.cfg.order_cooldown_seconds - since)
                return False, f"ORDER_COOLDOWN_ACTIVE ({remain}s remaining)"

        # Max notional cap (quote currency)
        if quote_size is not None:
            q = _as_float(quote_size, 0.0)
            if q > self.cfg.max_live_quote:
                return False, f"MAX_LIVE_QUOTE_EXCEEDED ({q} > {self.cfg.max_live_quote})"

        return True, "LIVE_OK"