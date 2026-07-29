"""Fail-closed mobile operator-control persistence."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MOBILE_CONTROL_FILE = PROJECT_ROOT / "artifacts" / "css_mobile_controls.json"

MOBILE_CONTROLS_SCHEMA_VERSION = "css.mobile_controls.v1"
MOBILE_CONTROLS_PAYLOAD_VERSION = "css.mobile_controls.payload.v2"
ENGINE_MODES = ("SAFE", "BALANCED", "AGGRESSIVE")
DISPLAY_MODES = ("COMPACT", "DEFAULT", "DETAILED")

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "password",
    "private",
    "secret",
    "token",
)
_WRITE_LOCK = threading.RLock()


class MobileControlPersistenceError(RuntimeError):
    """Raised when mobile controls cannot be persisted safely."""


class MobileControlRevisionError(MobileControlPersistenceError):
    """Raised when an expected revision is stale."""


DEFAULT_MOBILE_CONTROLS: dict[str, Any] = {
    "schema_version": MOBILE_CONTROLS_SCHEMA_VERSION,
    "payload_version": MOBILE_CONTROLS_PAYLOAD_VERSION,
    "control_revision": 0,
    "updated_utc": "",
    "requested_orders_enabled": False,
    "requested_pause": True,
    "operator_acknowledged": False,
    "requested_runtime_mode": "",
    "display_mode": "DEFAULT",
    "engine_mode": "SAFE",
    "notes": "",
    "legacy_compatibility": True,
    "runtime_mode": "DISABLED",
    "orders_enabled": False,
    "live_order_kill_switch": True,
    "global_live_order_kill_switch": True,
    "effective_order_permission": False,
    "effective_runtime_mode": "NOT_AUTHORITY",
    "live_capital_active": False,
    "broker_ready": False,
    "broker_execution_armed": False,
    "certification_status": "NOT_AUTHORITY",
    "platform_readiness_status": "NOT_AUTHORITY",
}


def load_mobile_controls(
    state_path: str | Path | None = None,
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    path = _state_path(state_path)
    with _WRITE_LOCK:
        try:
            if _unsafe_path(path) or not path.exists() or path.stat().st_size == 0:
                return _safe_controls(generated_at_utc=generated_at_utc)
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return _safe_controls(generated_at_utc=generated_at_utc)
        return _normalize_loaded_controls(raw, generated_at_utc=generated_at_utc)


def save_mobile_controls(
    controls: Mapping[str, Any] | None,
    *,
    state_path: str | Path | None = None,
    expected_revision: int | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    path = _state_path(state_path)
    if _unsafe_path(path):
        raise MobileControlPersistenceError("mobile_control_state_path_unsafe")

    with _WRITE_LOCK:
        current = load_mobile_controls(path, generated_at_utc=generated_at_utc)
        current_revision = int(current.get("control_revision", 0) or 0)
        if expected_revision is not None and int(expected_revision) != current_revision:
            raise MobileControlRevisionError("mobile_control_revision_stale")

        normalized = _normalize_requested_controls(
            controls,
            current_revision=current_revision,
            generated_at_utc=generated_at_utc,
        )
        _atomic_write_json(path, normalized)
        return normalized


def evaluate_kill_switch_state(
    controls: Mapping[str, Any] | None = None,
    *,
    canonical_kill_switch: Mapping[str, Any] | None = None,
    state_path: str | Path | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    active_controls = (
        _normalize_loaded_controls(controls, generated_at_utc=generated_at_utc)
        if isinstance(controls, Mapping)
        else load_mobile_controls(state_path, generated_at_utc=generated_at_utc)
    )
    canonical = dict(canonical_kill_switch) if isinstance(canonical_kill_switch, Mapping) else {}
    canonical_supplied = bool(canonical)
    blocked = True if not canonical_supplied else canonical.get("blocked") is True
    reason = (
        str(canonical.get("reason") or "canonical_kill_switch_supplied").strip()
        if canonical_supplied
        else "canonical_kill_switch_not_supplied"
    )
    return {
        "blocked": blocked,
        "reason": reason,
        "source": "canonical_authority_display" if canonical_supplied else "fail_closed_display",
        "controls": _dashboard_controls(active_controls),
        "authority": {
            "kill_switch_authority": False,
            "runtime_authority": False,
            "execution_authority": False,
            "order_authority": False,
            "broker_authority": False,
            "certification_authority": False,
        },
    }


def _normalize_loaded_controls(
    value: Any,
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return _safe_controls(generated_at_utc=generated_at_utc)
    if value.get("schema_version") != MOBILE_CONTROLS_SCHEMA_VERSION:
        return _safe_controls(generated_at_utc=generated_at_utc)
    return _normalize_requested_controls(
        value,
        current_revision=_safe_revision(value.get("control_revision")),
        generated_at_utc=generated_at_utc or str(value.get("updated_utc") or ""),
        advance_revision=False,
    )


def _normalize_requested_controls(
    value: Mapping[str, Any] | None,
    *,
    current_revision: int,
    generated_at_utc: str | None = None,
    advance_revision: bool = True,
) -> dict[str, Any]:
    source = dict(value) if isinstance(value, Mapping) else {}
    requested_runtime_mode = _requested_runtime_mode(source.get("requested_runtime_mode"))
    display_mode = _enum_text(source.get("display_mode"), DISPLAY_MODES, "DEFAULT")
    engine_mode = _enum_text(source.get("engine_mode"), ENGINE_MODES, "SAFE")
    revision = max(0, int(current_revision or 0)) + (1 if advance_revision else 0)
    return {
        **DEFAULT_MOBILE_CONTROLS,
        "control_revision": revision,
        "updated_utc": _timestamp(generated_at_utc),
        "requested_orders_enabled": _strict_bool(source.get("requested_orders_enabled")),
        "requested_pause": _strict_bool(source.get("requested_pause"), default=True),
        "operator_acknowledged": _strict_bool(source.get("operator_acknowledged")),
        "requested_runtime_mode": requested_runtime_mode,
        "display_mode": display_mode,
        "engine_mode": engine_mode,
        "notes": _safe_note(source.get("notes")),
        "runtime_mode": requested_runtime_mode or "DISABLED",
        "orders_enabled": False,
        "live_order_kill_switch": True,
        "global_live_order_kill_switch": True,
        "effective_order_permission": False,
        "effective_runtime_mode": "NOT_AUTHORITY",
        "live_capital_active": False,
        "broker_ready": False,
        "broker_execution_armed": False,
        "certification_status": "NOT_AUTHORITY",
        "platform_readiness_status": "NOT_AUTHORITY",
        "source_metadata": {
            "source": "dashboard.runtime.css_mobile_controls",
            "read_only_on_import": True,
            "operator_intent_only": True,
            "state_path_exposed": False,
            "sensitive_fields_omitted": _contains_sensitive_key(source),
            "no_environment_reads": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_runtime_authority": True,
            "no_certification_authority": True,
            "no_kill_switch_mutation": True,
        },
    }


def _safe_controls(*, generated_at_utc: str | None = None) -> dict[str, Any]:
    safe = dict(DEFAULT_MOBILE_CONTROLS)
    safe["updated_utc"] = _timestamp(generated_at_utc) if generated_at_utc else ""
    safe["source_metadata"] = {
        "source": "dashboard.runtime.css_mobile_controls",
        "read_only_on_import": True,
        "operator_intent_only": True,
        "state_path_exposed": False,
        "safe_default": True,
        "no_environment_reads": True,
        "no_broker_calls": True,
        "no_order_placement": True,
        "no_runtime_authority": True,
        "no_certification_authority": True,
        "no_kill_switch_mutation": True,
    }
    return safe


def _dashboard_controls(controls: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": str(controls.get("schema_version") or MOBILE_CONTROLS_SCHEMA_VERSION),
        "control_revision": int(controls.get("control_revision", 0) or 0),
        "updated_utc": str(controls.get("updated_utc") or ""),
        "requested_orders_enabled": controls.get("requested_orders_enabled") is True,
        "requested_pause": controls.get("requested_pause") is True,
        "operator_acknowledged": controls.get("operator_acknowledged") is True,
        "requested_runtime_mode": str(controls.get("requested_runtime_mode") or ""),
        "display_mode": str(controls.get("display_mode") or "DEFAULT"),
        "engine_mode": str(controls.get("engine_mode") or "SAFE"),
        "runtime_mode": str(controls.get("runtime_mode") or "DISABLED"),
        "orders_enabled": False,
        "effective_order_permission": False,
        "live_capital_active": False,
        "broker_ready": False,
        "broker_execution_armed": False,
    }


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as tmp:
            tmp_name = tmp.name
            json.dump(payload, tmp, indent=2, sort_keys=True)
            tmp.write("\n")
            tmp.flush()
            try:
                os.fsync(tmp.fileno())
            except OSError:
                pass
        os.replace(tmp_name, path)
    except Exception as exc:
        if tmp_name:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except Exception:
                pass
        raise MobileControlPersistenceError("mobile_control_persistence_failed") from exc


def _state_path(state_path: str | Path | None) -> Path:
    return Path(state_path) if state_path is not None else MOBILE_CONTROL_FILE


def _unsafe_path(path: Path) -> bool:
    return path.exists() and path.is_symlink()


def _strict_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return False


def _requested_runtime_mode(value: Any) -> str:
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    return text if text in {"PAPER", "LIVE_READ_ONLY"} else ""


def _enum_text(value: Any, allowed: tuple[str, ...], default: str) -> str:
    text = str(value or "").strip().upper()
    return text if text in allowed else default


def _safe_revision(value: Any) -> int:
    try:
        revision = int(value)
    except (TypeError, ValueError):
        return 0
    return revision if revision >= 0 else 0


def _safe_note(value: Any) -> str:
    text = str(value or "").strip()
    if any(part in text.lower() for part in _SENSITIVE_KEY_PARTS):
        return ""
    return text[:240]


def _contains_sensitive_key(value: Mapping[str, Any]) -> bool:
    for key, item in value.items():
        normalized = str(key).strip().lower()
        if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
            return True
        if isinstance(item, Mapping) and _contains_sensitive_key(item):
            return True
    return False


def _timestamp(value: str | None) -> str:
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return ""
        return parsed.astimezone(timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "DEFAULT_MOBILE_CONTROLS",
    "DISPLAY_MODES",
    "ENGINE_MODES",
    "MOBILE_CONTROLS_PAYLOAD_VERSION",
    "MOBILE_CONTROLS_SCHEMA_VERSION",
    "MOBILE_CONTROL_FILE",
    "MobileControlPersistenceError",
    "MobileControlRevisionError",
    "evaluate_kill_switch_state",
    "load_mobile_controls",
    "save_mobile_controls",
]
