from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.options.options_broker_abstraction import (
    OptionsBrokerAbstractionError,
    OptionsMarketDataSnapshot,
    contract_greeks,
    contract_quote,
    timestamp_or_now,
)
from backend.options.options_contract_provider import OptionsContractProvider


class OptionsMarketDataProvider:
    def __init__(
        self,
        contract_provider: OptionsContractProvider,
        *,
        source: str = "paper_market_data",
        max_cache_age_seconds: int = 900,
    ) -> None:
        if max_cache_age_seconds < 0:
            raise OptionsBrokerAbstractionError("max_cache_age_seconds cannot be negative")
        self.contract_provider = contract_provider
        self.source = str(source or "paper_market_data")
        self.max_cache_age_seconds = max_cache_age_seconds
        self._cache: dict[str, OptionsMarketDataSnapshot] = {}

    def snapshot(self, option_symbol: str, *, now: str | None = None) -> OptionsMarketDataSnapshot:
        key = str(option_symbol or "").strip().upper()
        current = timestamp_or_now(now)
        cached = self._cache.get(key)
        if cached is not None and _age_seconds(cached.freshness_timestamp, current) <= self.max_cache_age_seconds:
            return OptionsMarketDataSnapshot(**{**cached.to_dict(), "cached": True})
        return self.refresh(key, now=current)

    def refresh(self, option_symbol: str, *, now: str | None = None) -> OptionsMarketDataSnapshot:
        contract = self.contract_provider.get_contract(option_symbol)
        quote = contract_quote(contract)
        greeks = contract_greeks(contract)
        missing: list[str] = []
        if contract.implied_volatility <= 0:
            missing.append("iv")
        if not greeks:
            missing.append("greeks")
        status = "DEGRADED" if missing else "ONLINE"
        quality = "PARTIAL" if missing else "COMPLETE"
        snapshot = OptionsMarketDataSnapshot(
            option_symbol=contract.option_symbol,
            underlying_symbol=contract.underlying_symbol,
            quote=quote,
            greeks=greeks,
            implied_volatility=contract.implied_volatility,
            freshness_timestamp=timestamp_or_now(now),
            source=self.source,
            status=status,
            quality=quality,
            cached=False,
        )
        self._cache[contract.option_symbol.upper()] = snapshot
        return snapshot


def _age_seconds(start: str, end: str) -> float:
    first = datetime.fromisoformat(start.replace("Z", "+00:00"))
    second = datetime.fromisoformat(end.replace("Z", "+00:00"))
    if first.tzinfo is None:
        first = first.replace(tzinfo=timezone.utc)
    if second.tzinfo is None:
        second = second.replace(tzinfo=timezone.utc)
    return (second - first).total_seconds()


__all__ = ["OptionsMarketDataProvider"]
