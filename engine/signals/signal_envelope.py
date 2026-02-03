"""
Signal Envelope
----------------
Canonical normalization and confidence-scoring layer for ALL inbound signals.

Purpose:
- Normalize heterogeneous signals (price, indicators, volatility, news)
- Time-align signals to engine clock
- Apply confidence weights
- Emit a single, governance-safe envelope to strategy layer

NO execution logic lives here.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import time


@dataclass
class Signal:
    source: str                     # e.g. "twelvedata", "alpaca", "news"
    signal_type: str                # price | indicator | volatility | news
    value: float                    # normalized value (-1.0 to +1.0 preferred)
    confidence: float               # 0.0 – 1.0
    timestamp: float                # epoch seconds
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalEnvelope:
    """
    Container passed downstream to strategies.
    Strategies may READ ONLY.
    """
    instrument: str
    signals: Dict[str, Signal]
    envelope_timestamp: float
    regime_hint: Optional[str] = None   # e.g. risk_on | risk_off | neutral


class SignalNormalizer:
    """
    Normalizes raw inputs into Signal objects.
    """

    @staticmethod
    def normalize_value(raw: float, min_val: float, max_val: float) -> float:
        """
        Linearly normalize to [-1, +1]
        """
        if max_val == min_val:
            return 0.0
        scaled = (raw - min_val) / (max_val - min_val)
        return (scaled * 2.0) - 1.0

    @staticmethod
    def clamp_confidence(conf: float) -> float:
        return max(0.0, min(1.0, conf))


class SignalEnvelopeBuilder:
    """
    Single entry point for building signal envelopes.
    """

    def __init__(self, instrument: str):
        self.instrument = instrument
        self._signals: Dict[str, Signal] = {}

    def add_signal(
        self,
        name: str,
        source: str,
        signal_type: str,
        value: float,
        confidence: float,
        meta: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None
    ):
        self._signals[name] = Signal(
            source=source,
            signal_type=signal_type,
            value=value,
            confidence=SignalNormalizer.clamp_confidence(confidence),
            timestamp=timestamp or time.time(),
            meta=meta or {}
        )

    def build(self, regime_hint: Optional[str] = None) -> SignalEnvelope:
        return SignalEnvelope(
            instrument=self.instrument,
            signals=self._signals.copy(),
            envelope_timestamp=time.time(),
            regime_hint=regime_hint
        )


# Safety invariant: module must never execute trades
if __name__ == "__main__":
    raise RuntimeError(
        "signal_envelope.py is a library module only and must not be executed directly."
    )
