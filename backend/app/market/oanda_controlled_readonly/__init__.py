"""Phase 188 — controlled OANDA read-only certification package.

Uses OandaLiveReadOnlyAdapter only. Never enables execution.
"""

from __future__ import annotations

from backend.app.market.oanda_controlled_readonly.certified_provider import (
    PHASE188_VERSION,
    CertifiedOandaReadOnlyProvider,
    run_controlled_certification,
)
from backend.app.market.oanda_controlled_readonly.firewall import (
    adapter_has_no_write_methods,
    verify_phase188_firewall,
)
from backend.app.market.oanda_controlled_readonly.readonly_transport import (
    OandaReadOnlyHttpTransport,
)

__all__ = [
    "PHASE188_VERSION",
    "CertifiedOandaReadOnlyProvider",
    "run_controlled_certification",
    "adapter_has_no_write_methods",
    "verify_phase188_firewall",
    "OandaReadOnlyHttpTransport",
]
