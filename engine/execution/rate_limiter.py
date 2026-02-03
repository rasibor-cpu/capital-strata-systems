# engine/execution/rate_limiter.py
"""
Rate limiter (runtime, fail-closed-ish)

Purpose: prevent repeated arming/confirm cycles or rapid-fire execution checks from
becoming an abuse vector.

Stores state in audit/rate_limit.json (runtime artifact; never committed).
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, Any


RATE_LIMIT_PATH = os.path.join("audit", "rate_limit.json")


def _load() -> Dict[str, Any]:
    if not os.path.exists(RATE_LIMIT_PATH):
        return {"window_s": 60, "max_hits": 30, "hits": []}
    try:
        with open(RATE_LIMIT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # If corrupted, fail-closed (block)
        return {"window_s": 60, "max_hits": 0, "hits": []}


def _save(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(RATE_LIMIT_PATH), exist_ok=True)
    with open(RATE_LIMIT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def check_rate_limit() -> bool:
    """
    Returns True if allowed, False if rate-limited.
    Defaults: 30 hits per 60s.
    """
    data = _load()
    window_s = int(data.get("window_s", 60))
    max_hits = int(data.get("max_hits", 30))
    hits = data.get("hits", [])
    now = time.time()

    # keep only recent hits
    hits = [t for t in hits if (now - float(t)) <= window_s]

    if len(hits) >= max_hits:
        data["hits"] = hits
        _save(data)
        return False

    hits.append(now)
    data["hits"] = hits
    _save(data)
    return True
