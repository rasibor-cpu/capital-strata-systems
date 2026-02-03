"""
Centralized Logging & Audit Module
REA Capital Trading Engine

Purpose:
- Deterministic, structured logs
- One ENGINE_RUN_ID per engine start
- TRACE_ID support per trade / action
- Override-safe (even if overrides not yet wired)
- No side effects on strategy or execution
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
# Custom Log Record Factory
# -------------------------------------------------------------------

_old_factory = logging.getLogRecordFactory()

def record_factory(*args, **kwargs):
    record = _old_factory(*args, **kwargs)
    record.engine_run_id = ENGINE_RUN_ID
    record.trace_id = getattr(record, "trace_id", "N/A")
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

    # Avoid duplicate handlers on reload
    if not root.handlers:
        root.addHandler(handler)

    root.info("Logging initialized", extra={"trace_id": "SYSTEM"})

# -------------------------------------------------------------------
# Logger Access Helper
# -------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Obtain a standard logger.
    """
    return logging.getLogger(name)

# -------------------------------------------------------------------
# TRACE Context Helper
# -------------------------------------------------------------------

def with_trace(logger: logging.Logger, trace_id: Optional[str] = None) -> logging.LoggerAdapter:
    """
    Attach or propagate a TRACE_ID.
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
    """
    Log a human override or privileged action.
    This does NOT execute anything — audit only.
    """
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
    """
    Emit a deterministic startup banner.
    """
    adapter = with_trace(logger, "STARTUP")
    adapter.info("========================================")
    adapter.info("REA CAPITAL TRADING ENGINE — STARTUP")
    adapter.info("ENGINE_RUN_ID=%s", ENGINE_RUN_ID)
    adapter.info("PID=%s", os.getpid())
    adapter.info("START_TIME=%s", datetime.utcnow().isoformat() + "Z")
    adapter.info("========================================")
