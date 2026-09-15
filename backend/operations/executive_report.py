from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from .capacity_summary import CapacitySummary
from .executive_command import ExecutiveCommandSnapshot


def build_executive_operational_report(
    snapshot: ExecutiveCommandSnapshot,
    *,
    capacity: CapacitySummary | None = None,
) -> dict[str, Any]:
    """Build a deterministic, export-safe executive operations report."""

    report: dict[str, Any] = {
        "schema_version": "css.program_d.executive_report.v1",
        "observed_at_utc": snapshot.observed_at_utc.isoformat(),
        "operating_posture": snapshot.operating_posture,
        "attention_level": snapshot.attention_level,
        "blockers": list(snapshot.blockers),
        "warnings": list(snapshot.warnings),
        "dimensions": dict(sorted(snapshot.dimensions.items())),
        "safety": {
            "execution_allowed": False,
            "broker_execution_armed": False,
            "money_movement_authorized": False,
            "live_trading_authorized": False,
        },
    }
    if capacity is not None:
        report["capacity"] = {
            "status": capacity.status,
            "warnings": list(capacity.warnings),
            "metrics": dict(sorted(capacity.metrics.items())),
        }

    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    report["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    return report


def render_executive_operational_report_json(report: dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, indent=2) + "\n"
