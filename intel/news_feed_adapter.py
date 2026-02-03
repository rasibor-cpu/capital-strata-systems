"""
Structured News Feed Adapter (RSS)
----------------------------------
Exports:
- fetch_structured_news()        -> may raise
- fetch_structured_news_safe()   -> never raises (collector uses this)

Source-agnostic:
- Yahoo RSS
- Reuters RSS (may fail/redirect depending on region)
"""

from __future__ import annotations

import time
import datetime as dt
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict

from intel.intel_envelope import IntelEnvelope

DEFAULT_TIMEOUT = 8
MAX_ITEMS = 5
USER_AGENT = "REA-Intel/1.0 (research)"

RSS_SOURCES = {
    "yahoo": "https://finance.yahoo.com/rss/topstories",
    "reuters": "https://www.reuters.com/rssFeed/businessNews",
}

NEGATIVE_WORDS = {
    "crisis", "collapse", "risk", "fear", "recession", "slowdown",
    "tighten", "inflation", "hawkish", "selloff", "volatility"
}

POSITIVE_WORDS = {
    "growth", "relief", "stabilize", "cooling", "recovery",
    "dovish", "support", "optimism"
}


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        return resp.read()


def _score_headline(text: str) -> float:
    t = text.lower()
    score = 0
    for w in NEGATIVE_WORDS:
        if w in t:
            score -= 1
    for w in POSITIVE_WORDS:
        if w in t:
            score += 1
    return float(score)


def _parse_rss(xml_bytes: bytes, source: str) -> List[Dict]:
    root = ET.fromstring(xml_bytes)
    items: List[Dict] = []

    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue

        tone = _score_headline(title)
        pressure = min(abs(tone) * 0.25, 1.0)

        items.append({
            "ts_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source": source,
            "signal_class": "news",
            "regime_dimension": "risk",
            "pressure": pressure,
            "confidence": 0.70,
            "direction": ("risk_off" if tone < 0 else "risk_on" if tone > 0 else "neutral"),
            "meta": {
                "headline": title,
                "tone_score": tone,
                "source_quality": "free"
            }
        })

        if len(items) >= MAX_ITEMS:
            break

    return items


def fetch_structured_news() -> List[Dict]:
    """
    Returns structured dicts (not envelopes).
    May raise if RSS parsing fails.
    """
    results: List[Dict] = []
    for src, url in RSS_SOURCES.items():
        xml = _http_get(url)
        results.extend(_parse_rss(xml, src))
        time.sleep(1)
    return results


def fetch_structured_news_safe() -> List[IntelEnvelope]:
    """
    Safe wrapper used by intel_collector.
    Returns IntelEnvelope list and NEVER raises.
    """
    envs: List[IntelEnvelope] = []
    try:
        items = fetch_structured_news()
        for it in items:
            # Convert to envelope here (so collector gets envelopes)
            raw = {
                "headline": (it.get("meta") or {}).get("headline"),
                "tone_score": (it.get("meta") or {}).get("tone_score"),
                "direction": it.get("direction"),
                "source_quality": (it.get("meta") or {}).get("source_quality", "free"),
                "raw": it,
            }
            envs.append(
                IntelEnvelope.create(
                    provider=it.get("source", "news_feed"),
                    intel_type="news",
                    signal_class="news",
                    instrument_scope="GLOBAL",
                    raw=raw,
                    confidence=float(it.get("confidence", 0.7)),
                    severity=float(it.get("pressure", 0.0)),
                    rea_instrument=None,
                )
            )
    except Exception:
        return []

    return envs


if __name__ == "__main__":
    envs = fetch_structured_news_safe()
    print(f"STRUCTURED_NEWS_SAFE_OK: {len(envs)}")
    for e in envs[:5]:
        print(e)
