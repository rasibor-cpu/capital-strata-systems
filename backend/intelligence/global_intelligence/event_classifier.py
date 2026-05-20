from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List

from .event_models import EventCategory, EventSeverity, IntelligenceEvent
from .event_sources import get_source_reliability
from .market_impact_engine import get_impacted_assets


def _normalize_text(*parts: str) -> str:
    return " ".join(part.lower() for part in parts if part).strip()


def _assign_category(text: str) -> EventCategory:
    if any(keyword in text for keyword in ["fomc", "fed", "rate hike", "rate cut"]):
        return EventCategory.MONETARY_POLICY
    if any(keyword in text for keyword in ["cpi", "inflation", "ppi"]):
        return EventCategory.INFLATION
    if any(keyword in text for keyword in ["nfp", "payrolls", "unemployment"]):
        return EventCategory.EMPLOYMENT
    if any(keyword in text for keyword in ["war", "missile", "invasion", "sanctions"]):
        return EventCategory.GEOPOLITICAL
    if any(keyword in text for keyword in ["bank failure", "liquidity crisis", "deposit run"]):
        return EventCategory.BANKING_STRESS
    if any(keyword in text for keyword in ["crypto ban", "sec action", "regulation", "rulemaking"]):
        return EventCategory.REGULATORY
    if any(keyword in text for keyword in ["exchange outage", "broker outage"]):
        return EventCategory.EXCHANGE
    if any(keyword in text for keyword in ["flash crash", "liquidity shock"]):
        return EventCategory.LIQUIDITY
    if any(keyword in text for keyword in ["earnings", "guidance", "revenue beat", "revenue miss", "earnings beat", "earnings miss"]):
        return EventCategory.EARNINGS
    return EventCategory.UNKNOWN


def _assign_severity(text: str, category: EventCategory) -> EventSeverity:
    if category == EventCategory.MONETARY_POLICY:
        if "rate hike" in text or "rate cut" in text:
            return EventSeverity.HIGH
        return EventSeverity.MODERATE
    if category == EventCategory.INFLATION:
        return EventSeverity.HIGH if "surge" in text or "hot" in text else EventSeverity.MODERATE
    if category == EventCategory.EMPLOYMENT:
        return EventSeverity.MODERATE
    if category == EventCategory.GEOPOLITICAL:
        if any(keyword in text for keyword in ["war", "invasion"]):
            return EventSeverity.SEVERE
        return EventSeverity.HIGH
    if category == EventCategory.BANKING_STRESS:
        return EventSeverity.SEVERE
    if category == EventCategory.REGULATORY:
        return EventSeverity.MODERATE
    if category == EventCategory.EXCHANGE:
        return EventSeverity.HIGH
    if category == EventCategory.LIQUIDITY:
        return EventSeverity.SEVERE
    if category == EventCategory.EARNINGS:
        if any(keyword in text for keyword in ["miss", "beat"]):
            return EventSeverity.HIGH
        return EventSeverity.MODERATE
    return EventSeverity.LOW


def _build_event_id(title: str, timestamp: datetime) -> str:
    safe_title = re.sub(r"\s+", "_", title.strip().lower())[:50]
    return f"gie-{timestamp.strftime('%Y%m%d%H%M%S')}-{safe_title}"


def classify_event(title: str, description: str = "", source: str = "Unknown Source") -> IntelligenceEvent:
    normalized = _normalize_text(title, description)
    category = _assign_category(normalized)
    severity = _assign_severity(normalized, category)
    affected_assets = get_impacted_assets(category, title)
    confidence = float(get_source_reliability(source))
    now = datetime.now(timezone.utc)
    event = IntelligenceEvent(
        event_id=_build_event_id(title, now),
        timestamp=now,
        title=title,
        category=category,
        severity=severity,
        confidence=confidence,
        source=source,
        affected_assets=affected_assets,
        description=description,
    )
    return event