"""
Authoritative guarded startup wrapper for REA Capital Trading Engine.

Responsibilities:
- Fail-closed startup (especially in LIVE)
- Ensure ENGINE_RUN_ID exists
- Block on authentication gate
- Bind audit context BEFORE engine entrypoint
- Enforce LIVE / TEST mode toggle
- Provide kill-switch awareness
- Robust status printing (dict/tuple safe)
"""

from __future__ import annotations

import importlib
import os
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


# -----------------------------
# Utilities
# -----------------------------
def _utc_iso() -> str:
    try:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    except Exception:
        return "utc_unknown"


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v not in (None, "") else default


def _normalize_gate_result(x: Any) -> Dict[str, Any]:
    """
    Normalize different gate result shapes into a dict:
      - dict: returned as-is
      - tuple/list: best-effort mapping
          (decision, reason) or (allowed, reason) patterns
      - str/bool/None: wrap into {decision:..., reason:...}
    """
    if isinstance(x, dict):
        return dict(x)

    if isinstance(x, (tuple, list)):
        # common patterns: (allowed_bool, reason_str) or (decision_str, reason_str)
        if len(x) == 2:
            a, b = x[0], x[1]
            if isinstance(a, bool):
                return {"decision": "ALLOW" if a else "BLOCK", "reason": b}
            return {"decision": str(a), "reason": b}
        return {"decision": "TUPLE", "reason": f"len={len(x)}", "raw": list(x)}

    if isinstance(x, bool):
        return {"decision": "ALLOW" if x else "BLOCK", "reason": "boolean_gate"}

    if isinstance(x, str):
        return {"decision": x, "reason": "string_gate"}

    if x is None:
        return {"decision": "UNKNOWN", "reason": "none_gate"}

    return {"decision": "UNKNOWN", "reason": f"type={type(x).__name__}", "raw": repr(x)}


def _import_optional(path: str, name: str) -> Any:
    try:
        mod = importlib.import_module(path)
        return getattr(mod, name)
    except Exception:
        return None


# -----------------------------
# Logging (best-effort; do not crash)
# -----------------------------
def _init_logging() -> Any:
    init_logging = _import_optional("backend.app.observability.logger", "init_logging")
    get_logger = _import_optional("backend.app.observability.logger", "get_logger_with_trace")

    if init_logging:
        try:
            init_logging(os.getenv("LOG_LEVEL", "INFO"))
        except Exception:
            pass

    if get_logger:
        try:
            return get_logger(trace_id="STARTUP")
        except Exception:
            pass

    # fallback: tiny shim
    class _FallbackLogger:
        def info(self, msg: str, **kw: Any) -> None:
            print(f"{_utc_iso()} | INFO | {msg} | {kw}".rstrip())

        def warning(self, msg: str, **kw: Any) -> None:
            print(f"{_utc_iso()} | WARN | {msg} | {kw}".rstrip())

        def error(self, msg: str, **kw: Any) -> None:
            print(f"{_utc_iso()} | ERROR | {msg} | {kw}".rstrip())

        def critical(self, msg: str, **kw: Any) -> None:
            print(f"{_utc_iso()} | CRITICAL | {msg} | {kw}".rstrip())

    return _FallbackLogger()


# -----------------------------
# Guarded wrapper
# -----------------------------
@dataclass
class StartupContext:
    run_id: str
    mode: str
    entrypoint: str


def _ensure_engine_run_id(log: Any) -> str:
    rid = _env("ENGINE_RUN_ID")
    if not rid:
        rid = str(uuid.uuid4())
        os.environ["ENGINE_RUN_ID"] = rid
    try:
        log.info("ENGINE_RUN_ID_READY", run_id=rid)
    except Exception:
        pass
    return rid


def _read_mode(log: Any) -> str:
    mode = (_env("REA_ENGINE_MODE", "TEST") or "TEST").upper()
    if mode not in ("TEST", "LIVE"):
        mode = "TEST"
    try:
        log.info("ENGINE_MODE", mode=mode)
    except Exception:
        pass
    return mode


