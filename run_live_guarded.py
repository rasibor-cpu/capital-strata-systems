"""
run_live_guarded.py — REA Capital Trading Engine
------------------------------------------------
Authoritative guarded startup wrapper.

V1 goals:
- FAIL-CLOSED by default
- TEST is allowed to run paper/headless
- LIVE requires explicit operator intent + unlock flags + credentials
- Disallow dev bypass flags in LIVE
- Provide clear, auditable console output of gate decisions

Environment controls (V1):
- REA_ENGINE_MODE = TEST | LIVE
- REA_LIVE_CONFIRM = "I_UNDERSTAND_LIVE"
- REA_EXECUTION_UNLOCK = "1"
- REA_LIVE_PIN + REA_LIVE_PIN_CONFIRM must both be set and match (min 6 chars)
- HEADLESS_DEV_MODE must be OFF in LIVE
- DEV_FORCE_ALLOW must be OFF in LIVE

Credential presence (any one set accepted for LIVE):
- Alpaca:  APCA_API_KEY_ID + APCA_API_SECRET_KEY
- OANDA:   OANDA_API_KEY + OANDA_ACCOUNT_ID
- Binance: BINANCE_API_KEY + BINANCE_API_SECRET
- IBKR:    IBKR_HOST + IBKR_PORT  (placeholder check)
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Tuple, Dict, Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _env_bool(name: str) -> bool:
    return _env(name, "").strip() in ("1", "true", "TRUE", "yes", "YES", "on", "ON")


def _fail(msg: str, code: int = 1) -> None:
    print(msg)
    raise SystemExit(code)


def _print_gate(label: str, allowed: bool, reason: str) -> None:
    print(f"{label:<14} | allowed={str(allowed):<5} | reason={reason}")


def ensure_engine_run_id() -> str:
    rid = _env("ENGINE_RUN_ID", "").strip()
    if rid:
        return rid
    rid = str(uuid.uuid4())
    os.environ["ENGINE_RUN_ID"] = rid
    return rid


def _credentials_ok() -> Tuple[bool, str]:
    # Accept any ONE provider's credentials for LIVE V1.
    alpaca_ok = bool(_env("APCA_API_KEY_ID")) and bool(_env("APCA_API_SECRET_KEY"))
    if alpaca_ok:
        return True, "alpaca_keys_present"

    oanda_ok = bool(_env("OANDA_API_KEY")) and bool(_env("OANDA_ACCOUNT_ID"))
    if oanda_ok:
        return True, "oanda_keys_present"

    binance_ok = bool(_env("BINANCE_API_KEY")) and bool(_env("BINANCE_API_SECRET"))
    if binance_ok:
        return True, "binance_keys_present"

    ibkr_ok = bool(_env("IBKR_HOST")) and bool(_env("IBKR_PORT"))
    if ibkr_ok:
        return True, "ibkr_host_port_present"

    return False, "no_live_broker_credentials_detected"


def _live_intent_ok() -> Tuple[bool, str]:
    if _env("REA_LIVE_CONFIRM").strip() != "I_UNDERSTAND_LIVE":
        return False, "missing_REA_LIVE_CONFIRM"
    if _env("REA_EXECUTION_UNLOCK").strip() != "1":
        return False, "missing_REA_EXECUTION_UNLOCK"
    pin = _env("REA_LIVE_PIN").strip()
    pin2 = _env("REA_LIVE_PIN_CONFIRM").strip()
    if len(pin) < 6:
        return False, "REA_LIVE_PIN_too_short"
    if pin != pin2:
        return False, "REA_LIVE_PIN_mismatch"
    return True, "live_intent_confirmed"


def _live_dev_flags_ok() -> Tuple[bool, str]:
    if _env_bool("HEADLESS_DEV_MODE"):
        return False, "HEADLESS_DEV_MODE_not_allowed_in_LIVE"
    if _env_bool("DEV_FORCE_ALLOW"):
        return False, "DEV_FORCE_ALLOW_not_allowed_in_LIVE"
    if _env_bool("HEADLESS_DEV_MODE") or _env_bool("HEADLESS_DEV_MODE_1"):
        return False, "headless_flags_not_allowed_in_LIVE"
    return True, "dev_flags_ok"


def _exec_gate_ok(mode: str) -> Tuple[bool, str]:
    """
    V1 execution gate:
    - In TEST: allow paper entry (execution remains locked downstream)
    - In LIVE: require explicit unlock + credentials + intent + dev flags clean
    """
    if mode != "LIVE":
        return True, "ok_test_mode"

    intent_ok, intent_reason = _live_intent_ok()
    if not intent_ok:
        return False, intent_reason

    dev_ok, dev_reason = _live_dev_flags_ok()
    if not dev_ok:
        return False, dev_reason

    creds_ok, creds_reason = _credentials_ok()
    if not creds_ok:
        return False, creds_reason

    return True, "ok_live_mode"


def main() -> int:
    print("=== REA GUARDED STARTUP (FAIL-CLOSED) ===")
    print(f"UTC_NOW={_utc_now_iso()}")

    rid = ensure_engine_run_id()
    print(f"ENGINE_RUN_ID={rid}")

    mode = _env("REA_ENGINE_MODE", "TEST").upper().strip()
    if mode not in ("TEST", "LIVE"):
        _fail(f"FATAL | BAD_MODE | REA_ENGINE_MODE={mode!r} (use TEST or LIVE)", 2)

    print(f"MODE={'LIVE' if mode=='LIVE' else 'TEST'}")

    # ---------------------------
    # EXEC GATE (authoritative)
    # ---------------------------
    ok_exec, reason_exec = _exec_gate_ok(mode)
    _print_gate("EXEC_GATE", ok_exec, reason_exec)
    if not ok_exec:
        _fail(f"FATAL | EXEC_GATE_BLOCK | {reason_exec}", 1)

    # ---------------------------
    # Start engine entrypoint
    # ---------------------------
    # For V1, we keep the entrypoint simple:
    # - TEST: run headless guarded engine (paper/test)
    # - LIVE: still enters guarded engine, but now allowed only with explicit unlock
    try:
        # Prefer backend guarded entry if present, else use top-level.
        # (No dependency on brokers/adapters here.)
        try:
            from backend.app.headless_guarded_entry import main as guarded_main  # type: ignore
            entry = "backend.app.headless_guarded_entry"
        except Exception:
            from headless_guarded_entry import main as guarded_main  # type: ignore
            entry = "headless_guarded_entry"

        print(f"ENTRYPOINT     | {entry}")
        return int(guarded_main() or 0)

    except SystemExit:
        raise
    except Exception as e:
        _fail(f"FATAL | STARTUP_EXCEPTION | {type(e).__name__}: {e}", 1)


if __name__ == "__main__":
    raise SystemExit(main())
