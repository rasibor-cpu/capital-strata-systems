from __future__ import annotations

from typing import List

from .event_models import EventCategory


def get_impacted_assets(category: EventCategory, title: str = "") -> List[str]:
    normalized_title = title.lower() if title else ""
    if category == EventCategory.MONETARY_POLICY:
        return ["SPY", "QQQ", "TLT", "USD"]
    if category == EventCategory.INFLATION:
        return ["SPY", "QQQ", "TLT", "USD", "GOLD"]
    if category == EventCategory.EMPLOYMENT:
        return ["SPY", "QQQ", "TLT", "USD"]
    if category == EventCategory.GEOPOLITICAL:
        return ["SPY", "QQQ", "GOLD", "OIL", "USD"]
    if category == EventCategory.BANKING_STRESS:
        return ["KRE", "XLF", "SPY", "TLT"]
    if category == EventCategory.REGULATORY:
        if any(keyword in normalized_title for keyword in ["crypto", "btc", "eth", "coin"]):
            return ["BTC", "ETH", "COIN"]
        return ["SPY", "XLF", "USD"]
    if category == EventCategory.EXCHANGE:
        if "nasdaq" in normalized_title or "nyse" in normalized_title or "exchange" in normalized_title:
            return ["MARKET"]
        return ["MARKET"]
    if category == EventCategory.LIQUIDITY:
        return ["MARKET", "TLT"]
    if category == EventCategory.EARNINGS:
        sectors = []
        if any(keyword in normalized_title for keyword in ["tech", "software", "apple", "microsoft"]):
            sectors.append("QQQ")
        if any(keyword in normalized_title for keyword in ["bank", "finance", "jpm", "wells" ]):
            sectors.append("XLF")
        return sectors + ["QQQ", "SPY"] if sectors else ["QQQ", "SPY"]
    return ["MARKET"]