from __future__ import annotations

from typing import Any, Iterable, Mapping

from backend.options.options_broker_abstraction import (
    PAPER_ONLY_FLAGS,
    SUPPORTED_PAPER_STRATEGIES,
    OptionsBrokerAbstractionError,
    PaperAccountSnapshot,
    PaperOrderPreview,
    assert_paper_safe_posture,
)
from backend.options.options_broker_capabilities import OptionsBrokerCapabilities, default_paper_options_capabilities
from backend.options.options_chain_provider import OptionsChainProvider
from backend.options.options_contract_provider import OptionsContractProvider
from backend.options.options_market_data_provider import OptionsMarketDataProvider


class OptionsPaperBroker:
    version = "OI-009"

    def __init__(
        self,
        *,
        provider_name: str = "paper_options",
        contracts: Iterable[Any] | None = None,
        buying_power: float = 100000.0,
        cash: float | None = None,
        equity: float | None = None,
        mode: str = "PAPER",
    ) -> None:
        assert_paper_safe_posture(mode=mode)
        if buying_power < 0:
            raise OptionsBrokerAbstractionError("negative buying power")
        self.provider_name = str(provider_name or "paper_options").strip()
        if not self.provider_name:
            raise OptionsBrokerAbstractionError("provider name is required")
        self.contracts = OptionsContractProvider(contracts or [], provider_name=self.provider_name)
        self.chain_provider = OptionsChainProvider(self.contracts, provider_name=self.provider_name)
        self.market_data = OptionsMarketDataProvider(self.contracts)
        self.capabilities = default_paper_options_capabilities(self.provider_name)
        self.account = PaperAccountSnapshot(
            account_id="PAPER-OPTIONS-ACCOUNT",
            buying_power=float(buying_power),
            cash=float(cash if cash is not None else buying_power),
            equity=float(equity if equity is not None else buying_power),
            source=self.provider_name,
        )

    def quote(self, option_symbol: str, *, now: str | None = None) -> dict[str, Any]:
        return self.market_data.snapshot(option_symbol, now=now).to_dict()

    def contract(self, option_symbol: str) -> dict[str, Any]:
        return {**self.contracts.get_contract(option_symbol).to_dict(), **PAPER_ONLY_FLAGS}

    def chain(self, underlying_symbol: str, *, expiration_date: str | None = None, now: str | None = None) -> dict[str, Any]:
        return self.chain_provider.get_chain(underlying_symbol, expiration_date=expiration_date, now=now).to_dict()

    def buying_power_inquiry(self) -> dict[str, Any]:
        return self.account.to_dict()

    def account_summary(self) -> dict[str, Any]:
        return self.account.to_dict()

    def capability_report(self) -> dict[str, Any]:
        return self.capabilities.to_dict()

    def status(self) -> str:
        return "ONLINE"

    def preview_order(
        self,
        *,
        strategy: str,
        paper_account: Mapping[str, Any] | None = None,
        collateral: float,
        premium: float,
        quantity: int,
        option_symbol: str,
        underlying_symbol: str | None = None,
        mode: str = "PAPER",
    ) -> dict[str, Any]:
        assert_paper_safe_posture(mode=mode)
        strategy_name = str(strategy or "").strip().upper()
        if strategy_name not in SUPPORTED_PAPER_STRATEGIES:
            raise OptionsBrokerAbstractionError("unsupported strategy")
        if collateral < 0:
            raise OptionsBrokerAbstractionError("negative collateral")
        if premium < 0:
            raise OptionsBrokerAbstractionError("negative premium")
        if int(quantity or 0) <= 0:
            raise OptionsBrokerAbstractionError("quantity must be positive")
        account = dict(paper_account or self.account.to_dict())
        buying_power = float(account.get("buying_power", 0.0) or 0.0)
        if buying_power < 0:
            raise OptionsBrokerAbstractionError("negative buying power")
        symbol = str(option_symbol or "").strip().upper()
        if not symbol:
            raise OptionsBrokerAbstractionError("missing contract")
        contract = self.contracts.get_contract(symbol)
        estimated_collateral = round(float(collateral) * int(quantity), 6)
        estimated_premium = round(float(premium) * int(quantity), 6)
        buying_power_impact = round(estimated_collateral - estimated_premium, 6)
        warnings: list[str] = []
        reasons = ["paper preview only", "broker path absent", "no order identifier created"]
        if buying_power_impact > buying_power:
            warnings.append("INSUFFICIENT_PAPER_BUYING_POWER")
        preview_status = "WARNING" if warnings else "PASS"
        return PaperOrderPreview(
            strategy=strategy_name,
            underlying_symbol=str(underlying_symbol or contract.underlying_symbol).upper(),
            option_symbol=contract.option_symbol,
            quantity=int(quantity),
            estimated_collateral=estimated_collateral,
            estimated_premium=estimated_premium,
            estimated_buying_power_impact=buying_power_impact,
            warnings=warnings,
            reasons=reasons,
            preview_status=preview_status,
        ).to_dict()


__all__ = ["OptionsPaperBroker"]
