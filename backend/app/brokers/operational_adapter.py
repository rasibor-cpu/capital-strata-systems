"""Source-only Tier-1 operational adapters.

These adapters inspect supplied configuration evidence only. They never
authenticate, refresh tokens, connect to brokers, or enable execution.
"""

from __future__ import annotations

from typing import Any, Mapping

from backend.app.brokers.canonical_tier1 import get_canonical_broker_registry
from backend.app.brokers.operational_state import (
    BrokerCapability,
    BrokerOperationalState,
    BrokerOperationResult,
    certification_outcome,
    operation_result,
    utc_now,
)

_CREDENTIAL_KEYS: Mapping[str, tuple[str, ...]] = {
    "COINBASE": ("COINBASE_API_KEY", "COINBASE_API_SECRET"),
    "BINANCE": ("BINANCE_API_KEY", "BINANCE_API_SECRET"),
    "OANDA": ("OANDA_API_KEY|OANDA_ACCESS_TOKEN|OANDA_API_TOKEN|OANDA_TOKEN",),
    "QUESTRADE": ("QUESTRADE_REFRESH_TOKEN",),
}

_CONFIG_KEYS: Mapping[str, tuple[str, ...]] = {
    "COINBASE": (),
    "BINANCE": (),
    "OANDA": ("OANDA_BASE_URL",),
    "QUESTRADE": ("QUESTRADE_API_SERVER|QUESTRADE_BASE_URL|QUESTRADE_API_URL",),
}

_ACCOUNT_KEYS: Mapping[str, tuple[str, ...]] = {
    "COINBASE": (),
    "BINANCE": (),
    "OANDA": ("OANDA_ACCOUNT_ID",),
    "QUESTRADE": ("QUESTRADE_ACCOUNT_ID",),
}


