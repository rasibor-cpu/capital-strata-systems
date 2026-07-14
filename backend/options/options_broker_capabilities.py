from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.options.options_broker_abstraction import PAPER_ONLY_FLAGS, OptionsBrokerAbstractionError


@dataclass(frozen=True)
class OptionsBrokerCapabilities:
    provider_name: str
    supports_options: bool = True
    supports_covered_calls: bool = True
    supports_csp: bool = True
    supports_greeks: bool = True
    supports_iv: bool = True
    supports_paper_mode: bool = True
    supports_live_mode: bool = False
    supports_market_data: bool = True
    supports_order_preview: bool = True
    supports_assignment_simulation: bool = True
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    paper_only: bool = True

    def __post_init__(self) -> None:
        if self.supports_live_mode:
            raise OptionsBrokerAbstractionError("live support must remain disabled")
        if self.execution_allowed or not self.live_trading_blocked or not self.advisory_only:
            raise OptionsBrokerAbstractionError("execution-enabled posture is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), **PAPER_ONLY_FLAGS}


def default_paper_options_capabilities(provider_name: str = "paper_options") -> OptionsBrokerCapabilities:
    return OptionsBrokerCapabilities(provider_name=str(provider_name or "paper_options"))


__all__ = ["OptionsBrokerCapabilities", "default_paper_options_capabilities"]
