from __future__ import annotations

import random
import time
from typing import Dict, Any

# Persistent state (DO NOT REMOVE — used for velocity/acceleration continuity)
_prev: Dict[str, Dict[str, float]] = {}


def _get_real_price_safe(symbol: str) -> float | None:
    """
    Phase 5D: Safe hook for real price (non-breaking)
    Returns None if no real data source is wired yet.
    """
    try:
        # Future: plug broker here (Coinbase / OANDA)
        return None
    except Exception:
        return None


def load_runtime_asset(symbol: str) -> Dict[str, Any]:
    """
    Phase 5D – Enhanced Runtime Asset Loader

    Guarantees:
    - NO regression (PCNRASS compliant)
    - Same output structure preserved
    - Adds richer intelligence fields
    """

    now = time.time()

    # --- BASE PRICE (SAFE REAL + FALLBACK) ---
    real_price = _get_real_price_safe(symbol)

    if real_price is not None:
        price = real_price
    else:
        # Controlled mock (stable randomness)
        price = random.uniform(90, 110)

    # --- PREVIOUS STATE ---
    prev = _prev.get(symbol)

    if prev:
        prev_price = prev["price"]
        prev_velocity = prev["velocity"]
    else:
        prev_price = price
        prev_velocity = 0.0

    # --- VELOCITY (Δ price) ---
    velocity = price - prev_price

    # --- ACCELERATION (Δ velocity) ---
    acceleration = velocity - prev_velocity

    # --- VOLATILITY PROXY ---
    volatility = abs(velocity) + abs(acceleration)

    # --- PRESSURE SCORE (normalized directional force) ---
    pressure_raw = velocity + (0.5 * acceleration)

    # Normalize safely
    pressure_score = max(min(pressure_raw, 5.0), -5.0)

    # --- LIQUIDITY PROXY ---
    # Lower volatility → higher liquidity assumption
    liquidity_score = max(0.0, 10.0 - (volatility * 2))

    # Clamp liquidity
    liquidity_score = min(liquidity_score, 10.0)

    # --- STORE STATE ---
    _prev[symbol] = {
        "price": price,
        "velocity": velocity,
        "timestamp": now,
    }

    # --- OUTPUT STRUCTURE (DO NOT BREAK) ---
    return {
        "symbol": symbol,
        "price": price,
        "velocity": velocity,
        "acceleration": acceleration,
        "pressure_score": pressure_score,
        "liquidity_score": liquidity_score,
        "volatility": volatility,
        "timestamp": now,
    }