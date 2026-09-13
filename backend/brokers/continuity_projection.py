from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .observation_ledger import ObservationLedger, ReconciliationLedger
from .readonly_domain import PortfolioSnapshot, SnapshotSource
from .readonly_reconciliation import ReconciliationResult


def build_continuity_state(
    snapshot: PortfolioSnapshot | None,
    *,
    snapshot_status: str = "UNAVAILABLE",
    ledger: ObservationLedger | None = None,
    reconciliation: ReconciliationResult | Mapping[str, Any] | None = None,
    last_provider_recovery_utc: datetime | None = None,
) -> dict[str, Any]:
    payload = snapshot.as_dict() if snapshot is not None else {}
    reconciliation_payload = reconciliation.as_dict() if hasattr(reconciliation, "as_dict") else dict(reconciliation or {})
    source = payload.get("snapshot_source", SnapshotSource.UNAVAILABLE.value)
    if snapshot_status == "CORRUPT":
        source = SnapshotSource.UNAVAILABLE.value
    return {
        "provider": payload.get("provider", "UNKNOWN"),
        "account_masked": payload.get("account_id_masked"),
        "snapshot_id": payload.get("snapshot_id"),
        "snapshot_source": source,
        "snapshot_status": snapshot_status,
        "snapshot_age_seconds": max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(payload["as_of_utc"]).astimezone(timezone.utc)).total_seconds())) if payload.get("as_of_utc") else None,
        "last_successful_sync_utc": payload.get("last_successful_sync_utc"),
        "last_observation_utc": payload.get("as_of_utc"),
        "ledger_status": "AVAILABLE" if ledger is not None else "UNAVAILABLE",
        "ledger_entry_count": ledger.entry_count if ledger is not None else 0,
        "freshness": payload.get("broker_data_freshness", "UNKNOWN"),
        "broker_health": payload.get("broker_health", "UNAVAILABLE"),
        "reconciliation_status": reconciliation_payload.get("status", "UNAVAILABLE"),
        "open_reconciliation_count": reconciliation_payload.get("issue_count", len(reconciliation_payload.get("findings", []))),
        "highest_reconciliation_severity": reconciliation_payload.get("highest_severity", "info"),
        "duplicate_observation_count": ledger.duplicate_count if ledger is not None else 0,
        "last_provider_recovery_utc": last_provider_recovery_utc.isoformat() if last_provider_recovery_utc else None,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        "read_only": True,
    }


__all__ = ["build_continuity_state"]
