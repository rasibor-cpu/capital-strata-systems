"""Provider-neutral OAuth metadata registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import threading

from backend.security.oauth.oauth_models import OAuthProvider


@dataclass(frozen=True)
class OAuthProviderDefinition:
    provider: OAuthProvider
    display_name: str
    allowed_scopes: frozenset[str]
    pkce_required: bool
    refresh_supported: bool
    registration_only: bool = True
    authorization_enabled: bool = False

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["provider"] = self.provider.value
        payload["allowed_scopes"] = sorted(self.allowed_scopes)
        return payload


class OAuthProviderRegistry:
    def __init__(self):
        self._providers: dict[OAuthProvider, OAuthProviderDefinition] = {}
        self._lock = threading.RLock()
        baseline_scopes = frozenset(
            {"read", "openid", "profile", "email", "offline_access", "accounts", "market_data"}
        )
        for provider in OAuthProvider:
            self.register(
                OAuthProviderDefinition(
                    provider=provider,
                    display_name=provider.value.title(),
                    allowed_scopes=baseline_scopes,
                    pkce_required=provider in {
                        OAuthProvider.QUESTRADE,
                        OAuthProvider.MICROSOFT,
                        OAuthProvider.GOOGLE,
                        OAuthProvider.CUSTOM,
                    },
                    refresh_supported=provider in {
                        OAuthProvider.QUESTRADE,
                        OAuthProvider.MICROSOFT,
                        OAuthProvider.GOOGLE,
                        OAuthProvider.CUSTOM,
                    },
                )
            )

    def register(self, definition: OAuthProviderDefinition) -> None:
        with self._lock:
            if definition.provider in self._providers:
                raise ValueError("OAUTH_PROVIDER_ALREADY_REGISTERED")
            self._providers[definition.provider] = definition

    def get(self, provider: OAuthProvider | str) -> OAuthProviderDefinition:
        normalized = provider if isinstance(provider, OAuthProvider) else OAuthProvider(str(provider).upper())
        with self._lock:
            definition = self._providers.get(normalized)
        if definition is None:
            raise KeyError("OAUTH_PROVIDER_NOT_REGISTERED")
        return definition

    def inventory(self) -> list[dict]:
        with self._lock:
            return [definition.as_dict() for definition in self._providers.values()]


__all__ = ["OAuthProviderDefinition", "OAuthProviderRegistry"]
