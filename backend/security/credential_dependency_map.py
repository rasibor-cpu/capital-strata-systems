"""ESMS-002 reverse credential dependency graph."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CredentialDependency:
    vcid: str
    consumer: str
    service_tier: str
    required: bool
    safe_to_pause: bool
    rollback_supported: bool


class CredentialDependencyMap:
    def __init__(self):
        self._dependencies: dict[str, dict[str, CredentialDependency]] = {}

    def register(
        self,
        vcid: str,
        consumer: str,
        *,
        service_tier: str = "ADVISORY",
        required: bool = True,
        safe_to_pause: bool = True,
        rollback_supported: bool = True,
    ) -> CredentialDependency:
        if not str(vcid).startswith("VCID-"):
            raise ValueError("INVALID_VCID")
        dependency = CredentialDependency(
            vcid=str(vcid),
            consumer=str(consumer),
            service_tier=str(service_tier).upper(),
            required=bool(required),
            safe_to_pause=bool(safe_to_pause),
            rollback_supported=bool(rollback_supported),
        )
        self._dependencies.setdefault(vcid, {})[consumer] = dependency
        return dependency

    def consumers(self, vcid: str) -> tuple[CredentialDependency, ...]:
        return tuple(self._dependencies.get(str(vcid), {}).values())

    def credentials_for_consumer(self, consumer: str) -> tuple[str, ...]:
        return tuple(
            sorted(vcid for vcid, rows in self._dependencies.items() if consumer in rows)
        )

    def remove(self, vcid: str, consumer: str) -> bool:
        return self._dependencies.get(str(vcid), {}).pop(str(consumer), None) is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "css.credential.dependencies.v1",
            "credentials": {
                vcid: [asdict(row) for row in rows.values()]
                for vcid, rows in self._dependencies.items()
            },
            "contains_secrets": False,
            "execution_allowed": False,
        }


__all__ = ["CredentialDependency", "CredentialDependencyMap"]
