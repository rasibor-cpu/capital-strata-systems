from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


RUNTIME_EVENT_PERSISTENCE_CHECKLIST_EXPORT_VERSION = (
    "css.runtime_event_persistence_checklist_export.v1"
)
PERSISTENCE_CHECKLIST_SAFETY_DISCLAIMER = (
    "Persistence remains disabled. This export is a read-only operator review "
    "record and does not approve, activate, or write runtime event persistence."
)
_SENSITIVE_VALUE_MARKERS = (
    "api_key=",
    "apikey=",
    "bearer ",
    "private key",
    "secret=",
    "token=",
    "password=",
    "authorization:",
)


@dataclass(frozen=True)
class RuntimeEventPersistenceChecklistExport:
    export_id: str
    generated_at_utc: str
    checklist_id: str
    readiness_status: str
    report_id: str
    required_checks: list[dict[str, str]]
    passed_checks: list[dict[str, str]]
    failed_checks: list[dict[str, str]]
    blocking_items: list[str]
    warnings: list[str]
    operator_review_required: bool
    persistence_enabled: bool
    writes_performed: bool
    simulation_only: bool
    read_only: bool
    safety_disclaimer: str
    export_format: str = "json"
    payload_version: str = RUNTIME_EVENT_PERSISTENCE_CHECKLIST_EXPORT_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_runtime_event_persistence_checklist_export(
    checklist: dict[str, Any] | None = None,
    *,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    source = checklist or {}
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    checklist_id = str(source.get("checklist_id") or "")
    report_id = str(source.get("report_id") or "")
    export = RuntimeEventPersistenceChecklistExport(
        export_id=_export_id(
            {
                "generated_at_utc": generated,
                "checklist_id": checklist_id,
                "report_id": report_id,
                "readiness_status": source.get("readiness_status"),
            }
        ),
        generated_at_utc=generated,
        checklist_id=checklist_id,
        readiness_status=str(source.get("readiness_status") or "NOT_READY"),
        report_id=report_id,
        required_checks=_safe_check_list(source.get("required_checks")),
        passed_checks=_safe_check_list(source.get("passed_checks")),
        failed_checks=_safe_check_list(source.get("failed_checks")),
        blocking_items=[
            _sanitize_text(item) for item in source.get("blocking_items") or []
        ],
        warnings=[_sanitize_text(item) for item in source.get("warnings") or []],
        operator_review_required=True,
        persistence_enabled=False,
        writes_performed=False,
        simulation_only=True,
        read_only=True,
        safety_disclaimer=PERSISTENCE_CHECKLIST_SAFETY_DISCLAIMER,
        export_format="json",
    )
    return _json_safe(export.as_dict())


def _safe_check_list(value: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not isinstance(value, list):
        return items
    for item in value:
        if isinstance(item, dict):
            items.append(
                {
                    "check_id": _sanitize_text(item.get("check_id") or ""),
                    "label": _sanitize_text(item.get("label") or item.get("check_id") or ""),
                    "status": _sanitize_text(item.get("status") or ""),
                }
            )
        else:
            items.append({"check_id": "", "label": _sanitize_text(item), "status": ""})
    return items


def _sanitize_text(value: Any) -> str:
    text = str(value or "")
    normalized = text.lower()
    if any(marker in normalized for marker in _SENSITIVE_VALUE_MARKERS):
        return "REDACTED"
    return text


def _json_safe(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, sort_keys=True, default=str))


def _export_id(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"EVCHECKEXPORT-{digest}"


__all__ = [
    "PERSISTENCE_CHECKLIST_SAFETY_DISCLAIMER",
    "RUNTIME_EVENT_PERSISTENCE_CHECKLIST_EXPORT_VERSION",
    "RuntimeEventPersistenceChecklistExport",
    "build_runtime_event_persistence_checklist_export",
]
