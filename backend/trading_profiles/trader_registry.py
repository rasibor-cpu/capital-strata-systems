"""Approved CSS trader registry (event-sourced, hash-chained, dual-control).

The registry starts EMPTY. No trader is seeded, invented or approved automatically.
A trader becomes copyable only when:
  1. a SUPER_USER proposes them with an Ed25519 public key (for signal authentication)
     and an asset-class scope, and
  2. a DIFFERENT SUPER_USER approves the proposal.
Suspension and revocation (risk-reducing) need one SUPER_USER and take effect at once.
Revoked traders cannot be reinstated; a new proposal and approval is required.

State is rebuilt from the verified hash-chained event log on every read, so editing
the log (or deleting entries) is detected and fails closed.
"""
from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.trading_profiles.hash_chain import HashChainLog

ADMIN_ROLE = "SUPER_USER"
ASSET_CLASSES = frozenset({"FX", "CRYPTO", "FUTURES", "OPTIONS"})
_TRADER_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,47}$")


class TraderRegistryError(RuntimeError):
    """Fail-closed registry error; message is a stable reason code."""


@dataclass(frozen=True)
class ApprovedTrader:
    trader_id: str
    display_name: str
    status: str  # PENDING | ACTIVE | SUSPENDED | REVOKED
    public_key_b64: str
    asset_classes: tuple[str, ...]
    proposed_by: str
    approved_by: str | None
    updated_at_utc: str

    def public_key(self) -> Ed25519PublicKey:
        return Ed25519PublicKey.from_public_bytes(base64.b64decode(self.public_key_b64))

    def summary(self) -> dict[str, Any]:
        return {"trader_id": self.trader_id, "display_name": self.display_name, "status": self.status,
                "asset_classes": list(self.asset_classes), "public_key_fingerprint":
                hashlib.sha256(base64.b64decode(self.public_key_b64)).hexdigest()[:16]}


def _actor(actor_ctx: Mapping[str, Any] | None) -> str:
    actor = actor_ctx or {}
    if str(actor.get("role") or "").upper() != ADMIN_ROLE or not actor.get("user_id"):
        raise TraderRegistryError("super_user_required")
    return str(actor["user_id"])


