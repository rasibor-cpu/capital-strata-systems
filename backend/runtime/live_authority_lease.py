"""Bounded Phase 196 live-execution authority lease.

This module is an offline authority-control primitive. It creates no runtime
activation by itself. A lease remains subject to all other canonical live
execution gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import secrets
from typing import Any, Callable, Mapping


LIVE_AUTHORITY_SCOPE = "LIVE_EXECUTION"
LIVE_AUTHORITY_ACTION = "LIVE_EXECUTE"
MAX_LIVE_AUTHORITY_TTL_SECONDS = 300


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(value: Any) -> str:
    return str(value or "").strip().upper()


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("LIVE_AUTHORITY_TIMEZONE_REQUIRED")
    return value.astimezone(timezone.utc)


def _encode_time(value: datetime) -> str:
    return (
        _to_utc(value)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _decode_time(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("LIVE_AUTHORITY_TIMESTAMP_REQUIRED")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return _to_utc(parsed)


@dataclass(frozen=True)
class LiveAuthorityLease:
    lease_id: str
    token_digest: str
    issued_at: str
    expires_at: str
    broker: str
    environment: str
    action: str
    scope: str = LIVE_AUTHORITY_SCOPE
    consumed: bool = False
    revoked: bool = False
    generation: int = 1

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("token_digest", None)
        return payload


@dataclass(frozen=True)
class LiveAuthorityLeaseStatus:
    valid: bool
    reason: str
    lease_id: str = ""
    broker: str = ""
    environment: str = ""
    action: str = ""
    expires_at: str = ""
    consumed: bool = False
    revoked: bool = False


class LiveAuthorityLeaseRegistry:
    """Fail-closed bounded lease registry."""

    def __init__(
        self,
        *,
        durable_path: Path | str | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = now or _utc_now
        self._durable_path = (
            Path(durable_path) if durable_path is not None else None
        )
        self._generation = 0
        self._leases: dict[str, LiveAuthorityLease] = {}

        if self._durable_path is not None and self._durable_path.exists():
            self._load()

    def issue(
        self,
        *,
        broker: str,
        environment: str,
        ttl_seconds: int,
        action: str = LIVE_AUTHORITY_ACTION,
    ) -> tuple[str, LiveAuthorityLease]:
        ttl = int(ttl_seconds)

        if ttl <= 0 or ttl > MAX_LIVE_AUTHORITY_TTL_SECONDS:
            raise ValueError("LIVE_AUTHORITY_TTL_INVALID")

        broker_key = _normalize(broker)
        environment_key = _normalize(environment)
        action_key = _normalize(action)

        if not broker_key:
            raise ValueError("LIVE_AUTHORITY_BROKER_REQUIRED")

        if not environment_key:
            raise ValueError("LIVE_AUTHORITY_ENVIRONMENT_REQUIRED")

        if action_key != LIVE_AUTHORITY_ACTION:
            raise ValueError("LIVE_AUTHORITY_ACTION_INVALID")

        issued = _to_utc(self._clock())
        expires = issued + timedelta(seconds=ttl)

        raw_token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(
            raw_token.encode("utf-8")
        ).hexdigest()

        self._generation += 1

        seed = "|".join(
            (
                broker_key,
                environment_key,
                action_key,
                _encode_time(issued),
                str(self._generation),
                digest,
            )
        )

        lease_id = (
            "live-lease-"
            + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        )

        lease = LiveAuthorityLease(
            lease_id=lease_id,
            token_digest=digest,
            issued_at=_encode_time(issued),
            expires_at=_encode_time(expires),
            broker=broker_key,
            environment=environment_key,
            action=action_key,
            generation=self._generation,
        )

        self._leases[lease_id] = lease
        self._persist()

        return raw_token, lease

    def validate(
        self,
        lease_id: str,
        raw_token: str,
        *,
        broker: str,
        environment: str,
        action: str = LIVE_AUTHORITY_ACTION,
        now: datetime | None = None,
    ) -> LiveAuthorityLeaseStatus:
        lease = self._leases.get(str(lease_id or ""))

        if lease is None:
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_LEASE_UNKNOWN",
            )

        current = _to_utc(now if now is not None else self._clock())

        try:
            issued = _decode_time(lease.issued_at)
            expires = _decode_time(lease.expires_at)
        except (TypeError, ValueError):
            return self._status(
                lease,
                False,
                "LIVE_AUTHORITY_TIMESTAMP_INVALID",
            )

        if issued > current:
            return self._status(
                lease,
                False,
                "LIVE_AUTHORITY_ISSUED_IN_FUTURE",
            )

        if expires <= issued:
            return self._status(
                lease,
                False,
                "LIVE_AUTHORITY_EXPIRY_INVALID",
            )

        if current >= expires:
            return self._status(
                lease,
                False,
                "LIVE_AUTHORITY_LEASE_EXPIRED",
            )

        if lease.revoked:
            return self._status(
                lease,
                False,
                "LIVE_AUTHORITY_LEASE_REVOKED",
            )

        if lease.consumed:
            return self._status(
                lease,
                False,
                "LIVE_AUTHORITY_LEASE_CONSUMED",
            )

        supplied_digest = hashlib.sha256(
            str(raw_token or "").encode("utf-8")
        ).hexdigest()

        if not secrets.compare_digest(
            supplied_digest,
            lease.token_digest,
        ):
            return self._status(
                lease,
                False,
                "LIVE_AUTHORITY_TOKEN_MISMATCH",
            )

        if lease.scope != LIVE_AUTHORITY_SCOPE:
            return self._status(
                lease,
                False,
                "LIVE_AUTHORITY_SCOPE_INVALID",
            )

        if lease.broker != _normalize(broker):
            return self._status(
                lease,
                False,
                "LIVE_AUTHORITY_BROKER_MISMATCH",
            )

        if lease.environment != _normalize(environment):
            return self._status(
                lease,
                False,
                "LIVE_AUTHORITY_ENVIRONMENT_MISMATCH",
            )

        if lease.action != _normalize(action):
            return self._status(
                lease,
                False,
                "LIVE_AUTHORITY_ACTION_MISMATCH",
            )

        return self._status(
            lease,
            True,
            "LIVE_AUTHORITY_LEASE_VALID",
        )

    def consume(
        self,
        lease_id: str,
        raw_token: str,
        *,
        broker: str,
        environment: str,
        action: str = LIVE_AUTHORITY_ACTION,
        now: datetime | None = None,
    ) -> LiveAuthorityLeaseStatus:
        status = self.validate(
            lease_id,
            raw_token,
            broker=broker,
            environment=environment,
            action=action,
            now=now,
        )

        if not status.valid:
            return status

        lease = self._leases[str(lease_id)]
        consumed = replace(
            lease,
            consumed=True,
        )

        self._leases[str(lease_id)] = consumed
        self._persist()

        return self._status(
            consumed,
            True,
            "LIVE_AUTHORITY_LEASE_CONSUMED_SUCCESSFULLY",
        )

    def revoke(
        self,
        lease_id: str,
    ) -> LiveAuthorityLeaseStatus:
        lease = self._leases.get(str(lease_id or ""))

        if lease is None:
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_LEASE_UNKNOWN",
            )

        revoked = replace(
            lease,
            revoked=True,
        )

        self._leases[lease.lease_id] = revoked
        self._persist()

        return self._status(
            revoked,
            False,
            "LIVE_AUTHORITY_LEASE_REVOKED",
        )

    def public_record(
        self,
        lease_id: str,
    ) -> Mapping[str, Any] | None:
        lease = self._leases.get(str(lease_id or ""))

        if lease is None:
            return None

        return lease.public_dict()

    def _status(
        self,
        lease: LiveAuthorityLease,
        valid: bool,
        reason: str,
    ) -> LiveAuthorityLeaseStatus:
        return LiveAuthorityLeaseStatus(
            valid=valid,
            reason=reason,
            lease_id=lease.lease_id,
            broker=lease.broker,
            environment=lease.environment,
            action=lease.action,
            expires_at=lease.expires_at,
            consumed=lease.consumed,
            revoked=lease.revoked,
        )

    def _persist(self) -> None:
        if self._durable_path is None:
            return

        self._durable_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "generation": self._generation,
            "leases": {
                lease_id: asdict(lease)
                for lease_id, lease in self._leases.items()
            },
        }

        self._durable_path.write_text(
            json.dumps(
                payload,
                sort_keys=True,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _load(self) -> None:
        assert self._durable_path is not None

        try:
            payload = json.loads(
                self._durable_path.read_text(
                    encoding="utf-8",
                )
            )

            generation = int(
                payload.get("generation") or 0
            )

            rows = payload.get("leases")

            if not isinstance(rows, Mapping):
                raise ValueError(
                    "LIVE_AUTHORITY_DURABLE_STATE_INVALID"
                )

            loaded: dict[str, LiveAuthorityLease] = {}

            for lease_id, body in rows.items():
                if not isinstance(body, Mapping):
                    raise ValueError(
                        "LIVE_AUTHORITY_DURABLE_STATE_INVALID"
                    )

                lease = LiveAuthorityLease(
                    **dict(body)
                )

                if lease.lease_id != str(lease_id):
                    raise ValueError(
                        "LIVE_AUTHORITY_DURABLE_STATE_INVALID"
                    )

                loaded[str(lease_id)] = lease

            self._generation = generation
            self._leases = loaded

        except Exception:
            # Ambiguous durable state is intentionally treated as empty.
            self._generation = 0
            self._leases = {}


def evaluate_live_authority_lease_evidence(
    value: Mapping[str, Any] | None,
    *,
    broker: str,
    environment: str,
    action: str = LIVE_AUTHORITY_ACTION,
    now: datetime | None = None,
) -> LiveAuthorityLeaseStatus:
    """Validate public lease evidence without consuming it."""

    if not isinstance(value, Mapping):
        return LiveAuthorityLeaseStatus(
            False,
            "LIVE_AUTHORITY_LEASE_MISSING",
        )

    current = _to_utc(
        now if now is not None else _utc_now()
    )

    try:
        lease_id = str(
            value.get("lease_id") or ""
        ).strip()

        scope = str(
            value.get("scope") or ""
        ).strip()

        lease_broker = _normalize(
            value.get("broker")
        )

        lease_environment = _normalize(
            value.get("environment")
        )

        lease_action = _normalize(
            value.get("action")
        )

        issued = _decode_time(
            str(value.get("issued_at") or "")
        )

        expires = _decode_time(
            str(value.get("expires_at") or "")
        )

        consumed = bool(
            value.get("consumed", False)
        )

        revoked = bool(
            value.get("revoked", False)
        )

        if not lease_id:
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_LEASE_MALFORMED",
            )

        if scope != LIVE_AUTHORITY_SCOPE:
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_SCOPE_INVALID",
                lease_id=lease_id,
            )

        if issued > current:
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_ISSUED_IN_FUTURE",
                lease_id=lease_id,
            )

        if expires <= issued:
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_EXPIRY_INVALID",
                lease_id=lease_id,
            )

        if current >= expires:
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_LEASE_EXPIRED",
                lease_id=lease_id,
            )

        if revoked:
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_LEASE_REVOKED",
                lease_id=lease_id,
            )

        if consumed:
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_LEASE_CONSUMED",
                lease_id=lease_id,
            )

        if lease_broker != _normalize(broker):
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_BROKER_MISMATCH",
                lease_id=lease_id,
            )

        if lease_environment != _normalize(environment):
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_ENVIRONMENT_MISMATCH",
                lease_id=lease_id,
            )

        if lease_action != _normalize(action):
            return LiveAuthorityLeaseStatus(
                False,
                "LIVE_AUTHORITY_ACTION_MISMATCH",
                lease_id=lease_id,
            )

        return LiveAuthorityLeaseStatus(
            True,
            "LIVE_AUTHORITY_LEASE_VALID",
            lease_id=lease_id,
            broker=lease_broker,
            environment=lease_environment,
            action=lease_action,
            expires_at=str(value.get("expires_at") or ""),
            consumed=False,
            revoked=False,
        )

    except Exception:
        return LiveAuthorityLeaseStatus(
            False,
            "LIVE_AUTHORITY_LEASE_MALFORMED",
        )


__all__ = [
    "LIVE_AUTHORITY_ACTION",
    "LIVE_AUTHORITY_SCOPE",
    "MAX_LIVE_AUTHORITY_TTL_SECONDS",
    "LiveAuthorityLease",
    "LiveAuthorityLeaseRegistry",
    "LiveAuthorityLeaseStatus",
    "evaluate_live_authority_lease_evidence",
]