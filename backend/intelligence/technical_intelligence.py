from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


TECHNICAL_INTELLIGENCE_VERSION = "css.tai001.technical_intelligence.v1"


class TechnicalIntelligenceError(ValueError):
    """Raised only for caller contract errors; bad market data returns fail-closed output."""


@dataclass(frozen=True)
class TechnicalIntelligenceConfig:
    sma_fast_window: int = 10
    sma_slow_window: int = 30
    ema_fast_window: int = 12
    ema_slow_window: int = 26
    macd_signal_window: int = 9
    rsi_window: int = 14
    atr_window: int = 14
    bollinger_window: int = 20
    bollinger_stddev: float = 2.0
    structure_window: int = 20
    volume_window: int = 20
    volatility_window: int = 20
    stale_after_seconds: int = 3600
    volume_anomaly_ratio: float = 2.0
    breakout_volume_confirmation_ratio: float = 1.2
    weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "trend": 0.24,
            "momentum": 0.22,
            "volatility": 0.16,
            "volume": 0.12,
            "structure": 0.16,
            "patterns": 0.10,
        }
    )


@dataclass(frozen=True)
class TechnicalIndicatorObservation:
    name: str
    value: Any
    state: str
    direction_score: float
    confidence: float
    reason: str


@dataclass(frozen=True)
class TechnicalComponentContribution:
    component: str
    score: float
    confidence: float
    weight: float
    weighted_score: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class TechnicalIntelligenceSnapshot:
    schema_version: str
    instrument: str
    timeframe: str
    timestamp: str
    freshness: str
    sample_count: int
    data_quality: str
    insufficient_data: bool
    data_warnings: tuple[str, ...]
    trend_direction: str
    trend_strength: float
    rsi: float | None
    macd: Mapping[str, float | None]
    bollinger: Mapping[str, float | str | None]
    atr: float | None
    normalized_volatility: float | None
    volatility_state: str
    volume_score: float
    volume_anomaly: bool
    support: float | None
    resistance: float | None
    breakout_state: str
    distance_from_support: float | None
    distance_from_resistance: float | None
    patterns: tuple[str, ...]
    directional_score: float
    confidence: float
    regime: str
    observations: tuple[TechnicalIndicatorObservation, ...]
    component_contributions: tuple[TechnicalComponentContribution, ...]
    evidence_reasons: tuple[str, ...]
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MultiTimeframeTechnicalIntelligence:
    schema_version: str
    instrument: str
    timestamp: str
    timeframes: Mapping[str, TechnicalIntelligenceSnapshot]
    agreement: float
    dominant_direction: str
    directional_score: float
    confidence: float
    higher_timeframe_confirmation: bool
    conflict_indicators: tuple[str, ...]
    evidence_reasons: tuple[str, ...]
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timeframes"] = {
            timeframe: snapshot.to_dict()
            for timeframe, snapshot in self.timeframes.items()
        }
        return payload


@dataclass(frozen=True)
class _Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    order: int


