"""
FRED → IntelEnvelope Transformer
--------------------------------
Converts FRED macro series points into standardized IntelEnvelope
objects consumable by the REA engine (regime gate, risk, prompts).

Design goals:
- Deterministic
- Stateless
- Audit-friendly
- No trading decisions here
"""

from datetime import datetime, timezone
from typing import Dict, Any, List


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def fred_point_to_envelope(
    *,
    series_id: str,
    observation_date: str,
    value: float,
    frequency: str = "unknown",
    source: str = "fred",
) -> Dict[str, Any]:
    """
    Convert a single FRED observation into an IntelEnvelope dict.
    """

    return {
        "ts_utc": _utc_now(),
        "provider": source,
        "intel_type": "macro",
        "signal_class": "macro_indicator",
        "series_id": series_id,
        "observation_date": observation_date,
        "value": value,
        "frequency": frequency,
        "instrument_scope": "GLOBAL",
        "confidence": "official",
        "source_quality": "high",
    }


def fred_series_to_envelopes(
    *,
    series_id: str,
    observations: List[Dict[str, Any]],
    frequency: str = "unknown",
    source: str = "fred",
) -> List[Dict[str, Any]]:
    """
    Convert a list of FRED observations into IntelEnvelope objects.
    """

    envelopes = []

    for obs in observations:
        try:
            val = float(obs["value"])
        except (KeyError, ValueError, TypeError):
            continue

        env = fred_point_to_envelope(
            series_id=series_id,
            observation_date=obs.get("date"),
            value=val,
            frequency=frequency,
            source=source,
        )
        envelopes.append(env)

    return envelopes


# ---------------- SELF TEST ----------------

if __name__ == "__main__":
    sample = [
        {"date": "2025-12-01", "value": "5.33"},
        {"date": "2026-01-01", "value": "5.28"},
    ]

    out = fred_series_to_envelopes(
        series_id="DGS10",
        observations=sample,
        frequency="daily",
    )
"""
FRED → IntelEnvelope Transformer
--------------------------------
Converts FRED macro series points into standardized IntelEnvelope
objects consumable by the REA engine (regime gate, risk, prompts).

Design goals:
- Deterministic
- Stateless
- Audit-friendly
- No trading decisions here
"""

from datetime import datetime, timezone
from typing import Dict, Any, List


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def fred_point_to_envelope(
    *,
    series_id: str,
    observation_date: str,
    value: float,
    frequency: str = "unknown",
    source: str = "fred",
) -> Dict[str, Any]:
    """
    Convert a single FRED observation into an IntelEnvelope dict.
    """

    return {
        "ts_utc": _utc_now(),
        "provider": source,
        "intel_type": "macro",
        "signal_class": "macro_indicator",
        "series_id": series_id,
        "observation_date": observation_date,
        "value": value,
        "frequency": frequency,
        "instrument_scope": "GLOBAL",
        "confidence": "official",
        "source_quality": "high",
    }


def fred_series_to_envelopes(
    *,
    series_id: str,
    observations: List[Dict[str, Any]],
    frequency: str = "unknown",
    source: str = "fred",
) -> List[Dict[str, Any]]:
    """
    Convert a list of FRED observations into IntelEnvelope objects.
    """

    envelopes = []

    for obs in observations:
        try:
            val = float(obs["value"])
        except (KeyError, ValueError, TypeError):
            continue

        env = fred_point_to_envelope(
            series_id=series_id,
            observation_date=obs.get("date"),
            value=val,
            frequency=frequency,
            source=source,
        )
        envelopes.append(env)

    return envelopes


# ---------------- SELF TEST ----------------

if __name__ == "__main__":
    sample = [
        {"date": "2025-12-01", "value": "5.33"},
        {"date": "2026-01-01", "value": "5.28"},
    ]

    out = fred_series_to_envelopes(
        series_id="DGS10",
        observations=sample,
        frequency="daily",
    )

    for e in out:
        print(e)

    for e in out:
        print(e)
