from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


ARTIFACT_DIR = Path("artifacts")
TRADE_LOG_FILE = ARTIFACT_DIR / "css_trade_intelligence_log.jsonl"


def _safe(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


class TradeLogger:
    """
    CSS Trade Intelligence Logger

    Records detailed trade events so the engine can later analyze:
    - win rate
    - entry signals
    - exit reasons
    - strategy performance
    - gross vs net profitability
    - execution cost drag

    Backward compatibility:
    - Existing callers can keep using log_open(...) and log_close(...)
      with the original parameter set.
    - New optional fields support cost-aware reporting.
    """

    def __init__(self) -> None:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    def _write(self, payload: Dict[str, Any]) -> None:
        payload["logged_at_utc"] = datetime.now(timezone.utc).isoformat()

        with open(TRADE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

    def _normalize_cost_payload(self, payload: Optional[Dict[str, Any]]) -> Dict[str, float]:
        """
        Normalize cost payload to stable keys.

        Supported keys:
        - spread_cost_usd
        - slippage_cost_usd
        - fee_cost_usd
        - total_cost_usd

        If total_cost_usd is omitted, it is derived from components.
        """
        payload = payload or {}

        spread_cost_usd = _safe(payload.get("spread_cost_usd"), 0.0)
        slippage_cost_usd = _safe(payload.get("slippage_cost_usd"), 0.0)
        fee_cost_usd = _safe(payload.get("fee_cost_usd"), 0.0)

        explicit_total = payload.get("total_cost_usd")
        if explicit_total is None:
            total_cost_usd = spread_cost_usd + slippage_cost_usd + fee_cost_usd
        else:
            total_cost_usd = _safe(explicit_total, 0.0)

        return {
            "spread_cost_usd": spread_cost_usd,
            "slippage_cost_usd": slippage_cost_usd,
            "fee_cost_usd": fee_cost_usd,
            "total_cost_usd": total_cost_usd,
        }

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
        asset_class: str = "unknown",
        entry_costs: Optional[Dict[str, Any]] = None,
    ) -> None:
        normalized_entry_costs = self._normalize_cost_payload(entry_costs)

        distance_to_vwap_pct = 0.0
        if _safe(vwap, 0.0) > 0:
            distance_to_vwap_pct = (_safe(entry_price) - _safe(vwap)) / _safe(vwap)

        payload = {
            "event": "OPEN",
            "symbol": symbol,
            "asset_class": asset_class,
            "entry_price": _safe(entry_price),
            "quantity": _safe(quantity),
            "score": _safe(score),
            "signal": signal,
            "regime": regime,
            "vwap": _safe(vwap),
            "distance_to_vwap_pct": distance_to_vwap_pct,
            "spread_pct": _safe(spread_pct),
            "entry_spread_cost_usd": normalized_entry_costs["spread_cost_usd"],
            "entry_slippage_cost_usd": normalized_entry_costs["slippage_cost_usd"],
            "entry_fee_cost_usd": normalized_entry_costs["fee_cost_usd"],
            "entry_total_cost_usd": normalized_entry_costs["total_cost_usd"],
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
        asset_class: str = "unknown",
        entry_costs: Optional[Dict[str, Any]] = None,
        exit_costs: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry_price = _safe(entry_price)
        exit_price = _safe(exit_price)
        quantity = _safe(quantity)

        gross_pnl_pct = 0.0
        if entry_price > 0:
            gross_pnl_pct = (exit_price - entry_price) / entry_price

        gross_pnl_usd = (exit_price - entry_price) * quantity

        normalized_entry_costs = self._normalize_cost_payload(entry_costs)
        normalized_exit_costs = self._normalize_cost_payload(exit_costs)

        entry_total_cost_usd = normalized_entry_costs["total_cost_usd"]
        exit_total_cost_usd = normalized_exit_costs["total_cost_usd"]
        total_round_trip_cost_usd = entry_total_cost_usd + exit_total_cost_usd

        net_pnl_usd = gross_pnl_usd - total_round_trip_cost_usd

        notional_usd = entry_price * quantity
        net_pnl_pct = (net_pnl_usd / notional_usd) if notional_usd > 0 else 0.0

        payload = {
            "event": "CLOSE",
            "symbol": symbol,
            "asset_class": asset_class,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "gross_pnl_pct": gross_pnl_pct,
            "gross_pnl_usd": gross_pnl_usd,
            "pnl_pct": net_pnl_pct,
            "pnl_usd": net_pnl_usd,
            "net_pnl_pct": net_pnl_pct,
            "net_pnl_usd": net_pnl_usd,
            "entry_spread_cost_usd": normalized_entry_costs["spread_cost_usd"],
            "entry_slippage_cost_usd": normalized_entry_costs["slippage_cost_usd"],
            "entry_fee_cost_usd": normalized_entry_costs["fee_cost_usd"],
            "entry_total_cost_usd": entry_total_cost_usd,
            "exit_spread_cost_usd": normalized_exit_costs["spread_cost_usd"],
            "exit_slippage_cost_usd": normalized_exit_costs["slippage_cost_usd"],
            "exit_fee_cost_usd": normalized_exit_costs["fee_cost_usd"],
            "exit_total_cost_usd": exit_total_cost_usd,
            "total_round_trip_cost_usd": total_round_trip_cost_usd,
            "exit_reason": reason,
            "hold_minutes": _safe(hold_minutes),
        }

        self._write(payload)