from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path so absolute imports work
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.scanner.market_scanner import MarketScanner, ScannerConfig
from backend.scanner.fx_market_scanner import OandaFXMarketScanner, FXScannerConfig


@dataclass
class UnifiedScannerConfig:
    enable_crypto: bool = True
    enable_fx: bool = True
    crypto_top_n: int = 5
    fx_top_n: int = 5
    final_top_n: int = 8


class UnifiedMarketScanner:
    """
    CSS Unified Market Scanner

    Combines ranked opportunities from:
    - Coinbase crypto scanner
    - OANDA FX scanner

    Produces a richer normalized opportunity list for the router/scorer.
    """

    def __init__(self, config: Optional[UnifiedScannerConfig] = None) -> None:
        self.config = config or UnifiedScannerConfig()

    def scan_crypto(self) -> List[Dict[str, Any]]:
        if not self.config.enable_crypto:
            return []

        scanner = MarketScanner(
            config=ScannerConfig(
                top_n=self.config.crypto_top_n,
                quote_currency="USD",
                candle_granularity_seconds=900,
                lookback_candles=50,
                min_quote_volume_usd=10000.0,
                max_products_to_scan=120,
                vwap_window=20,
            )
        )

        results = scanner.scan_market()
        out: List[Dict[str, Any]] = []

        for r in results:
            last_price = self._to_float(getattr(r, "last_price", 0.0), 0.0)
            spread_pct = self._to_float(getattr(r, "spread_pct", 0.0), 0.0)
            volatility_pct = self._to_float(getattr(r, "volatility_pct", 0.0), 0.0)
            trend_pct = self._to_float(getattr(r, "trend_pct", 0.0), 0.0)
            scanner_score = self._to_float(getattr(r, "score", 0.0), 0.0)

            volume_24h = self._first_attr_float(
                r,
                ["quote_volume_usd", "quote_volume", "volume_24h", "notional_volume", "base_volume"],
                0.0,
            )
            avg_volume_24h = self._derive_avg_volume(volume_24h)
            spread_bps = self._pct_to_bps(spread_pct)

            top_of_book_depth = self._derive_depth(
                asset_class="CRYPTO",
                volume_24h=volume_24h,
                last_price=last_price,
            )
            slippage_bps = self._derive_slippage_bps(
                asset_class="CRYPTO",
                spread_bps=spread_bps,
                volume_24h=volume_24h,
            )
            avg_volatility = self._derive_avg_volatility(volatility_pct)
            order_flow_delta = self._derive_order_flow_delta(
                trend_pct=trend_pct,
                scanner_score=scanner_score,
                spread_pct=spread_pct,
                volatility_pct=volatility_pct,
            )
            buy_pressure, sell_pressure = self._derive_pressure_split(order_flow_delta)
            recent_high, recent_low = self._derive_recent_range(
                last_price=last_price,
                volatility_pct=volatility_pct,
            )
            rejection_strength = self._derive_rejection_strength(
                trend_pct=trend_pct,
                spread_pct=spread_pct,
                volatility_pct=volatility_pct,
            )
            wick_reversal_strength = self._derive_wick_reversal_strength(
                trend_pct=trend_pct,
                volatility_pct=volatility_pct,
            )
            liquidity_sweep_flag = self._derive_liquidity_sweep_flag(
                scanner_score=scanner_score,
                volatility_pct=volatility_pct,
                trend_pct=trend_pct,
            )

            out.append(
                {
                    "asset_class": "CRYPTO",
                    "symbol": str(getattr(r, "product_id", "UNKNOWN")),
                    "score": scanner_score,
                    "last_price": last_price,
                    "spread_pct": spread_pct,
                    "spread_bps": spread_bps,
                    "volatility_pct": volatility_pct,
                    "trend_pct": trend_pct,
                    "source": "Coinbase",
                    "volume_24h": volume_24h,
                    "avg_volume_24h": avg_volume_24h,
                    "avg_volatility": avg_volatility,
                    "top_of_book_depth": top_of_book_depth,
                    "slippage_bps": slippage_bps,
                    "order_flow_delta": order_flow_delta,
                    "buy_pressure": buy_pressure,
                    "sell_pressure": sell_pressure,
                    "recent_high": recent_high,
                    "recent_low": recent_low,
                    "rejection_strength": rejection_strength,
                    "wick_reversal_strength": wick_reversal_strength,
                    "liquidity_sweep_flag": liquidity_sweep_flag,
                }
            )

        return out

    def scan_fx(self) -> List[Dict[str, Any]]:
        if not self.config.enable_fx:
            return []

        scanner = OandaFXMarketScanner(
            config=FXScannerConfig(
                top_n=self.config.fx_top_n,
                granularity="M15",
                count=60,
                min_avg_range_pct=0.0001,
                min_abs_spread_from_vwap_pct=0.00001,
                vwap_window=20,
                debug=False,
            )
        )

        results = scanner.scan_market()
        out: List[Dict[str, Any]] = []

        for r in results:
            last_price = self._to_float(getattr(r, "last_mid", 0.0), 0.0)
            spread_pct = self._to_float(getattr(r, "spread_from_vwap_pct", 0.0), 0.0)
            volatility_pct = self._to_float(getattr(r, "volatility_pct", 0.0), 0.0)
            trend_pct = self._to_float(getattr(r, "trend_pct", 0.0), 0.0)
            scanner_score = self._to_float(getattr(r, "score", 0.0), 0.0)

            volume_24h = self._first_attr_float(
                r,
                ["volume_24h", "quote_volume", "notional_volume"],
                0.0,
            )
            if volume_24h <= 0:
                volume_24h = self._estimate_fx_notional_volume(scanner_score, volatility_pct)

            avg_volume_24h = self._derive_avg_volume(volume_24h)
            spread_bps = self._pct_to_bps(spread_pct)

            top_of_book_depth = self._derive_depth(
                asset_class="FX",
                volume_24h=volume_24h,
                last_price=last_price,
            )
            slippage_bps = self._derive_slippage_bps(
                asset_class="FX",
                spread_bps=spread_bps,
                volume_24h=volume_24h,
            )
            avg_volatility = self._derive_avg_volatility(volatility_pct)
            order_flow_delta = self._derive_order_flow_delta(
                trend_pct=trend_pct,
                scanner_score=scanner_score,
                spread_pct=spread_pct,
                volatility_pct=volatility_pct,
            )
            buy_pressure, sell_pressure = self._derive_pressure_split(order_flow_delta)
            recent_high, recent_low = self._derive_recent_range(
                last_price=last_price,
                volatility_pct=volatility_pct,
            )
            rejection_strength = self._derive_rejection_strength(
                trend_pct=trend_pct,
                spread_pct=spread_pct,
                volatility_pct=volatility_pct,
            )
            wick_reversal_strength = self._derive_wick_reversal_strength(
                trend_pct=trend_pct,
                volatility_pct=volatility_pct,
            )
            liquidity_sweep_flag = self._derive_liquidity_sweep_flag(
                scanner_score=scanner_score,
                volatility_pct=volatility_pct,
                trend_pct=trend_pct,
            )

            out.append(
                {
                    "asset_class": "FX",
                    "symbol": str(getattr(r, "instrument", "UNKNOWN")),
                    "score": scanner_score,
                    "last_price": last_price,
                    "spread_pct": spread_pct,
                    "spread_bps": spread_bps,
                    "volatility_pct": volatility_pct,
                    "trend_pct": trend_pct,
                    "source": "OANDA",
                    "volume_24h": volume_24h,
                    "avg_volume_24h": avg_volume_24h,
                    "avg_volatility": avg_volatility,
                    "top_of_book_depth": top_of_book_depth,
                    "slippage_bps": slippage_bps,
                    "order_flow_delta": order_flow_delta,
                    "buy_pressure": buy_pressure,
                    "sell_pressure": sell_pressure,
                    "recent_high": recent_high,
                    "recent_low": recent_low,
                    "rejection_strength": rejection_strength,
                    "wick_reversal_strength": wick_reversal_strength,
                    "liquidity_sweep_flag": liquidity_sweep_flag,
                }
            )

        return out

    def scan_all(self) -> List[Dict[str, Any]]:
        combined: List[Dict[str, Any]] = []
        combined.extend(self.scan_crypto())
        combined.extend(self.scan_fx())

        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[: self.config.final_top_n]

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _first_attr_float(self, obj: Any, names: List[str], default: float = 0.0) -> float:
        for name in names:
            if hasattr(obj, name):
                value = getattr(obj, name)
                if value is not None:
                    return self._to_float(value, default)
        return default

    @staticmethod
    def _pct_to_bps(value: float) -> float:
        return float(value) * 10000.0

    @staticmethod
    def _derive_avg_volume(volume_24h: float) -> float:
        if volume_24h <= 0:
            return 0.0
        return volume_24h * 0.72

    @staticmethod
    def _derive_avg_volatility(volatility_pct: float) -> float:
        if volatility_pct <= 0:
            return 0.0
        return volatility_pct * 0.82

    @staticmethod
    def _derive_depth(asset_class: str, volume_24h: float, last_price: float) -> float:
        if volume_24h <= 0:
            return 0.0

        if asset_class.upper() == "FX":
            depth_ratio = 0.0018
        else:
            depth_ratio = 0.0035

        depth = volume_24h * depth_ratio

        if last_price > 0:
            depth = max(depth, last_price * 25.0)

        return depth

    @staticmethod
    def _derive_slippage_bps(asset_class: str, spread_bps: float, volume_24h: float) -> float:
        if asset_class.upper() == "FX":
            base = max(0.3, spread_bps * 0.55)
            if volume_24h >= 20_000_000:
                return min(base, 1.2)
            if volume_24h >= 5_000_000:
                return min(max(base, 0.6), 2.0)
            return max(base, 1.5)

        base = max(0.6, spread_bps * 0.85)
        if volume_24h >= 50_000_000:
            return min(base, 2.0)
        if volume_24h >= 10_000_000:
            return min(max(base, 1.2), 3.5)
        if volume_24h >= 2_500_000:
            return min(max(base, 2.0), 5.5)
        return max(base, 4.5)

    @staticmethod
    def _derive_order_flow_delta(
        trend_pct: float,
        scanner_score: float,
        spread_pct: float,
        volatility_pct: float,
    ) -> float:
        quality_boost = min(scanner_score, 1.0) * 0.20
        trend_component = max(-1.0, min(1.0, trend_pct * 12.0))
        spread_penalty = min(max(spread_pct * 1500.0, 0.0), 0.20)
        vol_bonus = min(max(volatility_pct * 3.0, 0.0), 0.12)

        composite = trend_component + quality_boost + vol_bonus - spread_penalty
        return max(-1.0, min(1.0, composite))

    @staticmethod
    def _derive_pressure_split(order_flow_delta: float) -> tuple[float, float]:
        buy_pressure = 50.0 + (order_flow_delta * 50.0)
        buy_pressure = max(0.0, min(100.0, buy_pressure))
        sell_pressure = 100.0 - buy_pressure
        return buy_pressure, sell_pressure

    @staticmethod
    def _derive_recent_range(last_price: float, volatility_pct: float) -> tuple[float, float]:
        if last_price <= 0:
            return 0.0, 0.0

        band = max(last_price * max(volatility_pct, 0.0005) * 2.2, last_price * 0.001)
        recent_high = last_price + band
        recent_low = max(0.0, last_price - band)
        return recent_high, recent_low

    @staticmethod
    def _derive_rejection_strength(
        trend_pct: float,
        spread_pct: float,
        volatility_pct: float,
    ) -> float:
        raw = (
            min(abs(trend_pct) * 8.0, 0.55)
            + min(volatility_pct * 3.0, 0.30)
            + max(0.0, 0.18 - min(spread_pct * 1000.0, 0.18))
        )
        return max(0.0, min(1.0, raw))

    @staticmethod
    def _derive_wick_reversal_strength(trend_pct: float, volatility_pct: float) -> float:
        raw = min(abs(trend_pct) * 6.0, 0.45) + min(volatility_pct * 2.0, 0.25)
        return max(0.0, min(1.0, raw))

    @staticmethod
    def _derive_liquidity_sweep_flag(
        scanner_score: float,
        volatility_pct: float,
        trend_pct: float,
    ) -> bool:
        return bool(
            scanner_score >= 0.72
            and volatility_pct >= 0.001
            and abs(trend_pct) >= 0.002
        )

    @staticmethod
    def _estimate_fx_notional_volume(scanner_score: float, volatility_pct: float) -> float:
        base = 12_000_000.0
        boost = min(scanner_score, 1.0) * 8_000_000.0
        vol_boost = min(max(volatility_pct, 0.0), 0.01) * 300_000_000.0
        return base + boost + vol_boost


def print_unified_results(results: List[Dict[str, Any]]) -> None:
    print("\n=== CSS UNIFIED MARKET SCANNER ===")
    if not results:
        print("No qualifying opportunities found.")
        return

    for i, r in enumerate(results, start=1):
        print(
            f"{i:>2}. [{r['asset_class']}] {r['symbol']:<12} "
            f"score={r['score']:>8.4f}   "
            f"spread={r['spread_pct']:>10.6f}   "
            f"vol={r['volatility_pct']:>10.6f}   "
            f"trend={r['trend_pct']:>10.6f}   "
            f"vol24h={r['volume_24h']:>12.2f}   "
            f"src={r['source']}"
        )


if __name__ == "__main__":
    scanner = UnifiedMarketScanner(
        config=UnifiedScannerConfig(
            enable_crypto=True,
            enable_fx=True,
            crypto_top_n=5,
            fx_top_n=5,
            final_top_n=8,
        )
    )

    results = scanner.scan_all()
    print_unified_results(results)

    print("\nTop symbols only:")
    for item in results:
        print(f"{item['asset_class']} | {item['symbol']}")