"""Native enterprise-lease adapters for Coinbase, Binance, and OANDA."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any, Mapping, Protocol

from backend.brokers.runtime.runtime_models import BrokerCapabilityContract
from backend.options.options_income_freshness import utc_now
from backend.security.identity.runtime_secret_lease import RuntimeSecretLease
from backend.security.oauth.oauth_handles import OAuthHandle


COINBASE_CAPABILITIES = BrokerCapabilityContract(
    broker="COINBASE",
    operations=("ACCOUNTS", "BALANCES", "PORTFOLIOS", "PRODUCTS", "QUOTES"),
    credential_capabilities=("API_KEY_NAME", "PRIVATE_KEY"),
)
BINANCE_CAPABILITIES = BrokerCapabilityContract(
    broker="BINANCE",
    operations=("ACCOUNT", "BALANCES", "PRODUCTS", "QUOTES"),
    credential_capabilities=("API_KEY", "API_SECRET"),
)
OANDA_CAPABILITIES = BrokerCapabilityContract(
    broker="OANDA",
    operations=("ACCOUNT", "BALANCES", "MARGIN", "POSITIONS", "INSTRUMENTS", "QUOTES"),
    credential_capabilities=("ACCESS_TOKEN",),
)


class EnterpriseReadOnlyProvider(Protocol):
    def fetch(
        self,
        dataset: str,
        *,
        credentials: Mapping[str, memoryview],
        parameters: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class DisabledEnterpriseReadOnlyProvider:
    def fetch(self, *_: Any, **__: Any) -> Mapping[str, Any]:
        raise RuntimeError("ENTERPRISE_BROKER_PROVIDER_DISABLED")


class NativeEnterpriseBrokerAdapter:
    """No credential fields, OAuth state machine, network client, or write methods."""

    def __init__(
        self,
        *,
        broker: str,
        oauth_handle: OAuthHandle,
        leases: Mapping[str, RuntimeSecretLease],
        capabilities: BrokerCapabilityContract,
        provider: EnterpriseReadOnlyProvider | None = None,
    ):
        normalized = str(broker).upper()
        if oauth_handle.provider.upper() != normalized:
            raise ValueError("BROKER_OAUTH_HANDLE_MISMATCH")
        if capabilities.broker.upper() != normalized:
            raise ValueError("BROKER_CAPABILITY_CONTRACT_MISMATCH")
        if set(leases) != set(capabilities.credential_capabilities):
            raise ValueError("BROKER_RUNTIME_LEASE_SET_INCOMPLETE")
        if any(lease.metadata.broker != normalized for lease in leases.values()):
            raise ValueError("BROKER_RUNTIME_LEASE_BROKER_MISMATCH")
        self.broker = normalized
        self.oauth_handle = oauth_handle
        self.leases = dict(leases)
        self.capabilities = capabilities
        self.provider = provider or DisabledEnterpriseReadOnlyProvider()

    def read(self, dataset: str, **parameters: Any) -> dict[str, Any]:
        operation = str(dataset).upper()
        acquired = utc_now()
        if not self.capabilities.permits(operation):
            return self._blocked(operation, "CAPABILITY_NOT_ALLOWED", acquired)
        try:
            with ExitStack() as stack:
                credentials = {
                    capability: stack.enter_context(
                        lease.open(
                            consumer=lease.metadata.consumer,
                            capability=capability,
                        )
                    )
                    for capability, lease in self.leases.items()
                }
                payload = dict(
                    self.provider.fetch(
                        operation,
                        credentials=credentials,
                        parameters=parameters,
                    )
                    or {}
                )
        except PermissionError:
            return self._blocked(operation, "RUNTIME_SECRET_LEASE_UNAVAILABLE", acquired)
        except Exception:
            return {
                "broker": self.broker,
                "dataset": operation,
                "status": "PROVIDER_UNAVAILABLE",
                "failure_reason": "BROKER_PROVIDER_UNAVAILABLE",
                "acquisition_timestamp": acquired,
                "provider_timestamp": None,
                "provenance": self.broker,
                "fabricated": False,
                "execution_allowed": False,
            }
        return {
            "broker": self.broker,
            "dataset": operation,
            "status": "ADVISORY_READY",
            "data": payload,
            "acquisition_timestamp": acquired,
            "provider_timestamp": payload.get("timestamp"),
            "provenance": self.broker,
            "fabricated": False,
            "plaintext_returned": False,
            "advisory_only": True,
            "execution_allowed": False,
        }

    def runtime_health(self) -> dict[str, Any]:
        leases = [lease.health() for lease in self.leases.values()]
        return {
            "broker": self.broker,
            "status": "READY"
            if leases and all(row["status"] == "HEALTHY" for row in leases)
            else "DATA_DEPENDENCY_BLOCKED",
            "oauth_handle_bound": True,
            "secret_lease_health": leases,
            "provider_configured": not isinstance(
                self.provider, DisabledEnterpriseReadOnlyProvider
            ),
            "credential_fields_present": False,
            "oauth_state_owned_by_broker": False,
            "secret_storage_present": False,
            "execution_posture": "DISABLED",
            "execution_authority": "BLOCKED",
            "fail_closed": True,
            "advisory_only": True,
            "execution_allowed": False,
        }

    def _blocked(self, operation: str, reason: str, acquired: str) -> dict[str, Any]:
        return {
            "broker": self.broker,
            "dataset": operation,
            "status": "DATA_DEPENDENCY_BLOCKED",
            "failure_reason": reason,
            "acquisition_timestamp": acquired,
            "provider_timestamp": None,
            "provenance": "ENTERPRISE_BROKER_RUNTIME",
            "fabricated": False,
            "execution_allowed": False,
        }


class CoinbaseEnterpriseReadOnlyRuntime(NativeEnterpriseBrokerAdapter):
    def __init__(self, *, oauth_handle: OAuthHandle, leases: Mapping[str, RuntimeSecretLease], provider=None):
        super().__init__(
            broker="COINBASE",
            oauth_handle=oauth_handle,
            leases=leases,
            capabilities=COINBASE_CAPABILITIES,
            provider=provider,
        )


class BinanceEnterpriseReadOnlyRuntime(NativeEnterpriseBrokerAdapter):
    def __init__(self, *, oauth_handle: OAuthHandle, leases: Mapping[str, RuntimeSecretLease], provider=None):
        super().__init__(
            broker="BINANCE",
            oauth_handle=oauth_handle,
            leases=leases,
            capabilities=BINANCE_CAPABILITIES,
            provider=provider,
        )


class OandaEnterpriseReadOnlyRuntime(NativeEnterpriseBrokerAdapter):
    def __init__(self, *, oauth_handle: OAuthHandle, leases: Mapping[str, RuntimeSecretLease], provider=None):
        super().__init__(
            broker="OANDA",
            oauth_handle=oauth_handle,
            leases=leases,
            capabilities=OANDA_CAPABILITIES,
            provider=provider,
        )


__all__ = [
    "BINANCE_CAPABILITIES",
    "COINBASE_CAPABILITIES",
    "OANDA_CAPABILITIES",
    "BinanceEnterpriseReadOnlyRuntime",
    "CoinbaseEnterpriseReadOnlyRuntime",
    "DisabledEnterpriseReadOnlyProvider",
    "EnterpriseReadOnlyProvider",
    "NativeEnterpriseBrokerAdapter",
    "OandaEnterpriseReadOnlyRuntime",
]
