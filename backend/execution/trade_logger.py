from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any


ARTIFACT_DIR = Path("artifacts")
TRADE_LOG_FILE = ARTIFACT_DIR / "css_trade_intelligence_log.jsonl"


class TradeLogger:
    """
    CSS Trade Intelligence Logger

    Records detailed trade events so the engine can later
    analyze:

    - win rate
    - entry signals
    - exit reasons
    - strategy performance
    """

    def __init__(self) -> None:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    def _write(self, payload: Dict[str, Any]) -> None:
        payload["logged_at_utc"] = datetime.now(timezone.utc).isoformat()

        with open(TRADE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

    def log_open(
        self,
        *,
        symbol: str,
        entry_price: float,
        quantity: float,
        score: float,
        signal: str,
        regime: str,
        vwap: float,
        spread_pct: float,
    ) -> None:

        payload = {
            "event": "OPEN",
            "symbol": symbol,
            "entry_price": entry_price,
            "quantity": quantity,
            "score": score,
            "signal": signal,
            "regime": regime,
            "vwap": vwap,
            "distance_to_vwap_pct": (entry_price - vwap) / vwap,
            "spread_pct": spread_pct,
        }

        self._write(payload)

    def log_close(
        self,
        *,
        symbol: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        reason: str,
        hold_minutes: float,
    ) -> None:

        pnl_pct = (exit_price - entry_price) / entry_price
        pnl_usd = pnl_pct * entry_price * quantity

        payload = {
            "event": "CLOSE",
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "pnl_pct": pnl_pct,
            "pnl_usd": pnl_usd,
            "exit_reason": reason,
            "hold_minutes": hold_minutes,
        }

        self._write(payload)