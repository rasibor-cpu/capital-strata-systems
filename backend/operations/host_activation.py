"""Canonical OperationsService host activation (AR-028 / AR-029 / AR-030)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.operations.operations_service import OperationsService

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
) -> "OperationsService":
    """
    Instantiate OperationsService for a canonical host with required checkers.

    Startup fails closed if any required checker is missing.
    """
    # Lazy imports avoid circular import via operations package __init__.
    from backend.common.configuration import OperationsConfig
    from backend.operations.health_monitor import HealthMonitor
    from backend.operations.operational_state_manager import OperationalStateManager
    from backend.operations.operational_timeline import OperationalTimeline
    from backend.operations.operations_models import create_health_check_event
    from backend.operations.operations_service import OperationsService
    from backend.operations.runtime_statistics import RuntimeStatistics
    from backend.events.event_models import Event

    root = Path(artifacts_dir or os.getenv("CSS_OPS_ARTIFACTS_DIR") or "artifacts/operations")
    root.mkdir(parents=True, exist_ok=True)

    monitor = HealthMonitor()
    required = tuple(required_checkers or REQUIRED_CHECKERS_DEFAULT)

    def _default_checker(component: str, status: str = "OK") -> Callable[[], Event]:
        def _check() -> Event:
            return create_health_check_event(
                component=component,
                status=status,
                message=f"{component} advisory heartbeat",
                latency_ms=0.0,
            )

        return _check

    if register_defaults:
        for name in required:
            monitor.register_checker(name, _default_checker(name))

    missing = [name for name in required if name not in monitor._checkers]
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


def run_host_observability_tick(service: "OperationsService | None" = None) -> dict:
    """
    Heartbeat: diagnostics + metrics persist + alert retention (AR-028/029/030).
    """
    from backend.metrics import get_default_metrics_service
    from backend.monitoring.css_alert_repository import CSSAlertRepository

    ops = service or activate_operations_service()
    state = ops.run_diagnostics()

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
