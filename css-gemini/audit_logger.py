# audit_logger.py
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Institutional standard: JSON Lines for crash-resilient logging
AUDIT_LOG_PATH = "logs/audit.jsonl"
_lock = threading.Lock()

class AuditLogger:
    def __init__(self, path: str = AUDIT_LOG_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def log(self, event: str, module: str, payload: Dict[str, Any], level: str = "INFO", symbol: Optional[str] = None):
        """Standard thread-safe log entry."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "module": module,
            "level": level,
            "symbol": symbol,
            "data": payload,
        }
        with _lock:
            try:
                with open(self.path, "a") as f:
                    f.write(json.dumps(record) + "\n")
            except Exception as e:
                print(f"Audit write failed: {e}")

    def trade_executed(self, symbol, side, qty, price, sl, tp, cost_bps):
        self.log("TRADE_EXECUTED", "orchestrator", {"side": side, "qty": qty, "price": price}, symbol=symbol)

    def trade_rejected(self, symbol, reason, module):
        self.log("TRADE_REJECTED", module, {"reason": reason}, level="WARNING", symbol=symbol)

    def position_closed(self, symbol, pnl, reason, capital):
        self.log("POSITION_CLOSED", "orchestrator", {"pnl": pnl, "reason": reason, "capital": capital}, symbol=symbol)

    def regime_change(self, symbol, old, new):
        self.log("REGIME_CHANGE", "regime_filter", {"from": old, "to": new}, symbol=symbol)

# --- SINGLETON INTERFACE ---
_audit: Optional[AuditLogger] = None

def get_audit() -> AuditLogger:
    """Provides a single, global entry point for the logging engine."""
    global _audit
    if _audit is None:
        _audit = AuditLogger()
    return _audit