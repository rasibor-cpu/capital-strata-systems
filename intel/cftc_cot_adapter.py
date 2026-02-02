"""
CFTC COT Crowding Adapter (demo)
--------------------------------
Goal: provide a "positioning/crowding" IntelEnvelope based on a lightweight
approximation (or placeholder) so we can wire the pipeline end-to-end.

Collector contract:
- fetch_cftc_cot_safe() -> List[IntelEnvelope]  (never raises)

Run:
  python -m intel.cftc_cot_adapter
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple, Optional
import random

from intel.intel_envelope import IntelEnvelope


def compute_cftc_cot_crowding(market: str = "SP500") -> Tuple[Optional[IntelEnvelope], str]:
    """
    Demo crowding signal:
    - pressure: 0..1 (higher = more crowded / riskier)
    - confidence: modest, because this is a placeholder until we wire real COT data.
    """
    try:
        # Placeholder logic: stable pseudo-random based on day to avoid "always changing"
        seed = int(datetime.now(timezone.utc).strftime("%Y%m%d"))
        rnd = random.Random(seed)
        pressure = round(rnd.uniform(0.25, 0.75), 3)

        env = IntelEnvelope.create(
            provider="cftc",
            intel_type="positioning",
            signal_class="crowding",
            instrument_scope="EQUITY",
            raw={"market": market, "note": "demo placeholder until real COT wiring"},
            confidence=0.60,
            severity=pressure,
            rea_instrument=None,
        )
        return env, "ok"
    except Exception as e:
        return None, f"fail:{type(e).__name__}"


def fetch_cftc_cot_safe() -> List[IntelEnvelope]:
    """
    Collector contract: returns [] on failure, never raises.
    """
    try:
        env, status = compute_cftc_cot_crowding("SP500")
        if env is None:
            return []
        env_raw = dict(env.raw)
        env_raw["fetch_status"] = status
        return [
            IntelEnvelope.create(
                provider=env.provider,
                intel_type=env.intel_type,
                signal_class=env.signal_class,
                instrument_scope=env.instrument_scope,
                raw=env_raw,
                confidence=env.confidence,
                severity=env.severity,
                rea_instrument=None,
            )
        ]
    except Exception:
        return []


if __name__ == "__main__":
    envs = fetch_cftc_cot_safe()
    print(f"CFTC_COT_SAFE_OK: {len(envs)}")
    for e in envs:
        print(e)
