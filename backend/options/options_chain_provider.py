from __future__ import annotations

from typing import Any

from backend.options.options_broker_abstraction import OptionsBrokerAbstractionError, OptionsChainSnapshot, stable_contract_rows, timestamp_or_now
from backend.options.options_contract_provider import OptionsContractProvider


class OptionsChainProvider:
    def __init__(self, contract_provider: OptionsContractProvider, *, provider_name: str = "paper_options", source: str = "paper_contracts") -> None:
        self.contract_provider = contract_provider
        self.provider_name = str(provider_name or "paper_options")
        self.source = str(source or "paper_contracts")

    def available_expiries(self, underlying_symbol: str) -> list[str]:
        return self.contract_provider.underlying_metadata(underlying_symbol)["expiries"]

    def available_strikes(self, underlying_symbol: str) -> list[float]:
        return self.contract_provider.underlying_metadata(underlying_symbol)["strikes"]

    def calls(self, underlying_symbol: str, *, expiration_date: str | None = None) -> list[dict[str, Any]]:
        return stable_contract_rows(self.contract_provider.search_contracts(underlying_symbol=underlying_symbol, option_type="CALL", expiration_date=expiration_date))

    def puts(self, underlying_symbol: str, *, expiration_date: str | None = None) -> list[dict[str, Any]]:
        return stable_contract_rows(self.contract_provider.search_contracts(underlying_symbol=underlying_symbol, option_type="PUT", expiration_date=expiration_date))

    def get_chain(self, underlying_symbol: str, *, expiration_date: str | None = None, now: str | None = None) -> OptionsChainSnapshot:
        underlying = str(underlying_symbol or "").strip().upper()
        if not underlying:
            raise OptionsBrokerAbstractionError("underlying symbol is required")
        contracts = self.contract_provider.search_contracts(underlying_symbol=underlying, expiration_date=expiration_date)
        if not contracts:
            raise OptionsBrokerAbstractionError(f"missing chain: {underlying}")
        calls = [contract for contract in contracts if contract.option_type == "CALL"]
        puts = [contract for contract in contracts if contract.option_type == "PUT"]
        missing_fields: list[str] = []
        if not calls:
            missing_fields.append("calls")
        if not puts:
            missing_fields.append("puts")
        if any(contract.implied_volatility <= 0 for contract in contracts):
            missing_fields.append("iv")
        status = "DEGRADED" if missing_fields else "ONLINE"
        quality = "PARTIAL" if missing_fields else "COMPLETE"
        return OptionsChainSnapshot(
            provider_name=self.provider_name,
            underlying_symbol=underlying,
            expiries=sorted({contract.expiration_date.isoformat() for contract in contracts}),
            strikes=sorted({contract.strike for contract in contracts}),
            calls=stable_contract_rows(calls),
            puts=stable_contract_rows(puts),
            generated_at=timestamp_or_now(now),
            source=self.source,
            status=status,
            quality=quality,
            missing_fields=sorted(missing_fields),
        )


__all__ = ["OptionsChainProvider"]
