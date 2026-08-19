"""Phase 187A-R1 — deterministic replay protection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from backend.app.market.oanda_readonly_certification.contracts import SCHEMA_VERSION
from backend.app.market.oanda_readonly_certification.fingerprint import ProviderFingerprint


@dataclass
class ReplayProtectionRegistry:
    """Tracks accepted evidence hashes and generations. Offline only."""

    _seen_hashes: set[str] = field(default_factory=set)
    _min_generation: int = 0
    _locked_fingerprint_hash: str = ""
    _min_schema_version: str = SCHEMA_VERSION

    def register_accepted(self, evidence_hash: str, generation: int) -> None:
        if evidence_hash:
            self._seen_hashes.add(evidence_hash)
        if generation > self._min_generation:
            self._min_generation = generation

    def lock_fingerprint(self, fingerprint: ProviderFingerprint) -> None:
        self._locked_fingerprint_hash = fingerprint.fingerprint_hash()
        self._min_schema_version = fingerprint.schema_version


@dataclass(frozen=True)
class ReplayDecision:
    accepted: bool
    reason: str


def _schema_rank(version: str) -> tuple[int, ...]:
    """Parse versions like 187A.2 into comparable ranks; unknown sorts low."""
    parts: list[int] = []
    token = ""
    for ch in version:
        if ch.isdigit():
            token += ch
        elif token:
            parts.append(int(token))
            token = ""
    if token:
        parts.append(int(token))
    return tuple(parts) if parts else (0,)


def evaluate_replay(
    *,
    registry: ReplayProtectionRegistry,
    evidence_hash: str,
    fingerprint: ProviderFingerprint,
    certification_generation: int,
    schema_version: str,
) -> ReplayDecision:
    """Reject reused hashes, mismatched fingerprints, stale gens, schema downgrades."""
    if evidence_hash and evidence_hash in registry._seen_hashes:
        return ReplayDecision(False, "replay_rejected:reused_evidence_hash")
    if registry._locked_fingerprint_hash and fingerprint.fingerprint_hash() != registry._locked_fingerprint_hash:
        return ReplayDecision(False, "replay_rejected:mismatched_provider_fingerprint")
    if certification_generation < registry._min_generation:
        return ReplayDecision(False, "replay_rejected:stale_certification_generation")
    if certification_generation == registry._min_generation and evidence_hash in registry._seen_hashes:
        return ReplayDecision(False, "replay_rejected:reused_evidence_hash")
    if _schema_rank(schema_version) < _schema_rank(registry._min_schema_version):
        return ReplayDecision(False, "replay_rejected:downgraded_schema_version")
    return ReplayDecision(True, "")


def reject_if_any(decisions: Iterable[ReplayDecision]) -> ReplayDecision:
    for d in decisions:
        if not d.accepted:
            return d
    return ReplayDecision(True, "")
