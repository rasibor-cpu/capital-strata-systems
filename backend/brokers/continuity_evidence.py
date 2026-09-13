from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def export_continuity_evidence(
    output_json: str | Path,
    output_markdown: str | Path,
    *,
    continuity: Mapping[str, Any],
    snapshot: Mapping[str, Any] | None = None,
    observations: list[Mapping[str, Any]] | None = None,
    reconciliation: Mapping[str, Any] | None = None,
    audit_events: list[Mapping[str, Any]] | None = None,
    test_metadata: Mapping[str, Any] | None = None,
) -> None:
    def safe(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(key): safe(item) for key, item in value.items() if not any(part in str(key).lower() for part in ("token", "secret", "password", "authorization", "credential"))}
        if isinstance(value, list):
            return [safe(item) for item in value]
        return value

    payload = safe({"schema": "css.qro004x.evidence.v1", "continuity": continuity, "snapshot_lineage": {key: snapshot.get(key) for key in ("snapshot_id", "observation_ids", "prior_snapshot_id", "provider", "as_of_utc", "ingestion_utc", "snapshot_source") if snapshot and key in snapshot}, "observation_count": len(observations or []), "observations": observations or [], "reconciliation": reconciliation or {}, "audit_events": audit_events or [], "test_metadata": test_metadata or {}})
    json_path = Path(output_json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    markdown = "# QRO-004X Continuity Evidence\n\n"
    markdown += f"- Provider: `{payload['continuity'].get('provider', 'UNKNOWN')}`\n- Snapshot source: `{payload['continuity'].get('snapshot_source', 'UNAVAILABLE')}`\n- Snapshot status: `{payload['continuity'].get('snapshot_status', 'UNAVAILABLE')}`\n- Ledger entries: `{payload['observation_count']}`\n- Reconciliation status: `{payload['continuity'].get('reconciliation_status', 'UNAVAILABLE')}`\n- Execution allowed: `{payload['continuity'].get('execution_allowed', False)}`\n"
    Path(output_markdown).write_text(markdown, encoding="utf-8")


__all__ = ["export_continuity_evidence"]
