"""Passive offline quote facts — NOT AntiBleed, NOT an execution control.

Historical RC-LIVE Phase 186A composite providers returned
``LiveMicrostructureInputs`` from ``backend.app.risk.live_microstructure_provider``.
That module is a live AntiBleed/ExecutionGate bridge and is **not recovered**.

The composite still needs a place to hold four diagnostic numbers:

- expected_move_bps
- fee_bps
- spread_bps
- slippage_bps

This module localizes only that passive schema. It copies no AntiBleedGuard
logic, makes no risk decision, and grants no execution or live authority.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OfflineCertificationQuoteFacts:
    """Immutable diagnostic numbers from offline fixture providers.

    This is not ``LiveMicrostructureInputs``, not AntiBleedGuard, and not a
    trade-approval object. Callers must not treat a populated instance as
    permission to size, route, or execute an order.
    """

    expected_move_bps: float
    fee_bps: float
    spread_bps: float
    slippage_bps: float

    SCHEMA_ID = "css.rclive_consol_001.offline_certification_quote_facts.v1"
    SCHEMA_VERSION = "CONSOL.1"
    ADVISORY_ONLY = True
    EXECUTION_ALLOWED = False
    IS_ANTIBLEED_CONTROL = False
    GRANTS_LIVE_AUTHORITY = False
    MAY_SUBMIT_ORDERS = False
    MAY_MUTATE_UNIFIED_TRADE_GATE = False


__all__ = ["OfflineCertificationQuoteFacts"]
