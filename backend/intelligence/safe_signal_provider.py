from __future__ import annotations

from typing import Any, Optional, Tuple

from backend.data.coinbase_historical_downloader import load_runtime_asset


class SafeSignalProvider:
    """
    Phase 5C / 5D PCNRASS-safe unified multi-asset signal provider.

    Preserved behavior:
    - Uses real-data Phase 5B features:
      velocity, acceleration, pressure_score, top_of_book_depth.
    - Keeps futures/options/crypto/FX working together.
    - Preserves decision logging and scoring structure.
    - No fake/random fallback.

    Surgical compatibility improvement:
    - Supports BOTH call styles without breaking either one:
        get_signal(symbol, asset_class)
        get_signal(asset=asset, symbol=symbol, asset_class=asset_class)

    This is intentionally limited to SafeSignalProvider only.
    It does not modify dashboard, broker logic, PnL, auth, session, or execution flow.
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
        return str(symbol or "").upper().startswith(("ES", "NQ", "GC", "CL", "ZN"))

    def _is_crypto(self, symbol: str) -> bool:
        s = str(symbol or "").upper()
        return (
            s.endswith("-USD")
            or s.endswith("-USDT")
            or any(
                token in s
                for token in (
                    "BTC",
                    "ETH",
                    "SOL",
                    "XRP",
                    "ADA",
                    "DOGE",
                    "AVAX",
                    "LINK",
                    "LTC",
                    "BCH",
                )
            )
        )

    def _is_primary_crypto(self, symbol: str) -> bool:
        return str(symbol or "").upper() in ("BTC-USD", "ETH-USD", "SOL-USD")

    def _is_major_fx(self, symbol: str) -> bool:
        return str(symbol or "").upper() in (
            "EUR_USD",
            "GBP_USD",
            "USD_JPY",
            "USD_CHF",
            "USD_CAD",
            "AUD_USD",
            "NZD_USD",
            "EUR_GBP",
            "EUR_JPY",
            "GBP_JPY",
        )

    def _is_option(self, symbol: str) -> bool:
        s = str(symbol or "").upper()
        return (
            s.endswith("-C")
            or s.endswith("-P")
            or s.endswith("_CALL")
            or s.endswith("_PUT")
        )

    def _option_proxy_candidates(self, symbol: str) -> list[str]:
        s = str(symbol or "").upper()
        root = s
        for suffix in ("-C", "-P", "_CALL", "_PUT"):
            if root.endswith(suffix):
                root = root[: -len(suffix)]

        proxy_map = {
            "SPY": ["SPY", "ES"],
            "QQQ": ["QQQ", "NQ"],
            "AAPL": ["AAPL", "QQQ", "NQ"],
        }
        return proxy_map.get(root, [root])

    def _row_price(self, row: dict[str, Any]) -> float:
        return self._num(
            row.get(
                "price",
                row.get(
                    "current_price",
                    row.get("last", row.get("close", row.get("Close", 0.0))),
                ),
            )
        )

    def _load_row(self, symbol: str) -> tuple[dict[str, Any] | None, bool, str | None]:
        try:
            row = load_runtime_asset(symbol)
            if isinstance(row, dict) and self._row_price(row) > 0:
                return row, False, None
        except Exception:
            pass

        if self._is_option(symbol):
            for proxy in self._option_proxy_candidates(symbol):
                try:
                    row = load_runtime_asset(proxy)
                    if isinstance(row, dict) and self._row_price(row) > 0:
                        row = dict(row)
                        row["_proxy_source"] = proxy
                        return row, True, proxy
                except Exception:
                    continue

        return None, False, None

    def _resolve_row(
        self,
        symbol: Optional[str],
        asset: Optional[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, bool, str | None]:
        """
        PCNRASS-safe compatibility resolver.

        If dashboard passes a full asset row, use it.
        Otherwise preserve the existing behavior and load data by symbol.
        """
        if isinstance(asset, dict) and self._row_price(asset) > 0:
            return asset, False, asset.get("_proxy_source")

        if not symbol:
            return None, False, None

        return self._load_row(str(symbol))

    def get_signal(
        self,
        symbol: Optional[str] = None,
        asset_class: Optional[str] = None,
        asset: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Tuple[float, float]:
        """
        Returns:
            score, probability

        Compatible call styles:
            get_signal(symbol, asset_class)
            get_signal(asset=asset, symbol=symbol, asset_class=asset_class)
        """
        try:
            # Accept symbol/asset_class if passed via kwargs by any older dashboard variant.
            if symbol is None:
                symbol = kwargs.get("symbol")
            if asset_class is None:
                asset_class = kwargs.get("asset_class")
            if asset is None and isinstance(kwargs.get("asset"), dict):
                asset = kwargs.get("asset")

            symbol = str(symbol or "").strip()
            asset_class = str(asset_class or "").strip().upper()

            row, proxy_used, proxy_source = self._resolve_row(symbol, asset)

            if not isinstance(row, dict):
                print(f"[SIGNAL BLOCKED] {symbol} -> NO_VALID_ROW")
                return 0.0, 0.0

            price = self._row_price(row)
            if price <= 0:
                print(f"[SIGNAL BLOCKED] {symbol} -> BAD_PRICE")
                return 0.0, 0.0

            vwap = self._num(row.get("vwap", price))
            momentum_raw = self._num(row.get("momentum", 0.0))
            momentum = abs(momentum_raw)
            volatility = abs(self._num(row.get("volatility", row.get("avg_volatility", 0.0))))
            trend = abs(self._num(row.get("trend_efficiency", 0.0)))
            spread = abs(self._num(row.get("spread_bps", 0.0)))

            # Phase 5B real-data features.
            velocity = self._num(row.get("velocity", 0.0))
            acceleration = self._num(row.get("acceleration", 0.0))
            pressure = abs(self._num(row.get("pressure_score", row.get("pressure", 0.0))))
            liquidity = self._num(row.get("top_of_book_depth", row.get("volume_24h", 0.0)))

            vwap_dev = abs((price - vwap) / price) if vwap > 0 else 0.0
            mean_reversion = self._clamp(vwap_dev * 500.0, 0.0, 1.0)

            # Normalized core features.
            momentum_s = self._clamp(momentum * 50.0, 0.0, 1.0)
            vwap_s = self._clamp(vwap_dev * 400.0, 0.0, 1.0)
            vol_s = self._clamp(volatility * 60.0, 0.0, 1.0)
            trend_s = self._clamp(trend, 0.0, 1.0)

            # Active feature intelligence.
            velocity_s = self._clamp(abs(velocity) * 40.0, 0.0, 1.0)
            accel_s = self._clamp(abs(acceleration) * 30.0, 0.0, 1.0)
            pressure_s = self._clamp(pressure, 0.0, 1.0)
            liquidity_s = self._clamp(liquidity / 1_000_000.0, 0.0, 1.0)

            spread_penalty = self._clamp(spread / 80.0, 0.0, 0.25)

            # Direction filter: positive momentum has full conviction; negative/flat is discounted.
            direction_alignment = 1.0 if momentum_raw > 0 else 0.6

            core = (
                momentum_s * 0.24
                + vwap_s * 0.24
                + trend_s * 0.16
                + vol_s * 0.14
                + mean_reversion * 0.08
                + velocity_s * 0.06
                + accel_s * 0.04
                + pressure_s * 0.06
                + liquidity_s * 0.03
            ) * direction_alignment

            core = self._clamp(core - spread_penalty, 0.0, 1.0)

            if symbol == self.last_symbol:
                self.repeat_count += 1
            else:
                self.repeat_count = 0
            self.last_symbol = symbol

            # Preserved from Phase 5C.
            core += min(0.05 * self.repeat_count, 0.15)

            # Asset calibration: active but controlled.
            if self._is_futures(symbol):
                core += 0.20
                trend_s = self._clamp(trend_s + 0.10, 0.0, 1.0)

            elif self._is_option(symbol) or asset_class == "OPTIONS":
                core += 0.16
                trend_s = self._clamp(trend_s + 0.08, 0.0, 1.0)
                if proxy_used:
                    core -= 0.02

            elif self._is_primary_crypto(symbol):
                core += 0.16
                trend_s = self._clamp(trend_s + 0.05, 0.0, 1.0)

            elif self._is_crypto(symbol):
                core += 0.12
                trend_s = self._clamp(trend_s + 0.03, 0.0, 1.0)

            elif self._is_major_fx(symbol):
                core += 0.12
                trend_s = self._clamp(trend_s + 0.05, 0.0, 1.0)

            core = self._clamp(core, 0.0, 1.0)

            # Preserved Phase 5C score scale.
            score = 5.0 + core * 11.0

            prob = (
                0.40
                + core * 0.36
                + trend_s * 0.08
                + velocity_s * 0.04
                + accel_s * 0.03
                + pressure_s * 0.04
                + liquidity_s * 0.02
                - spread_penalty
            )

            if self._is_futures(symbol):
                prob += 0.05
            elif self._is_option(symbol) or asset_class == "OPTIONS":
                prob += 0.05
                if proxy_used:
                    prob -= 0.015
            elif self._is_primary_crypto(symbol):
                prob += 0.055
            elif self._is_crypto(symbol):
                prob += 0.04
            elif self._is_major_fx(symbol):
                prob += 0.04

            prob = self._clamp(prob, 0.05, 0.90)

            proxy_note = f" proxy={proxy_source}" if proxy_used and proxy_source else ""
            print(
                f"[DECISION] {symbol} | score={score:.2f} prob={prob:.3f} "
                f"core={core:.3f}{proxy_note} "
                f"vel={velocity_s:.3f} acc={accel_s:.3f} "
                f"press={pressure_s:.3f} liq={liquidity_s:.3f}"
            )

            return round(score, 4), round(prob, 4)

        except Exception as e:
            print(f"[SIGNAL ERROR] {symbol}: {str(e)[:120]}")
            return 0.0, 0.0