def _read_entrypoint(log: Any) -> str:
    ep = _env("REA_ENGINE_ENTRYPOINT", "")
    if not ep:
        # fail-closed always: entrypoint is mandatory
        try:
            log.critical("ENTRYPOINT_NOT_SET", hint='Set REA_ENGINE_ENTRYPOINT like: "engine.run_engine:main"')
        except Exception:
            pass
        raise RuntimeError("REA_ENGINE_ENTRYPOINT_not_set")
    return ep


def _kill_switch_active() -> bool:
    # Standard location used in your ops checks
    ks = os.path.join("runtime", "kill.switch")
    try:
        return os.path.exists(ks)
    except Exception:
        return False


def _token_validation(log: Any, ctx: StartupContext) -> None:
    """
    Token check is fail-closed in LIVE.
    In TEST: best-effort (warn if missing).
    """
    validate = _import_optional("engine.execution.confirm_token", "validate_token")
    if not validate:
        msg = "TOKEN_VALIDATOR_MISSING"
        if ctx.mode == "LIVE":
            log.critical(msg, action="ABORT_LIVE")
            raise RuntimeError("token_validator_missing_live")
        log.warning(msg, action="CONTINUE_TEST")
        return

    try:
        # validate_token is expected to raise on failure OR return (ok, reason) / dict
        out = validate()
        norm = _normalize_gate_result(out)
        if norm.get("decision") in ("BLOCK", "DENY") and ctx.mode == "LIVE":
            log.critical("TOKEN_CHECK_BLOCKED", **norm)
            raise RuntimeError("token_check_blocked_live")
        log.info("TOKEN_CHECK_OK", **norm)
    except Exception as e:
        if ctx.mode == "LIVE":
            log.critical("TOKEN_CHECK_EXCEPTION", error=str(e), action="ABORT_LIVE")
            raise
        log.warning("TOKEN_CHECK_EXCEPTION", error=str(e), action="CONTINUE_TEST")


def _await_login(log: Any, ctx: StartupContext) -> Dict[str, Any]:
    await_login_ready_state = _import_optional("backend.app.security.auth_gate", "await_login_ready_state")
    if not await_login_ready_state:
        log.critical("AUTH_GATE_MISSING", module="backend.app.security.auth_gate", action="ABORT")
        raise RuntimeError("auth_gate_missing")

    user_ctx: Dict[str, Any] = await_login_ready_state()
    # Expect at least: user_id, role, unit_code, branch
    log.info("AUTH_OK", **{k: user_ctx.get(k) for k in ("user_id", "role", "unit_code", "home_branch")})
    return user_ctx


def _bind_audit_context(log: Any, user_ctx: Dict[str, Any]) -> None:
    """
    Bind audit context using whatever functions are available in audit_context.py,
    without hard dependency on a single function name.
    """
    try:
        mod = importlib.import_module("backend.app.observability.audit_context")
    except Exception as e:
        log.warning("AUDIT_CONTEXT_MODULE_MISSING", error=str(e))
        return

    # Prefer set_audit_user if it exists; otherwise fall back to any similar function
    fn = getattr(mod, "set_audit_user", None) or getattr(mod, "set_user", None) or getattr(mod, "bind_user", None)
    if not fn:
        log.warning("AUDIT_CONTEXT_BIND_FN_MISSING", available=dir(mod))
        return

    try:
        fn(
            user_id=user_ctx.get("user_id"),
            role=user_ctx.get("role"),
            unit_code=user_ctx.get("unit_code"),
            home_branch=user_ctx.get("home_branch"),
        )
        log.info("AUDIT_CONTEXT_BOUND_OK")
    except Exception as e:
        log.warning("AUDIT_CONTEXT_BIND_FAILED", error=str(e))


