"""
REA Engine – Live Ingress Gate
------------------------------
Purpose:
- Single, auditable entry point for ALL live market data
- Enforces governance and sanity checks BEFORE engine consumption
- Read-only: no trading, no execution

Inputs:
- Normalized MarketDataTick dict (provider-agnostic)

Outputs:
- ACCEPTED / REJECTED decision
- Structured audit event (stdout + optional audit_logs)

Design principles:
- Fail-closed (reject on any ambiguity)
- Deterministic validation
- No provider symbol leakage into strategy logic
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any


# -----------------------------
# Models
# -----------------------------

@dataclass(frozen=True)
class MarketDataTick:
    ts_utc: str
    provider: str
    rea_instrument: str
    provider_symbol: str
    bid: Optional[float]
    ask: Optional[float]
    mid: Optional[float]
    source: str


@dataclass(frozen=True)
class IngressDecision:
    accepted: bool
    reason: str
    ts_utc: str
    provider: str
    rea_instrument: str


# -----------------------------
# Policy configuration
# -----------------------------

# Allowed providers (expand later)
ALLOWED_PROVIDERS = {"alpaca"}

# Max acceptable clock skew
MAX_SKEW = timedelta(seconds=30)

# Audit directory
AUDIT_DIR = Path("audit_logs")


# -----------------------------
# Helpers
# -----------------------------

def _parse_utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _write_audit(obj: Dict[str, Any], prefix: str) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{prefix}_{_now_utc().strftime('%Y%m%dT%H%M%SZ')}.json"
    path = AUDIT_DIR / fname
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    return path


# -----------------------------
# Ingress Gate
# -----------------------------

def validate_and_ingress(tick: MarketDataTick, audit: bool = True) -> IngressDecision:
    """
    Validate a normalized MarketDataTick before engine consumption.
    """

    now = _now_utc()

    # Provider allowlist
    if tick.provider not in ALLOWED_PROVIDERS:
        decision = IngressDecision(
            accepted=False,
            reason=f"Provider not allowed: {tick.provider}",
            ts_utc=now.isoformat(),
            provider=tick.provider,
            rea_instrument=tick.rea_instrument,
        )
        if audit:
            _write_audit(asdict(decision), "ingress_reject")
        return decision

    # Timestamp sanity
    try:
        tick_ts = _parse_utc(tick.ts_utc)
    except Exception:
        decision = IngressDecision(
            accepted=False,
            reason="Invalid timestamp format",
            ts_utc=now.isoformat(),
            provider=tick.provider,
            rea_instrument=tick.rea_instrument,
        )
        if audit:
            _write_audit(asdict(decision), "ingress_reject")
        return decision

    if abs(now - tick_ts) > MAX_SKEW:
        decision = IngressDecision(
            accepted=False,
            reason="Timestamp skew exceeds policy",
            ts_utc=now.isoformat(),
            provider=tick.provider,
            rea_instrument=tick.rea_instrument,
        )
        if audit:
            _write_audit(asdict(decision), "ingress_reject")
        return decision

    # Price sanity
    prices = [p for p in (tick.bid, tick.ask, tick.mid) if p is not None]
    if not prices or any(p <= 0 for p in prices):
        decision = IngressDecision(
            accepted=False,
            reason="Invalid or missing price fields",
            ts_utc=now.isoformat(),
            provider=tick.provider,
            rea_instrument=tick.rea_instrument,
        )
        if audit:
            _write_audit(asdict(decision), "ingress_reject")
        return decision

    # ACCEPT
    decision = IngressDecision(
        accepted=True,
        reason="Accepted",
        ts_utc=now.isoformat(),
        provider=tick.provider,
        rea_instrument=tick.rea_instrument,
    )

    if audit:
        _write_audit(
            {
                "decision": asdict(decision),
                "tick": asdict(tick),
            },
            "ingress_accept",
        )

    return decision


# -----------------------------
# CLI test harness
# -----------------------------

def _demo_tick() -> MarketDataTick:
    return MarketDataTick(
        ts_utc=_now_utc().isoformat(),
        provider="alpaca",
        rea_instrument="REA:CRYPTO:BTCUSD",
        provider_symbol="BTC/USD",
        bid=100.0,
        ask=101.0,
        mid=100.5,
        source="snapshot",
    )


def main() -> int:
    tick = _demo_tick()
    decision = validate_and_ingress(tick, audit=True)
    print(json.dumps(asdict(decision), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
