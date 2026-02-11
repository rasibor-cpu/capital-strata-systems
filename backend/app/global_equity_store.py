"""
Capital Strata Systems
Global Equity Store – Persistent Rolling Peak Authority

Purpose:
- Persist rolling equity peak to disk
- Survive restarts
- Never reduce peak unless manually reset
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


STORE_PATH = Path("global_equity_store.json")


def _read_store() -> dict:
    if not STORE_PATH.exists():
        return {}

    try:
        with STORE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Corrupt file fallback
        return {}


def _write_store(data: dict) -> None:
    with STORE_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_equity_peak() -> Optional[float]:
    data = _read_store()
    peak = data.get("equity_peak")
    if peak is None:
        return None
    return float(peak)


def update_equity_peak(current_equity: float) -> float:
    """
    Update rolling peak if current equity exceeds stored peak.
    Returns the effective peak after update.
    """
    data = _read_store()
    stored_peak = data.get("equity_peak")

    if stored_peak is None or current_equity > float(stored_peak):
        data["equity_peak"] = round(float(current_equity), 6)
        _write_store(data)
        return float(data["equity_peak"])

    return float(stored_peak)


def reset_equity_peak(new_peak: float) -> None:
    """
    Manual override. Use only with governance approval.
    """
    data = {"equity_peak": round(float(new_peak), 6)}
    _write_store(data)
