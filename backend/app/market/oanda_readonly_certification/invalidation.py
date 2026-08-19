"""Phase 187A-R1 — deterministic invalidation rules.

Invalidation always moves certification to REVALIDATION_PENDING.
Never silently jumps to READ_ONLY_CERTIFIED / REVALIDATED.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from backend.app.market.oanda_readonly_certification.fingerprint import ProviderFingerprint

INVALIDATION_TRIGGERS: tuple[str, ...] = (
    "provider_version_change",
    "endpoint_change",
    "schema_version_change",
    "certificate_rotation",
    "credential_rotation",
    "api_version_change",
    "adapter_version_change",
)


@dataclass(frozen=True)
class InvalidationResult:
    invalidated: bool
    target_state: str
    triggers: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if self.invalidated and self.target_state != "REVALIDATION_PENDING":
            raise ValueError("invalidation must target REVALIDATION_PENDING only")


def evaluate_invalidation(
    *,
    prior_fingerprint: ProviderFingerprint | None,
    current_fingerprint: ProviderFingerprint,
    explicit_triggers: Sequence[str] | None = None,
    certificate_rotated: bool = False,
    credential_rotated: bool = False,
) -> InvalidationResult:
    """Deterministic invalidation. Never returns CERTIFIED as target."""
    triggers: list[str] = []
    if prior_fingerprint is not None:
        triggers.extend(prior_fingerprint.differs_from(current_fingerprint))
    if certificate_rotated:
        triggers.append("certificate_rotation")
    if credential_rotated:
        triggers.append("credential_rotation")
    for t in explicit_triggers or ():
        if t in INVALIDATION_TRIGGERS and t not in triggers:
            triggers.append(t)

    # Deduplicate preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for t in triggers:
        if t not in seen:
            seen.add(t)
            ordered.append(t)

    if not ordered:
        return InvalidationResult(
            invalidated=False,
            target_state="",
            triggers=(),
            reason="",
        )
    return InvalidationResult(
        invalidated=True,
        target_state="REVALIDATION_PENDING",
        triggers=tuple(ordered),
        reason="invalidation:" + ",".join(ordered),
    )


def invalidation_catalog() -> Mapping[str, str]:
    return {
        "provider_version_change": "Provider version differs from certified fingerprint",
        "endpoint_change": "Endpoint differs from certified fingerprint",
        "schema_version_change": "Schema version differs from certified fingerprint",
        "certificate_rotation": "TLS/server certificate rotated",
        "credential_rotation": "Credential material rotated (presence/fingerprint only; no secrets)",
        "api_version_change": "API version differs from certified fingerprint",
        "adapter_version_change": "Adapter version differs from certified fingerprint",
    }
