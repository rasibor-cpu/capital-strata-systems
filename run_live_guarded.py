"""
run_live_guarded.py
===================

Guarded LIVE runner (FAIL-CLOSED) for REA / CSS.

This runner calls the canonical guarded entrypoint:
    backend.app.headless_guarded_entry.run_headless(req, cfg)

Facts (verified via introspection):
- run_headless(req: Dict[str, Any], cfg: HeadlessConfig) -> Dict[str, Any]
- HeadlessConfig(allow_live: bool = False)

We default to FAIL-CLOSED + NO-LIVE (allow_live=False).
Safe for first boot validation on a new machine.

Usage:
  python -u run_live_guarded.py

Optional env knobs (safe; still fail-closed):
  # Market diagnostics inputs (feed RegimeGate / volatility layers)
  CSS_BARS_5M=60
  CSS_VOL_NORM_0_1=0.35
  CSS_SPREAD_BPS=1.2
  CSS_HIGH_RISK_NEWS=0
  CSS_VOLATILITY_RATIO=1.0

  # Optional SAFE trade test payload (still allow_live=False, execution_armed=False)
  CSS_TRADE_TEST=1
  CSS_SIDE=BUY
  CSS_NOTIONAL=10000
  CSS_STOP_DISTANCE_PCT=0.005
"""

from __future__ import annotations

import os
import sys
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any, Dict, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    """
    Best-effort .env load from repo root.
    Requires python-dotenv (you installed it).
    """
    env_path = Path(".env")
    if not env_path.exists():
        print("[env] .env not found in repo root.")
        return

    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        print("[env] python-dotenv not available; skipping .env load.")
        return

    load_dotenv(dotenv_path=str(env_path), override=False)
    print("[env] .env loaded.")


def _print_banner(engine_run_id: str) -> None:
    print("=== REA / CSS GUARDED STARTUP (FAIL-CLOSED) ===")
    print(f"UTC_NOW={_utc_now()}")
    print(f"ENGINE_RUN_ID={engine_run_id}")
    print(f"CWD={Path.cwd()}")
    print(f"PY={sys.version.split()[0]}")
    print(f"VENV={os.environ.get('VIRTUAL_ENV', '')}")


def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name, None)
    if v is None or str(v).strip() == "":
        return float(default)
    try:
        return float(v)
    except Exception:
        return float(default)


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name, None)
    if v is None or str(v).strip() == "":
        return int(default)
    try:
        return int(float(v))
    except Exception:
        return int(default)


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, None)
    if v is None:
        return bool(default)
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def _maybe_trade_test_payload() -> Optional[Dict[str, Any]]:
    """
    Optional SAFE trade payload for exercising the full pipeline.
    Still fail-closed because:
      - cfg.allow_live=False
      - req.allow_live=False
      - req.execution_armed=False
    """
    if not _env_bool("CSS_TRADE_TEST", False):
        return None

    side = os.environ.get("CSS_SIDE", "BUY").strip().upper()
    notional = _env_float("CSS_NOTIONAL", 10000.0)
    stop_distance_pct = _env_float("CSS_STOP_DISTANCE_PCT", 0.005)

    return {
        "side": side,
        "notional": notional,
        "stop_distance_pct": stop_distance_pct,
    }


def _build_req(engine_run_id: str) -> Dict[str, Any]:
    """
    Request payload for run_headless.
    Conservative defaults:
    - No secrets
    - No "live" enablement
    - Explicit fail-closed flags
    - Optional diagnostic inputs for gate stacking
    - Optional safe trade test payload
    """
    fx_provider = os.environ.get("FX_PROVIDER", os.environ.get("FX_PROVIDER", "oanda"))
    fx_instrument = os.environ.get("FX_INSTRUMENT", "EUR_USD")

    req: Dict[str, Any] = {
        "engine_run_id": engine_run_id,
        "ts_utc": _utc_now(),
        "mode": os.environ.get("MODE", "TEST"),
        "fx_provider": fx_provider,
        "fx_instrument": fx_instrument,
        "fx_timeframe": os.environ.get("FX_TIMEFRAME", "1m"),
        "oanda_env": os.environ.get("OANDA_ENV", "practice"),
        # Explicit safety flags:
        "allow_live": False,
        "execution_armed": False,
        # Market diagnostics inputs (used by RegimeGate / volatility layers):
        "bars_5m": _env_int("CSS_BARS_5M", 60),
        "vol_norm_0_1": _env_float("CSS_VOL_NORM_0_1", 0.35),
        "spread_bps": _env_float("CSS_SPREAD_BPS", 1.2),
        "high_risk_news": _env_bool("CSS_HIGH_RISK_NEWS", False),
        # For AdaptiveCapital layer (volatility suppression):
        "volatility_ratio": _env_float("CSS_VOLATILITY_RATIO", 1.0),
        # Optional free-form notes:
        "note": "Guarded boot validation (fail-closed) + diagnostic inputs enabled.",
    }

    trade_payload = _maybe_trade_test_payload()
    if trade_payload:
        req["trade_test"] = True
        req.update(trade_payload)
        req["note"] = "Guarded SAFE trade-test payload included (still fail-closed; no-live)."

    return req


def main() -> int:
    engine_run_id = f"ae{uuid4()}"
    _print_banner(engine_run_id)

    # Ensure repo root is importable (so backend.* imports work)
    repo_root = str(Path(__file__).resolve().parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    _load_env()

    # Import guarded entry + config
    try:
        from backend.app.headless_guarded_entry import run_headless, HeadlessConfig  # type: ignore
    except Exception:
        print("FATAL | STARTUP_EXCEPTION | Failed to import guarded entrypoint")
        traceback.print_exc()
        return 2

    # Construct cfg (fail-closed: allow_live=False)
    try:
        cfg = HeadlessConfig(allow_live=False)  # type: ignore[call-arg]
    except Exception:
        print("FATAL | STARTUP_EXCEPTION | Failed to construct HeadlessConfig")
        traceback.print_exc()
        return 3

    req = _build_req(engine_run_id)

    # Echo minimal config (no secrets)
    print(f"MODE={req.get('mode')}")
    print(f"FX_PROVIDER={req.get('fx_provider')}")
    print(f"FX_INSTRUMENT={req.get('fx_instrument')}")
    print(f"OANDA_ENV={req.get('oanda_env')}")
    print(f"BARS_5M={req.get('bars_5m')} VOL_NORM_0_1={req.get('vol_norm_0_1')} SPREAD_BPS={req.get('spread_bps')} HIGH_RISK_NEWS={req.get('high_risk_news')}")
    print(f"VOLATILITY_RATIO={req.get('volatility_ratio')}")
    print(f"TRADE_TEST={req.get('trade_test', False)}")
    print("EXEC_GATE | allowed=False | reason=guarded_fail_closed_default")
    print("-" * 70)

    # Run (fail-closed)
    try:
        result = run_headless(req, cfg)  # type: ignore[misc]
    except KeyboardInterrupt:
        print("STOPPED | KeyboardInterrupt")
        return 0
    except Exception:
        print("FATAL | STARTUP_EXCEPTION | Exception raised by run_headless(req, cfg)")
        traceback.print_exc()
        return 4

    # Print returned diagnostics cleanly
    print("[guarded] run_headless returned diagnostics:")
    try:
        print(json.dumps(result, indent=2, default=str))
    except Exception:
        print(result)

    print("-" * 70)
    print("OK | GUARDED_STARTUP_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
