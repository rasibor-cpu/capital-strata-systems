from __future__ import annotations

from typing import Any, Tuple
from backend.data.coinbase_historical_downloader import load_runtime_asset


class SafeSignalProvider:
    """
    Phase 4C (Corrected): Full feature integration with conditional activation

    - Restores strong core (momentum + vwap + trend + volatility)
    - Uses advanced features ONLY when available (no dilution)
    - Preserves futures dominance
    - PCNRASS compliant (no regression risk)
    """

    def __init__(self) -> None:
        self.last_symbol = None
        self.repeat_count = 0

    def _num(self, v: Any, d: float = 0.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    def _clamp(self, v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    def _is_futures(self, symbol: str) -> bool:
        return symbol.startswith(("ES", "NQ", "GC", "CL", "ZN"))

    def _is_primary_crypto(self, symbol: str) -> bool:
        return symbol in ("BTC-USD", "ETH-USD")

    def _is_major_fx(self, symbol: str) -> bool:
        return symbol in ("EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF")

    def get_signal(self, symbol: str, asset_class: str) -> Tuple[float, float]:

        try:
            row = load_runtime_asset(symbol)

            if not isinstance(row, dict):
                return 0.0, 0.0

            # --- CORE INPUTS ---
            price = self._num(row.get("price", 0.0))
            vwap = self._num(row.get("vwap", price))

            momentum_raw = self._num(row.get("momentum", 0.0))
            momentum = abs(momentum_raw)

            volatility = abs(self._num(row.get("volatility", 0.0)))
            trend = abs(self._num(row.get("trend_efficiency", 0.0)))
            spread = abs(self._num(row.get("spread_bps", 0.0)))

            # --- OPTIONAL FEATURES ---
            velocity = abs(self._num(row.get("velocity", 0.0)))
            acceleration = abs(self._num(row.get("acceleration", 0.0)))
            pressure = abs(self._num(row.get("pressure_score", 0.0)))
            liquidity = self._num(row.get("top_of_book_depth", 0.0))

            if price <= 0:
                return 0.0, 0.0

            # --- DERIVED ---
            vwap_dev = abs((price - vwap) / price) if vwap > 0 else 0.0
            mean_reversion = self._clamp(vwap_dev * 500.0, 0, 1)

            # --- NORMALIZATION ---
            momentum_s = self._clamp(momentum * 50.0, 0, 1)
            vwap_s = self._clamp(vwap_dev * 400.0, 0, 1)
            vol_s = self._clamp(volatility * 60.0, 0, 1)
            trend_s = self._clamp(trend, 0, 1)

            velocity_s = self._clamp(velocity * 40.0, 0, 1)
            accel_s = self._clamp(acceleration * 30.0, 0, 1)
            pressure_s = self._clamp(pressure, 0, 1)
            liquidity_s = self._clamp(liquidity / 100000, 0, 1)

            spread_penalty = self._clamp(spread / 80.0, 0, 0.25)

            # --- FEATURE FLAGS ---
            has_velocity = velocity > 0
            has_accel = acceleration > 0
            has_pressure = pressure > 0
            has_liquidity = liquidity > 0

            # --- DIRECTION FILTER ---
            direction_alignment = 1.0 if momentum_raw > 0 else 0.6

            # =========================
            # 🔥 STRONG CORE (RESTORED)
            # =========================
            core = (
                momentum_s * 0.30
                + vwap_s * 0.30
                + trend_s * 0.20
                + vol_s * 0.20
            ) * direction_alignment

            # --- CONDITIONAL FEATURES ---
            if has_velocity:
                core += velocity_s * 0.08

            if has_accel:
                core += accel_s * 0.07

            if has_pressure:
                core += pressure_s * 0.08

            if has_liquidity:
                core += liquidity_s * 0.05

            # --- MEAN REVERSION (ALWAYS SAFE) ---
            core += mean_reversion * 0.10

            core = self._clamp(core - spread_penalty, 0, 1)

            # --- PERSISTENCE ---
            if symbol == self.last_symbol:
                self.repeat_count += 1
            else:
                self.repeat_count = 0

            self.last_symbol = symbol
            core += min(0.05 * self.repeat_count, 0.15)

            # --- ASSET CALIBRATION ---
            if self._is_futures(symbol):
                core += 0.20
                trend_s += 0.10

            elif self._is_primary_crypto(symbol):
                core += 0.08

            elif self._is_major_fx(symbol):
                core += 0.05

            core = self._clamp(core, 0, 1)

            # --- SCORE ---
            score = 5 + core * 11

            # --- PROBABILITY ---
            prob = (
                0.40
                + core * 0.40
                + trend_s * 0.10
                + velocity_s * 0.05
                + pressure_s * 0.05
                - spread_penalty
            )

            if self._is_futures(symbol):
                prob += 0.05

            prob = self._clamp(prob, 0.05, 0.90)

            print(
                f"[DECISION] {symbol} | score={score:.2f} prob={prob:.3f} core={core:.3f}"
            )

            return round(score, 4), round(prob, 4)

        except Exception as e:
            print(f"[SIGNAL ERROR] {symbol}: {str(e)[:100]}")
            return 0.0, 0.0
