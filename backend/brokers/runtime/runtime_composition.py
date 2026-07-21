"""Inactive composition root for Enterprise Identity/Secret/OAuth/Broker runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.brokers.runtime.enterprise_broker_runtime import EnterpriseBrokerRuntime
from backend.brokers.runtime.native_broker_adapters import (
    BINANCE_CAPABILITIES,
    COINBASE_CAPABILITIES,
    OANDA_CAPABILITIES,
    BinanceEnterpriseReadOnlyRuntime,
    CoinbaseEnterpriseReadOnlyRuntime,
    OandaEnterpriseReadOnlyRuntime,
)
from backend.brokers.runtime.questrade_readonly_runtime import (
    QUESTRADE_READ_ONLY_CAPABILITIES,
    QuestradeEnterpriseReadOnlyRuntime,
)
from backend.security.identity.authority_redirector import EnterpriseAuthorityRedirector
from backend.security.identity.enterprise_identity_service import EnterpriseIdentityService
from backend.security.identity.enterprise_secret_service import EnterpriseSecretService
from backend.security.oauth.oauth_manager import EnterpriseOAuthManager


@dataclass(frozen=True)
class EnterpriseBrokerRuntimeComposition:
    identities: EnterpriseIdentityService
    secrets: EnterpriseSecretService
    oauth: EnterpriseOAuthManager
    brokers: EnterpriseBrokerRuntime
    compatibility_authority: EnterpriseAuthorityRedirector | None = None

    def status(self) -> dict[str, Any]:
        compatibility = (
            self.compatibility_authority.ownership_inventory()
            if self.compatibility_authority is not None
            else []
        )
        return {
            "identity_runtime_composed": True,
            "secret_runtime_composed": True,
            "oauth_runtime_composed": True,
            "broker_runtime_composed": True,
            "broker_runtime_health": self.brokers.health(),
            "compatibility_bindings": compatibility,
            "compatibility_certified_enterprise_managed": False,
            "authentication_activated": False,
            "oauth_authorization_activated": False,
            "market_data_activated": False,
            "live_apis_activated": False,
            "execution_posture": "DISABLED",
            "execution_authority": "BLOCKED",
            "fail_closed": True,
            "advisory_only": True,
            "execution_allowed": False,
        }

    def native_adapter(
        self,
        broker: str,
        *,
        operator: str,
        provider: Any | None = None,
        duration_seconds: int = 60,
    ):
        """Build an inactive adapter from an existing enterprise binding."""
        binding = self.brokers.binding(broker)
        if binding.oauth_handle is None:
            raise ValueError("OAUTH_HANDLE_REQUIRED")
        capabilities = {
            "COINBASE": COINBASE_CAPABILITIES,
            "BINANCE": BINANCE_CAPABILITIES,
            "OANDA": OANDA_CAPABILITIES,
            "QUESTRADE": QUESTRADE_READ_ONLY_CAPABILITIES,
        }.get(binding.broker)
        if capabilities is None:
            raise ValueError("NATIVE_RUNTIME_ADAPTER_NOT_SUPPORTED")
        handles_by_type = {
            str(self.secrets.metadata(handle.secret_uuid)["secret_type"]): handle
            for handle in binding.secret_handles
        }
        leases = {
            capability: self.brokers.lease(
                binding.broker,
                secret_uuid=handles_by_type[capability].secret_uuid,
                capability=capability,
                operator=operator,
                duration_seconds=duration_seconds,
            )
            for capability in capabilities.credential_capabilities
        }
        adapter_type = {
            "COINBASE": CoinbaseEnterpriseReadOnlyRuntime,
            "BINANCE": BinanceEnterpriseReadOnlyRuntime,
            "OANDA": OandaEnterpriseReadOnlyRuntime,
        }.get(binding.broker)
        if binding.broker == "QUESTRADE":
            return QuestradeEnterpriseReadOnlyRuntime(
                access_token_lease=leases["OAUTH_ACCESS_TOKEN"],
                provider=provider,
            )
        if adapter_type is None:
            raise ValueError("NATIVE_RUNTIME_ADAPTER_NOT_SUPPORTED")
        return adapter_type(
            oauth_handle=binding.oauth_handle,
            leases=leases,
            provider=provider,
        )


def compose_enterprise_broker_runtime(
    *,
    identities: EnterpriseIdentityService,
    secrets: EnterpriseSecretService,
    oauth: EnterpriseOAuthManager,
    compatibility_authority: EnterpriseAuthorityRedirector | None = None,
) -> EnterpriseBrokerRuntimeComposition:
    """Compose services without registering providers or activating any runtime."""
    return EnterpriseBrokerRuntimeComposition(
        identities=identities,
        secrets=secrets,
        oauth=oauth,
        brokers=EnterpriseBrokerRuntime(secrets=secrets),
        compatibility_authority=compatibility_authority,
    )


__all__ = [
    "EnterpriseBrokerRuntimeComposition",
    "compose_enterprise_broker_runtime",
]
