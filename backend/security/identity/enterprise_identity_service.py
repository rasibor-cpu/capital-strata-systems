"""Canonical authority for human, service, and workload identities."""

from __future__ import annotations

import threading
import uuid

from backend.security.identity.identity_events import IdentityEventStream
from backend.security.identity.identity_models import EnterpriseIdentity, IdentityType


class EnterpriseIdentityService:
    def __init__(self, *, events: IdentityEventStream | None = None):
        self._identities: dict[str, EnterpriseIdentity] = {}
        self._events = events or IdentityEventStream()
        self._lock = threading.RLock()

    def register(
        self,
        *,
        display_name: str,
        identity_type: IdentityType,
        role: str,
        owner: str,
        environment: str,
        identity_id: str | None = None,
        permissions: tuple[str, ...] = (),
    ) -> EnterpriseIdentity:
        identifier = str(identity_id or f"EID-{uuid.uuid4()}")
        identity = EnterpriseIdentity(
            identity_id=identifier,
            display_name=str(display_name),
            identity_type=identity_type,
            role=str(role).upper(),
            owner=str(owner),
            environment=str(environment).upper(),
            permissions=tuple(sorted(set(permissions))),
        )
        with self._lock:
            if identifier in self._identities:
                raise ValueError("IDENTITY_ALREADY_REGISTERED")
            self._identities[identifier] = identity
        self._events.publish(
            event_type="IDENTITY_REGISTERED",
            identity_id=identifier,
            resource_id=identifier,
            result="SUCCESS",
        )
        return identity

    def get(self, identity_id: str) -> EnterpriseIdentity:
        with self._lock:
            identity = self._identities.get(str(identity_id))
        if identity is None:
            raise KeyError("IDENTITY_NOT_FOUND")
        return identity

    def inventory(self) -> list[dict]:
        with self._lock:
            return [identity.as_dict() for identity in self._identities.values()]

    @property
    def events(self) -> IdentityEventStream:
        return self._events


__all__ = ["EnterpriseIdentityService"]
