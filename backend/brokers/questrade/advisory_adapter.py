"""Questrade read-only advisory adapter — CONFIGURATION_REQUIRED without credentials/auth."""

from __future__ import annotations

from typing import Any, Mapping

from backend.app.brokers.operational_state import (
    BrokerCapability,
    BrokerOperationalState,
    operation_result,
)
from backend.brokers.questrade.capability import questrade_capability_descriptor
from backend.brokers.questrade.configuration import QuestradeSecureConfiguration
from backend.brokers.questrade.contracts import (
    account_hash,
    map_accounts,
    map_balances,
    map_option_chain,
    map_positions,
    map_quotes,
)
from backend.brokers.questrade.readiness import questrade_advisory_readiness, questrade_read_only_certification
from backend.brokers.questrade.readonly_client import QuestradeReadOnlyClient
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

    def __init__(
        self,
        *,
        token_lifecycle: TokenLifecycle | None = None,
        configuration: QuestradeSecureConfiguration | None = None,
        client: QuestradeReadOnlyClient | None = None,
    ) -> None:
        self.configuration = configuration or QuestradeSecureConfiguration.from_environment_presence()
        self.tokens = token_lifecycle or TokenLifecycle()
        self.client = client or QuestradeReadOnlyClient(self.tokens)
        self._generated_at = utc_now()
        self._account_catalog: dict[str, str] = {}
        self._account_metadata: dict[str, dict[str, Any]] = {}
        self._selected_account_hash: str | None = self.configuration.selected_account_hash
        self._evidence: dict[str, Any] = {"read_only_allowlist_active": True}

    def capability(self) -> dict[str, Any]:
        return questrade_capability_descriptor()

    def readiness(self) -> dict[str, Any]:
        return questrade_advisory_readiness(
            configuration=self.configuration,
            tokens=self.tokens,
            evidence=self._readiness_evidence(),
        )

    def certification(self) -> dict[str, Any]:
        return questrade_read_only_certification(self.readiness())

    def configuration_status(self) -> dict[str, Any]:
        return self.configuration.sanitized_summary()

    def token_status(self) -> dict[str, Any]:
        return self.tokens.status()

    def onboarding_status(self) -> dict[str, Any]:
        ready = self.readiness()
        return {
            "state": ready["state"],
            "steps": [
                "REVIEW_READ_ONLY_CAPABILITIES",
                "CONFIGURE_SECURE_SECRET_REFERENCES",
                "COMPLETE_SEPARATELY_AUTHORIZED_OAUTH",
                "VALIDATE_TOKEN_METADATA",
                "DISCOVER_ACCOUNTS",
                "SELECT_MASKED_ACCOUNT",
                "VALIDATE_BALANCES_AND_HOLDINGS",
                "VALIDATE_QUOTES_AND_OPTION_CHAIN",
                "RUN_READ_ONLY_CERTIFICATION",
                "REMAIN_EXECUTION_BLOCKED",
            ],
            "current_action": self.certification()["required_action"],
            "authorization_launch_enabled": False,
            "credential_form_enabled": False,
            "execution_allowed": False,
        }

    def health_check(self) -> dict[str, Any]:
        ready = self.readiness()
        state = self._canonical_state(str(ready.get("state") or "CONFIGURATION_REQUIRED"))
        result = operation_result(
            broker=self.broker,
            operation="health",
            state=state,
            success=state is BrokerOperationalState.READ_ONLY_READY,
            failure_code=None if state is BrokerOperationalState.READ_ONLY_READY else state.value,
            operator_message="Questrade read-only readiness evaluated",
            technical_message="No network or OAuth operation was attempted",
            recommended_action="Configure Questrade OAuth settings in an approved future activation phase",
            data={
                "connected": state is BrokerOperationalState.READ_ONLY_READY,
                "readiness_state": ready.get("state"),
                "certification": self.certification(),
                "configuration": self.configuration_status(),
            },
        ).as_dict()
        result.update(
            {
                "status": result["state"],
                "healthy": state is BrokerOperationalState.READ_ONLY_READY,
                "connected": state is BrokerOperationalState.READ_ONLY_READY,
            }
        )
        return result

    def _blocked(self, contract: str) -> dict[str, Any]:
        capability = {
            "account_data": BrokerCapability.ACCOUNT,
            "holdings": BrokerCapability.HOLDINGS,
            "quote": BrokerCapability.MARKET_DATA,
            "option_chain": BrokerCapability.OPTION_CHAIN,
        }.get(contract)
        token_state = str(self.tokens.status().get("state") or "")
        if not self.configuration.validate()["token_reference_present"]:
            state = BrokerOperationalState.CONFIGURATION_REQUIRED
        elif token_state in {"TOKEN_EXPIRED", "TOKEN_REFRESH_REQUIRED"}:
            state = BrokerOperationalState.TOKEN_REFRESH_REQUIRED
        else:
            state = BrokerOperationalState.AUTHENTICATION_REQUIRED
        if contract == "option_chain" and state is BrokerOperationalState.CONFIGURATION_REQUIRED:
            state = BrokerOperationalState.OPTION_CHAIN_PROVIDER_REQUIRED
        result = operation_result(
            broker=self.broker,
            operation=contract,
            state=state,
            failure_code=state.value,
            operator_message=f"Questrade {contract.replace('_', ' ')} configuration is required",
            technical_message="No credential or network operation was attempted",
            recommended_action=self.certification()["required_action"],
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
        prerequisite = self._prerequisite_failure("account_data")
        if prerequisite:
            return prerequisite
        result = self.client.request("/accounts", success_state=BrokerOperationalState.ACCOUNT_READY)
        if not result.success:
            return self._http_failure("account_data", result.diagnostics("accounts"))
        mapped = map_accounts(result.payload, generated_at=self._generated_at)
        self._account_catalog.clear()
        self._account_metadata.clear()
        raw_accounts = result.payload.get("accounts") if isinstance(result.payload.get("accounts"), list) else []
        for raw in raw_accounts:
            if not isinstance(raw, Mapping):
                continue
            number = raw.get("number") or raw.get("accountNumber") or raw.get("id")
            digest = account_hash(number)
            self._account_catalog[digest] = str(number)
        for row in mapped["accounts"]:
            self._account_metadata[str(row["account_hash"])] = dict(row)
        self._evidence["account_count"] = mapped["account_count"]
        return {**mapped, **result.diagnostics("accounts")}

    def select_account(self, masked_account_hash: str) -> dict[str, Any]:
        digest = str(masked_account_hash or "")
        if digest not in self._account_catalog:
            return operation_result(
                broker=self.broker,
                operation="select_account",
                state=BrokerOperationalState.ACCOUNT_REQUIRED,
                failure_code="ACCOUNT_SELECTION_REQUIRED",
                operator_message="Select an account from the sanitized discovery result",
                data={"selected": False, "available_account_hashes": sorted(self._account_catalog)},
            ).as_dict()
        self._selected_account_hash = digest
        self._evidence["selected_account"] = True
        return operation_result(
            broker=self.broker,
            operation="select_account",
            state=BrokerOperationalState.ACCOUNT_READY,
            success=True,
            operator_message="Approved masked Questrade account selected in memory",
            data={"selected": True, "account_hash": digest, "masked_identifier": self._account_metadata[digest]["masked_identifier"]},
        ).as_dict()

    def get_balances(self) -> dict[str, Any]:
        prerequisite = self._prerequisite_failure("balances")
        if prerequisite:
            return prerequisite
        number = self._selected_account_number()
        if not number:
            return self._account_selection_required("balances")
        result = self.client.request(
            f"/accounts/{number}/balances",
            success_state=BrokerOperationalState.ACCOUNT_READY,
        )
        if not result.success:
            return self._http_failure("balances", result.diagnostics("balances"))
        account_type = self._account_metadata.get(self._selected_account_hash or "", {}).get("account_type")
        mapped = map_balances(result.payload, account_type=account_type, generated_at=self._generated_at)
        self._evidence["balances_fresh"] = mapped["status"] == "ACCOUNT_READY"
        return {**mapped, **result.diagnostics("balances")}

    def get_activities(self, *, start_time: str | None = None, end_time: str | None = None) -> dict[str, Any]:
        prerequisite = self._prerequisite_failure("activities")
        if prerequisite:
            return prerequisite
        number = self._selected_account_number()
        if not number:
            return self._account_selection_required("activities")
        result = self.client.request(
            f"/accounts/{number}/activities",
            params={"startTime": start_time, "endTime": end_time},
            success_state=BrokerOperationalState.ACCOUNT_READY,
        )
        if not result.success:
            return self._http_failure("activities", result.diagnostics("activities"))
        activities = result.payload.get("activities") if isinstance(result.payload.get("activities"), list) else []
        return {
            **result.diagnostics("activities"),
            "status": "ACCOUNT_READY",
            "activity_count": len(activities),
            "activities": [
                {
                    "trade_date": row.get("tradeDate"),
                    "transaction_date": row.get("transactionDate"),
                    "type": row.get("type"),
                    "symbol": normalize_equity_symbol(str(row.get("symbol") or "")).get("canonical"),
                    "quantity": row.get("quantity"),
                    "currency": row.get("currency"),
                    "provenance": "QUESTRADE_ACTIVITIES",
                }
                for row in activities
                if isinstance(row, Mapping)
            ],
            "execution_allowed": False,
        }

    def get_holdings_snapshot(self) -> dict[str, Any]:
        prerequisite = self._prerequisite_failure("holdings")
        if prerequisite:
            prerequisite.update({"holdings": [], "option_positions": [], "cash": None, "buying_power": None})
            return prerequisite
        number = self._selected_account_number()
        if not number:
            row = self._account_selection_required("holdings")
            row.update({"holdings": [], "option_positions": [], "cash": None, "buying_power": None})
            return row
        result = self.client.request(
            f"/accounts/{number}/positions",
            success_state=BrokerOperationalState.HOLDINGS_READY,
        )
        if not result.success:
            return self._http_failure("holdings", result.diagnostics("positions"))
        mapped = map_positions(result.payload, generated_at=self._generated_at)
        balances = self.get_balances()
        combined = balances.get("balances") if isinstance(balances.get("balances"), list) else []
        first_balance = combined[0] if combined else {}
        mapped.update(
            {
                "account_id": None,
                "account_id_sanitized": self._account_metadata.get(self._selected_account_hash or "", {}).get("masked_identifier"),
                "account_hash": self._selected_account_hash,
                "account_type": self._account_metadata.get(self._selected_account_hash or "", {}).get("account_type"),
                "base_currency": first_balance.get("currency"),
                "cash": first_balance.get("cash"),
                "buying_power": first_balance.get("buying_power"),
                "equity": first_balance.get("equity"),
                "broker": self.broker,
                "full_account_number_returned": False,
            }
        )
        self._evidence["holdings_fresh"] = mapped["status"] == "HOLDINGS_READY"
        return {**mapped, **result.diagnostics("positions")}

    def get_underlying_quote(self, symbol: str) -> dict[str, Any]:
        prerequisite = self._prerequisite_failure("quote")
        if prerequisite:
            return prerequisite
        norm = normalize_equity_symbol(symbol)
        lookup = self.client.request("/symbols", params={"prefix": norm.get("provider_native")})
        if not lookup.success:
            return self._http_failure("quote", lookup.diagnostics("symbol_lookup"))
        symbols = lookup.payload.get("symbols") if isinstance(lookup.payload.get("symbols"), list) else []
        symbol_id = symbols[0].get("symbolId") if symbols and isinstance(symbols[0], Mapping) else None
        if symbol_id is None:
            row = self._blocked("quote")
            row.update({"failure_reason": "SYMBOL_UNSUPPORTED", "canonical_symbol": norm.get("canonical")})
            return row
        result = self.client.request(
            "/markets/quotes",
            params={"ids": symbol_id},
            success_state=BrokerOperationalState.MARKET_DATA_READY,
        )
        if not result.success:
            return self._http_failure("quote", result.diagnostics("quotes"))
        mapped = map_quotes(result.payload, generated_at=self._generated_at)
        quote = mapped["quotes"][0] if mapped["quotes"] else {}
        self._evidence["quotes_fresh"] = mapped["status"] == "MARKET_DATA_READY"
        return {**quote, **mapped, **result.diagnostics("quotes")}

    def search_symbols(self, prefix: str) -> dict[str, Any]:
        prerequisite = self._prerequisite_failure("symbol_search")
        if prerequisite:
            return prerequisite
        result = self.client.request("/symbols", params={"prefix": str(prefix or "")})
        if not result.success:
            return self._http_failure("symbol_search", result.diagnostics("symbol_search"))
        symbols = result.payload.get("symbols") if isinstance(result.payload.get("symbols"), list) else []
        return {
            **result.diagnostics("symbol_search"),
            "status": "MARKET_DATA_READY",
            "symbols": [
                {
                    "symbol_id": row.get("symbolId"),
                    "symbol": normalize_equity_symbol(str(row.get("symbol") or "")).get("canonical"),
                    "provider_native_symbol": row.get("symbol"),
                    "description": row.get("description"),
                    "security_type": row.get("securityType"),
                    "listing_exchange": row.get("listingExchange"),
                    "currency": row.get("currency"),
                    "is_tradable": row.get("isTradable"),
                }
                for row in symbols
                if isinstance(row, Mapping)
            ],
            "execution_allowed": False,
        }

    def get_market_status(self) -> dict[str, Any]:
        prerequisite = self._prerequisite_failure("market_status")
        if prerequisite:
            return prerequisite
        result = self.client.request("/markets", success_state=BrokerOperationalState.MARKET_DATA_READY)
        if not result.success:
            return self._http_failure("market_status", result.diagnostics("market_status"))
        markets = result.payload.get("markets") if isinstance(result.payload.get("markets"), list) else []
        return {
            **result.diagnostics("market_status"),
            "status": "MARKET_DATA_READY",
            "markets": [
                {
                    "name": row.get("name"),
                    "trading_venues": row.get("tradingVenues"),
                    "default_trading_venue": row.get("defaultTradingVenue"),
                    "primary_order_routes": row.get("primaryOrderRoutes"),
                    "secondary_order_routes": row.get("secondaryOrderRoutes"),
                }
                for row in markets
                if isinstance(row, Mapping)
            ],
            "execution_allowed": False,
        }

    def get_option_chain(self, underlying: str) -> dict[str, Any]:
        prerequisite = self._prerequisite_failure("option_chain")
        if prerequisite:
            prerequisite.update({"calls": [], "puts": [], "expirations": [], "greeks_origin": "MISSING"})
            return prerequisite
        norm = normalize_equity_symbol(underlying)
        lookup = self.client.request("/symbols", params={"prefix": norm.get("provider_native")})
        if not lookup.success:
            return self._http_failure("option_chain", lookup.diagnostics("symbol_lookup"))
        symbols = lookup.payload.get("symbols") if isinstance(lookup.payload.get("symbols"), list) else []
        symbol_id = symbols[0].get("symbolId") if symbols and isinstance(symbols[0], Mapping) else None
        if symbol_id is None:
            return self._blocked("option_chain")
        result = self.client.request(
            f"/symbols/{symbol_id}/options",
            success_state=BrokerOperationalState.OPTION_CHAIN_READY,
        )
        if not result.success:
            return self._http_failure("option_chain", result.diagnostics("option_chain"))
        mapped = map_option_chain(result.payload, generated_at=self._generated_at)
        option_ids = [
            row.get("symbol_id")
            for row in [*mapped.get("calls", []), *mapped.get("puts", [])]
            if isinstance(row, Mapping) and row.get("symbol_id") is not None
        ]
        if option_ids:
            quote_result = self.client.request("/markets/quotes", params={"ids": ",".join(map(str, option_ids))})
            if quote_result.success:
                quote_map = {
                    row.get("symbol_id"): row
                    for row in map_quotes(quote_result.payload, generated_at=self._generated_at).get("quotes", [])
                }
                for side in ("calls", "puts"):
                    mapped[side] = [
                        {**row, **dict(quote_map.get(row.get("symbol_id")) or {})}
                        for row in mapped.get(side, [])
                    ]
                mapped["contract_quotes_available"] = bool(quote_map)
        mapped.update({"underlying_symbol": underlying, "canonical_underlying": norm.get("canonical")})
        self._evidence["option_chain_ready"] = mapped["status"] == "OPTION_CHAIN_READY"
        return {**mapped, **result.diagnostics("option_chain")}

    def normalize_symbol(self, symbol: str) -> dict[str, Any]:
        return normalize_equity_symbol(symbol)

    def require_configured(self) -> dict[str, Any]:
        """Deprecated compatibility method; returns a canonical expected state."""
        return self._blocked("configuration")

    def _selected_account_number(self) -> str | None:
        return self._account_catalog.get(self._selected_account_hash or "")

    def _prerequisite_failure(self, contract: str) -> dict[str, Any] | None:
        config = self.configuration.validate()
        if not config["valid"] or not config["token_reference_present"]:
            return self._blocked(contract)
        if str(self.tokens.status().get("state") or "") != "AUTHENTICATED":
            return self._blocked(contract)
        return None

    def _account_selection_required(self, operation: str) -> dict[str, Any]:
        return operation_result(
            broker=self.broker,
            operation=operation,
            state=BrokerOperationalState.ACCOUNT_REQUIRED,
            failure_code="ACCOUNT_SELECTION_REQUIRED",
            operator_message="Explicit Questrade account selection is required",
            recommended_action="Discover accounts and select one masked account",
            data={"selected_account": False},
        ).as_dict()

    def _http_failure(self, contract: str, diagnostics: dict[str, Any]) -> dict[str, Any]:
        row = dict(diagnostics)
        row.update(
            {
                "contract": contract,
                "status": diagnostics.get("state"),
                "failure_reason": diagnostics.get("failure_code"),
                "authentication_activated": False,
                "advisory_only": True,
                "execution_allowed": False,
            }
        )
        return row

    def _readiness_evidence(self) -> dict[str, Any]:
        evidence = dict(self._evidence)
        evidence["selected_account"] = bool(self._selected_account_hash and self._selected_account_number())
        evidence["api_server_valid"] = bool(self.tokens.api_server_for_transport())
        return evidence

    @staticmethod
    def _canonical_state(onboarding_state: str) -> BrokerOperationalState:
        return {
            "CONFIGURATION_REQUIRED": BrokerOperationalState.CONFIGURATION_REQUIRED,
            "AUTHORIZATION_REQUIRED": BrokerOperationalState.AUTHENTICATION_REQUIRED,
            "TOKEN_REFRESH_REQUIRED": BrokerOperationalState.TOKEN_REFRESH_REQUIRED,
            "ACCOUNT_SELECTION_REQUIRED": BrokerOperationalState.ACCOUNT_REQUIRED,
            "READ_ONLY_VALIDATION_REQUIRED": BrokerOperationalState.DEGRADED,
            "READ_ONLY_READY": BrokerOperationalState.READ_ONLY_READY,
            "DEGRADED": BrokerOperationalState.DEGRADED,
            "FAILED": BrokerOperationalState.FAILED,
        }.get(onboarding_state, BrokerOperationalState.NOT_INITIALIZED)


__all__ = ["QuestradeAdvisoryAdapter"]
