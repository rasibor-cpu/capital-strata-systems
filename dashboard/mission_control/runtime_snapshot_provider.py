from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from dashboard.mission_control.runtime_snapshot_normalizer import normalize_runtime_snapshot, offline_runtime_snapshot
from dashboard.mission_control.runtime_source_resolver import RuntimeSourceResolver


RuntimeSnapshotSource = Callable[[], Mapping[str, Any] | None]


class RuntimeSnapshotProvider:
    def __init__(
        self,
        source: RuntimeSnapshotSource | None = None,
        *,
        artifact_root: str | Path = "artifacts",
        supervisor_state_path: str | Path = "runtime/supervisor/css_runtime_supervisor_state.json",
        active_source_binding: bool = False,
        endpoint_url: str | None = None,
    ) -> None:
        self._source = source
        self.artifact_root = Path(artifact_root)
        self.supervisor_state_path = Path(supervisor_state_path)
        self.active_source_binding = bool(active_source_binding)
        self.endpoint_url = endpoint_url

    def get_snapshot(self) -> dict[str, Any]:
        if self.active_source_binding:
            return self.get_state_payload()["runtime_snapshot"]

        if self._source is not None:
            try:
                payload = self._source()
            except Exception as exc:
                return offline_runtime_snapshot(reason=f"in_process_source_error:{exc.__class__.__name__}")
            if isinstance(payload, Mapping):
                return normalize_runtime_snapshot(payload, source_name="in_process_runtime_source")
            return offline_runtime_snapshot(reason="in_process_source_empty")

        artifact_payload = self._artifact_payload()
        if artifact_payload:
            return normalize_runtime_snapshot(artifact_payload, source_name="runtime_artifacts")
        return offline_runtime_snapshot(reason="no_runtime_artifacts")

    def get_state_payload(self) -> dict[str, Any]:
        if not self.active_source_binding:
            snapshot = self.get_snapshot()
            return {
                "runtime_snapshot": snapshot,
                "source": snapshot.get("source", "UNAVAILABLE"),
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
            }

        resolved = RuntimeSourceResolver(
            self._source,
            artifact_root=self.artifact_root,
            supervisor_state_path=self.supervisor_state_path,
            endpoint_url=self.endpoint_url,
        ).resolve()
        payload = resolved.get("payload") if isinstance(resolved.get("payload"), Mapping) else {}
        if str(payload.get("source_type") or payload.get("source") or "").upper() == "UNAVAILABLE":
            snapshot = offline_runtime_snapshot(
                reason="active_runtime_source_unavailable",
                source_name="runtime_source_resolver",
            )
            snapshot["source_diagnostics"] = dict(resolved.get("diagnostics", {}))
        else:
            snapshot = normalize_runtime_snapshot(payload, source_name="runtime_source_resolver")
        frontend_payload = payload.get("frontend_payload") if isinstance(payload.get("frontend_payload"), Mapping) else None
        return {
            "runtime_snapshot": snapshot,
            "frontend_payload": frontend_payload,
            "source": snapshot.get("source", payload.get("source", "UNAVAILABLE")),
            "runtime_source_diagnostics": resolved.get("diagnostics", {}),
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }

    def _artifact_payload(self) -> dict[str, Any]:
        frontend = self._read_json(self.artifact_root / "frontend_state.json")
        if isinstance(frontend, Mapping) and frontend:
            return {"frontend_payload": dict(frontend), "source": "CACHE"}

        supervisor = self._read_json(self.supervisor_state_path)
        if not supervisor and not self.supervisor_state_path.is_absolute():
            supervisor = self._read_json(Path.cwd() / self.supervisor_state_path)
        session = self._read_json(self.artifact_root / "css_session_state_pcnrass.json")
        account = self._read_json(self.artifact_root / "css_account_state_pcnrass.json")
        if not any(isinstance(item, Mapping) and item for item in (supervisor, session, account)):
            return {}

        return {
            "source": "CACHE",
            "supervisor": supervisor if isinstance(supervisor, Mapping) else {},
            "session": session if isinstance(session, Mapping) else {},
            "account": account if isinstance(account, Mapping) else {},
        }

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                return dict(payload) if isinstance(payload, Mapping) else {}
        except Exception:
            return {}
        return {}


def get_runtime_snapshot(source: RuntimeSnapshotSource | None = None) -> dict[str, Any]:
    return RuntimeSnapshotProvider(source).get_snapshot()


__all__ = ["RuntimeSnapshotProvider", "RuntimeSnapshotSource", "get_runtime_snapshot"]
