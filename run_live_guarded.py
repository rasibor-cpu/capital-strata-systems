"""
run_live_guarded.py
===================

Canonical Guarded Runner (FAIL-CLOSED)
Capital Strata Systems

This runner:
- Loads .env
- Builds a controlled probe trade payload
- Calls backend.app.headless_guarded_entry.run_headless(req, cfg)
- Prints clean diagnostics
- NEVER enables live trading (allow_live=False)

Safe for new machine validation.
"""

from __future__ import annotations

import os
import sys
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any, Dict


# ============================================================
# Utilities
# ============================================================

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        print("[env] .env not found.")
        return

    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(dotenv_path=str(env_path), override=False)
        print("[env] .env loaded.")
    except Exception:
        print("[env] dotenv unavailable; skipping.")


def _print_banner(run_id: str) -> None:
    print("=== REA / CSS GUARDED STARTUP (FAIL-CLOSED) ===")
    print(f"UTC_NOW={_utc_now()}")
    print(f"ENGINE_RUN_ID={run_id}")
    print(f"CWD={Path.cwd()}")
    print(f"PY={sys.version.split()[0]}")
    print(f"VENV={os.environ.get('VIRTUAL_ENV', '')}")


# ============================================================
# Controlled Probe Payload
# ============================================================

def _build_req(run_id: str) -> Dict[str, Any]:
    """
    Controlled SIMULATION trade probe.
    Still fail-closed.
    """

    return {
        "engine_run_id": run_id,
        "ts_utc": _utc_now(),
        "mode": os.environ.get("MODE", "TEST"),

        # Market context
        "fx_provider": os.environ.get("FX_PROVIDER", "oanda"),
        "fx_instrument": os.environ.get("FX_INSTRUMENT", "EUR_USD"),
        "fx_timeframe": os.environ.get("FX_TIMEFRAME", "1m"),
        "oanda_env": os.environ.get("OANDA_ENV", "practice"),

        # Volatility inputs
        "bars_5m": int(os.environ.get("BARS_5M", "60")),
        "vol_norm_0_1": float(os.environ.get("VOL_NORM_0_1", "0.35")),
        "spread_bps": float(os.environ.get("SPREAD_BPS", "1.2")),
        "high_risk_news": os.environ.get("HIGH_RISK_NEWS", "False") == "True",

        # Probe trade (required fields)
        "side": os.environ.get("TRADE_SIDE", "BUY"),
        "notional": float(os.environ.get("TRADE_NOTIONAL", "10000")),
        "stop_distance_pct": float(os.environ.get("TRADE_STOP_PCT", "0.005")),

        # Optional equity context
        "equity": float(os.environ.get("EQUITY", "100000")),
        "equity_peak": float(os.environ.get("EQUITY_PEAK", "100000")),
        "equity_risk": float(os.environ.get("EQUITY_RISK", "500")),

        # Regime persistence
        "regime_persistence": float(os.environ.get("REGIME_PERSISTENCE", "0.8")),

        # Safety locks
        "allow_live": False,
        "execution_armed": False,

        "note": "Guarded probe trade (simulation only).",
    }


# ============================================================
# Main
# ============================================================

def main() -> int:
    run_id = f"css-{uuid4()}"
    _print_banner(run_id)

    repo_root = str(Path(__file__).resolve().parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    _load_env()

    try:
        from backend.app.headless_guarded_entry import run_headless, HeadlessConfig  # type: ignore
    except Exception:
        print("FATAL | Import error (headless_guarded_entry)")
        traceback.print_exc()
        return 2

    try:
        cfg = HeadlessConfig(allow_live=False)
    except Exception:
        print("FATAL | HeadlessConfig construction failed")
        traceback.print_exc()
        return 3

    req = _build_req(run_id)

    print(f"MODE={req.get('mode')}")
    print(f"FX_PROVIDER={req.get('fx_provider')}")
    print(f"FX_INSTRUMENT={req.get('fx_instrument')}")
    print(f"OANDA_ENV={req.get('oanda_env')}")
    print("EXEC_GATE | allowed=False | reason=guarded_fail_closed_default")
    print("-" * 70)

    try:
        result = run_headless(req, cfg)
    except Exception:
        print("FATAL | Exception raised by run_headless(req, cfg)")
        traceback.print_exc()
        return 4

    print("[guarded] Diagnostics:")
    print(json.dumps(result, indent=2, default=str))

    print("-" * 70)
    print("OK | GUARDED_STARTUP_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