class TechnicalIntelligenceEngine:
    """Deterministic OHLCV technical evidence engine.

    This module is advisory-only. It does not import broker, order, execution,
    credential, or governance mutation modules.
    """

    TIMEFRAME_PRIORITY: tuple[str, ...] = ("1d", "4h", "1h", "15m", "5m", "1m")

    def __init__(self, config: TechnicalIntelligenceConfig | None = None) -> None:
        self.config = config or TechnicalIntelligenceConfig()
        self._weights = self._normalized_weights(self.config.weights)

    def analyze(
        self,
        *,
        instrument: str,
        candles: Sequence[Any],
        timeframe: str = "1d",
        now: datetime | None = None,
    ) -> TechnicalIntelligenceSnapshot:
        symbol = str(instrument or "").strip().upper()
        if not symbol:
            raise TechnicalIntelligenceError("instrument must be non-empty")
        tf = str(timeframe or "1d").strip().lower() or "1d"

        normalized, warnings = self._normalize_candles(candles)
        if warnings and any(
            warning.startswith(prefix)
            for warning in warnings
            for prefix in (
                "malformed_ohlc",
                "negative_volume",
                "non_finite",
                "duplicate_timestamps",
            )
        ):
            return self._insufficient_snapshot(
                instrument=symbol,
                timeframe=tf,
                sample_count=len(normalized),
                timestamp=normalized[-1].timestamp if normalized else "",
                warnings=warnings,
                reason="invalid_ohlcv_data",
            )
        if not normalized:
            return self._insufficient_snapshot(
                instrument=symbol,
                timeframe=tf,
                sample_count=0,
                timestamp="",
                warnings=warnings or ("missing_candles",),
                reason="missing_candles",
            )

        future_warnings = self._future_timestamp_warnings(normalized, now=now)
        if future_warnings:
            warnings = (*warnings, *future_warnings)
            return self._insufficient_snapshot(
                instrument=symbol,
                timeframe=tf,
                sample_count=len(normalized),
                timestamp=normalized[-1].timestamp,
                warnings=warnings,
                reason="future_timestamped_market_data",
                freshness="FUTURE_TIMESTAMP",
            )

        freshness = self._freshness(normalized[-1].timestamp, now=now)
        if freshness == "STALE":
            warnings = (*warnings, "stale_data")

        closes = [c.close for c in normalized]
        highs = [c.high for c in normalized]
        lows = [c.low for c in normalized]
        opens = [c.open for c in normalized]
        volumes = [c.volume for c in normalized]

        sma_fast = self.sma(closes, self.config.sma_fast_window)
        sma_slow = self.sma(closes, self.config.sma_slow_window)
        ema_fast = self.ema(closes, self.config.ema_fast_window)
        ema_slow = self.ema(closes, self.config.ema_slow_window)
        rsi = self.rsi(closes, self.config.rsi_window)
        macd = self.macd(closes)
        atr = self.atr(highs, lows, closes, self.config.atr_window)
        bollinger = self.bollinger(closes)
        normalized_vol = self.normalized_volatility(closes)
        volume_payload = self._volume_features(closes, volumes)
        structure = self._structure_features(normalized)
        patterns = self._candlestick_patterns(normalized)

        trend_score, trend_direction, trend_strength, trend_reasons = self._trend_component(
            closes=closes,
            sma_fast=sma_fast,
            sma_slow=sma_slow,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
        )
        momentum_score, momentum_reasons = self._momentum_component(
            closes=closes,
            rsi_value=rsi,
            macd_payload=macd,
        )
        volatility_score, volatility_state, volatility_reasons = self._volatility_component(
            close=closes[-1],
            bollinger_payload=bollinger,
            normalized_vol=normalized_vol,
        )
        volume_score = float(volume_payload["score"])
        volume_reasons = tuple(volume_payload["reasons"])
        structure_score = float(structure["score"])
        structure_reasons = tuple(structure["reasons"])
        pattern_score = 0.0
        pattern_reasons = tuple(f"pattern:{name}" for name in patterns) or ("no_candlestick_pattern",)

        components = self._component_contributions(
            {
                "trend": (trend_score, self._indicator_confidence(sma_slow is not None), trend_reasons),
                "momentum": (momentum_score, self._indicator_confidence(rsi is not None and macd["line"] is not None), momentum_reasons),
                "volatility": (volatility_score, self._indicator_confidence(bollinger["middle"] is not None and normalized_vol is not None), volatility_reasons),
                "volume": (volume_score, self._indicator_confidence(len(volumes) >= self.config.volume_window), volume_reasons),
                "structure": (structure_score, self._indicator_confidence(structure["support"] is not None and structure["resistance"] is not None), structure_reasons),
                "patterns": (pattern_score, 0.15 if patterns else 0.0, pattern_reasons),
            }
        )
        directional_score = self._clamp_signed(sum(item.weighted_score for item in components))
        coverage = sum(item.weight for item in components if item.confidence > 0.0)
        agreement = self._agreement([item.score for item in components if item.confidence > 0.0])
        confidence = self._confidence(
            sample_count=len(normalized),
            warnings=warnings,
            coverage=coverage,
            agreement=agreement,
            freshness=freshness,
        )
        insufficient = len(normalized) < self._minimum_required_samples() or coverage < 0.55 or confidence < 0.35
        if insufficient:
            confidence = min(confidence, 0.34)
            warnings = (*warnings, "insufficient_history")

        if insufficient:
            trend_direction = "INDETERMINATE"
            trend_strength = 0.0
            rsi = None
            macd = self._neutral_macd_payload()
            atr = None
            bollinger = self._neutral_bollinger_payload()
            normalized_vol = None
            volatility_state = "INSUFFICIENT"
            patterns = ()
            volume_score = 0.0
            structure = self._neutral_structure_payload(reason="insufficient_history")
            volume_payload = {**volume_payload, "score": 0.0, "anomaly": False, "reasons": ("insufficient_history",)}

        regime = "INSUFFICIENT_DATA" if insufficient else self._regime(
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            volatility_state=volatility_state,
            breakout_state=str(structure["breakout_state"]),
        )
        observations = self._observations(
            sma_fast=sma_fast,
            sma_slow=sma_slow,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi_value=rsi,
            macd_payload=macd,
            atr_value=atr,
            bollinger_payload=bollinger,
            volume_score=volume_score,
            structure=structure,
            patterns=patterns,
        )
        reasons = tuple(
            reason
            for component in components
            for reason in component.reasons
        )
        if insufficient:
            observations = self._neutralized_observations(observations, reason="insufficient_history")
            reasons = ("insufficient_history",)

        return TechnicalIntelligenceSnapshot(
            schema_version=TECHNICAL_INTELLIGENCE_VERSION,
            instrument=symbol,
            timeframe=tf,
            timestamp=normalized[-1].timestamp,
            freshness=freshness,
            sample_count=len(normalized),
            data_quality="DEGRADED" if warnings else "OK",
            insufficient_data=insufficient,
            data_warnings=tuple(dict.fromkeys(warnings)),
            trend_direction=trend_direction,
            trend_strength=self._round(trend_strength),
            rsi=self._optional_round(rsi),
            macd={key: self._optional_round(value) for key, value in macd.items()},
            bollinger={
                key: self._optional_round(value) if isinstance(value, float) else value
                for key, value in bollinger.items()
            },
            atr=self._optional_round(atr),
            normalized_volatility=self._optional_round(normalized_vol),
            volatility_state=volatility_state,
            volume_score=self._round(volume_score),
            volume_anomaly=bool(volume_payload["anomaly"]),
            support=self._optional_round(structure["support"]),
            resistance=self._optional_round(structure["resistance"]),
            breakout_state=str(structure["breakout_state"]),
            distance_from_support=self._optional_round(structure["distance_from_support"]),
            distance_from_resistance=self._optional_round(structure["distance_from_resistance"]),
            patterns=tuple(patterns),
            directional_score=self._round(0.0 if insufficient else directional_score),
            confidence=self._round(confidence),
            regime=regime,
            observations=tuple(observations),
            component_contributions=tuple(
                self._neutralized_contributions(components, reason="insufficient_history")
                if insufficient
                else components
            ),
            evidence_reasons=tuple(dict.fromkeys(reasons)),
        )

    def analyze_timeframes(
        self,
        *,
        instrument: str,
        timeframe_candles: Mapping[str, Sequence[Any]] | Sequence[Any],
        now: datetime | None = None,
        default_timeframe: str = "1d",
    ) -> MultiTimeframeTechnicalIntelligence:
        if isinstance(timeframe_candles, Mapping):
            if "timeframes" in timeframe_candles and isinstance(timeframe_candles["timeframes"], Mapping):
                raw_items = timeframe_candles["timeframes"].items()
            elif "candles" in timeframe_candles and isinstance(timeframe_candles["candles"], Sequence):
                raw_items = [(str(timeframe_candles.get("timeframe") or default_timeframe), timeframe_candles["candles"])]
            else:
                raw_items = timeframe_candles.items()
        else:
            raw_items = [(default_timeframe, timeframe_candles)]

        snapshots: dict[str, TechnicalIntelligenceSnapshot] = {}
        for timeframe, rows in raw_items:
            if isinstance(rows, Mapping) and isinstance(rows.get("candles"), Sequence):
                rows = rows["candles"]
            if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
                continue
            tf = str(timeframe or default_timeframe).strip().lower()
            snapshots[tf] = self.analyze(
                instrument=instrument,
                candles=rows,
                timeframe=tf,
                now=now,
            )

        if not snapshots:
            snapshots[default_timeframe] = self._insufficient_snapshot(
                instrument=str(instrument or "").strip().upper() or "UNKNOWN",
                timeframe=default_timeframe,
                sample_count=0,
                timestamp="",
                warnings=("missing_timeframe_candles",),
                reason="missing_timeframe_candles",
            )

        usable = [item for item in snapshots.values() if not item.insufficient_data and item.confidence > 0.0]
        if usable:
            total_conf = sum(item.confidence for item in usable)
            directional_score = sum(item.directional_score * item.confidence for item in usable) / max(total_conf, 1e-12)
            signs = [self._sign(item.directional_score) for item in usable if self._sign(item.directional_score) != 0]
            dominant_sign = 0 if not signs else 1 if signs.count(1) >= signs.count(-1) else -1
            agreement = signs.count(dominant_sign) / len(signs) if signs and dominant_sign else 0.0
            confidence = self._clamp01((total_conf / len(usable)) * (0.55 + 0.45 * agreement))
        else:
            directional_score = 0.0
            dominant_sign = 0
            agreement = 0.0
            confidence = 0.0

        dominant_direction = self._direction_from_score(directional_score if dominant_sign else 0.0)
        higher = self._highest_available_timeframe(snapshots)
        higher_confirmed = (
            bool(higher)
            and dominant_sign != 0
            and self._sign(snapshots[higher].directional_score) == dominant_sign
            and not snapshots[higher].insufficient_data
        )
        conflicts = tuple(
            timeframe
            for timeframe, snapshot in snapshots.items()
            if dominant_sign != 0
            and self._sign(snapshot.directional_score) not in {0, dominant_sign}
            and snapshot.confidence > 0.0
        )
        reasons = tuple(
            reason
            for snapshot in snapshots.values()
            for reason in snapshot.evidence_reasons[:3]
        )
        timestamp = max((snapshot.timestamp for snapshot in snapshots.values()), default="")

        return MultiTimeframeTechnicalIntelligence(
            schema_version=TECHNICAL_INTELLIGENCE_VERSION,
            instrument=str(instrument or "").strip().upper(),
            timestamp=timestamp,
            timeframes=snapshots,
            agreement=self._round(agreement),
            dominant_direction=dominant_direction,
            directional_score=self._round(directional_score),
            confidence=self._round(confidence),
            higher_timeframe_confirmation=higher_confirmed,
            conflict_indicators=conflicts,
            evidence_reasons=tuple(dict.fromkeys(reasons)),
        )

    @staticmethod
    def sma(values: Sequence[float], window: int) -> float | None:
        if window <= 0 or len(values) < window:
            return None
        subset = [float(value) for value in values[-window:]]
        return sum(subset) / window

    @classmethod
    def ema(cls, values: Sequence[float], window: int) -> float | None:
        series = cls._ema_series(values, window)
        return series[-1] if series else None

    @staticmethod
    def rsi(values: Sequence[float], window: int = 14) -> float | None:
        if window <= 0 or len(values) < window + 1:
            return None
        deltas = [float(values[idx]) - float(values[idx - 1]) for idx in range(1, len(values))]
        gains = [max(delta, 0.0) for delta in deltas[-window:]]
        losses = [abs(min(delta, 0.0)) for delta in deltas[-window:]]
        avg_gain = sum(gains) / window
        avg_loss = sum(losses) / window
        if avg_loss <= 0.0:
            return 100.0 if avg_gain > 0.0 else 50.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def macd(self, values: Sequence[float]) -> dict[str, float | None]:
        fast = self._ema_series(values, self.config.ema_fast_window)
        slow = self._ema_series(values, self.config.ema_slow_window)
        if not fast or not slow:
            return {"line": None, "signal": None, "histogram": None}
        offset = len(fast) - len(slow)
        macd_values = [fast[idx + offset] - slow[idx] for idx in range(len(slow))]
        signal = self.ema(macd_values, self.config.macd_signal_window)
        line = macd_values[-1] if macd_values else None
        histogram = None if line is None or signal is None else line - signal
        return {"line": line, "signal": signal, "histogram": histogram}

    @staticmethod
    def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], window: int = 14) -> float | None:
        if window <= 0 or len(closes) < window + 1:
            return None
        true_ranges: list[float] = []
        for idx in range(1, len(closes)):
            high = float(highs[idx])
            low = float(lows[idx])
            prev_close = float(closes[idx - 1])
            true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        if len(true_ranges) < window:
            return None
        return sum(true_ranges[-window:]) / window

    def bollinger(self, values: Sequence[float]) -> dict[str, float | str | None]:
        window = self.config.bollinger_window
        if window <= 0 or len(values) < window:
            return {"lower": None, "middle": None, "upper": None, "width": None, "position": None, "state": "INSUFFICIENT"}
        subset = [float(value) for value in values[-window:]]
        middle = sum(subset) / window
        variance = sum((value - middle) ** 2 for value in subset) / window
        stddev = math.sqrt(max(0.0, variance))
        lower = middle - (self.config.bollinger_stddev * stddev)
        upper = middle + (self.config.bollinger_stddev * stddev)
        close = subset[-1]
        width = 0.0 if middle == 0.0 else (upper - lower) / abs(middle)
        if upper == lower:
            position = 0.5
        else:
            position = (close - lower) / (upper - lower)
        if close > upper:
            state = "ABOVE_UPPER"
        elif close < lower:
            state = "BELOW_LOWER"
        else:
            state = "IN_BAND"
        return {"lower": lower, "middle": middle, "upper": upper, "width": width, "position": position, "state": state}

    def normalized_volatility(self, values: Sequence[float]) -> float | None:
        window = self.config.volatility_window
        if window <= 0 or len(values) < window + 1:
            return None
        returns = []
        for idx in range(1, len(values)):
            prev = float(values[idx - 1])
            curr = float(values[idx])
            if prev <= 0.0:
                return None
            returns.append((curr - prev) / prev)
        subset = returns[-window:]
        mean = sum(subset) / len(subset)
        variance = sum((value - mean) ** 2 for value in subset) / len(subset)
        return math.sqrt(max(0.0, variance))

    @staticmethod
    def _ema_series(values: Sequence[float], window: int) -> list[float]:
        if window <= 0 or len(values) < window:
            return []
        numbers = [float(value) for value in values]
        alpha = 2.0 / (window + 1.0)
        ema_value = sum(numbers[:window]) / window
        series = [ema_value]
        for value in numbers[window:]:
            ema_value = (value * alpha) + (ema_value * (1.0 - alpha))
            series.append(ema_value)
        return series

    def _normalize_candles(self, rows: Sequence[Any]) -> tuple[list[_Candle], tuple[str, ...]]:
        warnings: list[str] = []
        if rows is None or isinstance(rows, (str, bytes)):
            return [], ("missing_candles",)
        candles: list[_Candle] = []
        for idx, row in enumerate(rows):
            parsed = self._parse_candle(row, idx)
            if isinstance(parsed, str):
                warnings.append(parsed)
                continue
            candles.append(parsed)
        if not candles:
            return [], tuple(dict.fromkeys(warnings))

        timestamps = [c.timestamp for c in candles if c.timestamp]
        if len(timestamps) != len(set(timestamps)):
            warnings.append("duplicate_timestamps")
        if timestamps and len(timestamps) == len(candles):
            sorted_candles = sorted(candles, key=lambda item: (item.timestamp, item.order))
            if [c.order for c in sorted_candles] != [c.order for c in candles]:
                warnings.append("out_of_order_timestamps_sorted")
            candles = sorted_candles
        return candles, tuple(dict.fromkeys(warnings))

    def _future_timestamp_warnings(self, candles: Sequence[_Candle], *, now: datetime | None) -> tuple[str, ...]:
        evaluation_time = now or datetime.now(timezone.utc)
        if evaluation_time.tzinfo is None:
            evaluation_time = evaluation_time.replace(tzinfo=timezone.utc)
        evaluation_time = evaluation_time.astimezone(timezone.utc)

        for candle in candles:
            parsed = self._parse_timestamp(candle.timestamp)
            if parsed is not None and parsed > evaluation_time:
                return ("FUTURE_TIMESTAMP",)
        return ()

    def _parse_candle(self, row: Any, order: int) -> _Candle | str:
        if isinstance(row, Mapping):
            timestamp = str(row.get("timestamp", row.get("time", row.get("ts", ""))) or "")
            open_ = self._number(row.get("open", row.get("o")))
            high = self._number(row.get("high", row.get("h")))
            low = self._number(row.get("low", row.get("l")))
            close = self._number(row.get("close", row.get("c", row.get("price"))))
            volume = self._number(row.get("volume", row.get("v", 0.0)))
        elif isinstance(row, (list, tuple)):
            if len(row) >= 6:
                timestamp = str(row[0] or "")
                open_ = self._number(row[3])
                high = self._number(row[2])
                low = self._number(row[1])
                close = self._number(row[4])
                volume = self._number(row[5])
            elif len(row) >= 5:
                timestamp = str(row[0] or "")
                open_ = self._number(row[1])
                high = self._number(row[2])
                low = self._number(row[3])
                close = self._number(row[4])
                volume = 0.0
            else:
                return "malformed_candle"
        else:
            timestamp = str(getattr(row, "timestamp", getattr(row, "time", "")) or "")
            open_ = self._number(getattr(row, "open", None))
            high = self._number(getattr(row, "high", None))
            low = self._number(getattr(row, "low", None))
            close = self._number(getattr(row, "close", None))
            volume = self._number(getattr(row, "volume", 0.0))

        values = (open_, high, low, close, volume)
        if any(value is None for value in values):
            return "non_finite_candle_value"
        assert open_ is not None and high is not None and low is not None and close is not None and volume is not None
        if min(open_, high, low, close) <= 0.0 or high < low or high < max(open_, close) or low > min(open_, close):
            return "malformed_ohlc"
        if volume < 0.0:
            return "negative_volume"
        return _Candle(
            timestamp=timestamp,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            order=order,
        )

    def _trend_component(
        self,
        *,
        closes: Sequence[float],
        sma_fast: float | None,
        sma_slow: float | None,
        ema_fast: float | None,
        ema_slow: float | None,
    ) -> tuple[float, str, float, tuple[str, ...]]:
        if len(closes) < 2:
            return 0.0, "INDETERMINATE", 0.0, ("trend_insufficient",)
        score_parts: list[float] = []
        reasons: list[str] = []
        if sma_fast is not None and sma_slow is not None and sma_slow > 0.0:
            ma_score = self._clamp_signed((sma_fast - sma_slow) / sma_slow * 20.0)
            score_parts.append(ma_score)
            reasons.append("sma_fast_above_slow" if ma_score > 0 else "sma_fast_below_slow" if ma_score < 0 else "sma_neutral")
        if ema_fast is not None and ema_slow is not None and ema_slow > 0.0:
            ema_score = self._clamp_signed((ema_fast - ema_slow) / ema_slow * 20.0)
            score_parts.append(ema_score)
            reasons.append("ema_fast_above_slow" if ema_score > 0 else "ema_fast_below_slow" if ema_score < 0 else "ema_neutral")
        lookback = min(len(closes) - 1, self.config.sma_fast_window)
        if lookback > 0 and closes[-lookback - 1] > 0.0:
            slope_score = self._clamp_signed((closes[-1] - closes[-lookback - 1]) / closes[-lookback - 1] * 10.0)
            score_parts.append(slope_score)
            reasons.append("positive_price_slope" if slope_score > 0 else "negative_price_slope" if slope_score < 0 else "flat_price_slope")
        score = sum(score_parts) / len(score_parts) if score_parts else 0.0
        strength = abs(score)
        return self._clamp_signed(score), self._direction_from_score(score), strength, tuple(reasons or ("trend_neutral",))

    def _momentum_component(
        self,
        *,
        closes: Sequence[float],
        rsi_value: float | None,
        macd_payload: Mapping[str, float | None],
    ) -> tuple[float, tuple[str, ...]]:
        parts: list[float] = []
        reasons: list[str] = []
        if rsi_value is not None:
            rsi_score = self._clamp_signed((rsi_value - 50.0) / 25.0)
            parts.append(rsi_score)
            reasons.append("rsi_bullish" if rsi_score > 0.2 else "rsi_bearish" if rsi_score < -0.2 else "rsi_neutral")
        histogram = macd_payload.get("histogram")
        if histogram is not None:
            scale = max(abs(closes[-1]), 1.0) * 0.01
            macd_score = self._clamp_signed(float(histogram) / scale)
            parts.append(macd_score)
            reasons.append("macd_positive" if macd_score > 0 else "macd_negative" if macd_score < 0 else "macd_neutral")
        if len(closes) > self.config.rsi_window and closes[-self.config.rsi_window] > 0.0:
            roc = (closes[-1] - closes[-self.config.rsi_window]) / closes[-self.config.rsi_window]
            roc_score = self._clamp_signed(roc * 8.0)
            parts.append(roc_score)
            reasons.append("positive_rate_of_change" if roc_score > 0 else "negative_rate_of_change" if roc_score < 0 else "flat_rate_of_change")
        return (sum(parts) / len(parts) if parts else 0.0), tuple(reasons or ("momentum_insufficient",))

    def _volatility_component(
        self,
        *,
        close: float,
        bollinger_payload: Mapping[str, float | str | None],
        normalized_vol: float | None,
    ) -> tuple[float, str, tuple[str, ...]]:
        score = 0.0
        reasons: list[str] = []
        state = "UNKNOWN"
        band_state = str(bollinger_payload.get("state") or "INSUFFICIENT")
        if band_state == "ABOVE_UPPER":
            score = 0.35
            reasons.append("close_above_bollinger_upper")
        elif band_state == "BELOW_LOWER":
            score = -0.35
            reasons.append("close_below_bollinger_lower")
        elif band_state == "IN_BAND":
            position = bollinger_payload.get("position")
            if isinstance(position, float):
                score = self._clamp_signed((position - 0.5) * 0.8)
            reasons.append("close_inside_bollinger_band")
        else:
            reasons.append("bollinger_insufficient")

        if normalized_vol is None:
            state = "INSUFFICIENT"
        elif normalized_vol >= 0.035:
            state = "HIGH"
            reasons.append("high_normalized_volatility")
        elif normalized_vol <= 0.006:
            state = "LOW"
            reasons.append("low_normalized_volatility")
        else:
            state = "NORMAL"
            reasons.append("normal_normalized_volatility")
        if close <= 0.0:
            state = "INVALID"
        return score, state, tuple(reasons)

    def _volume_features(self, closes: Sequence[float], volumes: Sequence[float]) -> dict[str, Any]:
        if not volumes:
            return {"score": 0.0, "anomaly": False, "ratio": None, "reasons": ("volume_missing",)}
        window = min(len(volumes) - 1, self.config.volume_window)
        if window <= 0:
            return {"score": 0.0, "anomaly": False, "ratio": None, "reasons": ("volume_insufficient",)}
        baseline = sum(volumes[-window - 1:-1]) / window
        if baseline <= 0.0:
            return {"score": 0.0, "anomaly": False, "ratio": None, "reasons": ("volume_baseline_zero",)}
        ratio = volumes[-1] / baseline
        direction = 0.0
        if len(closes) >= 2:
            direction = 1.0 if closes[-1] > closes[-2] else -1.0 if closes[-1] < closes[-2] else 0.0
        confirmation = self._clamp01((ratio - 1.0) / max(self.config.volume_anomaly_ratio - 1.0, 1e-12))
        score = direction * confirmation
        anomaly = ratio >= self.config.volume_anomaly_ratio
        return {
            "score": self._clamp_signed(score),
            "anomaly": anomaly,
            "ratio": ratio,
            "reasons": (
                "volume_confirms_up_move" if score > 0 else "volume_confirms_down_move" if score < 0 else "volume_neutral",
                "volume_anomaly" if anomaly else "volume_normal",
            ),
        }

    def _structure_features(self, candles: Sequence[_Candle]) -> dict[str, Any]:
        if len(candles) < 3:
            return {
                "support": None,
                "resistance": None,
                "distance_from_support": None,
                "distance_from_resistance": None,
                "breakout_state": "INSUFFICIENT",
                "score": 0.0,
                "reasons": ("structure_insufficient",),
            }
        latest = candles[-1]
        prior = candles[:-1][-self.config.structure_window :]
        support = min(c.low for c in prior)
        resistance = max(c.high for c in prior)
        close = latest.close
        dist_support = None if close <= 0.0 else (close - support) / close
        dist_resistance = None if close <= 0.0 else (resistance - close) / close
        volume_payload = self._volume_features([c.close for c in candles], [c.volume for c in candles])
        volume_ratio = volume_payload.get("ratio")
        volume_confirmed = isinstance(volume_ratio, float) and volume_ratio >= self.config.breakout_volume_confirmation_ratio
        reasons: list[str] = []
        if close > resistance:
            state = "BREAKOUT_CONFIRMED" if volume_confirmed else "BREAKOUT_UNCONFIRMED"
            score = 1.0 if volume_confirmed else 0.65
            reasons.append("close_above_prior_resistance")
        elif close < support:
            state = "BREAKDOWN_CONFIRMED" if volume_confirmed else "BREAKDOWN_UNCONFIRMED"
            score = -1.0 if volume_confirmed else -0.65
            reasons.append("close_below_prior_support")
        else:
            state = "IN_RANGE"
            midpoint = (support + resistance) / 2.0
            score = 0.0 if resistance == support else self._clamp_signed((close - midpoint) / (resistance - support) * 0.5)
            reasons.append("price_inside_prior_range")
        if len(candles) >= 4:
            recent = candles[-3:]
            if recent[-1].high > recent[-2].high > recent[-3].high and recent[-1].low > recent[-2].low > recent[-3].low:
                reasons.append("higher_high_higher_low_structure")
            if recent[-1].high < recent[-2].high < recent[-3].high and recent[-1].low < recent[-2].low < recent[-3].low:
                reasons.append("lower_high_lower_low_structure")
        return {
            "support": support,
            "resistance": resistance,
            "distance_from_support": dist_support,
            "distance_from_resistance": dist_resistance,
            "breakout_state": state,
            "score": score,
            "reasons": tuple(reasons),
        }

    def _candlestick_patterns(self, candles: Sequence[_Candle]) -> tuple[str, ...]:
        if not candles:
            return ()
        current = candles[-1]
        body = abs(current.close - current.open)
        full_range = max(current.high - current.low, 1e-12)
        upper_shadow = current.high - max(current.open, current.close)
        lower_shadow = min(current.open, current.close) - current.low
        patterns: list[str] = []
        if body <= full_range * 0.10:
            patterns.append("doji")
        if lower_shadow >= max(body * 2.0, full_range * 0.45) and upper_shadow <= max(body, full_range * 0.20):
            patterns.append("hammer")
        if upper_shadow >= max(body * 2.0, full_range * 0.45) and lower_shadow <= max(body, full_range * 0.20):
            patterns.append("shooting_star")
        if len(candles) >= 2:
            prev = candles[-2]
            prev_low_body = min(prev.open, prev.close)
            prev_high_body = max(prev.open, prev.close)
            curr_low_body = min(current.open, current.close)
            curr_high_body = max(current.open, current.close)
            if prev.close < prev.open and current.close > current.open and curr_low_body <= prev_low_body and curr_high_body >= prev_high_body:
                patterns.append("bullish_engulfing")
            if prev.close > prev.open and current.close < current.open and curr_low_body <= prev_low_body and curr_high_body >= prev_high_body:
                patterns.append("bearish_engulfing")
        return tuple(dict.fromkeys(patterns))

    def _component_contributions(self, components: Mapping[str, tuple[float, float, tuple[str, ...]]]) -> tuple[TechnicalComponentContribution, ...]:
        output: list[TechnicalComponentContribution] = []
        for name in ("trend", "momentum", "volatility", "volume", "structure", "patterns"):
            score, confidence, reasons = components[name]
            weight = self._weights[name]
            effective_weight = weight * self._clamp01(confidence)
            output.append(
                TechnicalComponentContribution(
                    component=name,
                    score=self._round(self._clamp_signed(score)),
                    confidence=self._round(confidence),
                    weight=self._round(weight),
                    weighted_score=self._round(self._clamp_signed(score) * effective_weight),
                    reasons=reasons,
                )
            )
        return tuple(output)

    def _neutralized_contributions(
        self,
        components: Sequence[TechnicalComponentContribution],
        *,
        reason: str,
    ) -> tuple[TechnicalComponentContribution, ...]:
        return tuple(
            TechnicalComponentContribution(
                component=item.component,
                score=0.0,
                confidence=0.0,
                weight=item.weight,
                weighted_score=0.0,
                reasons=(reason,),
            )
            for item in components
        )

    def _neutralized_observations(
        self,
        observations: Sequence[TechnicalIndicatorObservation],
        *,
        reason: str,
    ) -> tuple[TechnicalIndicatorObservation, ...]:
        return tuple(
            TechnicalIndicatorObservation(
                name=item.name,
                value=self._neutral_observation_value(item.name, reason=reason),
                state="INSUFFICIENT",
                direction_score=0.0,
                confidence=0.0,
                reason=f"{item.reason};{reason}",
            )
            for item in observations
        )

    def _neutral_observation_value(self, name: str, *, reason: str) -> Any:
        normalized = str(name or "").strip().upper()
        if normalized in {"SMA", "EMA"}:
            return {"fast": None, "slow": None}
        if normalized == "RSI":
            return None
        if normalized == "MACD":
            return self._neutral_macd_payload()
        if normalized == "ATR":
            return None
        if normalized == "BOLLINGER":
            return self._neutral_bollinger_payload()
        if normalized == "VOLUME":
            return 0.0
        if normalized == "STRUCTURE":
            return self._neutral_structure_payload(reason=reason)
        if normalized == "CANDLESTICK":
            return ()
        return None

    def _observations(self, **kwargs: Any) -> tuple[TechnicalIndicatorObservation, ...]:
        observations: list[TechnicalIndicatorObservation] = []
        sma_fast = kwargs["sma_fast"]
        sma_slow = kwargs["sma_slow"]
        observations.append(self._observation("SMA", {"fast": sma_fast, "slow": sma_slow}, "OK" if sma_fast is not None and sma_slow is not None else "INSUFFICIENT", 0.0, "moving_average_relationship"))
        ema_fast = kwargs["ema_fast"]
        ema_slow = kwargs["ema_slow"]
        observations.append(self._observation("EMA", {"fast": ema_fast, "slow": ema_slow}, "OK" if ema_fast is not None and ema_slow is not None else "INSUFFICIENT", 0.0, "exponential_moving_average_relationship"))
        rsi_value = kwargs["rsi_value"]
        observations.append(self._observation("RSI", self._optional_round(rsi_value), "OK" if rsi_value is not None else "INSUFFICIENT", 0.0 if rsi_value is None else self._clamp_signed((rsi_value - 50.0) / 25.0), "rsi_momentum"))
        macd_payload = kwargs["macd_payload"]
        observations.append(self._observation("MACD", {k: self._optional_round(v) for k, v in macd_payload.items()}, "OK" if macd_payload.get("line") is not None else "INSUFFICIENT", 0.0, "macd_momentum"))
        observations.append(self._observation("ATR", self._optional_round(kwargs["atr_value"]), "OK" if kwargs["atr_value"] is not None else "INSUFFICIENT", 0.0, "average_true_range"))
        observations.append(self._observation("BOLLINGER", kwargs["bollinger_payload"], str(kwargs["bollinger_payload"].get("state") or "INSUFFICIENT"), 0.0, "bollinger_band_position"))
        observations.append(self._observation("VOLUME", self._round(kwargs["volume_score"]), "OK", kwargs["volume_score"], "relative_volume_confirmation"))
        observations.append(self._observation("STRUCTURE", kwargs["structure"], str(kwargs["structure"].get("breakout_state")), kwargs["structure"].get("score", 0.0), "support_resistance_breakout"))
        observations.append(self._observation("CANDLESTICK", tuple(kwargs["patterns"]), "OBSERVED" if kwargs["patterns"] else "NONE", 0.0, "descriptive_patterns_no_predictive_claim"))
        return tuple(observations)

    def _observation(self, name: str, value: Any, state: str, direction_score: float, reason: str) -> TechnicalIndicatorObservation:
        return TechnicalIndicatorObservation(
            name=name,
            value=value,
            state=state,
            direction_score=self._round(self._clamp_signed(float(direction_score or 0.0))),
            confidence=0.0 if state == "INSUFFICIENT" else 1.0,
            reason=reason,
        )

    def _confidence(
        self,
        *,
        sample_count: int,
        warnings: Sequence[str],
        coverage: float,
        agreement: float,
        freshness: str,
    ) -> float:
        sample_factor = self._clamp01(sample_count / max(float(self._minimum_required_samples()), 1.0))
        warning_penalty = min(0.45, len(tuple(dict.fromkeys(warnings))) * 0.08)
        if any(warning in warnings for warning in ("out_of_order_timestamps_sorted", "stale_data")):
            warning_penalty += 0.10
        freshness_factor = 0.75 if freshness == "STALE" else 1.0
        confidence = sample_factor * coverage * (0.5 + 0.5 * agreement) * freshness_factor
        return self._clamp01(confidence - warning_penalty)

    def _insufficient_snapshot(
        self,
        *,
        instrument: str,
        timeframe: str,
        sample_count: int,
        timestamp: str,
        warnings: Sequence[str],
        reason: str,
        freshness: str = "UNKNOWN",
    ) -> TechnicalIntelligenceSnapshot:
        return TechnicalIntelligenceSnapshot(
            schema_version=TECHNICAL_INTELLIGENCE_VERSION,
            instrument=instrument,
            timeframe=timeframe,
            timestamp=timestamp,
            freshness=freshness,
            sample_count=sample_count,
            data_quality="INVALID" if warnings else "INSUFFICIENT",
            insufficient_data=True,
            data_warnings=tuple(dict.fromkeys((*warnings, reason))),
            trend_direction="INDETERMINATE",
            trend_strength=0.0,
            rsi=None,
            macd=self._neutral_macd_payload(),
            bollinger=self._neutral_bollinger_payload(),
            atr=None,
            normalized_volatility=None,
            volatility_state="INSUFFICIENT",
            volume_score=0.0,
            volume_anomaly=False,
            support=None,
            resistance=None,
            breakout_state="INSUFFICIENT",
            distance_from_support=None,
            distance_from_resistance=None,
            patterns=(),
            directional_score=0.0,
            confidence=0.0,
            regime="INSUFFICIENT_DATA",
            observations=(),
            component_contributions=(),
            evidence_reasons=(reason,),
        )

    @staticmethod
    def _neutral_macd_payload() -> dict[str, float | None]:
        return {"line": None, "signal": None, "histogram": None}

    @staticmethod
    def _neutral_bollinger_payload() -> dict[str, float | str | None]:
        return {
            "lower": None,
            "middle": None,
            "upper": None,
            "width": None,
            "position": None,
            "state": "INSUFFICIENT",
        }

    @staticmethod
    def _neutral_structure_payload(*, reason: str) -> dict[str, Any]:
        return {
            "support": None,
            "resistance": None,
            "distance_from_support": None,
            "distance_from_resistance": None,
            "breakout_state": "INSUFFICIENT",
            "score": 0.0,
            "reasons": (reason,),
        }

    def _freshness(self, timestamp: str, *, now: datetime | None) -> str:
        if not timestamp or now is None:
            return "UNKNOWN"
        parsed = self._parse_timestamp(timestamp)
        if parsed is None:
            return "UNKNOWN"
        now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        age = (now_utc.astimezone(timezone.utc) - parsed).total_seconds()
        if age < 0:
            return "FUTURE_TIMESTAMP"
        return "STALE" if age > self.config.stale_after_seconds else "FRESH"

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        return number

    @staticmethod
    def _normalized_weights(weights: Mapping[str, float]) -> dict[str, float]:
        defaults = TechnicalIntelligenceConfig().weights
        merged = {key: max(0.0, float(weights.get(key, defaults[key]))) for key in defaults}
        total = sum(merged.values())
        if total <= 0.0:
            return {key: 1.0 / len(merged) for key in merged}
        return {key: value / total for key, value in merged.items()}

    def _minimum_required_samples(self) -> int:
        return max(
            self.config.sma_slow_window,
            self.config.ema_slow_window + self.config.macd_signal_window - 1,
            self.config.bollinger_window,
            self.config.atr_window + 1,
            self.config.structure_window + 1,
        )

    @staticmethod
    def _indicator_confidence(available: bool) -> float:
        return 1.0 if available else 0.0

    @staticmethod
    def _agreement(scores: Sequence[float]) -> float:
        signs = [1 if score > 0.05 else -1 if score < -0.05 else 0 for score in scores]
        directional = [sign for sign in signs if sign != 0]
        if not directional:
            return 0.5
        return max(directional.count(1), directional.count(-1)) / len(directional)

    @staticmethod
    def _regime(*, trend_direction: str, trend_strength: float, volatility_state: str, breakout_state: str) -> str:
        if volatility_state == "HIGH":
            return "VOLATILE"
        if breakout_state.startswith("BREAKOUT"):
            return "BREAKOUT"
        if breakout_state.startswith("BREAKDOWN"):
            return "BREAKDOWN"
        if trend_direction in {"UP", "DOWN"} and trend_strength >= 0.25:
            return "TREND"
        if volatility_state == "LOW":
            return "RANGE"
        return "NEUTRAL"

    @staticmethod
    def _direction_from_score(score: float) -> str:
        if score > 0.10:
            return "UP"
        if score < -0.10:
            return "DOWN"
        return "NEUTRAL"

    @staticmethod
    def _highest_available_timeframe(snapshots: Mapping[str, TechnicalIntelligenceSnapshot]) -> str | None:
        keys = {key.lower(): key for key in snapshots}
        for candidate in TechnicalIntelligenceEngine.TIMEFRAME_PRIORITY:
            if candidate in keys:
                return keys[candidate]
        return next(iter(snapshots.keys()), None)

    @staticmethod
    def _sign(value: float) -> int:
        if value > 0.05:
            return 1
        if value < -0.05:
            return -1
        return 0

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @classmethod
    def _clamp_signed(cls, value: float) -> float:
        return max(-1.0, min(1.0, float(value)))

    @staticmethod
    def _round(value: float) -> float:
        return round(float(value), 8)

    @classmethod
    def _optional_round(cls, value: Any) -> float | None:
        if value is None:
            return None
        return cls._round(float(value))


__all__ = [
    "TECHNICAL_INTELLIGENCE_VERSION",
    "MultiTimeframeTechnicalIntelligence",
    "TechnicalComponentContribution",
    "TechnicalIndicatorObservation",
    "TechnicalIntelligenceConfig",
    "TechnicalIntelligenceEngine",
    "TechnicalIntelligenceError",
    "TechnicalIntelligenceSnapshot",
]
