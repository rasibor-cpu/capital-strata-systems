from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import threading
import uuid
from typing import Any, Mapping


TTL_SECONDS = 60
LIVE_ENVIRONMENT = "LIVE"


@dataclass(frozen=True)
class LiveAuthorizationScope:
    order_identity: str
    environment: str
    broker: str
    account: str
    symbol: str
    side: str
    authoritative_exposure_amount: Decimal
    authoritative_exposure_currency: str
    quantity: str = ""
    order_type: str = ""
    limit_price: str = ""

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "LiveAuthorizationScope":
        return cls(
            order_identity=_required_text(payload.get("order_identity"), "order_identity"),
            environment=_required_text(payload.get("environment"), "environment").upper(),
            broker=_required_text(payload.get("broker"), "broker").upper(),
            account=_required_text(payload.get("account"), "account"),
            symbol=_required_text(payload.get("symbol"), "symbol").upper(),
            side=_required_text(payload.get("side"), "side").upper(),
            authoritative_exposure_amount=_decimal_money(payload.get("authoritative_exposure_amount")),
            authoritative_exposure_currency=_required_text(
                payload.get("authoritative_exposure_currency"),
                "authoritative_exposure_currency",
            ).upper(),
            quantity=_optional_text(payload.get("quantity")),
            order_type=_optional_text(payload.get("order_type")).upper(),
            limit_price=_optional_text(payload.get("limit_price")),
        )

    def fingerprint(self) -> str:
        payload = {
            "order_identity": self.order_identity,
            "environment": self.environment,
            "broker": self.broker,
            "account": self.account,
            "symbol": self.symbol,
            "side": self.side,
            "authoritative_exposure_amount": _money_string(self.authoritative_exposure_amount),
            "authoritative_exposure_currency": self.authoritative_exposure_currency,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "limit_price": self.limit_price,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(raw).hexdigest()


@dataclass(frozen=True)
class LiveAuthorizationTTLDecision:
    approved: bool
    reason: str
    decision: str
    evidence: dict[str, Any]


@dataclass
class _AuthorizationRecord:
    authorization_id: str
    issued_at: str
    expires_at: str
    ttl_seconds: int
    scope: LiveAuthorizationScope
    scope_fingerprint: str
    consumed: bool = False
    revoked: bool = False
    consumed_at: str = ""
    revoked_at: str = ""


class LiveAuthorizationTTLGate:
    """
    In-memory final authorization gate.

    Non-persistence is intentional: authorizations are process-local and do not
    survive restart.
    """

    def __init__(self, ttl_seconds: int = TTL_SECONDS) -> None:
        self._ttl_seconds = int(ttl_seconds)
        self._records: dict[str, _AuthorizationRecord] = {}
        self._lock = threading.RLock()

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def issue_authorization(
        self,
        scope: LiveAuthorizationScope,
        *,
        authorization_id: str | None = None,
        issuance_time: datetime | None = None,
    ) -> dict[str, Any]:
        issued_dt = _ensure_utc_aware(issuance_time or datetime.now(timezone.utc))
        expires_dt = issued_dt + timedelta(seconds=self._ttl_seconds)
        auth_id = str(authorization_id or uuid.uuid4())
        record = _AuthorizationRecord(
            authorization_id=auth_id,
            issued_at=_iso_utc(issued_dt),
            expires_at=_iso_utc(expires_dt),
            ttl_seconds=self._ttl_seconds,
            scope=scope,
            scope_fingerprint=scope.fingerprint(),
        )
        with self._lock:
            self._records[auth_id] = record
        return {
            "authorization_id": auth_id,
            "issued_at": record.issued_at,
            "expires_at": record.expires_at,
            "ttl_seconds": record.ttl_seconds,
            "scope_fingerprint": record.scope_fingerprint,
        }

    def revoke_authorization(self, authorization_id: str, *, evaluation_time: datetime | None = None) -> bool:
        auth_id = str(authorization_id or "").strip()
        with self._lock:
            record = self._records.get(auth_id)
            if record is None:
                return False
            record.revoked = True
            record.revoked_at = _iso_utc(_ensure_utc_aware(evaluation_time or datetime.now(timezone.utc)))
            return True

    def validate_and_consume(
        self,
        authorization_id: str,
        requested_scope: LiveAuthorizationScope,
        *,
        evaluation_time: datetime | None = None,
        kill_switch_active: bool = False,
    ) -> LiveAuthorizationTTLDecision:
        eval_dt = _ensure_utc_aware(evaluation_time or datetime.now(timezone.utc))
        auth_id = str(authorization_id or "").strip()
        with self._lock:
            record = self._records.get(auth_id) if auth_id else None
            if kill_switch_active:
                if record is not None:
                    record.revoked = True
                    record.revoked_at = _iso_utc(eval_dt)
                return self._reject(
                    "kill_switch_active",
                    auth_id,
                    record,
                    requested_scope,
                    eval_dt,
                    kill_switch_active=True,
                )

            if not auth_id or record is None:
                return self._reject(
                    "missing_authorization",
                    auth_id,
                    record,
                    requested_scope,
                    eval_dt,
                    kill_switch_active=False,
                )

            if not isinstance(record.scope, LiveAuthorizationScope) or not str(record.scope_fingerprint or "").strip():
                return self._reject(
                    "malformed_authorization",
                    auth_id,
                    record,
                    requested_scope,
                    eval_dt,
                    kill_switch_active=False,
                )

            if record.revoked:
                return self._reject(
                    "authorization_revoked",
                    auth_id,
                    record,
                    requested_scope,
                    eval_dt,
                    kill_switch_active=False,
                )

            if record.consumed:
                return self._reject(
                    "authorization_already_consumed",
                    auth_id,
                    record,
                    requested_scope,
                    eval_dt,
                    kill_switch_active=False,
                )

            issued_raw = record.issued_at
            if not str(issued_raw or "").strip():
                return self._reject("missing_issued_at", auth_id, record, requested_scope, eval_dt, kill_switch_active=False)
            issued_dt = _parse_utc_iso(issued_raw)
            if issued_dt is None:
                return self._reject("malformed_issued_at", auth_id, record, requested_scope, eval_dt, kill_switch_active=False)

            expires_raw = record.expires_at
            if not str(expires_raw or "").strip():
                return self._reject("missing_expires_at", auth_id, record, requested_scope, eval_dt, kill_switch_active=False)
            expires_dt = _parse_utc_iso(expires_raw)
            if expires_dt is None:
                return self._reject("invalid_expiry", auth_id, record, requested_scope, eval_dt, kill_switch_active=False)

            if issued_dt > eval_dt:
                return self._reject("future_issued_at", auth_id, record, requested_scope, eval_dt, kill_switch_active=False)

            if expires_dt != issued_dt + timedelta(seconds=self._ttl_seconds):
                return self._reject("invalid_expiry", auth_id, record, requested_scope, eval_dt, kill_switch_active=False)

            if eval_dt >= expires_dt:
                return self._reject("authorization_expired", auth_id, record, requested_scope, eval_dt, kill_switch_active=False)

            scope_reason = self._scope_mismatch_reason(record.scope, requested_scope)
            if scope_reason:
                return self._reject(scope_reason, auth_id, record, requested_scope, eval_dt, kill_switch_active=False)

            record.consumed = True
            record.consumed_at = _iso_utc(eval_dt)
            evidence = self._build_evidence(
                auth_id,
                record,
                requested_scope,
                eval_dt,
                kill_switch_active=False,
                reason="approved",
                decision="AUTHORIZED",
            )
            return LiveAuthorizationTTLDecision(True, "approved", "AUTHORIZED", evidence)

    def _scope_mismatch_reason(
        self,
        stored: LiveAuthorizationScope,
        requested: LiveAuthorizationScope,
    ) -> str:
        if requested.environment != LIVE_ENVIRONMENT or stored.environment != LIVE_ENVIRONMENT:
            return "environment_mismatch"
        if stored.broker != requested.broker:
            return "broker_mismatch"
        if stored.account != requested.account:
            return "account_mismatch"
        if stored.symbol != requested.symbol:
            return "instrument_mismatch"
        if stored.side != requested.side:
            return "order_mismatch"
        if stored.authoritative_exposure_currency != requested.authoritative_exposure_currency:
            return "order_mismatch"
        if stored.authoritative_exposure_amount != requested.authoritative_exposure_amount:
            return "order_mismatch"
        if stored.order_identity != requested.order_identity:
            return "order_mismatch"
        if stored.quantity != requested.quantity:
            return "order_mismatch"
        if stored.order_type != requested.order_type:
            return "order_mismatch"
        if stored.limit_price != requested.limit_price:
            return "order_mismatch"
        if stored.fingerprint() != requested.fingerprint():
            return "authorization_scope_mismatch"
        return ""

    def _reject(
        self,
        reason: str,
        authorization_id: str,
        record: _AuthorizationRecord | None,
        requested_scope: LiveAuthorizationScope,
        evaluation_time: datetime,
        *,
        kill_switch_active: bool,
    ) -> LiveAuthorizationTTLDecision:
        evidence = self._build_evidence(
            authorization_id,
            record,
            requested_scope,
            evaluation_time,
            kill_switch_active=kill_switch_active,
            reason=reason,
            decision="REJECT",
        )
        return LiveAuthorizationTTLDecision(False, reason, "REJECT", evidence)

    def _build_evidence(
        self,
        authorization_id: str,
        record: _AuthorizationRecord | None,
        requested_scope: LiveAuthorizationScope,
        evaluation_time: datetime,
        *,
        kill_switch_active: bool,
        reason: str,
        decision: str,
    ) -> dict[str, Any]:
        issued_at = record.issued_at if record is not None else ""
        expires_at = record.expires_at if record is not None else ""
        scope_fingerprint = record.scope_fingerprint if record is not None else ""
        consumed = bool(record.consumed) if record is not None else False
        revoked = bool(record.revoked) if record is not None else False
        freshness = "VALID" if decision == "AUTHORIZED" else "INVALID"
        return {
            "authorization_id": authorization_id,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "evaluation_time": _iso_utc(evaluation_time),
            "ttl_seconds": self._ttl_seconds,
            "scope_fingerprint": scope_fingerprint,
            "requested_scope_fingerprint": requested_scope.fingerprint(),
            "freshness_result": freshness,
            "consumed": consumed,
            "revoked": revoked,
            "kill_switch_active": kill_switch_active,
            "decision": decision,
            "rejection_reason": "" if decision == "AUTHORIZED" else reason,
        }


def _required_text(value: Any, key: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{key} is required")
    return text


def _optional_text(value: Any) -> str:
    return str(value or "").strip()


def _decimal_money(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("bool is not valid money")
    try:
        money = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid monetary value") from exc
    if not money.is_finite() or money <= Decimal("0.00"):
        raise ValueError("invalid monetary value")
    return money


def _money_string(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _parse_utc_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _ensure_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timezone-aware UTC datetime required")
    return value.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return _ensure_utc_aware(value).isoformat()


_GLOBAL_LIVE_AUTHORIZATION_TTL_GATE = LiveAuthorizationTTLGate()


def get_live_authorization_ttl_gate() -> LiveAuthorizationTTLGate:
    return _GLOBAL_LIVE_AUTHORIZATION_TTL_GATE


__all__ = [
    "LIVE_ENVIRONMENT",
    "TTL_SECONDS",
    "LiveAuthorizationScope",
    "LiveAuthorizationTTLDecision",
    "LiveAuthorizationTTLGate",
    "get_live_authorization_ttl_gate",
]
