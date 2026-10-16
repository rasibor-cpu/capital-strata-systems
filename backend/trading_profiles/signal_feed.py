"""Governed signal feed for Copy a CSS Trader (paper only).

A trader signal is accepted only if ALL of the following hold, checked in this order:
  1. well-formed payload (known fields only, finite numbers, valid side/asset class)
  2. the trader is in the dual-control TraderRegistry, and the Ed25519 signature by the
     trader's registered key over the canonical JSON payload verifies
  3. the trader is ACTIVE and the asset class is in the trader's approved scope
  4. fresh: issued no more than MAX_SIGNAL_AGE ago and not more than MAX_FUTURE_SKEW ahead
  5. not a replay: the (trader_id, signal_id) pair has never been accepted before

Every authenticated submission (signature verified: accepted, or rejected at 3-5) is
appended to a hash-chained feed ledger. Unauthenticated submissions (1-2) are rejected
without being written, so anonymous traffic cannot grow the ledger.
An accepted signal is only an input: each follower's copy is still decided by the
CopyTradeEngine (consent, mandate, personality, R14F, R7, AntiBleed, ...).
Nothing here touches a broker.
"""
from __future__ import annotations

import base64
import hashlib
import math
import re
from dataclasses import MISSING, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, MANUAL_ORDER_PREFIX, SourceSignal
from backend.trading_profiles.hash_chain import HashChainLog, canonical
from backend.trading_profiles.trader_registry import TraderRegistry, TraderRegistryError

MAX_SIGNAL_AGE = timedelta(seconds=120)
MAX_FUTURE_SKEW = timedelta(seconds=5)
_SIGNAL_FIELDS = {f.name: f for f in fields(SourceSignal)}
_REQUIRED = {name for name, f in _SIGNAL_FIELDS.items() if f.default is MISSING}
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class SignalFeedError(RuntimeError):
    """Signal rejected; message is a stable reason code."""


def canonical_payload(payload: Mapping[str, Any]) -> bytes:
    return canonical(payload)


def sign_signal(private_key: Ed25519PrivateKey, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Client-side helper for a registered trader: returns the envelope the feed accepts."""
    return {"payload": dict(payload),
            "signature_b64": base64.b64encode(private_key.sign(canonical_payload(payload))).decode("ascii")}


def _parse(payload: Any) -> tuple[SourceSignal, datetime]:
    if not isinstance(payload, Mapping):
        raise SignalFeedError("payload_invalid")
    unknown = set(payload) - set(_SIGNAL_FIELDS) - {"issued_at_utc"}
    if unknown:
        raise SignalFeedError("payload_unknown_fields")
    missing = (_REQUIRED | {"issued_at_utc"}) - set(payload)
    if missing:
        raise SignalFeedError("payload_missing_fields")
    values: dict[str, Any] = {}
    for name, value in payload.items():
        if name == "issued_at_utc":
            continue
        if _SIGNAL_FIELDS[name].type in ("float", float):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise SignalFeedError("payload_number_invalid")
            values[name] = float(value)
        else:
            if not isinstance(value, str) or not value.strip() or len(value) > 64:
                raise SignalFeedError("payload_text_invalid")
            values[name] = value
    signal = SourceSignal(**values)
    if not _ID.match(signal.signal_id) or not _ID.match(signal.trader_id):
        raise SignalFeedError("payload_id_invalid")
    if signal.side.upper() not in {"BUY", "SELL"} or signal.asset_class.upper() not in {"FX", "CRYPTO", "FUTURES", "OPTIONS"}:
        raise SignalFeedError("payload_side_or_asset_invalid")
    if signal.trader_id == AUTONOMOUS_SOURCE_ID or signal.trader_id.startswith(MANUAL_ORDER_PREFIX):
        raise SignalFeedError("reserved_source_id")
    try:
        issued = datetime.fromisoformat(str(payload["issued_at_utc"]))
    except ValueError as exc:
        raise SignalFeedError("issued_at_invalid") from exc
    if issued.tzinfo is None:
        raise SignalFeedError("issued_at_invalid")
    return signal, issued


class SignalFeed:
    def __init__(self, root: Path | str, registry: TraderRegistry) -> None:
        self.root = Path(root)
        self.registry = registry
        self.log = HashChainLog(self.root, "signal_feed", SignalFeedError)
        self.path = self.log.path
        self.lock_path = self.root / "signal_feed.lock"

    def _events(self) -> list[dict[str, Any]]:
        return self.log.events()

    def _append(self, events: list[dict[str, Any]], body: Mapping[str, Any]) -> None:
        self.log.append(body)

    def ingest(self, envelope: Mapping[str, Any], *, now: datetime | None = None) -> SourceSignal:
        now = now or datetime.now(timezone.utc)
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            events = self._events()  # a broken ledger fails closed before anything is accepted
            payload = envelope.get("payload") if isinstance(envelope, Mapping) else None
            trader_id = str(payload.get("trader_id", ""))[:64] if isinstance(payload, Mapping) else ""
            signal_id = str(payload.get("signal_id", ""))[:64] if isinstance(payload, Mapping) else ""
            signal = self._authenticate(envelope, payload)  # unauthenticated -> raise, nothing written
            try:
                self._authorize(signal, payload, events, now)
            except SignalFeedError as exc:
                self._append(events, {"event": "REJECTED", "trader_id": trader_id, "signal_id": signal_id,
                                      "reason": str(exc), "at_utc": now.isoformat()})
                raise
            self._append(events, {"event": "ACCEPTED", "trader_id": signal.trader_id, "signal_id": signal.signal_id,
                                  "payload_sha256": hashlib.sha256(canonical_payload(payload)).hexdigest(),
                                  "at_utc": now.isoformat()})
            return signal

    def _authenticate(self, envelope, payload) -> SourceSignal:
        signal, _ = _parse(payload)
        try:
            trader = self.registry.get(signal.trader_id)
        except TraderRegistryError as exc:
            raise SignalFeedError(f"trader_not_authorized:{exc}") from exc
        if trader is None:
            raise SignalFeedError("trader_not_authorized:trader_not_approved")
        try:
            signature = base64.b64decode(str(envelope.get("signature_b64") or ""), validate=True)
            trader.public_key().verify(signature, canonical_payload(payload))
        except (InvalidSignature, ValueError) as exc:
            raise SignalFeedError("signature_invalid") from exc
        return signal

    def _authorize(self, signal: SourceSignal, payload, events, now: datetime) -> None:
        _, issued = _parse(payload)
        try:
            self.registry.require_active(signal.trader_id, (signal.asset_class.upper(),))
        except TraderRegistryError as exc:
            raise SignalFeedError(f"trader_not_authorized:{exc}") from exc
        if issued > now + MAX_FUTURE_SKEW:
            raise SignalFeedError("signal_from_future")
        if now - issued > MAX_SIGNAL_AGE:
            raise SignalFeedError("signal_stale")
        if any(e["event"] == "ACCEPTED" and e["trader_id"] == signal.trader_id and e["signal_id"] == signal.signal_id
               for e in events):
            raise SignalFeedError("signal_replay")

    def accepted(self) -> list[dict[str, Any]]:
        return [e for e in self._events() if e["event"] == "ACCEPTED"]