class CanonicalOperationalAdapter:
    """Canonical expected-condition adapter for one Tier-1 broker."""

    broker = "NONE"

    def __init__(
        self,
        *,
        configuration: Mapping[str, Any] | None = None,
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        self.configuration = dict(configuration or {})
        self.evidence = dict(evidence or {})

    def authenticate(self) -> dict[str, Any]:
        prerequisite = self._prerequisite("authenticate")
        if prerequisite:
            return prerequisite.as_dict()
        if self.evidence.get("token_expired"):
            return self._result(
                "authenticate",
                BrokerOperationalState.TOKEN_REFRESH_REQUIRED,
                retryable=True,
                failure_code="TOKEN_REFRESH_REQUIRED",
                operator_message="Broker token refresh is required",
                recommended_action="Refresh the broker token through an approved future activation workflow",
            ).as_dict()
        if not self._verified_flag("authenticated"):
            return self._result(
                "authenticate",
                BrokerOperationalState.AUTHENTICATION_REQUIRED,
                failure_code="AUTHENTICATION_REQUIRED",
                operator_message="Broker authentication has not been performed",
                recommended_action="Authenticate through an approved future activation workflow",
            ).as_dict()
        return self._result(
            "authenticate",
            BrokerOperationalState.AUTHENTICATED,
            success=True,
            operator_message="Authentication evidence is present",
        ).as_dict()

    def account(self) -> dict[str, Any]:
        prerequisite = self._authenticated_prerequisite("account")
        if prerequisite:
            return prerequisite.as_dict()
        if not self._account_selected():
            return self._result(
                "account",
                BrokerOperationalState.ACCOUNT_REQUIRED,
                failure_code="ACCOUNT_REQUIRED",
                operator_message="A broker account must be selected",
                recommended_action="Select an authorized read-only account",
                capability=BrokerCapability.ACCOUNT,
            ).as_dict()
        if self.evidence.get("account_unavailable"):
            return self._result(
                "account",
                BrokerOperationalState.ACCOUNT_UNAVAILABLE,
                retryable=True,
                failure_code="ACCOUNT_UNAVAILABLE",
                operator_message="Broker account data is unavailable",
                recommended_action="Retry after provider recovery",
                capability=BrokerCapability.ACCOUNT,
            ).as_dict()
        return self._result(
            "account",
            BrokerOperationalState.ACCOUNT_READY,
            success=True,
            operator_message="Sanitized account evidence is ready",
            capability=BrokerCapability.ACCOUNT,
            data={"account_id_sanitized": self.evidence.get("account_id_sanitized")},
        ).as_dict()

    def balances(self) -> dict[str, Any]:
        return self._account_capability("balances", BrokerCapability.BALANCES)

    def holdings(self) -> dict[str, Any]:
        return self._account_capability("holdings", BrokerCapability.HOLDINGS)

    def positions(self) -> dict[str, Any]:
        return self._account_capability("positions", BrokerCapability.HOLDINGS)

    def market_data(self, symbol: str | None = None) -> dict[str, Any]:
        prerequisite = self._prerequisite("market_data")
        if prerequisite:
            return prerequisite.as_dict()
        if self.evidence.get("rate_limited"):
            return self._rate_limited("market_data", BrokerCapability.MARKET_DATA).as_dict()
        if self.evidence.get("provider_unavailable"):
            return self._provider_unavailable("market_data", BrokerCapability.MARKET_DATA).as_dict()
        if not self._verified_flag("market_data_ready"):
            return self._result(
                "market_data",
                BrokerOperationalState.MARKET_DATA_UNAVAILABLE,
                retryable=True,
                failure_code="MARKET_DATA_UNAVAILABLE",
                operator_message="Broker market data is unavailable",
                recommended_action="Configure or restore the broker market-data provider",
                capability=BrokerCapability.MARKET_DATA,
                data={"symbol": symbol},
            ).as_dict()
        return self._result(
            "market_data",
            BrokerOperationalState.MARKET_DATA_READY,
            success=True,
            operator_message="Broker market-data evidence is ready",
            capability=BrokerCapability.MARKET_DATA,
            freshness=str(self.evidence.get("freshness") or "UNKNOWN"),
            provider_timestamp=self.evidence.get("provider_timestamp"),
            data={"symbol": symbol},
        ).as_dict()

    def products(self) -> dict[str, Any]:
        if not self._verified_flag("products_ready"):
            return self._result(
                "products",
                BrokerOperationalState.MARKET_DATA_REQUIRED,
                failure_code="PRODUCT_SYNCHRONIZATION_REQUIRED",
                operator_message="Broker products have not been synchronized",
                recommended_action="Run an approved read-only product synchronization",
                data={"registered_capabilities": self.capability_states()},
            ).as_dict()
        return self._result(
            "products",
            BrokerOperationalState.READ_ONLY_READY,
            success=True,
            operator_message="Registered broker capabilities are available",
            data={"capabilities": self.capability_states()},
        ).as_dict()

    def health(self) -> dict[str, Any]:
        if self.evidence.get("rate_limited"):
            return self._rate_limited("health").as_dict()
        if self.evidence.get("provider_unavailable"):
            return self._provider_unavailable("health").as_dict()
        prerequisite = self._prerequisite("health")
        if prerequisite:
            return prerequisite.as_dict()
        state = (
            BrokerOperationalState.READ_ONLY_READY
            if self._verified_flag("authenticated") and (self._account_selected() or self.broker in {"COINBASE", "BINANCE"})
            else BrokerOperationalState.AUTHENTICATION_REQUIRED
        )
        return self._result(
            "health",
            state,
            success=state is BrokerOperationalState.READ_ONLY_READY,
            operator_message=(
                "Broker read-only evidence is ready"
                if state is BrokerOperationalState.READ_ONLY_READY
                else "Broker authentication has not been performed"
            ),
            recommended_action="" if state is BrokerOperationalState.READ_ONLY_READY else "Authenticate in an approved future phase",
        ).as_dict()

    def readiness(self) -> dict[str, Any]:
        health = self.health()
        state = BrokerOperationalState(str(health["state"]))
        outcome = certification_outcome(state)
        result = self._result(
            "readiness",
            state,
            success=state is BrokerOperationalState.READ_ONLY_READY,
            retryable=bool(health.get("retryable")),
            expected_condition=bool(health.get("expected_condition", True)),
            failure_code=health.get("failure_code"),
            operator_message=str(health.get("operator_message") or ""),
            technical_message=str(health.get("technical_message") or ""),
            recommended_action=str(health.get("recommended_action") or ""),
            data={
                "readiness": outcome,
                "certification": outcome,
                "capability_states": self.capability_states(),
                "execution_ready": False,
                "micro_pilot_ready": False,
                "live_ready": False,
            },
        ).as_dict()
        return result

    def capability(self, capability: BrokerCapability | str) -> dict[str, Any]:
        cap = capability if isinstance(capability, BrokerCapability) else BrokerCapability(str(capability).upper())
        supported = self._supports(cap)
        if cap is BrokerCapability.OPTION_CHAIN and not supported:
            state = BrokerOperationalState.OPTION_CHAIN_UNAVAILABLE
            action = "Use Questrade or an approved listed-options provider"
        elif cap is BrokerCapability.EXECUTION:
            state = BrokerOperationalState.EXECUTION_BLOCKED
            action = "Execution is not authorized"
            supported = False
        elif supported:
            return self._supported_capability_state(cap)
        else:
            state = BrokerOperationalState.PROVIDER_UNAVAILABLE
            action = "Use a broker that supports this capability"
        return self._result(
            f"capability:{cap.value.lower()}",
            state,
            success=supported,
            failure_code=None if supported else f"{cap.value}_UNAVAILABLE",
            operator_message=(
                f"{cap.value} is supported for read-only use"
                if supported
                else f"{cap.value} is not supported by {self.broker}"
            ),
            recommended_action=action,
            capability=cap,
            data={"supported": supported, "operationally_ready": False},
        ).as_dict()

    def _supported_capability_state(self, capability: BrokerCapability) -> dict[str, Any]:
        """Separate declared support from evidence-backed operational readiness."""
        if capability is BrokerCapability.ACCOUNT:
            dependency = self.account()
        elif capability is BrokerCapability.BALANCES:
            dependency = self.balances()
        elif capability is BrokerCapability.HOLDINGS:
            dependency = self.holdings()
        elif capability in {BrokerCapability.MARKET_DATA, BrokerCapability.HISTORICAL_DATA}:
            dependency = self.market_data()
        elif capability is BrokerCapability.OPTION_CHAIN and hasattr(self, "option_chain"):
            dependency = self.option_chain()  # type: ignore[attr-defined]
        else:
            prerequisite = self._authenticated_prerequisite(f"capability:{capability.value.lower()}")
            dependency = (
                prerequisite.as_dict()
                if prerequisite
                else self._result(
                    f"capability:{capability.value.lower()}",
                    BrokerOperationalState.READ_ONLY_READY,
                    success=True,
                    operator_message=f"{capability.value} is operationally ready for read-only use",
                    capability=capability,
                ).as_dict()
            )

        dependency_state = BrokerOperationalState(str(dependency["state"]))
        operationally_ready = bool(dependency.get("success")) and dependency_state in {
            BrokerOperationalState.ACCOUNT_READY,
            BrokerOperationalState.HOLDINGS_READY,
            BrokerOperationalState.MARKET_DATA_READY,
            BrokerOperationalState.OPTION_CHAIN_READY,
            BrokerOperationalState.READ_ONLY_READY,
            BrokerOperationalState.ADVISORY_READY,
        }
        state = dependency_state
        if capability is BrokerCapability.HOLDINGS and not operationally_ready:
            state = BrokerOperationalState.HOLDINGS_UNAVAILABLE

        return self._result(
            f"capability:{capability.value.lower()}",
            state,
            success=operationally_ready,
            retryable=bool(dependency.get("retryable")),
            expected_condition=bool(dependency.get("expected_condition", True)),
            failure_code=None if operationally_ready else state.value,
            operator_message=(
                f"{capability.value} is operationally ready for read-only use"
                if operationally_ready
                else f"{capability.value} is declared supported but is not operationally ready"
            ),
            technical_message=str(dependency.get("technical_message") or ""),
            recommended_action=str(dependency.get("recommended_action") or ""),
            capability=capability,
            freshness=str(dependency.get("freshness") or "UNKNOWN"),
            provider_timestamp=dependency.get("provider_timestamp"),
            data={
                "supported": True,
                "declared_supported": True,
                "operationally_ready": operationally_ready,
                "dependency_state": dependency_state.value,
            },
        ).as_dict()

    def capability_states(self) -> dict[str, Any]:
        return {
            capability.value: self.capability(capability)
            for capability in BrokerCapability
        }

    def operational_snapshot(self) -> dict[str, Any]:
        readiness = self.readiness()
        return {
            "broker": self.broker,
            "operational_state": readiness["state"],
            "readiness": readiness["data"]["readiness"],
            "certification": readiness["data"]["certification"],
            "recommended_action": readiness["recommended_action"],
            "expected_condition": readiness["expected_condition"],
            "retryable": readiness["retryable"],
            "last_successful_operation": self.evidence.get("last_successful_operation"),
            "latency_ms": self.evidence.get("latency_ms"),
            "freshness": self.evidence.get("freshness", "UNKNOWN"),
            "capability_states": readiness["data"]["capability_states"],
            "execution_state": BrokerOperationalState.EXECUTION_BLOCKED.value,
            "execution_allowed": False,
            "advisory_allowed": True,
            "generated_at": utc_now(),
            "operation_result": readiness,
        }

    def _prerequisite(self, operation: str) -> BrokerOperationResult | None:
        missing_config = [key for key in _CONFIG_KEYS[self.broker] if not self._configured_any(key)]
        if missing_config:
            return self._result(
                operation,
                BrokerOperationalState.CONFIGURATION_REQUIRED,
                failure_code="CONFIGURATION_REQUIRED",
                operator_message=f"{self.broker} configuration is required",
                technical_message="Required configuration keys are absent",
                recommended_action=f"Configure {self.broker} read-only settings",
                data={"missing_configuration_keys": missing_config},
            )
        missing_credentials = [key for key in _CREDENTIAL_KEYS[self.broker] if not self._configured_any(key)]
        if missing_credentials:
            return self._result(
                operation,
                BrokerOperationalState.CREDENTIALS_REQUIRED,
                failure_code="CREDENTIALS_REQUIRED",
                operator_message=f"{self.broker} credentials are required",
                technical_message="Required credential keys are absent",
                recommended_action=f"Configure {self.broker} credentials through the approved secret store",
                data={"missing_credential_keys": missing_credentials},
            )
        return None

    def _authenticated_prerequisite(self, operation: str) -> BrokerOperationResult | None:
        prerequisite = self._prerequisite(operation)
        if prerequisite:
            return prerequisite
        if self.evidence.get("token_expired"):
            return self._result(
                operation,
                BrokerOperationalState.TOKEN_REFRESH_REQUIRED,
                retryable=True,
                failure_code="TOKEN_REFRESH_REQUIRED",
                operator_message="Broker token refresh is required",
                recommended_action="Refresh token through an approved future activation workflow",
            )
        if not self._verified_flag("authenticated"):
            return self._result(
                operation,
                BrokerOperationalState.AUTHENTICATION_REQUIRED,
                failure_code="AUTHENTICATION_REQUIRED",
                operator_message="Broker authentication is required",
                recommended_action="Authenticate through an approved future activation workflow",
            )
        return None

    def _account_capability(self, operation: str, capability: BrokerCapability) -> dict[str, Any]:
        account = self.account()
        if account["state"] != BrokerOperationalState.ACCOUNT_READY.value:
            account["operation"] = operation
            account["capability"] = capability.value
            return account
        unavailable_key = f"{operation}_unavailable"
        if self.evidence.get(unavailable_key):
            state = (
                BrokerOperationalState.HOLDINGS_UNAVAILABLE
                if capability is BrokerCapability.HOLDINGS
                else BrokerOperationalState.ACCOUNT_UNAVAILABLE
            )
            return self._result(
                operation,
                state,
                retryable=True,
                failure_code=state.value,
                operator_message=f"Broker {operation} data is unavailable",
                recommended_action="Retry after provider recovery",
                capability=capability,
            ).as_dict()
        state = (
            BrokerOperationalState.HOLDINGS_READY
            if capability is BrokerCapability.HOLDINGS
            else BrokerOperationalState.ACCOUNT_READY
        )
        return self._result(
            operation,
            state,
            success=True,
            operator_message=f"Broker {operation} evidence is ready",
            capability=capability,
            data={operation: self.evidence.get(operation, [])},
        ).as_dict()

    def _account_selected(self) -> bool:
        required = _ACCOUNT_KEYS[self.broker]
        return not required or all(self.configuration.get(key) for key in required) or self._verified_flag("account_selected")

    def _configured_any(self, key_expression: str) -> bool:
        return any(bool(self.configuration.get(key)) for key in key_expression.split("|"))

    def _verified_flag(self, name: str) -> bool:
        provenance = str(self.evidence.get("provenance") or self.evidence.get("evidence_source") or "").upper()
        verified = bool(self.evidence.get("evidence_verified")) or provenance in {
            "BROKER",
            "BROKER_API",
            "SIGNED_CACHE",
            "CERTIFIED_RUNTIME",
        }
        return verified and bool(self.evidence.get(name))

    def _supports(self, capability: BrokerCapability) -> bool:
        spec = get_canonical_broker_registry().get(self.broker)
        if capability in {BrokerCapability.ACCOUNT, BrokerCapability.BALANCES, BrokerCapability.HOLDINGS}:
            return True
        if capability in {BrokerCapability.MARKET_DATA, BrokerCapability.HISTORICAL_DATA}:
            return bool(spec.capabilities.load_market_data)
        if capability is BrokerCapability.CRYPTO:
            return self.broker in {"COINBASE", "BINANCE"}
        if capability is BrokerCapability.FX:
            return self.broker == "OANDA"
        if capability is BrokerCapability.EQUITIES:
            return bool(spec.capabilities.canadian_equities)
        if capability is BrokerCapability.ETFS:
            return bool(spec.capabilities.etfs)
        if capability in {BrokerCapability.LISTED_OPTIONS, BrokerCapability.OPTION_CHAIN}:
            return bool(spec.capabilities.listed_options)
        if capability is BrokerCapability.REGISTERED_ACCOUNTS:
            return bool(spec.capabilities.registered_accounts_future)
        if capability is BrokerCapability.STREAMING:
            return False
        if capability is BrokerCapability.EXECUTION:
            return False
        return False

    def _rate_limited(self, operation: str, capability: BrokerCapability | None = None) -> BrokerOperationResult:
        return self._result(
            operation,
            BrokerOperationalState.RATE_LIMITED,
            retryable=True,
            failure_code="RATE_LIMITED",
            operator_message="Broker provider rate limit is active",
            recommended_action="Retry after the provider rate-limit window",
            capability=capability,
        )

    def _provider_unavailable(self, operation: str, capability: BrokerCapability | None = None) -> BrokerOperationResult:
        return self._result(
            operation,
            BrokerOperationalState.PROVIDER_UNAVAILABLE,
            retryable=True,
            failure_code="PROVIDER_UNAVAILABLE",
            operator_message="Broker provider is temporarily unavailable",
            recommended_action="Retry after provider recovery",
            capability=capability,
        )

    def _result(self, operation: str, state: BrokerOperationalState, **kwargs: Any) -> BrokerOperationResult:
        return operation_result(broker=self.broker, operation=operation, state=state, **kwargs)


class CoinbaseOperationalAdapter(CanonicalOperationalAdapter):
    broker = "COINBASE"


class BinanceOperationalAdapter(CanonicalOperationalAdapter):
    broker = "BINANCE"


class OandaOperationalAdapter(CanonicalOperationalAdapter):
    broker = "OANDA"

    def readiness(self) -> dict[str, Any]:
        configured_environment = str(
            self.configuration.get("OANDA_ENVIRONMENT") or self.configuration.get("OANDA_ENV") or ""
        ).lower()
        expected_environment = str(self.evidence.get("expected_environment") or "").lower()
        if configured_environment and expected_environment and configured_environment != expected_environment:
            return self._result(
                "readiness",
                BrokerOperationalState.CONFIGURATION_REQUIRED,
                failure_code="OANDA_ENVIRONMENT_MISMATCH",
                operator_message="OANDA practice/live environment selection does not match",
                technical_message="Configured environment differs from expected environment",
                recommended_action="Align OANDA environment and endpoint configuration",
                data={"configured_environment": configured_environment, "expected_environment": expected_environment},
            ).as_dict()
        return super().readiness()


class QuestradeOperationalAdapter(CanonicalOperationalAdapter):
    broker = "QUESTRADE"

    def option_chain(self, underlying: str | None = None) -> dict[str, Any]:
        prerequisite = self._authenticated_prerequisite("option_chain")
        if prerequisite:
            if prerequisite.state in {
                BrokerOperationalState.CONFIGURATION_REQUIRED,
                BrokerOperationalState.CREDENTIALS_REQUIRED,
            }:
                prerequisite = self._result(
                    "option_chain",
                    BrokerOperationalState.OPTION_CHAIN_PROVIDER_REQUIRED,
                    failure_code="OPTION_CHAIN_PROVIDER_REQUIRED",
                    operator_message="Questrade option-chain connectivity is not configured",
                    technical_message=prerequisite.technical_message,
                    recommended_action="Configure Questrade OAuth and option-chain access",
                    capability=BrokerCapability.OPTION_CHAIN,
                    data={"underlying": underlying, "broker_state": prerequisite.state.value},
                )
            return prerequisite.as_dict()
        if self.evidence.get("rate_limited"):
            return self._rate_limited("option_chain", BrokerCapability.OPTION_CHAIN).as_dict()
        if self.evidence.get("provider_unavailable"):
            return self._provider_unavailable("option_chain", BrokerCapability.OPTION_CHAIN).as_dict()
        if not self._verified_flag("option_chain_ready"):
            return self._result(
                "option_chain",
                BrokerOperationalState.OPTION_CHAIN_UNAVAILABLE,
                retryable=True,
                failure_code="OPTION_CHAIN_UNAVAILABLE",
                operator_message="Questrade option-chain data is unavailable",
                recommended_action="Retry after provider recovery",
                capability=BrokerCapability.OPTION_CHAIN,
                data={"underlying": underlying},
            ).as_dict()
        return self._result(
            "option_chain",
            BrokerOperationalState.OPTION_CHAIN_READY,
            success=True,
            operator_message="Questrade option-chain evidence is ready",
            capability=BrokerCapability.OPTION_CHAIN,
            data={"underlying": underlying},
        ).as_dict()


_ADAPTERS = {
    "COINBASE": CoinbaseOperationalAdapter,
    "BINANCE": BinanceOperationalAdapter,
    "OANDA": OandaOperationalAdapter,
    "QUESTRADE": QuestradeOperationalAdapter,
}


def get_operational_adapter(
    broker: str,
    *,
    configuration: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> CanonicalOperationalAdapter:
    key = str(broker or "").strip().upper()
    adapter = _ADAPTERS.get(key)
    if adapter is None:
        raise KeyError(f"Broker '{broker}' is not in the canonical Tier-1 registry")
    return adapter(configuration=configuration, evidence=evidence)


def tier1_operational_states(
    *,
    configuration_by_broker: Mapping[str, Mapping[str, Any]] | None = None,
    evidence_by_broker: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    configs = configuration_by_broker or {}
    evidence = evidence_by_broker or {}
    rows = {
        broker: get_operational_adapter(
            broker,
            configuration=configs.get(broker) or configs.get(broker.lower()),
            evidence=evidence.get(broker) or evidence.get(broker.lower()),
        ).operational_snapshot()
        for broker in _ADAPTERS
    }
    return {
        "schema_version": "css.broker.operational_states.v1",
        "brokers": rows,
        "execution_allowed": False,
        "execution_state": BrokerOperationalState.EXECUTION_BLOCKED.value,
        "generated_at": utc_now(),
    }


__all__ = [
    "BinanceOperationalAdapter",
    "CanonicalOperationalAdapter",
    "CoinbaseOperationalAdapter",
    "OandaOperationalAdapter",
    "QuestradeOperationalAdapter",
    "get_operational_adapter",
    "tier1_operational_states",
]
