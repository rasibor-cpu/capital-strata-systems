"""
Risk State Store – Phase 1 Persistence
REA Capital Trading Engine

Purpose:
- Persist risk state to disk (JSON) so the engine retains counters across runs.
- Fail-safe: corrupted or missing state returns a clean default (fail-closed behavior remains in gates).

Controls:
- REA_PERSIST_RISK_STATE=1 enables persistence
- REA_RISK_STATE_PATH can override default path
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict


DEFAULT_STATE_PATH = os.path.join("engine", "risk", "risk_state.json")


def persist_enabled() -> bool:
    return os.environ.get("REA_PERSIST_RISK_STATE", "0") == "1"


def state_path() -> str:
    return os.environ.get("REA_RISK_STATE_PATH", DEFAULT_STATE_PATH)


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def default_state() -> Dict[str, Any]:
    # Keep schema aligned with RiskGovernor.required fields + extras
    return {
        "day_key": _utc_today(),
        "trades_today": 0,
        "open_positions": 0,
        "consecutive_losses": 0,
        "losses_by_pair": {},
        "cooldown_until": None,
        # optional but used by newer logic
        "daily_pnl": 0.0,
    }


def _self_heal_schema(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure new keys exist so we don't KeyError when older state files exist.
    """
    base = default_state()
    for k, v in base.items():
        if k not in state:
            state[k] = v

    # Type safety guards
    if not isinstance(state.get("losses_by_pair"), dict):
        state["losses_by_pair"] = {}

    if not isinstance(state.get("trades_today"), int):
        state["trades_today"] = int(state.get("trades_today") or 0)

    if not isinstance(state.get("open_positions"), int):
        state["open_positions"] = int(state.get("open_positions") or 0)

    if not isinstance(state.get("consecutive_losses"), int):
        state["consecutive_losses"] = int(state.get("consecutive_losses") or 0)

    if not isinstance(state.get("daily_pnl"), (int, float)):
        try:
            state["daily_pnl"] = float(state.get("daily_pnl") or 0.0)
        except Exception:
            state["daily_pnl"] = 0.0

    # Ensure day_key exists
    if not state.get("day_key"):
        state["day_key"] = _utc_today()

    return state


def load_state() -> Dict[str, Any]:
    if not persist_enabled():
        return default_state()

    path = state_path()
    try:
        if not os.path.exists(path):
            st = default_state()
            save_state(st)
            return st

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return default_state()

        return _self_heal_schema(data)

    except Exception:
        # Fail-safe on any read/parse issue
        return default_state()


def save_state(state: Dict[str, Any]) -> None:
    if not persist_enabled():
        return

    path = state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    safe = _self_heal_schema(dict(state))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(safe, f, indent=2, sort_keys=True)
