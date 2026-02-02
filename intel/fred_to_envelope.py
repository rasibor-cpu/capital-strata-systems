"""
REA Capital — FRED → IntelEnvelope Transformer
Phase 6.2.3 (corrected)

Converts FRED records into canonical IntelEnvelope objects:
- Uses IntelEnvelope.create(...)
- Stores FRED fields inside envelope.raw (never as top-level args)
- Deterministic severity/confidence mapping
"""

from __future__ import annotations

from typing import Dict, Any
from intel.intel_envelope import IntelEnvelope


# -----------------------------
# Series classification map
# -----------------------------

SERIES_MAP = {
    "DGS10": {"signal_class": "rates", "instrument_scope": "GLOBAL", "severity_scale": (3.0, 6.0)},
    "DGS2": {"signal_class": "rates", "instrument_scope": "GLOBAL", "severity_scale": (2.0, 6.0)},
    "T10Y2Y": {"signal_class": "rates", "instrument_scope": "GLOBAL", "severity_scale": (-1.0, 2.0)},
    "CPIAUCSL": {"signal_class": "inflation", "instrument_scope": "GLOBAL", "severity_scale": (2.0, 5.0)},
    "UNRATE": {"signal_class": "labor", "instrument_scope": "GLOBAL", "severity_scale": (3.0, 10.0)},
    "FEDFUNDS": {"signal_class": "policy", "instrument_scope": "GLOBAL", "severity_scale": (1.0, 6.0)},
}


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def compute_confidence(source_quality: str) -> float:
    # Official macro series: high confidence by default
    return {
        "official": 0.95,
        "high": 0.90,
        "medium": 0.75,
        "low": 0.55,
    }.get((source_quality or "official").lower(), 0.80)


def compute_severity(value: float, lo: float, hi: float) -> float:
    # Maps value onto [0.2..0.9] linearly between (lo..hi)
    if hi == lo:
        return 0.5
    if value <= lo:
        return 0.2
    if value >= hi:
        return 0.9
    return round(0.2 + 0.7 * ((value - lo) / (hi - lo)), 3)


def fred_record_to_envelope(record: Dict[str, Any]) -> IntelEnvelope:
    """
    record shape expected:
      {
        "series_id": "DGS10",
        "observation_date": "2026-01-01",
        "value": 5.28,
        "frequency": "daily",
        "source_quality": "official"
      }
    """
    series_id = str(record["series_id"])
    cfg = SERIES_MAP.get(series_id)

    # Fail-closed: unknown series must be explicitly mapped
    if not cfg:
        raise ValueError(f"Unsupported FRED series_id '{series_id}'. Add to SERIES_MAP.")

    value = float(record["value"])
    obs_date = str(record.get("observation_date") or record.get("date") or "")

    lo, hi = cfg["severity_scale"]
    severity = compute_severity(value, lo, hi)
    confidence = compute_confidence(str(record.get("source_quality", "official")))

    raw = {
        "series_id": series_id,
        "observation_date": obs_date,
        "value": value,
        "frequency": record.get("frequency", "unknown"),
        "realtime_start": record.get("realtime_start"),
        "realtime_end": record.get("realtime_end"),
        "source_quality": record.get("source_quality", "official"),
    }

    return IntelEnvelope.create(
        provider="fred",
        intel_type="macro",
        signal_class=cfg["signal_class"],
        instrument_scope=cfg["instrument_scope"],
        raw=raw,
        rea_instrument=None,
        confidence=_clamp01(confidence),
        severity=_clamp01(severity),
    )


# -----------------------------
# Self-test
# -----------------------------

def _self_test():
    sample = {
        "series_id": "DGS10",
        "observation_date": "2026-01-01",
        "value": 5.28,
        "frequency": "daily",
        "source_quality": "official",
    }
    env = fred_record_to_envelope(sample)
    print("FRED_TO_ENVELOPE_OK")
    print(env)


if __name__ == "__main__":
    _self_test()
