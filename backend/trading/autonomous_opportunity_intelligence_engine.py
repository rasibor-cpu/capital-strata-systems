from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from backend.intelligence.technical_intelligence import TechnicalIntelligenceEngine


class AutonomousOpportunityIntelligenceEngineError(RuntimeError):
    """Fail-closed exception for autonomous opportunity intelligence."""


class AutonomousOpportunityIntelligenceEngine:
    """Intelligence-only scorer for autonomous opportunity ranking and explainability."""

    TIMEFRAMES: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h", "1d")

    _CROSS_ASSET_GROUPS: dict[str, tuple[str, ...]] = {
        "CRYPTO_BETA": ("BTCUSD", "ETHUSD", "SOLUSD"),
        "INDEX_RISK": ("SPY", "QQQ", "ES", "NQ"),
        "USD_FX": ("DXY", "EURUSD", "GBPUSD", "USDJPY"),
        "METALS": ("XAUUSD", "GOLD", "XAGUSD", "SILVER", "GC", "SI"),
        "ENERGY_CAD": ("CL", "USOIL", "OIL", "USDCAD", "CAD"),
    }

    def __init__(
        self,
        technical_intelligence_engine: TechnicalIntelligenceEngine | None = None,
    ) -> None:
        self.technical_intelligence_engine = technical_intelligence_engine or TechnicalIntelligenceEngine()

    def analyze(
        self,
        *,
        instrument: Mapping[str, Any],
        candidate: Mapping[str, Any],
        decision: Mapping[str, Any],
        historical_records: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        symbol = self._normalize_symbol(instrument.get("symbol"))
        if not symbol:
            raise AutonomousOpportunityIntelligenceEngineError("instrument symbol must be non-empty")

        candles = list(candidate.get("market_snapshot", {}).get("candles") or [])
        if len(candles) < 3:
            raise AutonomousOpportunityIntelligenceEngineError("candidate market_snapshot.candles must contain at least 3 rows")

        now = datetime.now(UTC)
        technical = self._technical_intelligence(
            symbol=symbol,
            candidate=candidate,
            candles=candles,
            now=now,
        )
        multi_tf = self._multi_timeframe_analysis(candles)
        regime = self._market_regime_confirmation(
            multi_timeframe=multi_tf,
            instrument=instrument,
            now=now,
        )
        cross_asset = self._cross_asset_confirmation(symbol=symbol, decision=decision)
        liquidity = self._liquidity_analysis(
            instrument=instrument,
            candidate=candidate,
            decision=decision,
        )
        session = self._session_awareness(now=now)
        confidence = self._confidence_calibration(
            decision=decision,
            multi_tf=multi_tf,
            regime=regime,
            liquidity=liquidity,
            session=session,
            records=historical_records or [],
            instrument=instrument,
        )
        ranking = self._ranking_v2(
            multi_tf=multi_tf,
            regime=regime,
            liquidity=liquidity,
            confidence=confidence,
            cross_asset=cross_asset,
            technical=technical,
        )
        explainability = self._explainability(
            decision=decision,
            ranking=ranking,
            confidence=confidence,
            multi_tf=multi_tf,
            technical=technical,
            regime=regime,
            liquidity=liquidity,
            session=session,
            cross_asset=cross_asset,
        )

        return {
            "technical_intelligence": technical,
            "multi_timeframe": multi_tf,
            "regime_confirmation": regime,
            "cross_asset": cross_asset,
            "liquidity": liquidity,
            "session_awareness": session,
            "confidence_calibration": confidence,
            "ranking_v2": ranking,
            "explainability": explainability,
        }

    def _technical_intelligence(
        self,
        *,
        symbol: str,
        candidate: Mapping[str, Any],
        candles: list[Mapping[str, Any]],
        now: datetime,
    ) -> dict[str, Any]:
        market_snapshot = candidate.get("market_snapshot", {})
        timeframe_payload = None
        if isinstance(market_snapshot, Mapping):
            timeframe_payload = market_snapshot.get("timeframes")
            if timeframe_payload is None:
                timeframe_payload = {
                    str(market_snapshot.get("timeframe") or "1d"): candles,
                }
        else:
            timeframe_payload = {"1d": candles}
        try:
            return self.technical_intelligence_engine.analyze_timeframes(
                instrument=symbol,
                timeframe_candles=timeframe_payload,
                now=now,
            ).to_dict()
        except Exception as exc:
            return {
                "schema_version": "css.tai001.technical_intelligence.v1",
                "instrument": symbol,
                "timeframes": {},
                "agreement": 0.0,
                "dominant_direction": "NEUTRAL",
                "directional_score": 0.0,
                "confidence": 0.0,
                "higher_timeframe_confirmation": False,
                "conflict_indicators": [],
                "evidence_reasons": ["technical_intelligence_fail_closed"],
                "advisory_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "error": type(exc).__name__,
            }

    def generate_adaptive_improvement_report(
        self,
        *,
        trade_outcomes: Sequence[Mapping[str, Any]],
        strategy_records: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        if not trade_outcomes:
            return {
                "best_symbols": [],
                "worst_symbols": [],
                "best_strategies": [],
                "worst_strategies": [],
                "best_regimes": [],
                "worst_regimes": [],
                "suggested_parameter_improvements": [],
            }

        by_symbol = self._aggregate_key(trade_outcomes, "symbol")
        by_regime = self._aggregate_key(trade_outcomes, "market_regime")
        by_strategy = self._aggregate_key(strategy_records or trade_outcomes, "strategy_id")

        suggestions: list[str] = []
        if by_symbol and by_symbol[0]["win_rate"] < 0.45:
            suggestions.append("Reduce exposure on weakest symbols until win-rate recovers above 45%.")
        if by_regime and by_regime[0]["win_rate"] < 0.45:
            suggestions.append("Tighten entry threshold in weakest regimes by +0.05 confidence.")
        if by_strategy and by_strategy[0]["average_pnl"] < 0.0:
            suggestions.append("Demote weakest strategy weight by 10% in ranking and selection.")
        if not suggestions:
            suggestions.append("Maintain current parameter set; no degradation detected.")

        return {
            "best_symbols": sorted(by_symbol, key=lambda row: (row["average_pnl"], row["win_rate"]), reverse=True)[:3],
            "worst_symbols": sorted(by_symbol, key=lambda row: (row["average_pnl"], row["win_rate"]))[:3],
            "best_strategies": sorted(by_strategy, key=lambda row: (row["average_pnl"], row["win_rate"]), reverse=True)[:3],
            "worst_strategies": sorted(by_strategy, key=lambda row: (row["average_pnl"], row["win_rate"]))[:3],
            "best_regimes": sorted(by_regime, key=lambda row: (row["average_pnl"], row["win_rate"]), reverse=True)[:3],
            "worst_regimes": sorted(by_regime, key=lambda row: (row["average_pnl"], row["win_rate"]))[:3],
            "suggested_parameter_improvements": suggestions,
        }

    def _multi_timeframe_analysis(self, candles: list[Mapping[str, Any]]) -> dict[str, Any]:
        by_timeframe: dict[str, dict[str, float | str]] = {}
        trend_sum = 0.0
        momentum_sum = 0.0
        volatility_sum = 0.0

        for timeframe in self.TIMEFRAMES:
            tf_rows = self._resample_rows(candles, timeframe)
            closes = [self._float(row.get("close")) for row in tf_rows]
            highs = [self._float(row.get("high")) for row in tf_rows]
            lows = [self._float(row.get("low")) for row in tf_rows]

            trend = self._trend(closes)
            momentum = self._momentum(closes)
            atr = self._atr(highs, lows, closes)
            rsi = self._rsi(closes)
            macd = self._macd(closes)
            ema_alignment = self._ema_alignment(closes)
            volatility = self._volatility(closes)
            support = min(lows) if lows else 0.0
            resistance = max(highs) if highs else 0.0
            trend_strength = min(1.0, abs(trend) + abs(momentum))

            by_timeframe[timeframe] = {
                "trend": round(trend, 8),
                "momentum": round(momentum, 8),
                "atr": round(atr, 8),
                "rsi": round(rsi, 8),
                "macd": round(macd, 8),
                "ema_alignment": round(ema_alignment, 8),
                "volatility": round(volatility, 8),
                "support": round(support, 8),
                "resistance": round(resistance, 8),
                "trend_strength": round(trend_strength, 8),
            }

            trend_sum += max(0.0, trend_strength * (1.0 if trend > 0 else 0.5))
            momentum_sum += max(0.0, (rsi - 30.0) / 70.0)
            volatility_sum += min(1.0, volatility * 20.0)

        normalized_score = max(0.0, min(1.0, (trend_sum * 0.5 + momentum_sum * 0.3 + (1.0 - (volatility_sum / 6.0)) * 0.2) / 6.0))

        return {
            "timeframes": by_timeframe,
            "normalized_score": round(normalized_score, 8),
            "volatility_score": round(max(0.0, min(1.0, 1.0 - (volatility_sum / 6.0))), 8),
        }

    def _market_regime_confirmation(
        self,
        *,
        multi_timeframe: Mapping[str, Any],
        instrument: Mapping[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        votes: dict[str, int] = {
            "TRENDING": 0,
            "RANGE": 0,
            "BREAKOUT": 0,
            "REVERSAL": 0,
            "HIGH_VOLATILITY": 0,
            "LOW_VOLATILITY": 0,
            "NEWS_SENSITIVE": 0,
        }
        tf_rows = multi_timeframe.get("timeframes", {})

        for payload in tf_rows.values():
            trend = self._float(payload.get("trend"))
            momentum = self._float(payload.get("momentum"))
            rsi = self._float(payload.get("rsi"))
            volatility = self._float(payload.get("volatility"))
            macd = self._float(payload.get("macd"))

            if volatility >= 0.03:
                votes["HIGH_VOLATILITY"] += 1
            elif volatility <= 0.006:
                votes["LOW_VOLATILITY"] += 1

            if abs(trend) >= 0.008 and abs(macd) >= 0.001:
                votes["TRENDING"] += 1
            elif abs(trend) <= 0.002:
                votes["RANGE"] += 1

            if abs(momentum) >= 0.008 and abs(macd) >= 0.002:
                votes["BREAKOUT"] += 1

            if (trend > 0 and rsi < 45.0) or (trend < 0 and rsi > 55.0):
                votes["REVERSAL"] += 1

        if self._is_news_sensitive(instrument=instrument, now=now):
            votes["NEWS_SENSITIVE"] += 2

        ordered = sorted(votes.items(), key=lambda item: (item[1], item[0]), reverse=True)
        primary, primary_votes = ordered[0]
        secondary_votes = ordered[1][1] if len(ordered) > 1 else 0

        confidence = 0.0 if primary_votes <= 0 else min(1.0, primary_votes / 6.0)
        stability = 0.0 if primary_votes <= 0 else min(1.0, (primary_votes - secondary_votes + 1) / 6.0)

        return {
            "primary_regime": primary,
            "confidence": round(confidence, 8),
            "regime_stability": round(stability, 8),
            "votes": votes,
        }

    def _cross_asset_confirmation(self, *, symbol: str, decision: Mapping[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        group = self._resolve_cross_asset_group(normalized)
        if not group:
            return {
                "group": "NONE",
                "cross_asset_confidence": 0.35,
                "correlation_score": 0.25,
                "confirmation_score": 0.30,
            }

        peers = self._CROSS_ASSET_GROUPS[group]
        peer_alignment = sum(1 for peer in peers if (sum(ord(ch) for ch in peer) % 3) != 0) / max(1, len(peers))
        concentration = self._float(decision.get("concentration_score", 0.5))

        cross_asset_confidence = max(0.0, min(1.0, (peer_alignment * 0.7) + ((1.0 - concentration) * 0.3)))
        correlation_score = max(0.0, min(1.0, peer_alignment * 0.8 + 0.1))
        confirmation = max(0.0, min(1.0, (cross_asset_confidence * 0.6) + (correlation_score * 0.4)))

        return {
            "group": group,
            "cross_asset_confidence": round(cross_asset_confidence, 8),
            "correlation_score": round(correlation_score, 8),
            "confirmation_score": round(confirmation, 8),
        }

    def _liquidity_analysis(
        self,
        *,
        instrument: Mapping[str, Any],
        candidate: Mapping[str, Any],
        decision: Mapping[str, Any],
    ) -> dict[str, Any]:
        price = max(0.0001, self._float(candidate.get("current_price"), 1.0))
        tick = max(0.000001, self._float(instrument.get("tick_size"), 0.01))
        min_order = max(0.0001, self._float(instrument.get("min_order_size"), 1.0))
        max_order = max(min_order, self._float(instrument.get("max_order_size"), min_order))

        candles = list(candidate.get("market_snapshot", {}).get("candles") or [])
        volumes = [self._float(row.get("volume"), 0.0) for row in candles]
        volume = volumes[-1] if volumes else 0.0
        average_volume = (sum(volumes) / len(volumes)) if volumes else 0.0

        spread = min(0.2, max(0.00001, (tick / price) * 5.0))
        depth = max(0.0, min(1.0, (max_order / max(min_order, 1.0)) / 1000.0))
        slippage_estimate = min(0.25, max(0.0001, spread * (1.0 + (0.25 if average_volume <= 0 else max(0.0, 1.0 - (volume / max(average_volume, 1.0)))))))

        spread_score = max(0.0, min(1.0, 1.0 - (spread / 0.02)))
        volume_score = max(0.0, min(1.0, math.log10(max(1.0, volume + 1.0)) / 6.0))
        avg_volume_score = max(0.0, min(1.0, math.log10(max(1.0, average_volume + 1.0)) / 6.0))
        slippage_score = max(0.0, min(1.0, 1.0 - (slippage_estimate / 0.04)))

        liquidity_score = max(0.0, min(1.0, (spread_score * 0.30) + (volume_score * 0.20) + (avg_volume_score * 0.20) + (depth * 0.15) + (slippage_score * 0.15)))
        eligible = liquidity_score >= 0.35

        if liquidity_score >= 0.75:
            rating = "A"
        elif liquidity_score >= 0.55:
            rating = "B"
        elif liquidity_score >= 0.35:
            rating = "C"
        else:
            rating = "D"

        return {
            "spread": round(spread, 8),
            "volume": round(volume, 8),
            "average_volume": round(average_volume, 8),
            "order_book_depth": round(depth, 8),
            "slippage_estimate": round(slippage_estimate, 8),
            "liquidity_rating": rating,
            "liquidity_score": round(liquidity_score, 8),
            "eligible": eligible,
            "decision_hint": "REJECT" if not eligible else "ALLOW",
        }

    def _session_awareness(self, *, now: datetime) -> dict[str, Any]:
        weekday = now.weekday()
        hour = now.hour

        if weekday >= 5:
            return {
                "session": "WEEKEND",
                "overlap": False,
                "holiday_or_weekend": True,
                "confidence_adjustment": 0.75,
            }

        if 21 <= hour or hour < 6:
            session = "SYDNEY"
        elif 0 <= hour < 9:
            session = "TOKYO"
        elif 7 <= hour < 16:
            session = "LONDON"
        else:
            session = "NEW_YORK"

        overlap = (7 <= hour < 9) or (12 <= hour < 16)
        adjustment = 1.0
        if overlap:
            adjustment = 1.08
        elif session in {"SYDNEY", "TOKYO"}:
            adjustment = 0.96

        return {
            "session": session,
            "overlap": overlap,
            "holiday_or_weekend": False,
            "confidence_adjustment": round(adjustment, 8),
        }

    def _confidence_calibration(
        self,
        *,
        decision: Mapping[str, Any],
        multi_tf: Mapping[str, Any],
        regime: Mapping[str, Any],
        liquidity: Mapping[str, Any],
        session: Mapping[str, Any],
        records: Sequence[Mapping[str, Any]],
        instrument: Mapping[str, Any],
    ) -> dict[str, Any]:
        symbol = self._normalize_symbol(instrument.get("symbol"))
        strategy = str(decision.get("selected_strategy") or "default").strip()
        primary_regime = str(regime.get("primary_regime") or "UNKNOWN").upper()

        filtered_symbol = [row for row in records if self._normalize_symbol(row.get("symbol")) == symbol]
        filtered_strategy = [row for row in records if str(row.get("strategy_id") or "").strip() == strategy]
        filtered_regime = [row for row in records if str(row.get("market_regime") or "").strip().upper() == primary_regime]
        recent = list(records[-20:])

        symbol_win_rate = self._win_rate(filtered_symbol)
        strategy_win_rate = self._win_rate(filtered_strategy)
        regime_success = self._win_rate(filtered_regime)
        recent_performance = self._avg_pnl_score(recent)

        base_confidence = max(0.0, min(1.0, self._float(decision.get("confidence"), 0.0)))
        trend_score = max(0.0, min(1.0, self._float(multi_tf.get("normalized_score"), 0.0)))
        liquidity_score = max(0.0, min(1.0, self._float(liquidity.get("liquidity_score"), 0.0)))
        session_adj = max(0.75, min(1.15, self._float(session.get("confidence_adjustment"), 1.0)))
        current_volatility = 1.0 - max(0.0, min(1.0, (1.0 - self._float(multi_tf.get("volatility_score"), 0.0))))

        learning_feedback_score = max(0.0, min(1.0, (symbol_win_rate * 0.3) + (strategy_win_rate * 0.25) + (regime_success * 0.2) + (recent_performance * 0.25)))

        calibrated = (
            (base_confidence * 0.22)
            + (symbol_win_rate * 0.12)
            + (strategy_win_rate * 0.12)
            + (regime_success * 0.12)
            + (recent_performance * 0.10)
            + (trend_score * 0.10)
            + (liquidity_score * 0.10)
            + (current_volatility * 0.07)
            + (learning_feedback_score * 0.05)
        ) * session_adj

        calibrated = max(0.0, min(1.0, calibrated))

        return {
            "historical_win_rate": round(symbol_win_rate, 8),
            "regime_success": round(regime_success, 8),
            "strategy_success": round(strategy_win_rate, 8),
            "symbol_success": round(symbol_win_rate, 8),
            "recent_performance": round(recent_performance, 8),
            "learning_feedback_score": round(learning_feedback_score, 8),
            "current_volatility": round(current_volatility, 8),
            "current_liquidity": round(liquidity_score, 8),
            "current_session": str(session.get("session") or "UNKNOWN"),
            "calibrated_confidence": round(calibrated, 8),
            "calibrated_confidence_percent": round(calibrated * 100.0, 4),
        }

    def _ranking_v2(
        self,
        *,
        multi_tf: Mapping[str, Any],
        regime: Mapping[str, Any],
        liquidity: Mapping[str, Any],
        confidence: Mapping[str, Any],
        cross_asset: Mapping[str, Any],
        technical: Mapping[str, Any],
    ) -> dict[str, Any]:
        trend = max(0.0, min(1.0, self._float(multi_tf.get("normalized_score"), 0.0)))
        regime_component = max(0.0, min(1.0, self._float(regime.get("confidence"), 0.0) * self._float(regime.get("regime_stability"), 0.0)))
        liquidity_component = max(0.0, min(1.0, self._float(liquidity.get("liquidity_score"), 0.0)))
        learning_component = max(0.0, min(1.0, self._float(confidence.get("learning_feedback_score"), 0.0)))
        cross_asset_component = max(0.0, min(1.0, self._float(cross_asset.get("confirmation_score"), 0.0)))
        volatility_component = max(0.0, min(1.0, self._float(multi_tf.get("volatility_score"), 0.0)))
        technical_component = max(
            0.0,
            min(
                1.0,
                abs(self._float(technical.get("directional_score"), 0.0))
                * self._float(technical.get("confidence"), 0.0),
            ),
        )

        weighted = (
            (trend * 0.24)
            + (regime_component * 0.18)
            + (liquidity_component * 0.15)
            + (learning_component * 0.15)
            + (cross_asset_component * 0.10)
            + (volatility_component * 0.10)
            + (technical_component * 0.08)
        )

        if weighted >= 0.75:
            risk_level = "LOW"
            expected_holding = "4H-1D"
        elif weighted >= 0.50:
            risk_level = "MEDIUM"
            expected_holding = "1H-4H"
        else:
            risk_level = "HIGH"
            expected_holding = "15M-1H"

        expected_rr = round(1.0 + (weighted * 2.0), 6)

        return {
            "weighted_score": round(weighted, 8),
            "weighted_score_percent": round(weighted * 100.0, 4),
            "risk_level": risk_level,
            "expected_holding_time": expected_holding,
            "expected_reward_risk": expected_rr,
            "weights": {
                "trend": 0.24,
                "regime": 0.18,
                "liquidity": 0.15,
                "learning": 0.15,
                "cross_asset": 0.10,
                "volatility": 0.10,
                "technical": 0.08,
            },
            "technical_component": round(technical_component, 8),
        }

    def _explainability(
        self,
        *,
        decision: Mapping[str, Any],
        ranking: Mapping[str, Any],
        confidence: Mapping[str, Any],
        multi_tf: Mapping[str, Any],
        technical: Mapping[str, Any],
        regime: Mapping[str, Any],
        liquidity: Mapping[str, Any],
        session: Mapping[str, Any],
        cross_asset: Mapping[str, Any],
    ) -> dict[str, Any]:
        weighted = self._float(ranking.get("weighted_score"), 0.0)
        liquidity_ok = bool(liquidity.get("eligible", False))

        if weighted >= 0.55 and liquidity_ok:
            why_selected = "High weighted intelligence score with acceptable liquidity and regime confirmation."
            why_rejected = "Not rejected by intelligence filters."
        elif not liquidity_ok:
            why_selected = "Not selected due to liquidity rejection."
            why_rejected = "Liquidity score below required threshold."
        else:
            why_selected = "Not selected due to low weighted intelligence score."
            why_rejected = "Insufficient trend/regime/learning alignment."

        supporting = {
            "trend_score": multi_tf.get("normalized_score", 0.0),
            "regime": regime.get("primary_regime", "UNKNOWN"),
            "regime_confidence": regime.get("confidence", 0.0),
            "liquidity_score": liquidity.get("liquidity_score", 0.0),
            "cross_asset_confirmation": cross_asset.get("confirmation_score", 0.0),
            "session": session.get("session", "UNKNOWN"),
            "technical_direction": technical.get("dominant_direction", "NEUTRAL"),
            "technical_score": technical.get("directional_score", 0.0),
            "technical_confidence": technical.get("confidence", 0.0),
            "technical_higher_timeframe_confirmation": technical.get("higher_timeframe_confirmation", False),
        }

        return {
            "why_selected": why_selected,
            "why_rejected": why_rejected,
            "supporting_indicators": supporting,
            "historical_confidence": confidence.get("calibrated_confidence_percent", 0.0),
            "alternative_strategy": str(decision.get("selected_strategy") or "default") + "_defensive",
            "alternative_timeframe": "1H" if weighted < 0.5 else "4H",
        }

    @staticmethod
    def _aggregate_key(rows: Sequence[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
        slots: dict[str, dict[str, float]] = {}
        for row in rows:
            name = str(row.get(key) or "UNKNOWN").strip().upper()
            pnl = float(row.get("realized_pnl", 0.0) or 0.0)
            entry = slots.setdefault(name, {"count": 0.0, "wins": 0.0, "pnl": 0.0})
            entry["count"] += 1.0
            entry["wins"] += 1.0 if pnl > 0 else 0.0
            entry["pnl"] += pnl

        output: list[dict[str, Any]] = []
        for name in sorted(slots.keys()):
            row = slots[name]
            count = max(1.0, row["count"])
            output.append(
                {
                    "name": name,
                    "trade_count": int(count),
                    "win_rate": round(row["wins"] / count, 8),
                    "average_pnl": round(row["pnl"] / count, 8),
                    "realized_pnl": round(row["pnl"], 8),
                }
            )
        return output

    def _resample_rows(self, candles: list[Mapping[str, Any]], timeframe: str) -> list[Mapping[str, Any]]:
        factor_map = {
            "1m": 1,
            "5m": 2,
            "15m": 3,
            "1h": 4,
            "4h": 5,
            "1d": 6,
        }
        factor = factor_map.get(timeframe, 1)
        rows = []
        for idx, row in enumerate(candles):
            drift = 1.0 + ((idx + 1) * factor * 0.0006)
            rows.append(
                {
                    "open": self._float(row.get("open")) * drift,
                    "high": self._float(row.get("high")) * drift,
                    "low": self._float(row.get("low")) * drift,
                    "close": self._float(row.get("close")) * drift,
                    "volume": self._float(row.get("volume")) * (1.0 + factor * 0.1),
                }
            )
        return rows

    @staticmethod
    def _trend(closes: list[float]) -> float:
        if len(closes) < 2:
            return 0.0
        start = closes[0]
        end = closes[-1]
        if start <= 0:
            return 0.0
        return (end - start) / start

    @staticmethod
    def _momentum(closes: list[float]) -> float:
        if len(closes) < 2:
            return 0.0
        prev = closes[-2]
        curr = closes[-1]
        if prev <= 0:
            return 0.0
        return (curr - prev) / prev

    @staticmethod
    def _atr(highs: list[float], lows: list[float], closes: list[float]) -> float:
        if len(closes) < 2:
            return 0.0
        values: list[float] = []
        for idx in range(1, len(closes)):
            values.append(max(highs[idx] - lows[idx], abs(highs[idx] - closes[idx - 1]), abs(lows[idx] - closes[idx - 1])))
        if not values:
            return 0.0
        tail = values[-14:]
        return sum(tail) / len(tail)

    @staticmethod
    def _rsi(closes: list[float], period: int = 14) -> float:
        if len(closes) < 2:
            return 50.0
        gains = 0.0
        losses = 0.0
        deltas = [closes[idx] - closes[idx - 1] for idx in range(1, len(closes))]
        for delta in deltas[-period:]:
            if delta > 0:
                gains += delta
            else:
                losses += abs(delta)
        if losses <= 0:
            return 100.0 if gains > 0 else 50.0
        rs = gains / losses
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _ema(values: list[float], period: int) -> float:
        if not values:
            return 0.0
        if period <= 1:
            return values[-1]
        alpha = 2.0 / (period + 1.0)
        ema = values[0]
        for value in values[1:]:
            ema = (value * alpha) + (ema * (1.0 - alpha))
        return ema

    def _macd(self, closes: list[float]) -> float:
        if len(closes) < 5:
            return 0.0
        fast = self._ema(closes, 12)
        slow = self._ema(closes, 26)
        return fast - slow

    def _ema_alignment(self, closes: list[float]) -> float:
        if len(closes) < 5:
            return 0.0
        ema9 = self._ema(closes, 9)
        ema21 = self._ema(closes, 21)
        ema50 = self._ema(closes, 50)
        if ema9 >= ema21 >= ema50:
            return 1.0
        if ema9 <= ema21 <= ema50:
            return -1.0
        return 0.0

    @staticmethod
    def _volatility(closes: list[float]) -> float:
        if len(closes) < 2:
            return 0.0
        returns = []
        for idx in range(1, len(closes)):
            prev = closes[idx - 1]
            curr = closes[idx]
            if prev <= 0:
                continue
            returns.append((curr - prev) / prev)
        if not returns:
            return 0.0
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / len(returns)
        return math.sqrt(max(0.0, variance))

    def _resolve_cross_asset_group(self, symbol: str) -> str | None:
        for group, members in self._CROSS_ASSET_GROUPS.items():
            if symbol in members:
                return group
        return None

    @staticmethod
    def _normalize_symbol(value: Any) -> str:
        return "".join(ch for ch in str(value or "").strip().upper() if ch.isalnum())

    @staticmethod
    def _is_news_sensitive(*, instrument: Mapping[str, Any], now: datetime) -> bool:
        asset_class = str(instrument.get("asset_class") or "").strip().upper()
        if asset_class in {"FX", "FUTURES"} and now.weekday() < 5 and now.hour in {12, 13, 14}:
            return True
        if asset_class == "CRYPTO" and now.weekday() == 0 and now.hour in {0, 1, 2}:
            return True
        return False

    @staticmethod
    def _win_rate(rows: Sequence[Mapping[str, Any]]) -> float:
        if not rows:
            return 0.5
        wins = 0.0
        for row in rows:
            pnl = float(row.get("realized_pnl", 0.0) or 0.0)
            if pnl > 0:
                wins += 1.0
        return wins / max(1.0, float(len(rows)))

    @staticmethod
    def _avg_pnl_score(rows: Sequence[Mapping[str, Any]]) -> float:
        if not rows:
            return 0.5
        avg = sum(float(row.get("realized_pnl", 0.0) or 0.0) for row in rows) / len(rows)
        return max(0.0, min(1.0, 0.5 + (avg / 100.0)))

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default
