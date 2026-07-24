"""Production HealthChecker callbacks for the OperationsService host."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from backend.events.event_models import Event
from backend.operations.operations_models import create_health_check_event
from backend.runtime.broker_readiness_consolidation import build_canonical_broker_readiness
from backend.runtime.canonical_runtime_snapshot import build_canonical_runtime_snapshot
from backend.runtime.runtime_artifact_freshness import RuntimeArtifactFreshnessManager


RuntimeSnapshotSource = Callable[[], Mapping[str, Any] | None]

PASS_STATUSES = {"PASS", "OK", "GREEN", "READY", "HEALTHY", "OPEN", "CLEAR", "AUTHORIZED"}
WARN_STATUSES = {"WARN", "WARNING", "AMBER", "DEGRADED", "AGING", "BLOCKED", "CLOSED", "REJECTING"}
FAIL_STATUSES = {"FAIL", "FAILED", "ERROR", "RED", "CRITICAL", "STALE", "MISSING", "UNAVAILABLE", "DATA UNAVAILABLE"}


class OperationsHealthEvidenceProvider:
    """Read-only adapter over canonical runtime artifacts for operations checks."""

    def __init__(
        self,
        *,
        artifacts_dir: str | Path = "artifacts",
        supervisor_state_path: str | Path = "runtime/supervisor/css_runtime_supervisor_state.json",
        runtime_snapshot_source: RuntimeSnapshotSource | None = None,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir)
        self.supervisor_state_path = Path(supervisor_state_path)
        self.runtime_snapshot_source = runtime_snapshot_source

    def freshness(self) -> dict[str, Any]:
        return RuntimeArtifactFreshnessManager(
            artifacts_dir=self.artifacts_dir,
            supervisor_state_path=self.supervisor_state_path,
        ).evaluate(runtime_active=None, refresh=False)

    def runtime_payload(self) -> dict[str, Any]:
        if self.runtime_snapshot_source is not None:
            try:
                payload = self.runtime_snapshot_source()
            except Exception as exc:
                return {"source": "UNAVAILABLE", "source_error": f"{exc.__class__.__name__}: {exc}"}
            return dict(payload) if isinstance(payload, Mapping) else {}

        frontend = self._read_json(self.artifacts_dir / "frontend_state.json")
        if frontend:
            return {"frontend_payload": frontend, "source": "CACHE"}

        return {
            "source": "CACHE",
            "supervisor": self._read_json(self.supervisor_state_path),
            "session": self._read_json(self.artifacts_dir / "css_session_state_pcnrass.json"),
            "account": self._read_json(self.artifacts_dir / "css_account_state_pcnrass.json"),
            "runtime_portfolio_state": self._read_json(self.artifacts_dir / "runtime_portfolio_state.json"),
            "runtime_advisory_snapshot": self._read_json(self.artifacts_dir / "runtime_advisory_snapshot.json"),
            "portfolio_snapshot": self._read_json(self.artifacts_dir / "portfolio_snapshot.json"),
            "portfolio_decision": self._read_json(self.artifacts_dir / "portfolio_decision.json"),
            "validation_summary": self._read_json(self.artifacts_dir / "validation_summary.json"),
        }

    def runtime_snapshot(self) -> dict[str, Any]:
        payload = self.runtime_payload()
        frontend = payload.get("frontend_payload") if isinstance(payload.get("frontend_payload"), Mapping) else None
        return build_canonical_runtime_snapshot(
            payload,
            frontend,
            source_name="backend.operations.health_checkers",
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                return dict(payload) if isinstance(payload, Mapping) else {}
        except Exception:
            return {}
        return {}


def build_production_health_checkers(
    *,
    artifacts_dir: str | Path = "artifacts",
    supervisor_state_path: str | Path = "runtime/supervisor/css_runtime_supervisor_state.json",
    runtime_snapshot_source: RuntimeSnapshotSource | None = None,
) -> dict[str, Callable[[], Event]]:
    provider = OperationsHealthEvidenceProvider(
        artifacts_dir=artifacts_dir,
        supervisor_state_path=supervisor_state_path,
        runtime_snapshot_source=runtime_snapshot_source,
    )
    return {
        "runtime_heartbeat": runtime_heartbeat_checker(provider),
        "risk_gate": risk_gate_checker(provider),
        "broker_readiness": broker_readiness_checker(provider),
    }


def runtime_heartbeat_checker(provider: OperationsHealthEvidenceProvider) -> Callable[[], Event]:
    def _check() -> Event:
        started = time.perf_counter()
        freshness = provider.freshness()
        supervisor = _mapping(_mapping(freshness.get("artifacts")).get("supervisor_state"))
        authority = _mapping(freshness.get("canonical_authority"))
        heartbeat_status = str(supervisor.get("freshness") or "MISSING").upper()
        blockers = _list(freshness.get("blockers"))

        if heartbeat_status in {"FRESH"} and not blockers and authority.get("canonical_alive", True):
            status = "OK"
            message = "Canonical runtime heartbeat is fresh"
        elif heartbeat_status == "AGING" and not blockers and authority.get("canonical_alive", True):
            status = "WARN"
            message = "Canonical runtime heartbeat is aging"
        else:
            status = "CRITICAL"
            message = "Canonical runtime heartbeat is stale or unavailable"

        return _event(
            "runtime_heartbeat",
            status,
            message,
            started,
            {
                "heartbeat_status": heartbeat_status,
                "freshness_status": freshness.get("freshness_status"),
                "blockers": blockers,
                "warnings": _list(freshness.get("warnings")),
                "supervisor_state": supervisor,
                "canonical_authority": authority,
                "execution_allowed": False,
                "advisory_only": True,
            },
        )

    return _check


def risk_gate_checker(provider: OperationsHealthEvidenceProvider) -> Callable[[], Event]:
    def _check() -> Event:
        started = time.perf_counter()
        snapshot = provider.runtime_snapshot()
        risk = _mapping(snapshot.get("risk"))
        risk_status = str(risk.get("risk_status") or "").upper()
        trade_gate_status = str(risk.get("trade_gate_status") or risk.get("gate_status") or "").upper()
        normalized = _normalize_status(risk_status, trade_gate_status)

        if normalized == "OK":
            message = "Risk gate evidence is present and controlled"
        elif normalized == "WARN":
            message = "Risk gate is restricting execution"
        else:
            message = "Risk gate evidence failed or is unavailable"

        return _event(
            "risk_gate",
            normalized,
            message,
            started,
            {
                "risk_status": risk_status or "UNAVAILABLE",
                "trade_gate_status": trade_gate_status or "UNAVAILABLE",
                "runtime_state_hash": snapshot.get("state_hash"),
                "runtime_source": snapshot.get("source"),
                "execution_allowed": False,
                "advisory_only": True,
            },
        )

    return _check


def broker_readiness_checker(provider: OperationsHealthEvidenceProvider) -> Callable[[], Event]:
    def _check() -> Event:
        started = time.perf_counter()
        payload = provider.runtime_payload()
        frontend = _mapping(payload.get("frontend_payload"))
        sections = _mapping(frontend.get("sections"))
        broker_section = _mapping(sections.get("broker"))
        certification = _mapping(sections.get("runtime_certification_snapshot"))
        snapshot = build_canonical_runtime_snapshot(
            payload,
            frontend if frontend else None,
            source_name="backend.operations.health_checkers",
        )
        runtime_broker = _mapping(snapshot.get("broker"))
        readiness = build_canonical_broker_readiness(
            broker_section=broker_section,
            runtime_snapshot=snapshot,
            certification_snapshot=certification,
        )
        overall = str(readiness.get("overall_status") or "UNAVAILABLE").upper()

        if not _has_broker_evidence(broker_section, runtime_broker):
            status = "CRITICAL"
            message = "Broker readiness evidence is missing"
        elif overall == "GREEN":
            status = "OK"
            message = "Broker readiness is green"
        elif overall == "AMBER":
            status = "WARN"
            message = "Broker readiness is degraded but observable"
        else:
            status = "CRITICAL"
            message = "Broker readiness failed or is unavailable"

        return _event(
            "broker_readiness",
            status,
            message,
            started,
            {
                "broker": readiness.get("broker"),
                "overall_status": overall,
                "readiness_score": readiness.get("readiness_score"),
                "failure_reason": readiness.get("failure_reason"),
                "operational_state": readiness.get("operational_state"),
                "ready_for_read_only_validation": readiness.get("ready_for_read_only_validation"),
                "runtime_state_hash": snapshot.get("state_hash"),
                "execution_allowed": False,
                "advisory_only": True,
            },
        )

    return _check


def _event(component: str, status: str, message: str, started: float, details: Mapping[str, Any]) -> Event:
    return create_health_check_event(
        component=component,
        status=status,
        message=message,
        latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
        details=dict(details),
    )


def _normalize_status(*values: Any) -> str:
    observed = [str(value or "").strip().upper() for value in values if value not in (None, "")]
    if not observed:
        return "CRITICAL"
    if any(value in FAIL_STATUSES for value in observed):
        return "CRITICAL"
    if any(value in WARN_STATUSES for value in observed):
        return "WARN"
    if any(value in PASS_STATUSES for value in observed):
        return "OK"
    return "CRITICAL"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _has_broker_evidence(*payloads: Mapping[str, Any]) -> bool:
    for payload in payloads:
        data = _mapping(payload)
        for key in ("selected_broker", "broker", "overall_status", "broker_health", "readiness", "authentication"):
            value = data.get(key)
            if str(value or "").strip().upper() not in {"", "UNAVAILABLE", "DATA UNAVAILABLE", "UNKNOWN", "NONE"}:
                return True
    return False


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if value in (None, ""):
        return []
    return [value]


__all__ = [
    "OperationsHealthEvidenceProvider",
    "RuntimeSnapshotSource",
    "build_production_health_checkers",
    "broker_readiness_checker",
    "risk_gate_checker",
    "runtime_heartbeat_checker",
]
