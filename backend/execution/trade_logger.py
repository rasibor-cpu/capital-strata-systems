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
    CSS Trade Intelligence Logger (Enhanced)

    Adds:
    - VWAP / momentum / velocity / mean reversion tracking
    - pressure + acceleration tracking
    - allocator output tracking
    - decision traceability

    Fully backward compatible.
    """

    def __init__(self) -> None:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    def _write(self, payload: Dict[str, Any]) -> None:
        payload["logged_at_utc"] = datetime.now(timezone.utc).isoformat()

        with open(TRADE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

    def _normalize_cost_payload(self, payload: Optional[Dict[str, Any]]) -> Dict[str, float]:
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

        # 🔥 NEW INTELLIGENCE FIELDS
        momentum: float = 0.0,
        velocity: float = 0.0,
        vwap_dev: float = 0.0,
        mean_reversion_score: float = 0.0,
        pressure_score: float = 0.0,
        acceleration_score: float = 0.0,

        # allocator tracking
        allocated_capital: float = 0.0,
        allocation_weight: float = 0.0,
    ) -> None:

        normalized_entry_costs = self._normalize_cost_payload(entry_costs)

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
            "vwap_dev": _safe(vwap_dev),

            "momentum": _safe(momentum),
            "velocity": _safe(velocity),
            "mean_reversion_score": _safe(mean_reversion_score),

            "pressure_score": _safe(pressure_score),
            "acceleration_score": _safe(acceleration_score),

            "allocated_capital": _safe(allocated_capital),
            "allocation_weight": _safe(allocation_weight),

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

        # 🔥 NEW
        momentum: float = 0.0,
        velocity: float = 0.0,
        mean_reversion_score: float = 0.0,
        pressure_score: float = 0.0,
        acceleration_score: float = 0.0,
    ) -> None:

        entry_price = _safe(entry_price)
        exit_price = _safe(exit_price)
        quantity = _safe(quantity)

        gross_pnl_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0
        gross_pnl_usd = (exit_price - entry_price) * quantity

        normalized_entry_costs = self._normalize_cost_payload(entry_costs)
        normalized_exit_costs = self._normalize_cost_payload(exit_costs)

        total_cost = normalized_entry_costs["total_cost_usd"] + normalized_exit_costs["total_cost_usd"]
        net_pnl_usd = gross_pnl_usd - total_cost

        payload = {
            "event": "CLOSE",
            "symbol": symbol,
            "asset_class": asset_class,

            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,

            "gross_pnl_usd": gross_pnl_usd,
            "net_pnl_usd": net_pnl_usd,

            "exit_reason": reason,
            "hold_minutes": _safe(hold_minutes),

            # 🔥 intelligence snapshot at exit
            "momentum": _safe(momentum),
            "velocity": _safe(velocity),
            "mean_reversion_score": _safe(mean_reversion_score),
            "pressure_score": _safe(pressure_score),
            "acceleration_score": _safe(acceleration_score),
        }

        self._write(payload)