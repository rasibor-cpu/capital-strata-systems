"""Phase 189 — broker-independent authorization TTL (NOT trading authorization).

Scope is limited to READ_ONLY_OPERATIONAL certification sessions.
Restart cannot re-arm: expired records remain expired after reload.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from backend.app.brokers.multi_broker_readiness.contracts import SCHEMA_VERSION, BrokerType

TTL_SCOPE = "READ_ONLY_OPERATIONAL"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class AuthorizationTTL:
    ttl_id: str
    broker_type: str
    scope: str
    issued_at: str
    expires_at: str  # immutable once issued
    generation: int
    trading_authorization: bool = False
    schema_version: str = SCHEMA_VERSION
    audit_hash: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trading_authorization"] = False
        return payload

    def __post_init__(self) -> None:
        if self.trading_authorization:
            raise ValueError("AuthorizationTTL must never grant trading_authorization")
        if self.scope != TTL_SCOPE:
            raise ValueError(f"unsupported TTL scope: {self.scope}")


@dataclass(frozen=True)
class TTLStatus:
    ttl_id: str
    broker_type: str
    active: bool
    expired: bool
    remaining_seconds: float
    expires_at: str
    generation: int
    trading_authorization: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trading_authorization"] = False
        return payload


class AuthorizationTTLRegistry:
    """In-memory + optional durable audit store. Never arms trading authority."""

    FORBIDDEN_METHODS: frozenset[str] = frozenset(
        {
            "arm_live_authority",
            "enable_execution",
            "place_order",
            "submit_order",
            "rearm_trading",
        }
    )

    def __init__(
        self,
        *,
        durable_path: Path | str | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._now = now or _utc_now
        self._records: dict[str, AuthorizationTTL] = {}
        self._by_broker: dict[str, str] = {}
        self._durable_path = Path(durable_path) if durable_path else None
        self._audit: list[dict[str, Any]] = []
        if self._durable_path and self._durable_path.exists():
            self._load_durable()

    def issue(
        self,
        broker: BrokerType | str,
        *,
        ttl_seconds: int,
        generation: int | None = None,
    ) -> AuthorizationTTL:
        broker_key = _broker_key(broker)
        issued = self._now()
        expires = issued + timedelta(seconds=max(1, int(ttl_seconds)))
        prior_gen = 0
        existing_id = self._by_broker.get(broker_key)
        if existing_id and existing_id in self._records:
            prior_gen = self._records[existing_id].generation
        next_gen = generation if generation is not None else prior_gen + 1
        ttl_id = "ttl-" + hashlib.sha256(
            f"{broker_key}|{_iso(issued)}|{next_gen}".encode("utf-8")
        ).hexdigest()[:20]
        body = {
            "ttl_id": ttl_id,
            "broker_type": broker_key,
            "scope": TTL_SCOPE,
            "issued_at": _iso(issued),
            "expires_at": _iso(expires),
            "generation": next_gen,
            "trading_authorization": False,
            "schema_version": SCHEMA_VERSION,
        }
        audit_hash = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        record = AuthorizationTTL(**body, audit_hash=audit_hash)
        self._records[ttl_id] = record
        self._by_broker[broker_key] = ttl_id
        self._audit.append(
            {
                "event": "TTL_ISSUED",
                "ttl_id": ttl_id,
                "broker_type": broker_key,
                "generation": next_gen,
                "expires_at": record.expires_at,
                "trading_authorization": False,
            }
        )
        self._persist()
        return record

    def status(self, broker: BrokerType | str) -> TTLStatus:
        broker_key = _broker_key(broker)
        ttl_id = self._by_broker.get(broker_key, "")
        record = self._records.get(ttl_id) if ttl_id else None
        if record is None:
            return TTLStatus(
                ttl_id="",
                broker_type=broker_key,
                active=False,
                expired=True,
                remaining_seconds=0.0,
                expires_at="",
                generation=0,
                trading_authorization=False,
                reason="no_ttl_issued",
            )
        now = self._now()
        expires = datetime.fromisoformat(record.expires_at.replace("Z", "+00:00"))
        remaining = (expires - now).total_seconds()
        expired = remaining <= 0
        if expired:
            self._audit.append(
                {
                    "event": "TTL_EXPIRED",
                    "ttl_id": record.ttl_id,
                    "broker_type": broker_key,
                    "generation": record.generation,
                    "trading_authorization": False,
                }
            )
        return TTLStatus(
            ttl_id=record.ttl_id,
            broker_type=broker_key,
            active=not expired,
            expired=expired,
            remaining_seconds=max(0.0, remaining),
            expires_at=record.expires_at,
            generation=record.generation,
            trading_authorization=False,
            reason="active" if not expired else "expired",
        )

    def audit_log(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self._audit)

    def _persist(self) -> None:
        if self._durable_path is None:
            return
        self._durable_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": {k: v.as_dict() for k, v in self._records.items()},
            "by_broker": dict(self._by_broker),
            "audit": list(self._audit),
        }
        self._durable_path.write_text(
            json.dumps(payload, sort_keys=True, indent=2),
            encoding="utf-8",
        )

    def _load_durable(self) -> None:
        assert self._durable_path is not None
        raw = json.loads(self._durable_path.read_text(encoding="utf-8"))
        for ttl_id, body in dict(raw.get("records") or {}).items():
            body = dict(body)
            body["trading_authorization"] = False
            self._records[ttl_id] = AuthorizationTTL(**body)
        self._by_broker = {str(k): str(v) for k, v in dict(raw.get("by_broker") or {}).items()}
        self._audit = list(raw.get("audit") or [])

    def __getattribute__(self, name: str) -> Any:
        if name in AuthorizationTTLRegistry.FORBIDDEN_METHODS:
            raise AttributeError(
                f"Phase 189 AuthorizationTTLRegistry forbids '{name}' "
                "(no trading authorization)"
            )
        return object.__getattribute__(self, name)


def _broker_key(broker: BrokerType | str) -> str:
    if isinstance(broker, BrokerType):
        return broker.value
    return str(broker or "").strip().upper()
