"""Compatibility adapter between legacy broker APIs and enterprise handles."""

from __future__ import annotations

from typing import Any, Mapping

from backend.security.identity.authority_redirector import EnterpriseAuthorityRedirector
from backend.security.identity.identity_policy import SecretAccessRequest

_ACTIVE_ADAPTER: "BrokerSecretCompatibilityAdapter | None" = None


class BrokerSecretCompatibilityAdapter:
    def __init__(self, redirector: EnterpriseAuthorityRedirector):
        self.redirector = redirector

    def register_legacy_mapping(
        self,
        broker: str,
        credentials: Mapping[str, Any],
        *,
        component: str,
        source_path: str,
        owner: str,
        environment: str,
        operator: str,
    ) -> dict[str, Any]:
        return self.redirector.register_legacy_credentials(
            broker,
            credentials,
            component=component,
            source_path=source_path,
            owner=owner,
            environment=environment,
            operator=operator,
        )

    def request_handles(
        self,
        broker: str,
        credential_names: tuple[str, ...],
        *,
        request: SecretAccessRequest,
    ) -> dict[str, Any]:
        return self.redirector.resolve(
            broker,
            credential_names,
            request=request,
        )

    def preserve_legacy_mapping(
        self,
        broker: str,
        credentials: Mapping[str, Any],
        *,
        component: str,
        source_path: str,
        owner: str,
        environment: str,
        operator: str,
    ) -> dict[str, Any]:
        """Migration-only bridge.

        The returned mapping preserves the existing broker API. Its use is
        explicitly classified as a direct-access violation until the broker
        consumes SecretHandles natively.
        """
        authority = self.register_legacy_mapping(
            broker,
            credentials,
            component=component,
            source_path=source_path,
            owner=owner,
            environment=environment,
            operator=operator,
        )
        self.redirector.record_direct_access(
            broker=broker,
            component=component,
            source_path=source_path,
        )
        return {
            **dict(credentials),
            "enterprise_secret_authority": authority,
            "legacy_compatibility": True,
            "execution_allowed": False,
        }


def install_broker_secret_adapter(adapter: BrokerSecretCompatibilityAdapter) -> None:
    global _ACTIVE_ADAPTER
    _ACTIVE_ADAPTER = adapter


def clear_broker_secret_adapter() -> None:
    global _ACTIVE_ADAPTER
    _ACTIVE_ADAPTER = None


def redirect_legacy_mapping_if_configured(
    broker: str,
    credentials: Mapping[str, Any],
    *,
    component: str,
    source_path: str,
    environment: str,
) -> dict[str, Any]:
    if _ACTIVE_ADAPTER is None:
        return dict(credentials)
    return _ACTIVE_ADAPTER.preserve_legacy_mapping(
        broker,
        credentials,
        component=component,
        source_path=source_path,
        owner="broker-platform",
        environment=environment,
        operator="credential-loader",
    )


def broker_secret_presence_if_configured(broker: str) -> bool | None:
    if _ACTIVE_ADAPTER is None:
        return None
    return _ACTIVE_ADAPTER.redirector.has_broker_bindings(broker)


__all__ = [
    "BrokerSecretCompatibilityAdapter",
    "clear_broker_secret_adapter",
    "broker_secret_presence_if_configured",
    "install_broker_secret_adapter",
    "redirect_legacy_mapping_if_configured",
]
