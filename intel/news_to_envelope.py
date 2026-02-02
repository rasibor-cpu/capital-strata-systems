"""
News → IntelEnvelope transformer
--------------------------------
Converts structured news dicts (from news_feed_adapter) into IntelEnvelope.

Run:
  python -m intel.news_to_envelope
"""

from typing import Dict, Optional
from intel.intel_envelope import IntelEnvelope


def news_item_to_envelope(item: Dict) -> Optional[IntelEnvelope]:
    try:
        provider = item.get("source", "news_feed")
        pressure = float(item.get("pressure", 0.0))
        confidence = float(item.get("confidence", 0.6))
        direction = item.get("direction", "neutral")

        raw = {
            "headline": (item.get("meta") or {}).get("headline"),
            "tone_score": (item.get("meta") or {}).get("tone_score"),
            "direction": direction,
            "source_quality": (item.get("meta") or {}).get("source_quality", "free"),
            "raw": item,
        }

        return IntelEnvelope.create(
            provider=provider,
            intel_type="news",
            signal_class="news",
            instrument_scope="GLOBAL",
            raw=raw,
            confidence=min(max(confidence, 0.0), 1.0),
            severity=min(max(pressure, 0.0), 1.0),
            rea_instrument=None,
        )
    except Exception:
        return None


def _self_test():
    sample = {
        "ts_utc": "2026-02-03T00:00:00+00:00",
        "source": "yahoo",
        "signal_class": "news",
        "regime_dimension": "risk",
        "pressure": 0.65,
        "confidence": 0.7,
        "direction": "risk_off",
        "meta": {"headline": "Fed signals higher for longer", "tone_score": -2, "source_quality": "free"},
    }

    env = news_item_to_envelope(sample)
    print("NEWS_ENVELOPE_OK" if env else "NEWS_ENVELOPE_FAILED")
    print(env)


if __name__ == "__main__":
    _self_test()
