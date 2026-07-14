from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from backend.options.options_broker_abstraction import PAPER_ONLY_FLAGS, SUPPORTED_PAPER_STRATEGIES, OptionsBrokerAbstractionError
from backend.options.options_paper_broker import OptionsPaperBroker


@dataclass(frozen=True)
class OptionsBrokerRegistryEntry:
    provider_name: str
    version: str
    capabilities: dict[str, Any]
    status: str
    priority: int
    supported_assets: list[str]
    supported_strategies: list[str]
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    paper_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), **PAPER_ONLY_FLAGS}


class OptionsBrokerRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, tuple[OptionsPaperBroker, OptionsBrokerRegistryEntry]] = {}

    def register(
        self,
        provider: OptionsPaperBroker,
        *,
        priority: int = 100,
        supported_assets: Iterable[str] = ("OPTIONS",),
        supported_strategies: Iterable[str] = tuple(sorted(SUPPORTED_PAPER_STRATEGIES)),
    ) -> OptionsBrokerRegistryEntry:
        if not isinstance(provider, OptionsPaperBroker):
            raise OptionsBrokerAbstractionError("unsupported provider")
        capabilities = provider.capability_report()
        if capabilities.get("supports_live_mode") is True:
            raise OptionsBrokerAbstractionError("live provider registration is prohibited")
        name = str(provider.provider_name or "").strip().lower()
        if not name:
            raise OptionsBrokerAbstractionError("provider name is required")
        if name in self._providers:
            raise OptionsBrokerAbstractionError(f"duplicate provider: {provider.provider_name}")
        strategies = sorted({str(item or "").strip().upper() for item in supported_strategies if str(item or "").strip()})
        if any(strategy not in SUPPORTED_PAPER_STRATEGIES for strategy in strategies):
            raise OptionsBrokerAbstractionError("unsupported strategy")
        entry = OptionsBrokerRegistryEntry(
            provider_name=provider.provider_name,
            version=provider.version,
            capabilities=capabilities,
            status=provider.status(),
            priority=int(priority),
            supported_assets=sorted({str(item or "").strip().upper() for item in supported_assets if str(item or "").strip()}),
            supported_strategies=strategies,
        )
        self._providers[name] = (provider, entry)
        return entry

    def get(self, provider_name: str) -> OptionsPaperBroker:
        key = str(provider_name or "").strip().lower()
        if key not in self._providers:
            raise OptionsBrokerAbstractionError(f"missing provider: {provider_name}")
        return self._providers[key][0]

    def entry(self, provider_name: str) -> dict[str, Any]:
        key = str(provider_name or "").strip().lower()
        if key not in self._providers:
            raise OptionsBrokerAbstractionError(f"missing provider: {provider_name}")
        return self._providers[key][1].to_dict()

    def providers(self) -> list[dict[str, Any]]:
        entries = [entry.to_dict() for _, entry in self._providers.values()]
        entries.sort(key=lambda row: (row["priority"], row["provider_name"]))
        return entries


def create_default_paper_options_registry(provider: OptionsPaperBroker | None = None) -> OptionsBrokerRegistry:
    registry = OptionsBrokerRegistry()
    registry.register(provider or OptionsPaperBroker(), priority=100)
    return registry


__all__ = ["OptionsBrokerRegistry", "OptionsBrokerRegistryEntry", "create_default_paper_options_registry"]
