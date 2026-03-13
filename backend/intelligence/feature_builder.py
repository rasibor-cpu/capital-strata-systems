from __future__ import annotations

from typing import Any, Dict, List


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class FeatureBuilder:
    """
    CSS Feature Builder

    Enriches raw market rows with institutional-style scoring inputs
    required by AIOpportunityScorer.
    """

    def __init__(self) -> None:
        pass

    def enrich_row(
        self,
        row: Dict[str, Any],
        candles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        enriched = dict(row)

        if not candles:
            return enriched

        closes = [_to_float(c.get("close")) for c in candles if _to_float(c.get("close")) > 0]
        highs = [_to_float(c.get("high")) for c in candles if _to_float(c.get("high")) > 0]
        lows = [_to_float(c.get("low")) for c in candles if _to_float(c.get("low")) > 0]
        volumes = [_to_float(c.get("volume")) for c in candles if _to_float(c.get("volume")) >= 0]

        if len(closes) < 5:
            return enriched

        current_price = closes[-1]
        recent_high = max(highs[-20:]) if highs else current_price
        recent_low = min(lows[-20:]) if lows else current_price

        # ---------------------------------------------------------
        # MOMENTUM
        # ---------------------------------------------------------
        first_close = closes[0]
        momentum = ((current_price - first_close) / first_close) if first_close > 0 else 0.0

        # ---------------------------------------------------------
        # TREND EFFICIENCY
        # ---------------------------------------------------------
        net_move = abs(closes[-1] - closes[0])
        path_move = 0.0
        for i in range(1, len(closes)):
            path_move += abs(closes[i] - closes[i - 1])
        trend_efficiency = (net_move / path_move) if path_move > 0 else 0.0
        trend_efficiency = _clamp(trend_efficiency)

        # ---------------------------------------------------------
        # VOLATILITY / AVG_VOLATILITY
        # ---------------------------------------------------------
        returns: List[float] = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            curr = closes[i]
            if prev > 0:
                returns.append(abs((curr - prev) / prev))

        volatility = sum(returns[-10:]) / max(len(returns[-10:]), 1)
        avg_volatility = sum(returns) / max(len(returns), 1)

        # ---------------------------------------------------------
        # VOLUME
        # ---------------------------------------------------------
        volume_24h = sum(volumes[-24:]) if volumes else 0.0
        avg_volume_24h = (sum(volumes) / len(volumes)) * 24 if volumes else 0.0

        # ---------------------------------------------------------
        # ORDER FLOW PRESSURE (proxy)
        # ---------------------------------------------------------
        up_count = 0
        down_count = 0
        up_volume = 0.0
        down_volume = 0.0

        for i in range(1, len(closes)):
            prev = closes[i - 1]
            curr = closes[i]
            vol = volumes[i] if i < len(volumes) else 0.0

            if curr > prev:
                up_count += 1
                up_volume += vol
            elif curr < prev:
                down_count += 1
                down_volume += vol

        total_directional = up_count + down_count
        order_flow_delta = ((up_count - down_count) / total_directional) if total_directional > 0 else 0.0
        buy_pressure = up_volume
        sell_pressure = down_volume

        # ---------------------------------------------------------
        # LIQUIDITY SWEEP / REJECTION PROXY
        # ---------------------------------------------------------
        last_high = highs[-1] if highs else current_price
        last_low = lows[-1] if lows else current_price
        last_close = closes[-1]

        range_size = max(last_high - last_low, 1e-9)
        upper_wick = max(last_high - last_close, 0.0)
        lower_wick = max(last_close - last_low, 0.0)
        wick_reversal_strength = max(upper_wick, lower_wick) / range_size

        liquidity_sweep_flag = False
        rejection_strength = 0.0

        if len(highs) >= 5 and len(lows) >= 5:
            prior_high = max(highs[-6:-1])
            prior_low = min(lows[-6:-1])

            if last_high > prior_high and last_close < prior_high:
                liquidity_sweep_flag = True
                rejection_strength = (last_high - last_close) / range_size

            elif last_low < prior_low and last_close > prior_low:
                liquidity_sweep_flag = True
                rejection_strength = (last_close - last_low) / range_size

        # ---------------------------------------------------------
        # TOP OF BOOK DEPTH / SLIPPAGE PROXIES
        # ---------------------------------------------------------
        avg_vol_per_candle = (sum(volumes) / len(volumes)) if volumes else 0.0
        top_of_book_depth = avg_vol_per_candle * current_price * 0.05

        spread_bps = abs(_to_float(enriched.get("spread_bps"), 0.0))
        if spread_bps <= 2:
            slippage_bps = 1.5
        elif spread_bps <= 5:
            slippage_bps = 2.5
        elif spread_bps <= 10:
            slippage_bps = 4.0
        elif spread_bps <= 20:
            slippage_bps = 7.5
        else:
            slippage_bps = 12.0

        # ---------------------------------------------------------
        # REGIME MAPPING
        # ---------------------------------------------------------
        base_signal = str(enriched.get("signal", "HOLD")).upper()
        base_regime = str(enriched.get("regime", "")).upper()

        regime = base_regime
        if not regime or regime == "MEAN_REVERSION":
            if trend_efficiency >= 0.55 and abs(momentum) >= 0.01:
                regime = "TREND"
            elif volatility > avg_volatility * 1.35:
                regime = "BREAKOUT"
            else:
                regime = "RANGE"

        if base_signal == "BUY" and regime == "RANGE":
            regime = "BREAKOUT"

        enriched.update(
            {
                "price": current_price,
                "current_price": current_price,
                "recent_high": recent_high,
                "recent_low": recent_low,
                "momentum": round(momentum, 6),
                "trend_efficiency": round(trend_efficiency, 6),
                "volatility": round(volatility, 6),
                "avg_volatility": round(max(avg_volatility, 1e-6), 6),
                "volume_24h": round(volume_24h, 2),
                "avg_volume_24h": round(max(avg_volume_24h, 1.0), 2),
                "order_flow_delta": round(order_flow_delta, 6),
                "buy_pressure": round(buy_pressure, 2),
                "sell_pressure": round(sell_pressure, 2),
                "liquidity_sweep_flag": liquidity_sweep_flag,
                "rejection_strength": round(_clamp(rejection_strength), 6),
                "wick_reversal_strength": round(_clamp(wick_reversal_strength), 6),
                "top_of_book_depth": round(top_of_book_depth, 2),
                "slippage_bps": round(slippage_bps, 4),
                "spread_bps": round(abs(spread_bps), 4),
                "regime": regime,
            }
        )

        return enriched

    def enrich_rows(
        self,
        rows: List[Dict[str, Any]],
        candle_cache: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows:
            asset = str(row.get("asset", row.get("symbol", ""))).strip()
            candles = candle_cache.get(asset, [])
            enriched.append(self.enrich_row(row, candles))

        return enriched