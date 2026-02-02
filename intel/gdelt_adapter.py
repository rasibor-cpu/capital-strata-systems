"""
REA Capital – GDELT News/Event Radar Adapter (FREE, HARDENED)
------------------------------------------------------------
Purpose:
- Pull near-real-time global headlines from GDELT (v2 DOC API)
- Normalize to REA-friendly RiskHeadline objects
- Fail gracefully on empty / non-JSON responses

Public API:
- fetch_headlines(query, minutes, max_records)
- fetch_gdelt_headlines(query, minutes, max_records)  # stable alias
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RiskHeadline:
    ts_utc: str
    provider: str
    query: str
    title: str
    url: str
    domain: Optional[str]
    language: Optional[str]
    source_country: Optional[str]
    seendate_utc: Optional[str]
    tone: Optional[float]
    relevance: Optional[float]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def fmt_gdelt_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def http_get_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "REA-Capital/1.0 (gdelt adapter)",
            "Accept": "application/json",
        },
        method="GET",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace").strip()

    if not raw:
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


GDELT_DOC_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"


def build_gdelt_doc_url(query: str, start: datetime, end: datetime, max_records: int) -> str:
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(max_records),
        "startdatetime": fmt_gdelt_dt(start),
        "enddatetime": fmt_gdelt_dt(end),
    }
    return f"{GDELT_DOC_ENDPOINT}?{urllib.parse.urlencode(params)}"


def parse_articles(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    arts = payload.get("articles")
    return arts if isinstance(arts, list) else []


def normalize_article(article: Dict[str, Any], query: str) -> RiskHeadline:
    def s(x): return str(x).strip() if x is not None else None

    title = s(article.get("title")) or ""
    url = s(article.get("url")) or ""
    if not title or not url:
        raise ValueError("Missing title/url")

    tone = None
    try:
        if article.get("tone") is not None:
            tone = float(article.get("tone"))
    except Exception:
        pass

    relevance = None
    try:
        if article.get("relevance") is not None:
            relevance = float(article.get("relevance"))
    except Exception:
        pass

    return RiskHeadline(
        ts_utc=utc_now().isoformat(),
        provider="gdelt",
        query=query,
        title=title,
        url=url,
        domain=s(article.get("domain")),
        language=s(article.get("language")),
        source_country=s(article.get("sourceCountry")),
        seendate_utc=s(article.get("seendate")),
        tone=tone,
        relevance=relevance,
    )


def fetch_headlines(query: str, minutes: int = 60, max_records: int = 25) -> List[RiskHeadline]:
    end = utc_now()
    start = end - timedelta(minutes=minutes)
    url = build_gdelt_doc_url(query, start, end, max_records)

    payload = http_get_json(url)
    articles = parse_articles(payload)

    out: List[RiskHeadline] = []
    for a in articles:
        try:
            out.append(normalize_article(a, query))
        except Exception:
            continue
    return out


# Stable alias (do not remove): used by other modules / overlays
def fetch_gdelt_headlines(query: str, minutes: int = 60, max_records: int = 25) -> List[RiskHeadline]:
    return fetch_headlines(query=query, minutes=minutes, max_records=max_records)


def write_audit(headlines: List[RiskHeadline], query: str) -> Path:
    log_dir = Path("audit_logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    fname = f"gdelt_headlines_{utc_now().strftime('%Y%m%dT%H%M%SZ')}.json"
    path = log_dir / fname

    payload = {
        "ts_utc": utc_now().isoformat(),
        "provider": "gdelt",
        "query": query,
        "count": len(headlines),
        "headlines": [asdict(h) for h in headlines],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def main() -> int:
    p = argparse.ArgumentParser(description="GDELT News/Event Radar (REA)")
    p.add_argument("--query", required=True)
    p.add_argument("--minutes", type=int, default=60)
    p.add_argument("--max", type=int, default=25)
    p.add_argument("--audit", action="store_true")
    args = p.parse_args()

    headlines = fetch_headlines(args.query, args.minutes, args.max)
    print(json.dumps([asdict(h) for h in headlines], indent=2))

    if args.audit:
        path = write_audit(headlines, args.query)
        print(f"\nAUDIT_LOG_WRITTEN: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
