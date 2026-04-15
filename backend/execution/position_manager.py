from __future__ import annotations

from typing import Dict, List
from datetime import datetime


class PositionManager:

    DEFAULT_TRAIL_TRIGGER_PCT = 0.015
    DEFAULT_TRAIL_STOP_PCT = 0.0075

    ASSET_CLASS_PROFILES = {
        "crypto": {
            "trigger_pct": 0.018,
            "stop_pct": 0.009,
            "tier2_stop": 0.007,
            "tier3_stop": 0.0055,
        },
        "fx": {
            "trigger_pct": 0.010,
            "stop_pct": 0.005,
            "tier2_stop": 0.004,
            "tier3_stop": 0.003,
        },
        "options": {
            "trigger_pct": 0.022,
            "stop_pct": 0.011,
            "tier2_stop": 0.008,
            "tier3_stop": 0.006,
        },
        "futures": {
            "trigger_pct": 0.015,
            "stop_pct": 0.007,
            "tier2_stop": 0.0055,
            "tier3_stop": 0.004,
        },
        "default": {
            "trigger_pct": 0.015,
            "stop_pct": 0.0075,
            "tier2_stop": 0.006,
            "tier3_stop": 0.0045,
        },
    }

    def __init__(self):
        self.positions: Dict[str, Dict] = {}
        self.closed_log: List[Dict] = []

    # =========================
    # CORE OPEN (PQR-1 UPGRADE)
    # =========================

    def open_position(
        self,
        *,
        symbol: str,
        entry_price: float,
        size: float,
        take_profit: float,
        stop_loss: float,
        side: str = "LONG",
        confidence: float = 0.0,
        regime: str = "UNKNOWN",
    ) -> None:

        if symbol in self.positions:
            return

        side = str(side).upper().strip()
        if side not in {"LONG", "SHORT"}:
            side = "LONG"

        asset_class = self._classify_asset(symbol)
        profile = self.ASSET_CLASS_PROFILES.get(
            asset_class,
            self.ASSET_CLASS_PROFILES["default"]
        )

        self.positions[symbol] = {
            "symbol": symbol,
            "asset_class": asset_class,
            "entry_price": float(entry_price),
            "size": abs(float(size)),
            "side": side,
            "take_profit": float(take_profit),
            "stop_loss": float(stop_loss),
            "confidence": float(confidence),
            "regime": regime,
            "opened_at": datetime.utcnow(),

            # trailing engine fields
            "peak_price_seen": float(entry_price),
            "trailing_active": False,
            "trail_trigger_pct": profile["trigger_pct"],
            "trail_stop_pct": profile["stop_pct"],

            # adaptive ladder tiers
            "tier_level": 1,
            "tier2_stop_pct": profile["tier2_stop"],
            "tier3_stop_pct": profile["tier3_stop"],

            # runtime tracking
            "current_price": float(entry_price),
            "unrealized_pnl": 0.0,
        }

    # =========================
    # BACKWARD COMPATIBILITY
    # =========================

    def open_long_position(self, **kwargs):
        self.open_position(side="LONG", **kwargs)

    def open_short_position(self, **kwargs):
        self.open_position(side="SHORT", **kwargs)

    # =========================
    # ASSET CLASSIFIER
    # =========================

    def _classify_asset(self, symbol: str) -> str:
        s = str(symbol).upper()

        # Options
        if "-C" in s or "-P" in s:
            return "options"

        # Crypto
        crypto_markers = [
            "BTC", "ETH", "SOL", "XRP", "ADA",
            "DOGE", "AVAX", "LINK", "LTC", "BCH"
        ]
        if any(x in s for x in crypto_markers):
            return "crypto"

        # FX
        if "_" in s and len(s) >= 7:
            return "fx"

        # Futures
        futures_symbols = [
            "ES", "NQ", "CL", "GC", "ZN", "YM", "RTY"
        ]
        if s in futures_symbols:
            return "futures"

        return "default"
    # =========================
    # UPDATE
    # =========================

    def update_positions(self, market_prices: Dict[str, float]) -> None:

        to_close = []

        for symbol, pos in self.positions.items():

            if symbol not in market_prices:
                continue

            price = float(market_prices[symbol])
            side = pos["side"]
            entry_price = float(pos["entry_price"])

            pos["current_price"] = price
            pos["unrealized_pnl"] = self._compute_pnl(
                side=side,
                entry=entry_price,
                exit_price=price,
                size=float(pos["size"]),
            )

            # ---------------------------
            # Peak favorable excursion
            # ---------------------------
            if side == "LONG":
                pos["peak_price_seen"] = max(
                    float(pos["peak_price_seen"]),
                    price
                )
            else:
                pos["peak_price_seen"] = min(
                    float(pos["peak_price_seen"]),
                    price
                )

            # ---------------------------
            # Profit ladder escalation
            # ---------------------------
            self._apply_profit_ladder(pos)

            # ---------------------------
            # Stop loss always active
            # ---------------------------
            if side == "LONG":
                if price <= pos["stop_loss"]:
                    to_close.append((symbol, price, "SL"))
                    continue

            elif side == "SHORT":
                if price >= pos["stop_loss"]:
                    to_close.append((symbol, price, "SL"))
                    continue

            # ---------------------------
            # Activate trailing
            # ---------------------------
            if not pos["trailing_active"]:
                if self._trail_trigger_hit(pos, price):
                    pos["trailing_active"] = True

            # ---------------------------
            # Trailing exit
            # ---------------------------
            if pos["trailing_active"]:
                if self._trail_exit_hit(pos, price):
                    to_close.append((symbol, price, "TRAIL_TP"))
                    continue

            # ---------------------------
            # Legacy TP fallback
            # ---------------------------
            if not pos["trailing_active"]:
                if side == "LONG":
                    if price >= pos["take_profit"]:
                        pos["trailing_active"] = True
                elif side == "SHORT":
                    if price <= pos["take_profit"]:
                        pos["trailing_active"] = True

        for symbol, exit_price, reason in to_close:
            self.close_position(symbol, exit_price, reason)

    # =========================
    # PROFIT LADDER ENGINE
    # =========================

    def _apply_profit_ladder(self, pos: Dict) -> None:
        pnl = float(pos["unrealized_pnl"])
        tier = int(pos["tier_level"])

        # Tier thresholds by absolute unrealized pnl
        if pnl >= 25 and tier < 3:
            pos["tier_level"] = 3
            pos["trail_stop_pct"] = float(pos["tier3_stop_pct"])

        elif pnl >= 10 and tier < 2:
            pos["tier_level"] = 2
            pos["trail_stop_pct"] = float(pos["tier2_stop_pct"])

    # =========================
    # CLOSE
    # =========================

    def close_position(self, symbol: str, exit_price: float, reason: str):

        if symbol not in self.positions:
            return

        pos = self.positions.pop(symbol)

        entry = float(pos["entry_price"])
        size = float(pos["size"])
        side = pos["side"]

        pnl = self._compute_pnl(
            side=side,
            entry=entry,
            exit_price=float(exit_price),
            size=size,
        )

        self.closed_log.append({
            "symbol": symbol,
            "asset_class": pos.get("asset_class", "default"),
            "entry_price": entry,
            "exit_price": float(exit_price),
            "size": size,
            "side": side,
            "pnl": pnl,
            "reason": reason,
            "confidence": pos["confidence"],
            "regime": pos["regime"],
            "tier_level": pos.get("tier_level", 1),
            "opened_at": pos["opened_at"],
            "closed_at": datetime.utcnow(),
        })
    # =========================
    # HELPERS
    # =========================

    def _compute_pnl(
        self,
        *,
        side: str,
        entry: float,
        exit_price: float,
        size: float,
    ) -> float:
        if side == "SHORT":
            return (entry - exit_price) * size
        return (exit_price - entry) * size

    def _trail_trigger_hit(self, pos: Dict, price: float) -> bool:
        entry = float(pos["entry_price"])
        trigger_pct = float(pos["trail_trigger_pct"])
        side = pos["side"]

        if side == "LONG":
            return price >= entry * (1.0 + trigger_pct)
        else:
            return price <= entry * (1.0 - trigger_pct)

    def _trail_exit_hit(self, pos: Dict, price: float) -> bool:
        peak = float(pos["peak_price_seen"])
        trail_pct = float(pos["trail_stop_pct"])
        side = pos["side"]

        if side == "LONG":
            trail_level = peak * (1.0 - trail_pct)
            return price <= trail_level
        else:
            trail_level = peak * (1.0 + trail_pct)
            return price >= trail_level

    # =========================
    # GETTERS
    # =========================

    def get_open_positions(self) -> List[Dict]:
        return list(self.positions.values())

    def get_closed_positions(self) -> List[Dict]:
        return self.closed_log

    def get_total_pnl(self) -> float:
        return sum(t["pnl"] for t in self.closed_log)