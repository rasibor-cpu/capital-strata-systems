"""Certification-first redirection of legacy credential ownership."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import re
import threading
from pathlib import Path
from typing import Any, Mapping

from backend.security.identity.enterprise_secret_service import EnterpriseSecretService
from backend.security.identity.identity_policy import SecretAccessRequest

_CREDENTIAL_KEY = re.compile(
    r"(KEY|SECRET|TOKEN|PASSWORD|CERTIFICATE|PRIVATE_KEY|CREDENTIAL|ACCOUNT_ID|ACCOUNT_NUMBER)",
    re.I,
)
_DIRECT_ACCESS = re.compile(
    r"(?:os\.getenv|os\.environ\.get)\(\s*['\"]"
    r"(?P<name>(?P<broker>COINBASE|BINANCE|OANDA|QUESTRADE)_[A-Z0-9_]*"
    r"(?:KEY|SECRET|TOKEN|PASSWORD|CERTIFICATE|ACCOUNT_ID))['\"]",
    re.I,
)


class OwnershipStatus(str, Enum):
    ENTERPRISE_MANAGED = "ENTERPRISE_MANAGED"
    LEGACY_COMPATIBILITY = "LEGACY_COMPATIBILITY"
    ORPHANED = "ORPHANED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OwnershipRecord:
    resource_id: str
    broker: str
    credential_name: str
    secret_uuid: str | None
    status: OwnershipStatus
    component: str
    source_path: str
    direct_access: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


class EnterpriseAuthorityRedirector:
    def __init__(self, service: EnterpriseSecretService):
        self.service = service
        self._bindings: dict[tuple[str, str], str] = {}
        self._ownership: dict[str, OwnershipRecord] = {}
        self._violations: list[dict[str, Any]] = []
        self._lock = threading.RLock()

    def register_legacy_credentials(
        self,
        broker: str,
        credentials: Mapping[str, Any],
        *,
        component: str,
        source_path: str,
        owner: str,
        environment: str,
        operator: str,
    ) -> dict[str, Any]:
        """Register legacy material and return handles/metadata only."""
        broker_name = str(broker).upper()
        results: dict[str, Any] = {}
        for key, value in credentials.items():
            if (
                not _CREDENTIAL_KEY.search(str(key))
                or value in (None, "")
                or isinstance(value, (Mapping, list, tuple, set, bool))
            ):
                continue
            material = bytearray(str(value).encode("utf-8"))
            fingerprint = self.service.vault.crypto.fingerprint(material)
            existing = self.service.find_by_fingerprint(fingerprint)
            if existing is None:
                metadata = self.service.register(
                    material,
                    provider="LEGACY_COMPATIBILITY_ADAPTER",
                    secret_type=str(key),
                    owner=owner,
                    environment=environment,
                    operator=operator,
                    broker=broker_name,
                )
            else:
                material[:] = b"\x00" * len(material)
                metadata = existing
            binding = (broker_name, str(key))
            record_id = f"{broker_name}:{key}:{component}"
            with self._lock:
                self._bindings[binding] = metadata.secret_uuid
                self._ownership[record_id] = OwnershipRecord(
                    resource_id=record_id,
                    broker=broker_name,
                    credential_name=str(key),
                    secret_uuid=metadata.secret_uuid,
                    status=OwnershipStatus.LEGACY_COMPATIBILITY,
                    component=str(component),
                    source_path=str(source_path),
                    direct_access=True,
                )
            results[str(key)] = {
                "secret_uuid": metadata.secret_uuid,
                "vcid": metadata.vcid,
                "fingerprint": metadata.fingerprint,
                "classification": metadata.classification.value,
                "handle_reference": f"secret-handle:{metadata.secret_uuid}",
                "plaintext_returned": False,
            }
        return {
            "broker": broker_name,
            "credentials": results,
            "ownership_status": OwnershipStatus.LEGACY_COMPATIBILITY.value,
            "plaintext_returned": False,
            "execution_allowed": False,
        }

    def resolve(
        self,
        broker: str,
        credential_names: tuple[str, ...],
        *,
        request: SecretAccessRequest,
    ) -> dict[str, Any]:
        resolved = {}
        for name in credential_names:
            secret_uuid = self._bindings.get((str(broker).upper(), str(name)))
            if not secret_uuid:
                continue
            resolved[name] = self.service.retrieve(secret_uuid, request=request)
        return {
            "broker": str(broker).upper(),
            "credentials": resolved,
            "authority": "EnterpriseSecretService",
            "plaintext_returned": False,
            "execution_allowed": False,
        }

    def has_broker_bindings(self, broker: str) -> bool:
        broker_name = str(broker).upper()
        with self._lock:
            return any(bound_broker == broker_name for bound_broker, _ in self._bindings)

    def certify_binding(
        self,
        broker: str,
        credential_name: str,
        *,
        native_handle_consumer: bool = False,
    ) -> None:
        if not native_handle_consumer:
            raise PermissionError("NATIVE_SECRET_HANDLE_CONSUMER_REQUIRED")
        broker_name = str(broker).upper()
        binding = self._bindings.get((broker_name, str(credential_name)))
        if not binding:
            raise KeyError("AUTHORITY_BINDING_NOT_FOUND")
        with self._lock:
            for resource_id, record in tuple(self._ownership.items()):
                if record.broker == broker_name and record.credential_name == credential_name:
                    self._ownership[resource_id] = OwnershipRecord(
                        **{
                            **record.__dict__,
                            "status": OwnershipStatus.ENTERPRISE_MANAGED,
                            "direct_access": False,
                        }
                    )

    def record_direct_access(self, *, broker: str, component: str, source_path: str) -> None:
        violation = {
            "broker": str(broker).upper(),
            "component": str(component),
            "source_path": str(source_path),
            "violation": "DIRECT_BROKER_CREDENTIAL_ACCESS",
            "execution_allowed": False,
        }
        with self._lock:
            if violation not in self._violations:
                self._violations.append(violation)

    def record_unknown_credential(
        self,
        *,
        broker: str,
        credential_name: str,
        component: str,
        source_path: str,
    ) -> None:
        record_id = f"UNKNOWN:{broker}:{credential_name}:{component}"
        with self._lock:
            self._ownership[record_id] = OwnershipRecord(
                resource_id=record_id,
                broker=str(broker).upper(),
                credential_name=str(credential_name),
                secret_uuid=None,
                status=OwnershipStatus.UNKNOWN,
                component=str(component),
                source_path=str(source_path),
                direct_access=True,
            )

    def scan_direct_access_paths(self, paths: tuple[str | Path, ...]) -> list[dict[str, Any]]:
        for raw_path in paths:
            path = Path(raw_path)
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            for match in _DIRECT_ACCESS.finditer(text):
                self.record_direct_access(
                    broker=match.group("broker"),
                    component=path.stem,
                    source_path=str(path),
                )
        return self.direct_access_violations()

    def scan_repository_direct_access(self, repository_root: str | Path) -> list[dict[str, Any]]:
        root = Path(repository_root)
        paths: list[Path] = []
        for relative in ("backend", "live_data", "dashboard"):
            parent = root / relative
            if not parent.exists():
                continue
            paths.extend(
                path
                for path in parent.rglob("*.py")
                if "backend/security/identity" not in path.as_posix()
            )
        return self.scan_direct_access_paths(tuple(paths))

    def ownership_inventory(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = [record.as_dict() for record in self._ownership.values()]
            bound = set(self._bindings.values())
        for metadata in self.service._inventory():
            if metadata["secret_uuid"] not in bound:
                rows.append(
                    OwnershipRecord(
                        resource_id=metadata["secret_uuid"],
                        broker=str(metadata.get("broker") or "NONE"),
                        credential_name=str(metadata.get("secret_type") or "UNKNOWN"),
                        secret_uuid=metadata["secret_uuid"],
                        status=OwnershipStatus.ORPHANED,
                        component="UNASSIGNED",
                        source_path="UNASSIGNED",
                        direct_access=False,
                    ).as_dict()
                )
        return rows

    def direct_access_violations(self) -> list[dict[str, Any]]:
        with self._lock:
            explicit = list(self._violations)
            compatibility = [
                {
                    "broker": row.broker,
                    "component": row.component,
                    "source_path": row.source_path,
                    "violation": (
                        "LEGACY_DIRECT_ACCESS_REMAINS"
                        if row.status is OwnershipStatus.LEGACY_COMPATIBILITY
                        else "UNKNOWN_DIRECT_ACCESS_REMAINS"
                    ),
                    "execution_allowed": False,
                }
                for row in self._ownership.values()
                if row.direct_access
            ]
        return [*explicit, *compatibility]

    def dependency_graph(self) -> dict[str, Any]:
        brokers = sorted({row["broker"] for row in self.ownership_inventory() if row["broker"] != "NONE"})
        edges = [
            {
                "from": broker,
                "to": "BrokerSecretCompatibilityAdapter",
            }
            for broker in brokers
        ]
        edges.extend(
            [
                {"from": "BrokerSecretCompatibilityAdapter", "to": "EnterpriseSecretService"},
                {"from": "EnterpriseSecretService", "to": "EnterpriseVault"},
            ]
        )
        return {
            "nodes": [*brokers, "BrokerSecretCompatibilityAdapter", "EnterpriseSecretService", "EnterpriseVault"],
            "edges": edges,
            "direct_access_violations": self.direct_access_violations(),
            "canonical_path": "Broker -> Compatibility Adapter -> Enterprise Secret Service -> Enterprise Vault",
            "automatic_rewrites": False,
            "execution_allowed": False,
        }

    def migration_status(self) -> dict[str, Any]:
        inventory = self.ownership_inventory()
        total = len(inventory)
        managed = sum(row["status"] == OwnershipStatus.ENTERPRISE_MANAGED.value for row in inventory)
        compatibility = sum(row["status"] == OwnershipStatus.LEGACY_COMPATIBILITY.value for row in inventory)
        orphaned = sum(row["status"] == OwnershipStatus.ORPHANED.value for row in inventory)
        return {
            "total": total,
            "enterprise_managed": managed,
            "legacy_compatibility": compatibility,
            "orphaned": orphaned,
            "unknown": sum(row["status"] == OwnershipStatus.UNKNOWN.value for row in inventory),
            "coverage_pct": round(100.0 * managed / total, 2) if total else 100.0,
            "complete": total == managed and not self.direct_access_violations(),
            "execution_allowed": False,
        }


__all__ = [
    "EnterpriseAuthorityRedirector",
    "OwnershipRecord",
    "OwnershipStatus",
]
