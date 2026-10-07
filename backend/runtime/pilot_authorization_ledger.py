"""One-time pilot authorization ledger. Persists consumption; never places orders.

Replay/duplicate/restart resistance:
- consumption is claimed by creating ``<approval_id>.claim`` with O_CREAT|O_EXCL,
  which is atomic across threads, processes and restarts on a local filesystem;
- revocation writes the same claim marker, so a revoked approval can never be
  consumed later;
- a crash between claim and journal append leaves the approval burned (fail closed);
- every event is appended to a SHA-256 hash-chained JSONL journal (fsync'd);
  a broken chain, unreadable journal or claim without journal entry fails closed.

The ledger is preflight infrastructure only. It is not wired to any broker
submission path and does not alter execution_allowed / live_trading_blocked.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.runtime.governed_pilot_profile import (
    GovernedPilotProfile,
    PilotConfigurationError,
)
from backend.runtime.pilot_dual_control import keys_currently_usable, verify_dual_control


GENESIS_HASH = "0" * 64


class PilotReplayError(RuntimeError):
    """Approval already consumed, revoked, or ledger integrity cannot be proven."""


@dataclass(frozen=True)
class PilotConsumptionReceipt:
    approval_id: str
    profile_digest: str
    session_id: str
    instrument: str
    effective_ceiling_cad: str
    consumed_at: str
    entry_hash: str


def _entry_hash(prev_hash: str, body: dict[str, Any]) -> str:
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + encoded).encode("utf-8")).hexdigest()


class PilotAuthorizationLedger:
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.claims = self.root / "claims"
        self.journal = self.root / "journal.jsonl"
        self.claims.mkdir(parents=True, exist_ok=True)

    # -- integrity -----------------------------------------------------
    def verify_chain(self) -> list[dict[str, Any]]:
        """Return journal entries; raise PilotReplayError if tampered or unreadable."""
        entries: list[dict[str, Any]] = []
        if not self.journal.exists():
            return entries
        prev = GENESIS_HASH
        try:
            lines = self.journal.read_text(encoding="utf-8").splitlines()
            for line in lines:
                record = json.loads(line)
                body = {k: v for k, v in record.items() if k not in {"prev_hash", "entry_hash"}}
                if record.get("prev_hash") != prev or record.get("entry_hash") != _entry_hash(prev, body):
                    raise PilotReplayError("ledger hash chain broken")
                prev = record["entry_hash"]
                entries.append(record)
        except PilotReplayError:
            raise
        except Exception as exc:
            raise PilotReplayError(f"ledger unreadable: {type(exc).__name__}") from exc
        return entries

    @contextmanager
    def _locked(self):
        with (self.root / "journal.lock").open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _append(self, body: dict[str, Any]) -> str:
        with self._locked():
            entries = self.verify_chain()
            prev = entries[-1]["entry_hash"] if entries else GENESIS_HASH
            entry_hash = _entry_hash(prev, body)
            line = json.dumps({**body, "prev_hash": prev, "entry_hash": entry_hash}, sort_keys=True)
            with self.journal.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return entry_hash

    def _claim(self, approval_id: str, event: str) -> None:
        path = self.claims / f"{approval_id}.claim"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise PilotReplayError(f"approval {approval_id} already consumed or revoked") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(event)
            handle.flush()
            os.fsync(handle.fileno())

    # -- operations ----------------------------------------------------
    def is_claimed(self, approval_id: str) -> bool:
        return (self.claims / f"{approval_id}.claim").exists()

    def revoke(self, approval_id: str, *, revoked_by: str, reason: str) -> str:
        self.verify_chain()
        self._claim(approval_id, "REVOKED")
        return self._append({
            "event": "REVOKED", "approval_id": approval_id, "revoked_by": revoked_by,
            "reason": reason, "at": datetime.now(timezone.utc).isoformat(),
        })

    def consume(
        self,
        profile: GovernedPilotProfile,
        *,
        approvals: Any,
        key_registry: Any,
        session_id: str,
        running_release_sha: str,
        now: datetime | None = None,
    ) -> PilotConsumptionReceipt:
        """Atomically consume a dual-control approval exactly once, bound to session and release."""
        if not verify_dual_control(profile, approvals, registry=key_registry):
            raise PilotConfigurationError("dual-control approval invalid")
        approvals = tuple(approvals)
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or not profile.issued_at <= now < profile.expires_at:
            raise PilotConfigurationError("approval expired or clock invalid")
        if not keys_currently_usable(approvals, key_registry, now):
            raise PilotConfigurationError("approval key revoked, retired or out of window")
        if session_id != profile.session_id:
            raise PilotConfigurationError("approval bound to a different process session")
        if running_release_sha != profile.release_sha:
            raise PilotConfigurationError("approval bound to a different release")
        self.verify_chain()  # refuse to consume against a tampered ledger
        self._claim(profile.approval_id, "CONSUMED")
        body = {
            "event": "CONSUMED", "approval_id": profile.approval_id,
            "profile_digest": profile.digest(), "session_id": session_id,
            "instrument": profile.instrument,
            "release_sha": profile.release_sha,
            "effective_ceiling_cad": str(profile.effective_ceiling_cad()),
            # Attributable approvals: role, approver, key id/version, time, digest. No key material.
            "approvals": sorted((a.evidence() for a in approvals), key=lambda e: e["role"]),
            "at": now.isoformat(),
        }
        entry_hash = self._append(body)
        return PilotConsumptionReceipt(
            approval_id=profile.approval_id, profile_digest=body["profile_digest"],
            session_id=session_id, instrument=profile.instrument,
            effective_ceiling_cad=body["effective_ceiling_cad"], consumed_at=body["at"],
            entry_hash=entry_hash,
        )

    def receipt_is_recorded(self, receipt: Any) -> bool:
        """True only if the receipt matches a CONSUMED entry in an intact chain."""
        if type(receipt) is not PilotConsumptionReceipt:
            return False
        try:
            entries = self.verify_chain()
        except PilotReplayError:
            return False
        for entry in entries:
            if entry.get("entry_hash") == receipt.entry_hash:
                return (entry.get("event") == "CONSUMED"
                        and entry.get("approval_id") == receipt.approval_id
                        and entry.get("profile_digest") == receipt.profile_digest
                        and entry.get("session_id") == receipt.session_id
                        and entry.get("instrument") == receipt.instrument
                        and entry.get("effective_ceiling_cad") == receipt.effective_ceiling_cad
                        and self.is_claimed(receipt.approval_id))
        return False
