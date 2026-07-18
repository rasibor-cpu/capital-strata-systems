from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.runtime.runtime_artifact_freshness import RuntimeArtifactFreshnessManager
from dashboard.mission_control.active_runtime_source import (
    RuntimeSourceCandidate,
    SOURCE_HISTORICAL,
    SOURCE_RUNTIME_ARTIFACT,
)
from dashboard.mission_control.serializers import state_hash


class RuntimeArtifactReader:
    """Read the existing desktop runtime publisher artifacts without side effects."""

    def __init__(
        self,
        *,
        artifact_root: str | Path = "artifacts",
        supervisor_state_path: str | Path = "runtime/supervisor/css_runtime_supervisor_state.json",
    ) -> None:
        self.artifact_root = Path(artifact_root)
        self.supervisor_state_path = Path(supervisor_state_path)
        self.paths = {
            "supervisor": self.supervisor_state_path,
            "session": self.artifact_root / "css_session_state_pcnrass.json",
            "account": self.artifact_root / "css_account_state_pcnrass.json",
            "runtime_portfolio_state": self.artifact_root / "runtime_portfolio_state.json",
            "runtime_advisory_snapshot": self.artifact_root / "runtime_advisory_snapshot.json",
            "portfolio_snapshot": self.artifact_root / "portfolio_snapshot.json",
            "portfolio_decision": self.artifact_root / "portfolio_decision.json",
            "validation_summary": self.artifact_root / "validation_summary.json",
        }

    def read_candidate(self) -> RuntimeSourceCandidate:
        payloads = {name: self._read_json(path) for name, path in self.paths.items()}
        freshness = self._freshness()
        artifacts = freshness.get("artifacts") if isinstance(freshness.get("artifacts"), Mapping) else {}
        critical_names = ("supervisor", "session", "account")
        critical_available = all(isinstance(payloads.get(name), Mapping) and bool(payloads.get(name)) for name in critical_names)
        freshness_status = str(freshness.get("freshness_status") or "UNAVAILABLE").upper()
        canonical_authority = freshness.get("canonical_authority") if isinstance(freshness.get("canonical_authority"), Mapping) else {}
        canonical_alive = bool(canonical_authority.get("canonical_alive"))
        active = critical_available and freshness_status in {"GREEN", "AMBER"} and canonical_alive
        source_type = SOURCE_RUNTIME_ARTIFACT if active else SOURCE_HISTORICAL if any(payloads.values()) else SOURCE_RUNTIME_ARTIFACT
        failure = ""
        if not any(payloads.values()):
            failure = "runtime_artifacts_missing"
        elif not critical_available:
            failure = "critical_runtime_artifacts_missing"
        elif canonical_authority.get("orphan_runtime"):
            failure = "orphaned_runtime_detected"
        elif not canonical_alive:
            failure = f"canonical_runtime_not_alive:{canonical_authority.get('authority_status', 'UNKNOWN')}"
        elif freshness_status not in {"GREEN", "AMBER"}:
            failure = f"runtime_artifacts_not_fresh:{freshness_status}"

        payload = {
            "source": source_type,
            "source_type": source_type,
            "source_name": "runtime_artifact_reader",
            "supervisor": payloads["supervisor"],
            "session": payloads["session"],
            "account": payloads["account"],
            "runtime_portfolio_state": payloads["runtime_portfolio_state"],
            "runtime_advisory_snapshot": payloads["runtime_advisory_snapshot"],
            "portfolio_snapshot": payloads["portfolio_snapshot"],
            "portfolio_decision": payloads["portfolio_decision"],
            "validation_summary": payloads["validation_summary"],
            "runtime_source_diagnostics": {
                "source_type": source_type,
                "freshness": freshness,
                "paths": self._path_metadata(artifacts),
                "publisher": "scripts.css_live_dashboard.pcnrass_publish_runtime_artifacts",
                "publisher_module": "backend.runtime.runtime_artifact_publisher.RuntimeArtifactPublisher",
                "read_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
            },
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }
        digest = state_hash(payload)
        return RuntimeSourceCandidate(
            name="desktop_runtime_artifacts",
            source_type=source_type,
            available=active,
            freshness_status=freshness_status,
            path_category="ACTIVE_RUNTIME_ARTIFACTS",
            process_relationship="CROSS_PROCESS_FILE_ARTIFACT",
            generated_at=self._generated_at(payloads),
            observed_at=self._observed_at(payloads),
            failure=failure,
            fallback_reason="" if active else failure,
            state_hash=digest,
            metadata=payload["runtime_source_diagnostics"],
            payload=payload,
        )

    def read_cache_candidate(self) -> RuntimeSourceCandidate:
        path = self.artifact_root / "frontend_state.json"
        payload = self._read_json(path)
        active = bool(payload)
        wrapped = {
            "source": "CACHE",
            "source_type": "CACHE",
            "source_name": "frontend_state_cache",
            "frontend_payload": payload,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }
        return RuntimeSourceCandidate(
            name="frontend_state_cache",
            source_type="CACHE",
            available=active,
            freshness_status="FRESH" if active else "UNAVAILABLE",
            path_category="FRESH_CACHE",
            process_relationship="CROSS_PROCESS_FILE_CACHE",
            generated_at=str(payload.get("generated_at") or payload.get("timestamp") or "UNAVAILABLE") if isinstance(payload, Mapping) else "UNAVAILABLE",
            observed_at=str(payload.get("generated_at") or payload.get("timestamp") or "UNAVAILABLE") if isinstance(payload, Mapping) else "UNAVAILABLE",
            failure="" if active else "frontend_state_cache_missing",
            fallback_reason="" if active else "frontend_state_cache_missing",
            state_hash=state_hash(wrapped) if active else "UNAVAILABLE",
            metadata={"path": str(path), "exists": path.exists()},
            payload=wrapped if active else None,
        )

    def _freshness(self) -> dict[str, Any]:
        try:
            return RuntimeArtifactFreshnessManager(
                artifacts_dir=self.artifact_root,
                supervisor_state_path=self.supervisor_state_path,
            ).evaluate(runtime_active=None, refresh=False)
        except Exception as exc:
            return {
                "freshness_status": "RED",
                "blockers": [f"freshness_error:{exc.__class__.__name__}"],
                "warnings": [],
                "artifacts": {},
                "advisory_only": True,
                "execution_allowed": False,
            }

    def _path_metadata(self, artifacts: Mapping[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, path in self.paths.items():
            state = artifacts.get({"supervisor": "supervisor_state", "session": "session_state", "account": "account_state"}.get(name, name))
            result[name] = {
                "path": str(path),
                "exists": path.exists(),
                "freshness": state.get("freshness", "UNKNOWN") if isinstance(state, Mapping) else "UNKNOWN",
                "age_seconds": state.get("age_seconds") if isinstance(state, Mapping) else None,
            }
        return result

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                return dict(payload) if isinstance(payload, Mapping) else {}
        except Exception:
            return {}
        return {}

    @staticmethod
    def _generated_at(payloads: Mapping[str, Mapping[str, Any]]) -> str:
        for payload in payloads.values():
            if isinstance(payload, Mapping):
                value = payload.get("generated_at") or payload.get("timestamp")
                if value:
                    return str(value)
        return "UNAVAILABLE"

    @staticmethod
    def _observed_at(payloads: Mapping[str, Mapping[str, Any]]) -> str:
        supervisor = payloads.get("supervisor")
        if isinstance(supervisor, Mapping):
            value = supervisor.get("last_heartbeat") or supervisor.get("last_heartbeat_at")
            if value:
                return str(value)
        return RuntimeArtifactReader._generated_at(payloads)


__all__ = ["RuntimeArtifactReader"]
