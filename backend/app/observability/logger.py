"""
Centralized Logging & Audit Module
REA Capital Trading Engine

FIXED:
- Prevents duplicate 'trace_id' injection
- Safe with LoggerAdapter + LogRecordFactory
"""

import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Optional

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

# -------------------------------------------------------------------
# Custom Log Record Factory (SAFE)
# -------------------------------------------------------------------

_old_factory = logging.getLogRecordFactory()

def record_factory(*args, **kwargs):
    record = _old_factory(*args, **kwargs)

    # Always inject ENGINE_RUN_ID
    record.engine_run_id = ENGINE_RUN_ID

    # Inject TRACE_ID only if not already present
    if not hasattr(record, "trace_id"):
        record.trace_id = "N/A"

    return record

logging.setLogRecordFactory(record_factory)

# -------------------------------------------------------------------
# Logger Initializer
# -------------------------------------------------------------------

def init_logging(level: str = "INFO") -> None:
    """
    Initialize root logging configuration.
    Safe to call once at engine startup.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    if not root.handlers:
        root.addHandler(handler)

    # IMPORTANT: do NOT pass trace_id here
    root.info("Logging initialized")

# -------------------------------------------------------------------
# Logger Access Helper
# -------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

# -------------------------------------------------------------------
# TRACE Context Helper (ONLY source of trace_id override)
# -------------------------------------------------------------------

def with_trace(
    logger: logging.Logger,
    trace_id: Optional[str] = None
) -> logging.LoggerAdapter:
    """
    Attach or propagate a TRACE_ID safely.
    """
    if trace_id is None:
        trace_id = str(uuid.uuid4())

    return logging.LoggerAdapter(logger, {"trace_id": trace_id})

# -------------------------------------------------------------------
# Override / Human Action Audit Helper
# -------------------------------------------------------------------

def log_override(
    logger: logging.Logger,
    actor: str,
    action: str,
    reason: str,
    trace_id: Optional[str] = None
) -> None:
    adapter = with_trace(logger, trace_id)
    adapter.warning(
        "HUMAN_OVERRIDE | actor=%s | action=%s | reason=%s",
        actor,
        action,
        reason,
    )

# -------------------------------------------------------------------
# Startup Banner Helper
# -------------------------------------------------------------------

def log_startup_banner(logger: logging.Logger) -> None:
    adapter = with_trace(logger, "STARTUP")
    adapter.info("========================================")
    adapter.info("REA CAPITAL TRADING ENGINE — STARTUP")
    adapter.info("ENGINE_RUN_ID=%s", ENGINE_RUN_ID)
    adapter.info("PID=%s", os.getpid())
    adapter.info("START_TIME=%s", datetime.utcnow().isoformat() + "Z")
    adapter.info("========================================")
