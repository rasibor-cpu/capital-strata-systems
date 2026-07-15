from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from dashboard.mission_control.active_runtime_source import (
    RuntimeSourceCandidate,
    SOURCE_RUNTIME_REGISTRY,
    SOURCE_UNAVAILABLE,
)
from dashboard.mission_control.runtime_artifact_reader import RuntimeArtifactReader
from dashboard.mission_control.runtime_endpoint_reader import RuntimeEndpointReader
from dashboard.mission_control.runtime_source_diagnostics import source_diagnostics
from dashboard.mission_control.serializers import state_hash


RuntimeSnapshotSource = Callable[[], Mapping[str, Any] | None]


class RuntimeSourceResolver:
    """Resolve Mission Control to the active runtime publisher without side effects."""

    def __init__(
        self,
        source: RuntimeSnapshotSource | None = None,
        *,
        artifact_root: str | Path = "artifacts",
        supervisor_state_path: str | Path = "runtime/supervisor/css_runtime_supervisor_state.json",
        endpoint_url: str | None = None,
        endpoint_timeout_seconds: float = 0.35,
    ) -> None:
        self.source = source
        self.artifact_root = Path(artifact_root)
        self.supervisor_state_path = Path(supervisor_state_path)
        self.endpoint_url = endpoint_url
        self.endpoint_timeout_seconds = float(endpoint_timeout_seconds)

    def resolve(self) -> dict[str, Any]:
        candidates = self._candidates()
        selected = next((candidate for candidate in candidates if candidate.available and isinstance(candidate.payload, Mapping)), None)
        diagnostics = source_diagnostics(selected=selected, candidates=candidates)
        if selected is None:
            payload: dict[str, Any] = {
                "source": SOURCE_UNAVAILABLE,
                "source_type": SOURCE_UNAVAILABLE,
                "source_name": "runtime_source_resolver",
                "runtime_source_diagnostics": diagnostics,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
            }
            return {
                "selected": None,
                "candidates": candidates,
                "diagnostics": diagnostics,
                "payload": payload,
            }

        payload = dict(selected.payload or {})
        payload["source"] = selected.source_type
        payload["source_type"] = selected.source_type
        payload["runtime_source_diagnostics"] = diagnostics
        payload["execution_allowed"] = False
        payload["live_trading_blocked"] = True
        payload["broker_execution_armed"] = False
        payload["advisory_only"] = True
        return {
            "selected": selected,
            "candidates": candidates,
            "diagnostics": diagnostics,
            "payload": payload,
        }

    def _candidates(self) -> list[RuntimeSourceCandidate]:
        registry = self._registry_candidate()
        endpoint = RuntimeEndpointReader(self.endpoint_url, timeout_seconds=self.endpoint_timeout_seconds).read_candidate()
        artifact_reader = RuntimeArtifactReader(
            artifact_root=self.artifact_root,
            supervisor_state_path=self.supervisor_state_path,
        )
        artifact = artifact_reader.read_candidate()
        cache = artifact_reader.read_cache_candidate()
        return [registry, endpoint, artifact, cache]

    def _registry_candidate(self) -> RuntimeSourceCandidate:
        if self.source is None:
            return RuntimeSourceCandidate(
                name="shared_runtime_registry",
                source_type=SOURCE_RUNTIME_REGISTRY,
                available=False,
                freshness_status="UNAVAILABLE",
                path_category="RUNTIME_REGISTRY",
                process_relationship="NO_SHARED_REGISTRY",
                failure="shared_runtime_registry_not_configured",
            )
        try:
            payload = self.source()
        except Exception as exc:
            return RuntimeSourceCandidate(
                name="shared_runtime_registry",
                source_type=SOURCE_RUNTIME_REGISTRY,
                available=False,
                freshness_status="UNAVAILABLE",
                path_category="RUNTIME_REGISTRY",
                process_relationship="IN_PROCESS_CALLBACK",
                failure=f"registry_callback_failed:{exc.__class__.__name__}",
            )
        if not isinstance(payload, Mapping):
            return RuntimeSourceCandidate(
                name="shared_runtime_registry",
                source_type=SOURCE_RUNTIME_REGISTRY,
                available=False,
                freshness_status="UNAVAILABLE",
                path_category="RUNTIME_REGISTRY",
                process_relationship="IN_PROCESS_CALLBACK",
                failure="registry_payload_empty",
            )
        cross_process_safe = bool(payload.get("mission_control_runtime_registry_cross_process_safe"))
        unavailable = str(payload.get("mission_control_data_source") or "").upper() == "UNAVAILABLE"
        wrapped = {
            "source": SOURCE_RUNTIME_REGISTRY,
            "source_type": SOURCE_RUNTIME_REGISTRY,
            "source_name": "shared_runtime_registry",
            "frontend_payload": dict(payload),
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }
        available = cross_process_safe and not unavailable
        failure = "" if available else "registry_not_cross_process_safe" if not cross_process_safe else "registry_payload_unavailable"
        return RuntimeSourceCandidate(
            name="shared_runtime_registry",
            source_type=SOURCE_RUNTIME_REGISTRY,
            available=available,
            freshness_status="FRESH" if available else "UNAVAILABLE",
            path_category="RUNTIME_REGISTRY",
            process_relationship="CROSS_PROCESS_REGISTRY" if cross_process_safe else "IN_PROCESS_CALLBACK_ONLY",
            generated_at=str(payload.get("generated_at") or payload.get("timestamp") or "UNAVAILABLE"),
            observed_at=str(payload.get("generated_at") or payload.get("timestamp") or "UNAVAILABLE"),
            failure=failure,
            fallback_reason="" if available else failure,
            state_hash=state_hash(wrapped),
            metadata={"cross_process_safe": cross_process_safe},
            payload=wrapped if available else None,
        )


__all__ = ["RuntimeSourceResolver", "RuntimeSnapshotSource"]
