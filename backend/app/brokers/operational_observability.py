"""Sanitized logging policy for canonical broker operation results."""

from __future__ import annotations

import logging
from threading import Lock
from typing import Any, Mapping

from backend.app.brokers.operational_state import sanitize_value

_SEEN_EXPECTED: set[tuple[str, str, str, str | None]] = set()
_LOCK = Lock()


def log_operation_result(
    result: Mapping[str, Any],
    *,
    logger: logging.Logger | None = None,
    deduplicate_expected: bool = True,
) -> None:
    log = logger or logging.getLogger("css.brokers.operational")
    payload = sanitize_value(dict(result))
    broker = str(payload.get("broker") or "UNKNOWN")
    operation = str(payload.get("operation") or "status")
    state = str(payload.get("state") or "NOT_INITIALIZED")
    failure_code = payload.get("failure_code")
    expected = bool(payload.get("expected_condition", True))
    key = (broker, operation, state, str(failure_code) if failure_code else None)

    if expected and deduplicate_expected:
        with _LOCK:
            if key in _SEEN_EXPECTED:
                return
            _SEEN_EXPECTED.add(key)

    message = "%s %s state=%s code=%s correlation_id=%s"
    args = (broker, operation, state, failure_code or "NONE", payload.get("correlation_id") or "NONE")
    if not expected:
        log.error(message, *args)
    elif state in {"DEGRADED", "PROVIDER_UNAVAILABLE", "RATE_LIMITED", "TOKEN_REFRESH_REQUIRED"}:
        log.warning(message, *args)
    else:
        log.info(message, *args)


def reset_expected_log_deduplication() -> None:
    with _LOCK:
        _SEEN_EXPECTED.clear()


__all__ = ["log_operation_result", "reset_expected_log_deduplication"]
