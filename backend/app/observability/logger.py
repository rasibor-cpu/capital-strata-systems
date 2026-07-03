"""
Centralized Logging & Audit Module
REA Capital Trading Engine

Correct design:
- Do NOT inject 'trace_id' via LogRecordFactory (it breaks LoggerAdapter extra).
- Use a logging.Filter to add defaults AFTER extras are applied.
- Keep ENGINE_RUN_ID always present.

This prevents:
KeyError: "Attempt to overwrite 'trace_id' in LogRecord"
"""

import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"

# -------------------------------------------------------------------
# Engine Run Identity (one per process)
# -------------------------------------------------------------------

ENGINE_RUN_ID = os.getenv("ENGINE_RUN_ID", str(uuid.uuid4()))

# -------------------------------------------------------------------
# Log Format
# -------------------------------------------------------------------

LOG_FORMAT = (
    "%(asctime)s | "
    "%(levelname)s | "
    "ENGINE_RUN_ID=%(engine_run_id)s | "
    "TRACE_ID=%(trace_id)s | "
    "%(name)s | "
    "%(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class _DefaultsFilter(logging.Filter):
    """
    Ensures required fields exist on every record.

    IMPORTANT: This runs after LoggerAdapter 'extra' is merged,
    so it will NOT conflict with trace_id passed via LoggerAdapter.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "engine_run_id"):
            record.engine_run_id = ENGINE_RUN_ID
        if not hasattr(record, "trace_id"):
            record.trace_id = "N/A"
        return True


def init_logging(level: str = "INFO") -> None:
    """
    Initialize root logging configuration.
    Safe to call once at engine startup.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_DefaultsFilter())

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Avoid duplicates on reload
    if not root.handlers:
        root.addHandler(handler)

    root.info("Logging initialized")  # do NOT pass trace_id here


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def with_trace(logger: logging.Logger, trace_id: Optional[str] = None) -> logging.LoggerAdapter:
    """
    Attach or propagate a TRACE_ID safely.
    """
    if trace_id is None:
        trace_id = str(uuid.uuid4())
    return logging.LoggerAdapter(logger, {"trace_id": trace_id})


def log_override(
    logger: logging.Logger,
    actor: str,
    action: str,
    reason: str,
    trace_id: Optional[str] = None,
) -> None:
    adapter = with_trace(logger, trace_id)
    adapter.warning(
        "HUMAN_OVERRIDE | actor=%s | action=%s | reason=%s",
        actor,
        action,
        reason,
    )


def log_startup_banner(logger: logging.Logger) -> None:
    adapter = with_trace(logger, "STARTUP")
    adapter.info("========================================")
    adapter.info("REA CAPITAL TRADING ENGINE — STARTUP")
    adapter.info("ENGINE_RUN_ID=%s", ENGINE_RUN_ID)
    adapter.info("PID=%s", os.getpid())
    adapter.info("START_TIME=%s", _now_iso_z())
    adapter.info("========================================")
