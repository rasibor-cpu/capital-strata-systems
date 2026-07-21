"""Phase 178A — Questrade advisory (read-only) package.

No credentials. No live auth. Adapter surfaces CONFIGURATION_REQUIRED
until an operator supplies approved secrets out-of-band.
"""

from __future__ import annotations

from backend.brokers.questrade.advisory_adapter import QuestradeAdvisoryAdapter
from backend.brokers.questrade.capability import questrade_capability_descriptor
from backend.brokers.questrade.configuration import QuestradeSecureConfiguration
from backend.brokers.questrade.readiness import (
    QuestradeOnboardingState,
    questrade_advisory_readiness,
    questrade_read_only_certification,
)
from backend.brokers.questrade.readonly_client import QuestradeReadOnlyClient
from backend.brokers.questrade.token_lifecycle import QuestradeTokenBundle, TokenLifecycle

__all__ = [
    "QuestradeAdvisoryAdapter",
    "QuestradeOnboardingState",
    "QuestradeReadOnlyClient",
    "QuestradeSecureConfiguration",
    "QuestradeTokenBundle",
    "TokenLifecycle",
    "questrade_advisory_readiness",
    "questrade_read_only_certification",
    "questrade_capability_descriptor",
]
