"""Copy-trader mandates: signed, scoped, expiring, revocable, periodically reauthorized.

A mandate records that a follower authorized copying one CSS trader with one risk
personality, within an asset-class scope and an allocation ceiling, until an expiry.
It must be renewed either at each sign-on or at a fixed interval. Any expired,
revoked, unsigned, tampered, mismatched or out-of-scope mandate blocks new copied
trades (fail closed). Managing existing positions to a safe exit stays allowed.

Signatures are HMAC-SHA256 over the canonical mandate body with a key from an
injected provider. There is no default key: without one, mandates cannot be issued
or verified, and copying is blocked.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from backend.certification.ov002_persistence import (
    PersistenceError,
    atomic_append_jsonl,
    atomic_write_json,
    read_json_object,
)
from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.trading_profiles.risk_personalities import RiskPersonality

MANDATE_SCHEMA = "css.trading_profiles.mandates.v1"
MIN_KEY_BYTES = 32
MAX_MANDATE_DAYS = 90

KeyProvider = Callable[[], bytes]


class MandateError(RuntimeError):
    """Fail-closed mandate error."""


class ReauthorizationPolicy(str, Enum):
    EACH_SIGN_ON = "EACH_SIGN_ON"
    INTERVAL = "INTERVAL"


@dataclass(frozen=True)
class CopyMandate:
    mandate_id: str
    follower_user_id: str
    trader_id: str
    personality: str
    asset_classes: tuple[str, ...]
    max_allocation: float
    currency: str
    issued_at_utc: str
    expires_at_utc: str
    reauthorization_policy: str
    reauthorization_interval_hours: float
    last_authorized_at_utc: str
    authorized_session_id: str
    revoked_at_utc: str | None = None
    revocation_reason: str | None = None
    signature: str = ""

    def body(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("signature")
        data["asset_classes"] = list(self.asset_classes)
        return data


@dataclass(frozen=True)
class MandateDecision:
    valid_for_new_trades: bool
    may_manage_existing_positions: bool
    reason: str
    mandate_id: str | None = None


def _canonical(body: dict[str, Any]) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _key(provider: KeyProvider | None) -> bytes:
    if provider is None:
        raise MandateError("mandate_signing_key_unavailable")
    key = provider()
    if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES:
        raise MandateError("mandate_signing_key_invalid")
    return bytes(key)


def sign_mandate(mandate: CopyMandate, key_provider: KeyProvider | None) -> CopyMandate:
    signature = hmac.new(_key(key_provider), _canonical(mandate.body()), hashlib.sha256).hexdigest()
    return replace(mandate, signature=signature)


def signature_valid(mandate: CopyMandate, key_provider: KeyProvider | None) -> bool:
    try:
        expected = hmac.new(_key(key_provider), _canonical(mandate.body()), hashlib.sha256).hexdigest()
    except MandateError:
        return False
    return bool(mandate.signature) and hmac.compare_digest(expected, mandate.signature)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        raise MandateError("naive timestamp in mandate")
    return value


def evaluate_mandate(
    mandate: CopyMandate | None,
    *,
    key_provider: KeyProvider | None,
    follower_user_id: str,
    trader_id: str,
    personality: RiskPersonality,
    asset_class: str,
    session_id: str,
    now: datetime,
) -> MandateDecision:
    """Decide whether this mandate allows a NEW copied trade now."""
    if mandate is None:
        return MandateDecision(False, False, "mandate_missing")
    mid = mandate.mandate_id
    if not signature_valid(mandate, key_provider):
        # A tampered or unverifiable mandate gives no authority at all.
        return MandateDecision(False, False, "mandate_signature_invalid", mid)
    if mandate.follower_user_id != follower_user_id:
        return MandateDecision(False, False, "mandate_follower_mismatch", mid)
    if mandate.trader_id != trader_id:
        return MandateDecision(False, True, "mandate_trader_mismatch", mid)
    if mandate.revoked_at_utc:
        return MandateDecision(False, True, "mandate_revoked", mid)
    try:
        expires = _parse(mandate.expires_at_utc)
        last = _parse(mandate.last_authorized_at_utc)
    except (MandateError, ValueError):
        return MandateDecision(False, True, "mandate_timestamps_invalid", mid)
    if now >= expires:
        return MandateDecision(False, True, "mandate_expired", mid)
    if mandate.personality != personality.value:
        return MandateDecision(False, True, "mandate_personality_mismatch", mid)
    if mandate.reauthorization_policy == ReauthorizationPolicy.EACH_SIGN_ON.value:
        if not session_id or mandate.authorized_session_id != session_id:
            return MandateDecision(False, True, "mandate_reauthorization_required_at_sign_on", mid)
    elif mandate.reauthorization_policy == ReauthorizationPolicy.INTERVAL.value:
        if now >= last + timedelta(hours=float(mandate.reauthorization_interval_hours)):
            return MandateDecision(False, True, "mandate_reauthorization_overdue", mid)
    else:
        return MandateDecision(False, True, "mandate_reauthorization_policy_invalid", mid)
    if str(asset_class).upper() not in mandate.asset_classes:
        return MandateDecision(False, True, "mandate_asset_class_out_of_scope", mid)
    return MandateDecision(True, True, "mandate_valid", mid)


class MandateRegistry:
    """Persistent mandates plus an append-only, hash-chained audit trail."""

    def __init__(self, root: Path | str, *, key_provider: KeyProvider | None) -> None:
        self.root = Path(root)
        self.path = self.root / "copy_mandates.json"
        self.audit_path = self.root / "copy_mandates_audit.jsonl"
        self.lock_path = self.root / "copy_mandates.lock"
        self.key_provider = key_provider

    # -- storage ---------------------------------------------------------
    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            document = read_json_object(self.path)
        except PersistenceError as exc:
            raise MandateError(f"mandates unreadable: {exc}") from exc
        if document.get("schema") != MANDATE_SCHEMA or not isinstance(document.get("mandates"), dict):
            raise MandateError("mandate schema mismatch")
        return document["mandates"]

    def _write(self, mandates: dict[str, dict[str, Any]]) -> None:
        atomic_write_json(self.path, {"schema": MANDATE_SCHEMA, "mandates": mandates}, expected_root=self.root)

    def _audit(self, event: str, mandate: CopyMandate, now: datetime) -> None:
        prev = self._last_audit_hash()
        body = {"event": event, "mandate_id": mandate.mandate_id, "follower_user_id": mandate.follower_user_id,
                "trader_id": mandate.trader_id, "personality": mandate.personality, "at_utc": _iso(now),
                "signature": mandate.signature, "prev_hash": prev}
        body["entry_hash"] = hashlib.sha256(_canonical(body)).hexdigest()
        atomic_append_jsonl(self.audit_path, body, expected_root=self.root)

    def _last_audit_hash(self) -> str:
        if not self.audit_path.exists():
            return "GENESIS"
        lines = [line for line in self.audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return json.loads(lines[-1])["entry_hash"] if lines else "GENESIS"

    def verify_audit_chain(self) -> int:
        """Return the number of audit entries; raise MandateError if the chain is broken."""
        if not self.audit_path.exists():
            return 0
        prev = "GENESIS"
        count = 0
        for line in self.audit_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            claimed = record.pop("entry_hash", None)
            if record.get("prev_hash") != prev or hashlib.sha256(_canonical(record)).hexdigest() != claimed:
                raise MandateError("mandate audit chain broken")
            prev = claimed
            count += 1
        return count

    @staticmethod
    def _from_record(record: dict[str, Any]) -> CopyMandate:
        data = dict(record)
        data["asset_classes"] = tuple(data.get("asset_classes") or ())
        try:
            return CopyMandate(**data)
        except TypeError as exc:
            raise MandateError("mandate record malformed") from exc

    # -- operations ------------------------------------------------------
    def get(self, mandate_id: str) -> CopyMandate | None:
        record = self._read().get(mandate_id)
        return self._from_record(record) if record else None

    def active_for(self, follower_user_id: str, now: datetime) -> CopyMandate | None:
        """Newest unrevoked, unexpired mandate of a follower (signature checked later)."""
        candidates = []
        for record in self._read().values():
            mandate = self._from_record(record)
            if mandate.follower_user_id != follower_user_id or mandate.revoked_at_utc:
                continue
            if _parse(mandate.expires_at_utc) <= now:
                continue
            candidates.append(mandate)
        return max(candidates, key=lambda m: m.issued_at_utc) if candidates else None

    def authorize(
        self,
        *,
        follower_user_id: str,
        trader_id: str,
        personality: RiskPersonality,
        asset_classes: tuple[str, ...],
        max_allocation: float,
        currency: str,
        valid_days: float,
        reauthorization_policy: ReauthorizationPolicy,
        reauthorization_interval_hours: float,
        session_id: str,
        now: datetime,
    ) -> CopyMandate:
        if not follower_user_id or not trader_id or not session_id:
            raise MandateError("follower, trader and session are required")
        if follower_user_id == trader_id:
            raise MandateError("a user cannot copy themselves")
        if not 0 < float(valid_days) <= MAX_MANDATE_DAYS:
            raise MandateError(f"mandate validity must be within 0..{MAX_MANDATE_DAYS} days")
        if not float(max_allocation) > 0:
            raise MandateError("max_allocation must be positive")
        if reauthorization_policy == ReauthorizationPolicy.INTERVAL and not float(reauthorization_interval_hours) > 0:
            raise MandateError("reauthorization interval must be positive")
        scope = tuple(sorted({str(a).upper() for a in asset_classes}))
        if not scope or not set(scope) <= {"FX", "CRYPTO", "FUTURES", "OPTIONS"}:
            raise MandateError("asset class scope invalid")
        mandate = CopyMandate(
            mandate_id="mdt-" + secrets.token_hex(12),
            follower_user_id=follower_user_id,
            trader_id=trader_id,
            personality=RiskPersonality(personality).value,
            asset_classes=scope,
            max_allocation=round(float(max_allocation), 2),
            currency=str(currency).upper(),
            issued_at_utc=_iso(now),
            expires_at_utc=_iso(now + timedelta(days=float(valid_days))),
            reauthorization_policy=ReauthorizationPolicy(reauthorization_policy).value,
            reauthorization_interval_hours=float(reauthorization_interval_hours),
            last_authorized_at_utc=_iso(now),
            authorized_session_id=session_id,
        )
        mandate = sign_mandate(mandate, self.key_provider)
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            mandates = self._read()
            # One active mandate per follower: issuing a new one revokes the previous ones.
            for mid, record in list(mandates.items()):
                old = self._from_record(record)
                if old.follower_user_id == follower_user_id and not old.revoked_at_utc:
                    revoked = sign_mandate(replace(old, revoked_at_utc=_iso(now), revocation_reason="superseded"), self.key_provider)
                    mandates[mid] = asdict(revoked)
                    self._audit("REVOKED_SUPERSEDED", revoked, now)
            mandates[mandate.mandate_id] = asdict(mandate)
            self._write(mandates)
            self._audit("AUTHORIZED", mandate, now)
        return mandate

    def _mutate(self, mandate_id: str, event: str, now: datetime, **changes: Any) -> CopyMandate:
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            mandates = self._read()
            if mandate_id not in mandates:
                raise MandateError("mandate_not_found")
            current = self._from_record(mandates[mandate_id])
            if not signature_valid(current, self.key_provider):
                raise MandateError("mandate_signature_invalid")
            if current.revoked_at_utc:
                raise MandateError("mandate_already_revoked")
            updated = sign_mandate(replace(current, **changes), self.key_provider)
            mandates[mandate_id] = asdict(updated)
            self._write(mandates)
            self._audit(event, updated, now)
        return updated

    def reauthorize(self, mandate_id: str, *, follower_user_id: str, session_id: str, now: datetime) -> CopyMandate:
        current = self.get(mandate_id)
        if current is None or current.follower_user_id != follower_user_id:
            raise MandateError("mandate_not_found")
        if now >= _parse(current.expires_at_utc):
            raise MandateError("mandate_expired_issue_new")
        return self._mutate(mandate_id, "REAUTHORIZED", now, last_authorized_at_utc=_iso(now), authorized_session_id=session_id)

    def revoke(self, mandate_id: str, *, follower_user_id: str, reason: str, now: datetime) -> CopyMandate:
        current = self.get(mandate_id)
        if current is None or current.follower_user_id != follower_user_id:
            raise MandateError("mandate_not_found")
        return self._mutate(mandate_id, "REVOKED", now, revoked_at_utc=_iso(now), revocation_reason=str(reason or "user_revoked")[:200])
