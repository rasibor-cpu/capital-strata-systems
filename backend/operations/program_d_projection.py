from __future__ import annotations

from typing import Any

from .executive_command import ExecutiveCommandSnapshot
from .executive_report import build_executive_operational_report


def build_program_d_projection(
    snapshot: ExecutiveCommandSnapshot,
    *,
    backup_recovery: dict[str, Any] | None = None,
    incident_rollup: dict[str, Any] | None = None,
    project_atlas: dict[str, Any] | None = None,
    improvement_register: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose a read-only Program D enterprise operations projection."""

    return {
        "schema_version": "css.program_d.enterprise_projection.v1",
        "executive": build_executive_operational_report(snapshot),
        "backup_recovery": backup_recovery or {
            "overall_status": "UNKNOWN",
            "evidence_count": 0,
            "items": [],
        },
        "incident_rollup": incident_rollup or {
            "open_incident_count": 0,
            "highest_open_severity": "INFO",
            "open_by_domain": {},
            "incidents": [],
        },
        "project_atlas": project_atlas or {
            "entry_count": 0,
            "entries": [],
            "read_only": True,
        },
        "continuous_improvement": improvement_register or {
            "total_items": 0,
            "open_items": 0,
            "items": [],
            "read_only": True,
        },
        "safety": {
            "execution_allowed": False,
            "broker_execution_armed": False,
            "money_movement_authorized": False,
            "live_trading_authorized": False,
        },
        "read_only": True,
    }
