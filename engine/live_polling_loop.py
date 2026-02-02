"""
REA Engine – Controlled Live Polling Loop
-----------------------------------------
Purpose:
- Periodically pull live market data snapshots
- Route through REA Live Data Controller
- Validate via Engine Live Ingress Gate
- NO execution, NO trading

Flow:
  Provider Snapshot
    -> REA Live Data Controller (normalized tick)
    -> Engine Live Ingress Gate (accept/reject)
    -> Audit logs

Safe-by-design:
- Configurable interval
- Hard stop on exception
- Ctrl-C graceful shutdown
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

# --- Ensure repo root is on sys.path (critical for Windows "python path\script.py") ---
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.live_ingress import MarketDataTick, validate_and_ingress  # noqa: E402


# -----------------------------
# Configuration
# -----------------------------

PROVIDER = "alpaca"
REA_INSTRUMENT = "REA:CRYPTO:BTCUSD"
POLL_INTERVAL_SECONDS = 5  # safe default

CONTROLLER_CMD = [
    sys.executable,
    str(REPO_ROOT / "live_data" / "rea_live_data_controller.py"),
    "--provider",
    PROVIDER,
    "--rea",
    REA_INSTRUMENT,
]


# -----------------------------
# Helpers
# -----------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_controller() -> Dict[str, Any]:
    """
    Run the REA live data controller as a subprocess and parse its JSON stdout.
    """
    result = subprocess.run(
        CONTROLLER_CMD,
        capture_output=True,
        text=True,
        check=True,
        cwd=str(REPO_ROOT),
    )

    # Controller prints JSON to stdout (no extra text unless --audit is used)
    return json.loads(result.stdout)


def _tick_from_json(obj: Dict[str, Any]) -> MarketDataTick:
    return MarketDataTick(
        ts_utc=obj["ts_utc"],
        provider=obj["provider"],
        rea_instrument=obj["rea_instrument"],
        provider_symbol=obj["provider_symbol"],
        bid=obj.get("bid"),
        ask=obj.get("ask"),
        mid=obj.get("mid"),
        source=obj.get("source", "snapshot"),
    )


# -----------------------------
# Main loop
# -----------------------------

def main() -> int:
    print("=" * 72)
    print("REA Engine – Live Polling Loop (SAFE MODE)")
    print(f"Repo Root      : {REPO_ROOT}")
    print(f"Provider       : {PROVIDER}")
    print(f"REA Instrument : {REA_INSTRUMENT}")
    print(f"Interval (sec) : {POLL_INTERVAL_SECONDS}")
    print(f"UTC Start      : {_utc_now_iso()}")
    print("=" * 72)

    try:
        while True:
            try:
                raw = _run_controller()
                tick = _tick_from_json(raw)
                decision = validate_and_ingress(tick, audit=True)
                print(json.dumps(asdict(decision), indent=2))

            except Exception as e:
                print("FATAL ERROR IN POLLING LOOP:", repr(e))
                print("Loop terminated for safety.")
                return 1

            time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nCtrl-C received. Live polling loop stopped safely.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