class TraderRegistry:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.log = HashChainLog(self.root, "trader_registry", TraderRegistryError)
        self.path = self.log.path
        self.lock_path = self.root / "trader_registry.lock"

    # -- event log -----------------------------------------------------------
    def _events(self) -> list[dict[str, Any]]:
        return self.log.events()

    def _append(self, body: Mapping[str, Any]) -> None:
        self.log.append(body)

    def _state(self) -> dict[str, ApprovedTrader]:
        traders: dict[str, ApprovedTrader] = {}
        for e in self._events():
            tid, kind, at = e["trader_id"], e["event"], e["at_utc"]
            current = traders.get(tid)
            if kind == "PROPOSED":
                traders[tid] = ApprovedTrader(tid, e["display_name"], "PENDING", e["public_key_b64"],
                                              tuple(e["asset_classes"]), e["actor"], None, at)
            elif current is None:
                raise TraderRegistryError("trader_registry_event_without_proposal")
            elif kind == "APPROVED":
                traders[tid] = ApprovedTrader(tid, current.display_name, "ACTIVE", current.public_key_b64,
                                              current.asset_classes, current.proposed_by, e["actor"], at)
            elif kind in {"SUSPENDED", "REVOKED", "REINSTATED"}:
                status = {"SUSPENDED": "SUSPENDED", "REVOKED": "REVOKED", "REINSTATED": "ACTIVE"}[kind]
                traders[tid] = ApprovedTrader(tid, current.display_name, status, current.public_key_b64,
                                              current.asset_classes, current.proposed_by, current.approved_by, at)
            else:
                raise TraderRegistryError("trader_registry_unknown_event")
        return traders

    # -- queries ---------------------------------------------------------------
    def get(self, trader_id: str) -> ApprovedTrader | None:
        return self._state().get(trader_id)

    def list(self) -> list[ApprovedTrader]:
        return sorted(self._state().values(), key=lambda t: t.trader_id)

    def require_active(self, trader_id: str, asset_classes: tuple[str, ...] | list[str] = ()) -> ApprovedTrader:
        trader = self.get(trader_id)
        if trader is None:
            raise TraderRegistryError("trader_not_approved")
        if trader.status != "ACTIVE":
            raise TraderRegistryError(f"trader_not_active:{trader.status}")
        outside = {a.upper() for a in asset_classes} - set(trader.asset_classes)
        if outside:
            raise TraderRegistryError(f"trader_scope_excludes:{sorted(outside)}")
        return trader

    # -- governed changes ----------------------------------------------------------
    def propose(self, *, trader_id: str, display_name: str, public_key_b64: str, asset_classes: list[str],
                actor_ctx: Mapping[str, Any], now: datetime | None = None) -> ApprovedTrader:
        actor = _actor(actor_ctx)
        if not _TRADER_ID.match(trader_id or ""):
            raise TraderRegistryError("trader_id_invalid")
        scope = sorted({str(a).upper() for a in asset_classes})
        if not scope or not set(scope) <= ASSET_CLASSES:
            raise TraderRegistryError("asset_scope_invalid")
        try:
            raw = base64.b64decode(public_key_b64, validate=True)
            Ed25519PublicKey.from_public_bytes(raw)
        except Exception as exc:
            raise TraderRegistryError("public_key_invalid") from exc
        name = str(display_name or "").strip()[:80]
        if not name:
            raise TraderRegistryError("display_name_required")
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            existing = self._state().get(trader_id)
            if existing is not None and existing.status != "REVOKED":
                raise TraderRegistryError(f"trader_exists:{existing.status}")
            self._append({"event": "PROPOSED", "trader_id": trader_id, "display_name": name,
                          "public_key_b64": public_key_b64, "asset_classes": scope, "actor": actor,
                          "at_utc": (now or datetime.now(timezone.utc)).isoformat()})
        return self.get(trader_id)

    def approve(self, trader_id: str, *, actor_ctx: Mapping[str, Any], now: datetime | None = None) -> ApprovedTrader:
        actor = _actor(actor_ctx)
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            trader = self._state().get(trader_id)
            if trader is None or trader.status != "PENDING":
                raise TraderRegistryError("trader_not_pending")
            if trader.proposed_by == actor:
                raise TraderRegistryError("dual_control_requires_different_approver")
            self._append({"event": "APPROVED", "trader_id": trader_id, "actor": actor,
                          "at_utc": (now or datetime.now(timezone.utc)).isoformat()})
        return self.get(trader_id)

    def _transition(self, trader_id: str, event: str, allowed_from: set[str], actor_ctx, reason: str, now) -> ApprovedTrader:
        actor = _actor(actor_ctx)
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            trader = self._state().get(trader_id)
            if trader is None or trader.status not in allowed_from:
                raise TraderRegistryError(f"trader_transition_not_allowed:{event}")
            self._append({"event": event, "trader_id": trader_id, "actor": actor, "reason": str(reason)[:200],
                          "at_utc": (now or datetime.now(timezone.utc)).isoformat()})
        return self.get(trader_id)

    def suspend(self, trader_id: str, *, actor_ctx, reason: str, now: datetime | None = None) -> ApprovedTrader:
        return self._transition(trader_id, "SUSPENDED", {"ACTIVE", "PENDING"}, actor_ctx, reason, now)

    def revoke(self, trader_id: str, *, actor_ctx, reason: str, now: datetime | None = None) -> ApprovedTrader:
        return self._transition(trader_id, "REVOKED", {"ACTIVE", "PENDING", "SUSPENDED"}, actor_ctx, reason, now)

    def reinstate(self, trader_id: str, *, actor_ctx, reason: str, now: datetime | None = None) -> ApprovedTrader:
        """Risk-increasing: requires a SUPER_USER other than the one who suspended."""
        events = [e for e in self._events() if e["trader_id"] == trader_id]
        if events and events[-1]["event"] == "SUSPENDED" and events[-1]["actor"] == _actor(actor_ctx):
            raise TraderRegistryError("dual_control_requires_different_approver")
        return self._transition(trader_id, "REINSTATED", {"SUSPENDED"}, actor_ctx, reason, now)
