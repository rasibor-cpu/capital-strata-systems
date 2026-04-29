from __future__ import annotations

from typing import Any, Optional, Tuple
from backend.data.coinbase_historical_downloader import load_runtime_asset


class SafeSignalProvider:

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

    def _row_price(self, row):
        return self._num(row.get("price", row.get("current_price", 0.0)))

    def get_signal(self, symbol=None, asset_class=None, asset=None, **kwargs) -> Tuple[float, float]:

        if asset is None:
            try:
                asset = load_runtime_asset(symbol)
            except:
                return 0.0, 0.0

        if not isinstance(asset, dict):
            return 0.0, 0.0

        velocity = self._num(asset.get("velocity", 0.0))
        acceleration = self._num(asset.get("acceleration", 0.0))
        pressure = self._num(asset.get("pressure_score", 0.0))
        liquidity = self._num(asset.get("volume_24h", 0.0))

        core = (
            abs(velocity) * 0.4 +
            abs(acceleration) * 0.3 +
            abs(pressure) * 0.2 +
            (liquidity / 1_000_000.0) * 0.1
        )

        core = self._clamp(core, 0.0, 1.0)

        score = 6.0 + core * 12.0

        # --- PCNRASS QUALITY FILTER ---
        if core < 0.28:
            return 0.0, 0.0

        prob = 0.45 + core * 0.4
        prob = self._clamp(prob, 0.05, 0.90)

        print(f"[DECISION] {symbol} | score={score:.2f} prob={prob:.3f} core={core:.3f}")

        return score, prob
