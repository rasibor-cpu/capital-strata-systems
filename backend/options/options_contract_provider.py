from __future__ import annotations

from typing import Any, Iterable

from backend.options.options_broker_abstraction import OptionsBrokerAbstractionError, normalize_option_contract
from backend.trading.option_contract import CanonicalOptionContract


class OptionsContractProvider:
    def __init__(self, contracts: Iterable[Any] | None = None, *, provider_name: str = "paper_options") -> None:
        self.provider_name = str(provider_name or "paper_options").strip()
        if not self.provider_name:
            raise OptionsBrokerAbstractionError("provider name is required")
        self._contracts: dict[str, CanonicalOptionContract] = {}
        for contract in contracts or []:
            normalized = normalize_option_contract(contract)
            key = _symbol(normalized.option_symbol)
            if key in self._contracts:
                raise OptionsBrokerAbstractionError(f"duplicate contract: {normalized.option_symbol}")
            self._contracts[key] = normalized

    def get_contract(self, option_symbol: str) -> CanonicalOptionContract:
        key = _symbol(option_symbol)
        if not key:
            raise OptionsBrokerAbstractionError("option symbol is required")
        if key not in self._contracts:
            raise OptionsBrokerAbstractionError(f"missing contract: {option_symbol}")
        return self._contracts[key]

    def search_contracts(
        self,
        *,
        underlying_symbol: str | None = None,
        option_type: str | None = None,
        expiration_date: str | None = None,
        min_strike: float | None = None,
        max_strike: float | None = None,
    ) -> list[CanonicalOptionContract]:
        underlying = _symbol(underlying_symbol)
        requested_type = _symbol(option_type)
        expiry = str(expiration_date or "").strip()
        rows: list[CanonicalOptionContract] = []
        for contract in self._contracts.values():
            if underlying and _symbol(contract.underlying_symbol) != underlying:
                continue
            if requested_type and contract.option_type != requested_type:
                continue
            if expiry and contract.expiration_date.isoformat() != expiry:
                continue
            if min_strike is not None and contract.strike < float(min_strike):
                continue
            if max_strike is not None and contract.strike > float(max_strike):
                continue
            rows.append(contract)
        rows.sort(key=lambda item: (item.expiration_date, item.strike, item.option_type, item.option_symbol))
        return rows

    def underlying_metadata(self, underlying_symbol: str) -> dict[str, Any]:
        rows = self.search_contracts(underlying_symbol=underlying_symbol)
        if not rows:
            raise OptionsBrokerAbstractionError(f"missing contracts for underlying: {underlying_symbol}")
        return {
            "underlying_symbol": _symbol(underlying_symbol),
            "expiries": sorted({row.expiration_date.isoformat() for row in rows}),
            "strikes": sorted({row.strike for row in rows}),
            "contract_count": len(rows),
            "paper_only": True,
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
        }


def _symbol(value: Any) -> str:
    return str(value or "").strip().upper()


__all__ = ["OptionsContractProvider"]
