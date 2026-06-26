from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any, Protocol

from .option_contract import CanonicalOptionContract


class OptionsRepositoryAdapter(Protocol):
    def fetch_option_chain(self, underlying_symbol: str) -> Iterable[Mapping[str, Any]]:
        ...

    def fetch_option_contract(self, option_symbol: str) -> Mapping[str, Any] | None:
        ...

    def search_option_contracts(self, **filters: Any) -> Iterable[Mapping[str, Any]]:
        ...


class CanonicalOptionsRepository:
    def __init__(
        self,
        *,
        adapter: OptionsRepositoryAdapter | None = None,
        contracts: Iterable[CanonicalOptionContract] | None = None,
    ) -> None:
        self._adapter = adapter
        self._contracts_by_symbol: dict[str, CanonicalOptionContract] = {}
        for contract in contracts or []:
            self._contracts_by_symbol[contract.option_symbol] = contract

    def get_option_chain(
        self,
        underlying_symbol: str,
        *,
        expiration_date: str | None = None,
        option_type: str | None = None,
    ) -> list[CanonicalOptionContract]:
        symbol = str(underlying_symbol or "").strip().upper()
        if not symbol:
            raise ValueError("underlying_symbol must be non-empty")

        if self._adapter is not None:
            for raw in self._adapter.fetch_option_chain(symbol):
                normalized = self.normalize_contract(raw)
                self._contracts_by_symbol[normalized.option_symbol] = normalized

        requested_type = str(option_type or "").strip().upper()
        return [
            contract
            for contract in self._contracts_by_symbol.values()
            if contract.underlying_symbol.upper() == symbol
            and (not expiration_date or contract.expiration_date.isoformat() == expiration_date)
            and (not requested_type or contract.option_type == requested_type)
        ]

    def get_contract(self, option_symbol: str) -> CanonicalOptionContract | None:
        symbol = str(option_symbol or "").strip().upper()
        if not symbol:
            raise ValueError("option_symbol must be non-empty")

        cached = self._contracts_by_symbol.get(symbol)
        if cached is not None:
            return cached

        if self._adapter is None:
            return None

        raw = self._adapter.fetch_option_contract(symbol)
        if raw is None:
            return None
        normalized = self.normalize_contract(raw)
        self._contracts_by_symbol[normalized.option_symbol] = normalized
        return normalized

    def search_contracts(
        self,
        *,
        underlying_symbol: str | None = None,
        option_type: str | None = None,
        min_strike: float | None = None,
        max_strike: float | None = None,
        exchange: str | None = None,
    ) -> list[CanonicalOptionContract]:
        if self._adapter is not None:
            raw_rows = self._adapter.search_option_contracts(
                underlying_symbol=underlying_symbol,
                option_type=option_type,
                min_strike=min_strike,
                max_strike=max_strike,
                exchange=exchange,
            )
            for raw in raw_rows:
                normalized = self.normalize_contract(raw)
                self._contracts_by_symbol[normalized.option_symbol] = normalized

        expected_symbol = str(underlying_symbol or "").strip().upper()
        expected_type = str(option_type or "").strip().upper()
        expected_exchange = str(exchange or "").strip().upper()

        results = []
        for contract in self._contracts_by_symbol.values():
            if expected_symbol and contract.underlying_symbol.upper() != expected_symbol:
                continue
            if expected_type and contract.option_type != expected_type:
                continue
            if min_strike is not None and contract.strike < float(min_strike):
                continue
            if max_strike is not None and contract.strike > float(max_strike):
                continue
            if expected_exchange and contract.exchange.upper() != expected_exchange:
                continue
            results.append(contract)
        return sorted(results, key=lambda item: (item.expiration_date, item.strike, item.option_symbol))

    def normalize_contract(self, raw_contract: Mapping[str, Any]) -> CanonicalOptionContract:
        data = dict(raw_contract)

        option_symbol = str(data.get("option_symbol") or data.get("symbol") or "").strip().upper()
        if not option_symbol:
            raise ValueError("option symbol is required")

        underlying_symbol = str(
            data.get("underlying_symbol") or data.get("underlying") or ""
        ).strip().upper()
        if not underlying_symbol:
            raise ValueError("underlying_symbol is required")

        bid = float(data.get("bid", 0.0))
        ask = float(data.get("ask", 0.0))
        midpoint = data.get("midpoint")
        if midpoint is None:
            midpoint = (bid + ask) / 2.0 if ask >= bid else bid
        last = float(data.get("last", midpoint))

        option_type = str(data.get("option_type") or data.get("right") or "").strip().upper()
        if option_type not in {"CALL", "PUT"}:
            raise ValueError("option_type must be CALL or PUT")

        intrinsic_value = data.get("intrinsic_value")
        if intrinsic_value is None:
            spot = data.get("underlying_price")
            strike = float(data.get("strike") or data.get("strike_price"))
            if spot is not None:
                spot_price = float(spot)
                intrinsic_value = max(spot_price - strike, 0.0) if option_type == "CALL" else max(strike - spot_price, 0.0)
            else:
                intrinsic_value = 0.0
        intrinsic_value = float(intrinsic_value)

        extrinsic_value = data.get("extrinsic_value")
        if extrinsic_value is None:
            extrinsic_value = max(last - intrinsic_value, 0.0)

        probability_itm = data.get("probability_itm")
        if probability_itm is None:
            delta = float(data.get("delta", 0.0))
            probability_itm = min(max(abs(delta), 0.0), 1.0)

        timestamp = data.get("timestamp") or data.get("quote_time") or datetime.now(timezone.utc).isoformat()

        return CanonicalOptionContract.from_dict(
            {
                "underlying_symbol": underlying_symbol,
                "option_symbol": option_symbol,
                "expiration_date": data.get("expiration_date") or data.get("expiration") or data.get("expiry"),
                "strike": data.get("strike") or data.get("strike_price"),
                "option_type": option_type,
                "bid": bid,
                "ask": ask,
                "midpoint": midpoint,
                "last": last,
                "volume": data.get("volume", 0),
                "open_interest": data.get("open_interest", 0),
                "implied_volatility": data.get("implied_volatility") or data.get("iv") or 0.0,
                "delta": data.get("delta", 0.0),
                "gamma": data.get("gamma", 0.0),
                "theta": data.get("theta", 0.0),
                "vega": data.get("vega", 0.0),
                "rho": data.get("rho", 0.0),
                "intrinsic_value": intrinsic_value,
                "extrinsic_value": extrinsic_value,
                "probability_itm": probability_itm,
                "exchange": data.get("exchange") or "UNKNOWN",
                "multiplier": data.get("multiplier", 100),
                "currency": data.get("currency") or "USD",
                "timestamp": timestamp,
            }
        )
