"""
Structured News Feed Adapter
----------------------------

Purpose:
- Pull low-rate, free news headlines (RSS)
- Normalize to IntelEnvelope-compatible dict
- Deterministic sentiment → risk pressure
- Source-agnostic (Yahoo / Reuters RSS today, Bloomberg later)

Design rules:
- NO execution logic
- NO broker coupling
- SAFE rate limits
"""

from __future__ import annotations

import time
import datetime as dt
import urllib.request
import xml.etree.ElementTree as ET

# -----------------------------
# CONFIG
# -----------------------------

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

# -----------------------------
# INTERNAL HELPERS
# -----------------------------

def _http_get(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        return resp.read()


def _score_headline(text: str) -> float:
    """
    Very simple deterministic tone score:
    - Positive → +1
    - Negative → -1
    """
    t = text.lower()
    score = 0
    for w in NEGATIVE_WORDS:
        if w in t:
            score -= 1
    for w in POSITIVE_WORDS:
        if w in t:
            score += 1
    return float(score)


def _parse_rss(xml_bytes: bytes, source: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []

    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue

        tone = _score_headline(title)

        items.append({
            "ts_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source": source,
            "signal_class": "news",
            "regime_dimension": "risk",
            "pressure": min(abs(tone) * 0.25, 1.0),
            "confidence": 0.7,
            "direction": (
                "risk_off" if tone < 0 else
                "risk_on" if tone > 0 else
                "neutral"
            ),
            "meta": {
                "headline": title,
                "tone_score": tone,
                "source_quality": "free"
            }
        })

        if len(items) >= MAX_ITEMS:
            break

    return items


# -----------------------------
# PUBLIC API
# -----------------------------

def fetch_structured_news() -> list[dict]:
    """
    Fetch and normalize news into IntelEnvelope-ready dicts
    """
    results = []

    for src, url in RSS_SOURCES.items():
        try:
            xml = _http_get(url)
            parsed = _parse_rss(xml, src)
            results.extend(parsed)
        except Exception as e:
            # Hard-fail forbidden — log via envelope meta later
            continue

        # Gentle pacing
        time.sleep(1)

    return results


# -----------------------------
# CLI TEST
# -----------------------------

if __name__ == "__main__":
    news = fetch_structured_news()
    print(f"STRUCTURED_NEWS_FOUND: {len(news)}")
    for n in news:
        print(n)
