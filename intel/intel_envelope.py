"""
REA Capital – Canonical Intel Envelope
-------------------------------------
Single normalized structure for all non-price intelligence
(macro, news, events, narrative, policy).

This module is PURE / DETERMINISTIC:
- No I/O
- No network
- No side effects
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid


@dataclass(frozen=True)
class IntelEnvelope:
    # Core identity
    intel_id: str
    ts_utc: str

    # Source
    provider: str            # e.g. fred, gdelt, reuters
    intel_type: str          # macro | news | event
    signal_class: str        # rates | inflation | risk | sentiment

    # Scope
    instrument_scope: str    # GLOBAL | FX:USD | CRYPTO | EQUITY
    rea_instrument: Optional[str]

    # Scoring (0.0 – 1.0)
    confidence: float
    severity: float

    # Raw payload (verbatim source data)
    raw: Dict[str, Any] = field(repr=False)

    @staticmethod
    def now_utc() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(
        cls,
        *,
        provider: str,
        intel_type: str,
        signal_class: str,
        instrument_scope: str,
        raw: Dict[str, Any],
        rea_instrument: Optional[str] = None,
        confidence: float = 0.5,
        severity: float = 0.5,
    ) -> "IntelEnvelope":

        if not (0.0 <= confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")

        if not (0.0 <= severity <= 1.0):
            raise ValueError("severity must be between 0.0 and 1.0")

        return cls(
            intel_id=str(uuid.uuid4()),
            ts_utc=cls.now_utc(),
            provider=provider.lower(),
            intel_type=intel_type.lower(),
            signal_class=signal_class.lower(),
            instrument_scope=instrument_scope.upper(),
            rea_instrument=rea_instrument,
            confidence=round(confidence, 3),
            severity=round(severity, 3),
            raw=raw,
        )


def self_test() -> None:
    sample = IntelEnvelope.create(
        provider="fred",
        intel_type="macro",
        signal_class="rates",
        instrument_scope="GLOBAL",
        raw={"series": "DGS10", "value": 4.12},
        confidence=0.85,
        severity=0.7,
    )

    print("INTEL_ENVELOPE_OK")
    print(sample)


if __name__ == "__main__":
    self_test()
