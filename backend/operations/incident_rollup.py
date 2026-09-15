from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


_SEVERITIES = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
_DOMAINS = {"SECURITY", "GOVERNANCE", "OPERATIONS", "BROKER", "RUNTIME", "DATA", "RECONCILIATION"}


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("timestamp must be timezone-aware UTC")


@dataclass(frozen=True)
class OperationalIncident:
    incident_id: str
    domain: str
    severity: str
    status: str
    opened_at_utc: datetime
    summary: str

    def __post_init__(self) -> None:
        if not self.incident_id.strip() or not self.summary.strip():
            raise ValueError("incident id and summary are required")
        _require_utc(self.opened_at_utc)
        if self.domain.upper() not in _DOMAINS:
            raise ValueError("unsupported incident domain")
        if self.severity.upper() not in _SEVERITIES:
            raise ValueError("unsupported incident severity")
        if self.status.upper() not in {"OPEN", "RESOLVED"}:
            raise ValueError("unsupported incident status")


def build_incident_rollup(items: Iterable[OperationalIncident]) -> dict:
    rows = list(items)
    open_rows = [row for row in rows if row.status.upper() == "OPEN"]
    highest = max((row.severity.upper() for row in open_rows), key=lambda s: _SEVERITIES[s], default="INFO")
    by_domain = {}
    for row in open_rows:
        domain = row.domain.upper()
        by_domain[domain] = by_domain.get(domain, 0) + 1

    return {
        "schema_version": "css.program_d.incident_rollup.v1",
        "open_incident_count": len(open_rows),
        "highest_open_severity": highest,
        "open_by_domain": dict(sorted(by_domain.items())),
        "attention_required": highest in {"HIGH", "CRITICAL"},
        "incidents": [
            {
                "incident_id": row.incident_id,
                "domain": row.domain.upper(),
                "severity": row.severity.upper(),
                "status": row.status.upper(),
                "opened_at_utc": row.opened_at_utc.isoformat(),
                "summary": row.summary,
            }
            for row in sorted(rows, key=lambda x: (x.status.upper() != "OPEN", -_SEVERITIES[x.severity.upper()], x.incident_id))
        ],
        "execution_allowed": False,
        "broker_execution_armed": False,
    }
