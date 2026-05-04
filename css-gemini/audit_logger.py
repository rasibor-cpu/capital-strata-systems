"""
audit_logger.py
Structured JSON audit trail for all engine events, trades, signals,
and risk decisions. Every action is immutably logged with timestamp,
module, and full context payload.
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

AUDIT_LOG_PATH = "logs/audit.jsonl"
logger = logging.getLogger(__name__)
_lock = threading.Lock()


class AuditLogger:

    EVENTS = {
        "ENGINE_START", "ENGINE_STOP", "ENGINE_HALT", "ENGINE_RESUME",
        "BROKER_CONNECT", "BROKER_DISCONNECT", "BROKER_ERROR",
        "SIGNAL_GENERATED", "SIGNAL_REJECTED",
        "TRADE_APPROVED", "TRADE_REJECTED", "TRADE_EXECUTED", "TRADE_FAILED",
        "POSITION_OPENED", "POSITION_CLOSED", "PARTIAL_CLOSE",
        "TRAILING_UPDATED", "SL_HIT", "TP_HIT",
        "REGIME_CHANGE", "COST_REJECTED",
        "RISK_BREACH", "DRAWDOWN_WARNING", "DAILY_LIMIT_HIT",
        "CAPITAL_REALLOCATED", "SYSTEM_ERROR",
    }

    def __init__(self, path: str = AUDIT_LOG_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.log("ENGINE_START", "audit_logger", {"status": "audit trail initialised"})

    def log(
        self,
        event: str,
        module: str,
        payload: Dict[str, Any],
        level: str = "INFO",
        symbol: Optional[str] = None,
    ) -> None:
        record = {
            "ts":     datetime.now(timezone.utc).isoformat(),
            "event":  event,
            "module": module,
            "level":  level,
            "symbol": symbol,
            "data":   payload,
        }
        with _lock:
            try:
                with open(self.path, "a") as f:
                    f.write(json.dumps(record) + "\n")
            except Exception as e:
                logger.error(f"Audit write failed: {e}")

    def signal(self, symbol: str, side: str, score: float, reasons: list, timeframe: str):
        self.log("SIGNAL_GENERATED", "signal_engine",
                 {"side": side, "score": score, "reasons": reasons, "tf": timeframe},
                 symbol=symbol)

    def trade_executed(self, symbol: str, side: str, qty: float, price: float,
                       sl: float, tp: float, cost_bps: float):
        self.log("TRADE_EXECUTED", "orchestrator",
                 {"side": side, "qty": qty, "price": price,
                  "sl": sl, "tp": tp, "cost_bps": cost_bps},
                 symbol=symbol)

    def trade_rejected(self, symbol: str, reason: str, module: str):
        self.log("TRADE_REJECTED", module, {"reason": reason},
                 level="WARNING", symbol=symbol)

    def position_closed(self, symbol: str, pnl: float, reason: str, capital: float):
        level = "INFO" if pnl >= 0 else "WARNING"
        self.log("POSITION_CLOSED", "orchestrator",
                 {"pnl": pnl, "reason": reason, "capital_after": capital},
                 level=level, symbol=symbol)

    def regime_change(self, symbol: str, old: str, new: str):
        self.log("REGIME_CHANGE", "regime_filter",
                 {"from": old, "to": new}, symbol=symbol)

    def risk_breach(self, reason: str, capital: float, drawdown_pct: float):
        self.log("RISK_BREACH", "risk_engine",
                 {"reason": reason, "capital": capital, "drawdown_pct": drawdown_pct},
                 level="CRITICAL")

    def tail(self, n: int = 50) -> list:
        """Return the last n audit records."""
        try:
            with open(self.path, "r") as f:
                lines = f.readlines()
            return [json.loads(l) for l in lines[-n:] if l.strip()]
        except Exception:
            return []


# Singleton
_audit: Optional[AuditLogger] = None

def get_audit() -> AuditLogger:
    global _audit
    if _audit is None:
        _audit = AuditLogger()
    return _audit