def _enforce_live_toggle(log: Any, ctx: StartupContext) -> None:
    """
    Enforce LIVE/TEST runtime toggle gate.
    (Your current live_toggle.py intentionally blocks execution in TEST mode.)
    """
    require_live_allowed = _import_optional("backend.app.security.live_toggle", "require_live_allowed")
    if not require_live_allowed:
        # If missing, fail-closed in LIVE, allow in TEST
        if ctx.mode == "LIVE":
            log.critical("LIVE_TOGGLE_MISSING", action="ABORT_LIVE")
            raise RuntimeError("live_toggle_missing_live")
        log.warning("LIVE_TOGGLE_MISSING", action="CONTINUE_TEST")
        return

    try:
        require_live_allowed()
        log.info("LIVE_TOGGLE_OK", mode=ctx.mode)
    except Exception as e:
        # This is expected in TEST mode in your current design
        log.error("LIVE_TOGGLE_BLOCKED", mode=ctx.mode, error=str(e))
        raise


def _call_entrypoint(log: Any, entrypoint: str) -> None:
    """
    Entry point format: "module.path:function_name"
    Example: "engine.run_engine:main"
    """
    if ":" not in entrypoint:
        raise RuntimeError("entrypoint_format_invalid")

    mod_path, fn_name = entrypoint.split(":", 1)
    mod = importlib.import_module(mod_path)
    fn = getattr(mod, fn_name)
    if not callable(fn):
        raise RuntimeError("entrypoint_not_callable")

    log.info("ENTRYPOINT_CALL", entrypoint=entrypoint)
    fn()


def show_status(log: Any, ctx: StartupContext) -> None:
    """
    Safe status snapshot. Never crashes.
    """
    try:
        log.info("RUN_LIVE_GUARDED_START", mode=ctx.mode, entrypoint=ctx.entrypoint, now_utc=_utc_iso())
        log.info("KILL_SWITCH", active=_kill_switch_active())

        # Session gate (optional)
        session_gate = _import_optional("backend.app.observability.session_time", "session_gate")
        if session_gate:
            out = session_gate(asset_class="fx")
            norm = _normalize_gate_result(out)
            log.info("SESSION_GATE", **norm)
        else:
            log.warning("SESSION_GATE_MISSING")

        # Config drift (optional)
        drift = _import_optional("backend.app.observability.config_drift", "log_config_drift")
        if drift:
            try:
                drift()
                log.info("CONFIG_DRIFT_OK")
            except Exception as e:
                log.warning("CONFIG_DRIFT_FAIL", error=str(e))
        else:
            log.warning("CONFIG_DRIFT_MISSING")

    except Exception as e:
        try:
            log.warning("STATUS_ERROR_IGNORED", error=str(e))
        except Exception:
            pass


def main() -> int:
    log = _init_logging()

    run_id = _ensure_engine_run_id(log)
    mode = _read_mode(log)
    entrypoint = _read_entrypoint(log)

    ctx = StartupContext(run_id=run_id, mode=mode, entrypoint=entrypoint)

    # Quick status (must never crash)
    show_status(log, ctx)

    # Hard fail if kill switch is active
    if _kill_switch_active():
        log.critical("KILL_SWITCH_ACTIVE_ABORT", reason="runtime/kill.switch present")
        return 2

    # Token validation (fail-closed in LIVE)
    _token_validation(log, ctx)

    # Auth gate (required)
    user_ctx = _await_login(log, ctx)

    # Bind audit context BEFORE entrypoint
    _bind_audit_context(log, user_ctx)

    # Enforce LIVE/TEST toggle rules
    _enforce_live_toggle(log, ctx)

    # Call engine entrypoint
    _call_entrypoint(log, ctx.entrypoint)

    log.info("RUN_LIVE_GUARDED_OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        # clean exit (CTRL+C)
        print(f"{_utc_iso()} | INFO | KeyboardInterrupt | exiting")
        raise
