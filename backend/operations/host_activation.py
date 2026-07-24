"""Canonical OperationsService host activation (AR-028 / AR-029 / AR-030)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.operations.operations_service import OperationsService
    from backend.operations.health_checkers import RuntimeSnapshotSource
    from backend.events.event_models import Event

REQUIRED_CHECKERS_DEFAULT = (
    "runtime_heartbeat",
    "risk_gate",
    "broker_readiness",
)


class OperationsActivationError(RuntimeError):
    """Raised when required operations checkers are missing (fail-closed)."""


def activate_operations_service(
    *,
    artifacts_dir: str | Path | None = None,
    required_checkers: Iterable[str] | None = None,
    register_defaults: bool = True,
    runtime_artifacts_dir: str | Path | None = None,
    supervisor_state_path: str | Path | None = None,
    runtime_snapshot_source: "RuntimeSnapshotSource | None" = None,
) -> "OperationsService":
    """
    Instantiate OperationsService for a canonical host with required checkers.

    Startup fails closed if any required checker is missing.
    """
    # Lazy imports avoid circular import via operations package __init__.
    from backend.common.configuration import OperationsConfig
    from backend.operations.health_monitor import HealthMonitor
    from backend.operations.health_checkers import build_production_health_checkers
    from backend.operations.operational_state_manager import OperationalStateManager
    from backend.operations.operational_timeline import OperationalTimeline
    from backend.operations.operations_service import OperationsService
    from backend.operations.runtime_statistics import RuntimeStatistics

    root = Path(artifacts_dir or os.getenv("CSS_OPS_ARTIFACTS_DIR") or "artifacts/operations")
    root.mkdir(parents=True, exist_ok=True)

    monitor = HealthMonitor()
    required = tuple(required_checkers or REQUIRED_CHECKERS_DEFAULT)

    if register_defaults:
        concrete = build_production_health_checkers(
            artifacts_dir=runtime_artifacts_dir or os.getenv("CSS_RUNTIME_ARTIFACTS_DIR") or "artifacts",
            supervisor_state_path=supervisor_state_path
            or os.getenv("CSS_RUNTIME_SUPERVISOR_STATE_PATH")
            or "runtime/supervisor/css_runtime_supervisor_state.json",
            runtime_snapshot_source=runtime_snapshot_source,
        )
        for name in required:
            checker = concrete.get(name)
            if checker is not None:
                monitor.register_checker(name, checker)

    missing = monitor.require_checkers(list(required))
    if missing:
        raise OperationsActivationError(
            f"REQUIRED_CHECKERS_MISSING:{','.join(missing)}"
        )

    config = OperationsConfig(default_source="ops_host")
    service = OperationsService(
        config=config,
        monitor=monitor,
        state_manager=OperationalStateManager(file_path=str(root / "state.json")),
        timeline=OperationalTimeline(file_path=str(root / "timeline.json")),
        statistics=RuntimeStatistics(),
    )
    return service


def run_host_observability_tick(
    service: "OperationsService | None" = None,
    diagnostics: "Event | None" = None,
) -> dict:
    """
    Heartbeat: diagnostics + metrics persist + alert retention (AR-028/029/030).
    """
    from backend.metrics import get_default_metrics_service
    from backend.monitoring.css_alert_repository import CSSAlertRepository

    ops = service or activate_operations_service()
    state = diagnostics or ops.run_diagnostics()

    metrics = get_default_metrics_service()
    persist_ok = False
    try:
        snapshot = metrics.persist_snapshot()
        persist_ok = snapshot is not None
        persist_path = "ok" if persist_ok else "empty"
    except Exception as exc:  # noqa: BLE001 — observability must not crash host
        persist_path = f"persist_failed:{exc}"
        persist_ok = False
    purged = 0
    try:
        purged = CSSAlertRepository().purge_old_alerts(keep_latest=500)
    except Exception:
        purged = 0

    return {
        "operations_status": state.payload.get("overall_status"),
        "health_score": state.payload.get("health_score"),
        "metrics_persist": persist_path,
        "metrics_persist_ok": persist_ok,
        "alerts_purged": purged,
        "monitoring_authority": "CSSAlertRepository",
        "monitoring_production_pager": False,
    }
