"""Questrade read-only advisory adapter — CONFIGURATION_REQUIRED without credentials/auth."""

from __future__ import annotations

from typing import Any

from backend.app.brokers.operational_state import (
    BrokerCapability,
    BrokerOperationalState,
    operation_result,
)
from backend.brokers.questrade.capability import questrade_capability_descriptor
from backend.brokers.questrade.readiness import questrade_advisory_readiness
from backend.brokers.questrade.token_lifecycle import TokenLifecycle
from backend.options.options_income_freshness import utc_now
from backend.options.options_income_symbol_normalization import normalize_equity_symbol


class QuestradeAdvisoryAdapter:
    """Read-only contracts for accounts, holdings, quotes, and option chains.

    Does not authenticate or place orders. Expected conditions are returned as
    canonical structured results.
    """

    broker = "QUESTRADE"
    mode = "ADVISORY_READ_ONLY"

    def __init__(self, *, token_lifecycle: TokenLifecycle | None = None) -> None:
        self.tokens = token_lifecycle or TokenLifecycle()
        self._generated_at = utc_now()

    def capability(self) -> dict[str, Any]:
        return questrade_capability_descriptor()

    def readiness(self) -> dict[str, Any]:
        return questrade_advisory_readiness()

    def health_check(self) -> dict[str, Any]:
        ready = self.readiness()
        result = operation_result(
            broker=self.broker,
            operation="health",
            state=BrokerOperationalState.CONFIGURATION_REQUIRED,
            failure_code="CONFIGURATION_REQUIRED",
            operator_message="Questrade read-only configuration is required",
            technical_message="No network or OAuth operation was attempted",
            recommended_action="Configure Questrade OAuth settings in an approved future activation phase",
            data={"connected": False, "readiness_state": ready.get("state")},
        ).as_dict()
        result.update({"status": result["state"], "healthy": False, "connected": False})
        return result

    def _blocked(self, contract: str) -> dict[str, Any]:
        capability = {
            "account_data": BrokerCapability.ACCOUNT,
            "holdings": BrokerCapability.HOLDINGS,
            "quote": BrokerCapability.MARKET_DATA,
            "option_chain": BrokerCapability.OPTION_CHAIN,
        }.get(contract)
        state = (
            BrokerOperationalState.OPTION_CHAIN_PROVIDER_REQUIRED
            if contract == "option_chain"
            else BrokerOperationalState.CONFIGURATION_REQUIRED
        )
        result = operation_result(
            broker=self.broker,
            operation=contract,
            state=state,
            failure_code=state.value,
            operator_message=f"Questrade {contract.replace('_', ' ')} configuration is required",
            technical_message="No credential or network operation was attempted",
            recommended_action="Configure Questrade OAuth settings in an approved future activation phase",
            capability=capability,
            data={"authentication_activated": False, "demonstration": False},
            provenance="CONFIGURATION|BROKER_OPERATIONAL_STATE",
        ).as_dict()
        # Phase 178A compatibility fields derive from the canonical result.
        result.update(
            {
                "contract": contract,
                "status": result["state"],
                "failure_reason": result["failure_code"],
                "authentication_activated": False,
                "generated_at": result["received_at"],
                "advisory_only": True,
                "execution_allowed": False,
                "demonstration": False,
                "deprecated_fields": ["status", "failure_reason"],
            }
        )
        return result

    def get_accounts(self) -> dict[str, Any]:
        return self._blocked("account_data")

    def get_holdings_snapshot(self) -> dict[str, Any]:
        row = self._blocked("holdings")
        row.update(
            {
                "account_id": None,
                "account_type": None,
                "base_currency": None,
                "cash": None,
                "buying_power": None,
                "equity": None,
                "holdings": [],
                "option_positions": [],
            }
        )
        return row

    def get_underlying_quote(self, symbol: str) -> dict[str, Any]:
        norm = normalize_equity_symbol(symbol)
        row = self._blocked("quote")
        row.update(
            {
                "symbol": symbol,
                "canonical_symbol": norm.get("canonical"),
                "provider_native_symbol": norm.get("provider_native"),
                "bid": None,
                "ask": None,
                "last": None,
            }
        )
        return row

    def get_option_chain(self, underlying: str) -> dict[str, Any]:
        norm = normalize_equity_symbol(underlying)
        row = self._blocked("option_chain")
        row.update(
            {
                "underlying_symbol": underlying,
                "canonical_underlying": norm.get("canonical"),
                "calls": [],
                "puts": [],
                "expirations": [],
                "greeks_origin": "MISSING",
            }
        )
        return row

    def normalize_symbol(self, symbol: str) -> dict[str, Any]:
        return normalize_equity_symbol(symbol)

    def require_configured(self) -> dict[str, Any]:
        """Deprecated compatibility method; returns a canonical expected state."""
        return self._blocked("configuration")


__all__ = ["QuestradeAdvisoryAdapter"]
