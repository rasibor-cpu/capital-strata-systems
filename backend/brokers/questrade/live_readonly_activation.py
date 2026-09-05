"""Explicit Questrade LIVE READ-ONLY activation. Default remains disabled."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.brokers.questrade.dpapi_refresh_token_store import (
    DpapiProtectBackend,
    WindowsDpapiRefreshTokenStore,
)
from backend.brokers.questrade.errors import QuestradeAdvisoryError, TokenStoreError
from backend.brokers.questrade.get_only_transport import QuestradeGetOnlyHttpTransport
from backend.brokers.questrade.live_readonly_provider import QuestradeLiveReadOnlyDataProvider
from backend.brokers.questrade.oauth_refresh import (
    QuestradeBoundedOAuthRefresh,
    QuestradeOAuthFormTransport,
    public_oauth_result,
)
from backend.brokers.questrade.readonly_client import QuestradeReadOnlyClient, QuestradeTransport
from backend.brokers.questrade.token_lifecycle import InMemoryRefreshTokenStore, TokenLifecycle
from backend.brokers.runtime.questrade_readonly_runtime import DisabledQuestradeEnterpriseDataProvider


SAFETY = {
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
    "advisory_only": True,
}


@dataclass
class QuestradeLiveReadOnlyActivation:
    payload: dict[str, Any]
    provider: Any = field(default=None, repr=False)
    client: QuestradeReadOnlyClient | None = field(default=None, repr=False)
    lifecycle: TokenLifecycle | None = field(default=None, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.payload)

    def __repr__(self) -> str:
        return (
            "QuestradeLiveReadOnlyActivation("
            f"activated={self.payload.get('activated')}, "
            f"status={self.payload.get('status')!r}, "
            "secret_material_redacted=True, execution_allowed=False)"
        )


def compose_questrade_live_read_only_activation(
    *,
    refresh_token_store_path: str | Path | None = None,
    account_reference: str | None = None,
    activation_authorized: bool = False,
    protect_backend: DpapiProtectBackend | None = None,
    oauth_transport: QuestradeOAuthFormTransport | None = None,
    http_transport: QuestradeTransport | None = None,
    now: datetime | None = None,
) -> QuestradeLiveReadOnlyActivation:
    """Construct the LIVE READ-ONLY stack only when explicitly authorized.

    Default is disabled: no OAuth, no network, provider unavailable.
    """
    clock = now or datetime.now(timezone.utc)
    if not activation_authorized:
        return QuestradeLiveReadOnlyActivation(
            payload=_disabled_payload(reason="ACTIVATION_DISABLED"),
            provider=DisabledQuestradeEnterpriseDataProvider(),
        )
    if refresh_token_store_path in (None, ""):
        return QuestradeLiveReadOnlyActivation(payload=_disabled_payload(reason="QUESTRADE_TOKEN_PATH_REQUIRED"))
    try:
        store = WindowsDpapiRefreshTokenStore(
            refresh_token_store_path,
            protect_backend=protect_backend,
            now=clock,
        )
    except (TokenStoreError, QuestradeAdvisoryError) as exc:
        return QuestradeLiveReadOnlyActivation(payload=_disabled_payload(reason=exc.code))
    except Exception:
        return QuestradeLiveReadOnlyActivation(payload=_disabled_payload(reason="QUESTRADE_TOKEN_STORE_UNAVAILABLE"))

    refresher = QuestradeBoundedOAuthRefresh(store, transport=oauth_transport, now=clock)
    oauth_result = public_oauth_result(refresher.refresh())
    bundle = refresher.memory_bundle
    public = oauth_result
    if not oauth_result.get("success") or bundle is None:
        payload = {
            **_base_payload(),
            "activated": False,
            "status": "UNAVAILABLE",
            "reason": public.get("reason") or "QUESTRADE_OAUTH_REFRESH_FAILED",
            "oauth_refresh_attempted": public.get("oauth_refresh_attempted"),
            "oauth_refresh_succeeded": False,
            "refresh_token_persisted": False,
            "network_call_performed": public.get("network_call_performed"),
            "token_store": store.metadata(),
            "provider_available": False,
        }
        return QuestradeLiveReadOnlyActivation(payload=payload, provider=DisabledQuestradeEnterpriseDataProvider())

    memory_store = InMemoryRefreshTokenStore()
    memory_store.replace(bundle)
    lifecycle = TokenLifecycle(memory_store, now=clock)
    transport = http_transport or QuestradeGetOnlyHttpTransport()
    client = QuestradeReadOnlyClient(lifecycle, transport=transport)
    try:
        provider = QuestradeLiveReadOnlyDataProvider(client, account_reference=account_reference)
    except QuestradeAdvisoryError as exc:
        payload = {
            **_base_payload(),
            "activated": False,
            "status": "UNAVAILABLE",
            "reason": exc.code,
            "oauth_refresh_attempted": True,
            "oauth_refresh_succeeded": True,
            "refresh_token_persisted": True,
            "network_call_performed": True,
            "token_store": store.metadata(),
            "provider_available": False,
        }
        return QuestradeLiveReadOnlyActivation(payload=payload, provider=DisabledQuestradeEnterpriseDataProvider())

    payload = {
        **_base_payload(),
        "activated": True,
        "status": "READY",
        "reason": "ok",
        "oauth_refresh_attempted": True,
        "oauth_refresh_succeeded": True,
        "refresh_token_persisted": True,
        "access_token_memory_only": True,
        "network_call_performed": True,
        "account_reference_bound": bool(account_reference),
        "token_store": store.metadata(),
        "provider_available": True,
        "metadata": bundle.metadata(now=clock),
    }
    return QuestradeLiveReadOnlyActivation(
        payload=payload,
        provider=provider,
        client=client,
        lifecycle=lifecycle,
    )


def _base_payload() -> dict[str, Any]:
    return {
        "schema": "css.questrade.live_read_only_activation.v1",
        "access_token_persisted": False,
        "token_values_returned": False,
        "secrets_returned": False,
        **SAFETY,
    }


def _disabled_payload(*, reason: str) -> dict[str, Any]:
    return {
        **_base_payload(),
        "activated": False,
        "status": "DISABLED" if reason == "ACTIVATION_DISABLED" else "UNAVAILABLE",
        "reason": reason,
        "oauth_refresh_attempted": False,
        "oauth_refresh_succeeded": False,
        "refresh_token_persisted": False,
        "access_token_memory_only": False,
        "network_call_performed": False,
        "account_reference_bound": False,
        "provider_available": False,
    }


__all__ = [
    "QuestradeLiveReadOnlyActivation",
    "compose_questrade_live_read_only_activation",
]
