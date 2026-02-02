"""
REA Capital — RegimeSignal
Phase 6.3

Canonical output of the Intel Router.
This is the ONLY object allowed to influence RegimeGate.

Design goals:
- Source-agnostic (FRED, GDELT, Reuters, Bloomberg, etc.)
- Deterministic and auditable
- No execution logic
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class RegimeSignal:
    """
    Interpretable, normalized regime pressure signal.

    All scores MUST be in [0.0 .. 1.0]
    Higher = stronger pressure
    """

    # Core identity
    ts_utc: str
    source: str                 # "fred", "gdelt", "reuters", "bloomberg", etc.
    signal_class: str            # macro | news | volatility | liquidity | policy
    regime_dimension: str        # risk | volatility | liquidity | growth | inflation

    # Normalized pressures
    pressure: float              # overall pressure strength (0..1)
    confidence: float            # confidence in the signal (0..1)

    # Optional semantic direction
    direction: Optional[str] = None
    # e.g. "risk_on", "risk_off", "tightening", "easing"

    # Traceability
    raw_ref: Optional[str] = None   # pointer to audit log / envelope id
    meta: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def now(
        *,
        source: str,
        signal_class: str,
        regime_dimension: str,
        pressure: float,
        confidence: float,
        direction: Optional[str] = None,
        raw_ref: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "RegimeSignal":
        """
        Factory method for safe construction.
        """
        return RegimeSignal(
            ts_utc=datetime.now(timezone.utc).isoformat(),
            source=source,
            signal_class=signal_class,
            regime_dimension=regime_dimension,
            pressure=_clamp01(pressure),
            confidence=_clamp01(confidence),
            direction=direction,
            raw_ref=raw_ref,
            meta=meta or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts_utc": self.ts_utc,
            "source": self.source,
            "signal_class": self.signal_class,
            "regime_dimension": self.regime_dimension,
            "pressure": self.pressure,
            "confidence": self.confidence,
            "direction": self.direction,
            "raw_ref": self.raw_ref,
            "meta": self.meta,
        }


def _clamp01(x: float) -> float:
    try:
        x = float(x)
    except Exception:
        return 0.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return round(x, 3)


# -----------------------------
# Self-test
# -----------------------------

if __name__ == "__main__":
    sig = RegimeSignal.now(
        source="fred",
        signal_class="macro",
        regime_dimension="rates",
        pressure=0.72,
        confidence=0.95,
        direction="tightening",
        raw_ref="audit_logs/fred_DGS10_20260202.json",
        meta={"series_id": "DGS10"},
    )
    print("REGIME_SIGNAL_OK")
    print(sig.to_dict())
