"""Phase 178A — Questrade advisory (read-only) package.

No credentials. No live auth. Adapter surfaces CONFIGURATION_REQUIRED
until an operator supplies approved secrets out-of-band.
"""

from __future__ import annotations

from backend.brokers.questrade.advisory_adapter import QuestradeAdvisoryAdapter
from backend.brokers.questrade.capability import questrade_capability_descriptor
from backend.brokers.questrade.readiness import questrade_advisory_readiness

__all__ = [
    "QuestradeAdvisoryAdapter",
    "questrade_advisory_readiness",
    "questrade_capability_descriptor",
]
