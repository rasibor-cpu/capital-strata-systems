"""Lease-only broker runtime composition."""

from __future__ import annotations

import threading
from typing import Any

from backend.brokers.runtime.runtime_models import (
    EnterpriseBrokerBinding,
    canonical_broker_consumer,
)
from backend.security.identity.enterprise_secret_service import EnterpriseSecretService
from backend.security.identity.runtime_secret_lease import RuntimeSecretLease


class EnterpriseBrokerRuntime:
    def __init__(self, *, secrets: EnterpriseSecretService):
        self.secrets = secrets
        self._bindings: dict[str, EnterpriseBrokerBinding] = {}
        self._leases: dict[str, RuntimeSecretLease] = {}
        self._lock = threading.RLock()

    def register(self, binding: EnterpriseBrokerBinding, *, operator: str) -> None:
        broker = str(binding.broker).upper()
        if binding.capabilities.broker.upper() != broker:
            raise ValueError("BROKER_CAPABILITY_CONTRACT_MISMATCH")
        if binding.oauth_handle and binding.oauth_handle.provider.upper() != broker:
            raise ValueError("BROKER_OAUTH_HANDLE_MISMATCH")
        if binding.legacy_compatibility:
            raise ValueError("LEGACY_COMPATIBILITY_CANNOT_BE_ENTERPRISE_RUNTIME")
        if not binding.secret_handles:
            raise ValueError("ENTERPRISE_SECRET_HANDLE_REQUIRED")
        if binding.consumer != canonical_broker_consumer(broker):
            raise PermissionError("BROKER_RUNTIME_CONSUMER_MISMATCH")
        if any(handle.issued_to != binding.consumer for handle in binding.secret_handles):
            raise PermissionError("SECRET_HANDLE_CONSUMER_MISMATCH")
        if any(
            str(handle.broker or handle.provider).upper() != broker
            for handle in binding.secret_handles
        ):
            raise PermissionError("SECRET_HANDLE_BROKER_MISMATCH")
        with self._lock:
            if broker in self._bindings:
                raise ValueError("BROKER_RUNTIME_ALREADY_REGISTERED")
            for handle in binding.secret_handles:
                self.secrets.authorize_runtime_consumer(
                    handle.secret_uuid,
                    consumer=binding.consumer,
                    operator=operator,
                )
            self._bindings[broker] = binding

    def lease(
        self,
        broker: str,
        *,
        secret_uuid: str,
        capability: str,
        operator: str,
        duration_seconds: int = 60,
    ) -> RuntimeSecretLease:
        binding = self.binding(broker)
        normalized = str(capability).upper()
        if normalized not in binding.capabilities.credential_capabilities:
            raise PermissionError("BROKER_SECRET_CAPABILITY_NOT_ALLOWED")
        if secret_uuid not in {handle.secret_uuid for handle in binding.secret_handles}:
            raise PermissionError("SECRET_HANDLE_NOT_BOUND_TO_BROKER")
        lease = self.secrets.issue_runtime_lease(
            secret_uuid,
            consumer=binding.consumer,
            capability=normalized,
            operator=operator,
            duration_seconds=duration_seconds,
        )
        with self._lock:
            self._leases[lease.metadata.lease_id] = lease
        return lease

    def binding(self, broker: str) -> EnterpriseBrokerBinding:
        with self._lock:
            binding = self._bindings.get(str(broker).upper())
        if binding is None:
            raise KeyError("BROKER_RUNTIME_NOT_REGISTERED")
        return binding

    def inventory(self) -> list[dict[str, Any]]:
        with self._lock:
            return [binding.as_dict() for binding in self._bindings.values()]

    def health(self) -> dict[str, Any]:
        with self._lock:
            leases = [lease.health() for lease in self._leases.values()]
            bindings = list(self._bindings.values())
        return {
            "status": "READY" if bindings else "CONFIGURATION_REQUIRED",
            "broker_count": len(bindings),
            "bindings": [binding.as_dict() for binding in bindings],
            "secret_lease_health": leases,
            "legacy_compatibility_count": sum(binding.legacy_compatibility for binding in bindings),
            "plaintext_returned": False,
            "execution_posture": "DISABLED",
            "execution_authority": "BLOCKED",
            "fail_closed": True,
            "advisory_only": True,
            "execution_allowed": False,
        }


__all__ = ["EnterpriseBrokerRuntime"]
