from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Tuple

from backend.app.period_close import get_period


SNAPSHOT_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class PeriodSnapshotArtifact:
    period_type: str
    period_value: str
    snapshot_path: str
    printable_path: str
    integrity_hash: str
    version: str


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _hash_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()


def _validate_period_type(period_type: str) -> str:
    normalized = (period_type or "").strip().upper()
    if normalized not in {"DAY", "MONTH", "YEAR"}:
        raise ValueError("period_type must be DAY, MONTH, or YEAR")
    return normalized


def _require_closed_period(
    period_type: str,
    period_value: str,
) -> None:
    if period_type not in {"MONTH", "YEAR"}:
        return
    period = get_period(period_type, period_value)
    if period["state"] not in {"CLOSED", "LOCKED"}:
        raise RuntimeError(
            f"{period_type} {period_value} must be CLOSED or LOCKED "
            "before snapshot"
        )


def create_period_snapshot(
    *,
    period_type: str,
    period_value: str,
    created_at: str,
    created_by: str,
    journal_digest: Mapping[str, Any],
    gl_balances: Mapping[str, Any],
    financial_statements: Mapping[str, Any] | None = None,
    output_dir: Path,
) -> PeriodSnapshotArtifact:
    normalized = _validate_period_type(period_type)
    if not period_value or period_value != period_value.strip():
        raise ValueError("period_value is required and must be canonical")
    if not created_at or created_at != created_at.strip():
        raise ValueError("created_at is required")
    if not created_by or created_by != created_by.strip():
        raise ValueError("created_by is required")
    _require_closed_period(normalized, period_value)

    payload = {
        "version": SNAPSHOT_VERSION,
        "period_type": normalized,
        "period_value": period_value,
        "created_at": created_at,
        "created_by": created_by,
        "journal_digest": dict(journal_digest),
        "gl_balances": dict(gl_balances),
        "financial_statements": dict(financial_statements or {}),
    }
    integrity_hash = _hash_payload(payload)
    document = dict(payload)
    document["integrity_hash"] = integrity_hash

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{normalized.lower()}_{period_value.replace(':', '-').replace('/', '-')}"
    snapshot_path = output_dir / f"{stem}.json"
    printable_path = output_dir / f"{stem}.txt"

    snapshot_path.write_text(
        json.dumps(document, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    lines = [
        "CSS PERIOD SNAPSHOT",
        f"Version: {SNAPSHOT_VERSION}",
        f"Period: {normalized} {period_value}",
        f"Created At: {created_at}",
        f"Created By: {created_by}",
        f"Integrity SHA256: {integrity_hash}",
        "",
        "JOURNAL DIGEST",
        json.dumps(dict(journal_digest), indent=2, sort_keys=True, default=str),
        "",
        "GL BALANCES",
        json.dumps(dict(gl_balances), indent=2, sort_keys=True, default=str),
        "",
        "FINANCIAL STATEMENTS",
        json.dumps(
            dict(financial_statements or {}),
            indent=2,
            sort_keys=True,
            default=str,
        ),
    ]
    printable_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return PeriodSnapshotArtifact(
        period_type=normalized,
        period_value=period_value,
        snapshot_path=str(snapshot_path),
        printable_path=str(printable_path),
        integrity_hash=integrity_hash,
        version=SNAPSHOT_VERSION,
    )


def verify_period_snapshot(snapshot_path: Path) -> Tuple[bool, str]:
    try:
        document = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"SNAPSHOT_UNREADABLE:{type(exc).__name__}"

    expected = str(document.pop("integrity_hash", "")).strip()
    if not expected:
        return False, "SNAPSHOT_HASH_MISSING"
    actual = _hash_payload(document)
    if actual != expected:
        return False, "SNAPSHOT_HASH_MISMATCH"
    return True, "OK"
