from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any, Protocol

from .futures_contract import CanonicalFuturesContract


class FuturesRepositoryAdapter(Protocol):
    def fetch_active_contracts(self, root_symbol: str | None = None) -> Iterable[Mapping[str, Any]]:
        ...

    def fetch_futures_contract(self, contract_symbol: str) -> Mapping[str, Any] | None:
        ...

    def search_futures_contracts(self, **filters: Any) -> Iterable[Mapping[str, Any]]:
        ...


class CanonicalFuturesRepository:
    def __init__(
        self,
        *,
        adapter: FuturesRepositoryAdapter | None = None,
        contracts: Iterable[CanonicalFuturesContract] | None = None,
    ) -> None:
        self._adapter = adapter
        self._contracts_by_symbol: dict[str, CanonicalFuturesContract] = {}
        for contract in contracts or []:
            self._contracts_by_symbol[contract.contract_symbol] = contract

    def get_active_contracts(self, root_symbol: str | None = None) -> list[CanonicalFuturesContract]:
        if self._adapter is not None:
            for raw in self._adapter.fetch_active_contracts(root_symbol):
                normalized = self.normalize_contract(raw)
                self._contracts_by_symbol[normalized.contract_symbol] = normalized

        expected_root = str(root_symbol or "").strip().upper()
        return [
            contract
            for contract in self._contracts_by_symbol.values()
            if contract.active_contract and (not expected_root or contract.root_symbol.upper() == expected_root)
        ]

    def get_contract(self, contract_symbol: str) -> CanonicalFuturesContract | None:
        symbol = str(contract_symbol or "").strip().upper()
        if not symbol:
            raise ValueError("contract_symbol must be non-empty")

        cached = self._contracts_by_symbol.get(symbol)
        if cached is not None:
            return cached

        if self._adapter is None:
            return None
        raw = self._adapter.fetch_futures_contract(symbol)
        if raw is None:
            return None

        normalized = self.normalize_contract(raw)
        self._contracts_by_symbol[normalized.contract_symbol] = normalized
        return normalized

    def search_contracts(
        self,
        *,
        root_symbol: str | None = None,
        exchange: str | None = None,
        active_only: bool = False,
    ) -> list[CanonicalFuturesContract]:
        if self._adapter is not None:
            raw_rows = self._adapter.search_futures_contracts(
                root_symbol=root_symbol,
                exchange=exchange,
                active_only=active_only,
            )
            for raw in raw_rows:
                normalized = self.normalize_contract(raw)
                self._contracts_by_symbol[normalized.contract_symbol] = normalized

        expected_root = str(root_symbol or "").strip().upper()
        expected_exchange = str(exchange or "").strip().upper()
        results = []
        for contract in self._contracts_by_symbol.values():
            if expected_root and contract.root_symbol.upper() != expected_root:
                continue
            if expected_exchange and contract.exchange.upper() != expected_exchange:
                continue
            if active_only and not contract.active_contract:
                continue
            results.append(contract)
        return sorted(results, key=lambda item: (item.expiration, item.contract_symbol))

    def normalize_contract(self, raw_contract: Mapping[str, Any]) -> CanonicalFuturesContract:
        data = dict(raw_contract)
        contract_symbol = str(data.get("contract_symbol") or data.get("symbol") or "").strip().upper()
        if not contract_symbol:
            raise ValueError("contract symbol is required")

        root_symbol = str(data.get("root_symbol") or data.get("root") or "").strip().upper()
        if not root_symbol:
            raise ValueError("root_symbol is required")

        timestamp = data.get("timestamp") or data.get("quote_time") or datetime.now(timezone.utc).isoformat()

        return CanonicalFuturesContract.from_dict(
            {
                "root_symbol": root_symbol,
                "contract_symbol": contract_symbol,
                "expiration": data.get("expiration") or data.get("expiry"),
                "exchange": data.get("exchange") or "UNKNOWN",
                "tick_size": data.get("tick_size"),
                "point_value": data.get("point_value") or data.get("contract_value"),
                "bid": data.get("bid", 0.0),
                "ask": data.get("ask", 0.0),
                "last": data.get("last", 0.0),
                "volume": data.get("volume", 0),
                "open_interest": data.get("open_interest", 0),
                "active_contract": data.get("active_contract", False),
                "rollover_date": data.get("rollover_date") or data.get("roll_date") or data.get("expiration") or data.get("expiry"),
                "timestamp": timestamp,
            }
        )
