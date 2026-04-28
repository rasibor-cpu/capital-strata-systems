from __future__ import annotations

from typing import Any, Tuple

from backend.data.coinbase_historical_downloader import load_runtime_asset


class SafeSignalProvider:
    """
    Phase 3D-F: Futures-calibrated provider with directional-entry refinement.

    PCNRASS intent:
    - Preserve working futures activation from Phase 3D-E
    - Keep crypto/FX selective
    - Add momentum-direction confirmation to reduce early entries
    - No random fallback
    - Deterministic output
    """

    def __init__(self) -> None:
        self.last_symbol = None
        self.repeat_count = 0

    def _num(self, v: Any, d: float = 0.0) -> float:
        try:
            if v is None:
                return d
            return float(v)
        except Exception:
            return d

    def _clamp(self, v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, float(v)))

    def _is_futures(self, symbol: str) -> bool:
        futures_roots = ("ES", "NQ", "GC", "CL", "ZN")
        return str(symbol or "").upper().startswith(futures_roots)

    def get_signal(self, symbol: str, asset_class: str) -> Tuple[float, float]:
        try:
            row = load_runtime_asset(symbol)

            if not isinstance(row, dict):
                print(f"[SIGNAL BLOCKED] {symbol} -> BAD_RUNTIME_ROW {type(row).__name__}")
                return 0.0, 0.0

            price = self._num(row.get("price", row.get("current_price", 0.0)))
            vwap = self._num(row.get("vwap", price))

            momentum_raw = self._num(row.get("momentum", 0.0))
            momentum = abs(momentum_raw)

            volatility = abs(self._num(row.get("volatility", row.get("avg_volatility", 0.0))))
            trend = abs(self._num(row.get("trend_efficiency", 0.0)))
            spread = abs(self._num(row.get("spread_bps", 0.0)))

            if price <= 0:
                print(f"[SIGNAL BLOCKED] {symbol} -> BAD_PRICE")
                return 0.0, 0.0

            vwap_dev = abs((price - vwap) / price) if vwap > 0 else 0.0

            momentum_s = self._clamp(momentum * 50.0, 0.0, 1.0)
            vwap_s = self._clamp(vwap_dev * 400.0, 0.0, 1.0)
            vol_s = self._clamp(volatility * 60.0, 0.0, 1.0)
            trend_s = self._clamp(trend, 0.0, 1.0)

            spread_penalty = self._clamp(spread / 80.0, 0.0, 0.25)

            direction_alignment = 1.0 if momentum_raw > 0 else 0.6

            core = (
                momentum_s * 0.30
                + vwap_s * 0.30
                + vol_s * 0.15
                + trend_s * 0.25
            ) * direction_alignment

            core = self._clamp(core - spread_penalty, 0.0, 1.0)

            if symbol == self.last_symbol:
                self.repeat_count += 1
            else:
                self.repeat_count = 0

            self.last_symbol = symbol
            core += min(0.05 * self.repeat_count, 0.15)
            core = self._clamp(core, 0.0, 1.0)

            if self._is_futures(symbol):
                core += 0.20
                trend_s = self._clamp(trend_s + 0.10, 0.0, 1.0)

            core = self._clamp(core, 0.0, 1.0)

            signal_score = 5.0 + (core * 11.0)

            probability = (
                0.40
                + core * 0.45
                + trend_s * 0.10
                + momentum_s * 0.05
                - spread_penalty
            )

            if self._is_futures(symbol):
                probability += 0.05

            probability = self._clamp(probability, 0.05, 0.90)

            print(
                f"[DECISION] {symbol} | score={signal_score:.2f} "
                f"prob={probability:.3f} core={core:.3f} "
                f"mom={momentum_raw:.5f} align={direction_alignment:.1f} "
                f"rep={self.repeat_count}"
            )

            return round(signal_score, 4), round(probability, 4)

        except Exception as e:
            print(f"[SIGNAL ERROR] {symbol}: {str(e)[:120]}")
            return 0.0, 0.0
