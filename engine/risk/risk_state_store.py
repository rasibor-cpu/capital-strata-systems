"""
Risk State Store
Persistent state layer for RiskGovernor
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


STATE_FILE = Path("engine/risk/risk_state.json")


def default_state() -> Dict[str, Any]:
    return {
        "day_key": "",
        "trades_today": 0,
        "open_positions": 0,
        "consecutive_losses": 0,
        "losses_by_pair": {},
        "cooldown_until": None,
    }


def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return default_state()

    try:
        with STATE_FILE.open("r") as f:
            return json.load(f)
    except Exception:
        return default_state()


def save_state(state: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w") as f:
        json.dump(state, f, indent=2)
