# -*- coding: utf-8 -*-
"""
REA Capital — Module 6: Risk Engine (Position Sizing & Exposure Control)
PROMPT-ONLY • NO EXECUTION • NO BROKER ACCESS

Purpose:
- Consume EngineDecision-like objects from Module 5
- Convert conviction into bounded, auditable risk limits
- Enforce hard portfolio + symbol caps
- Provide a kill-switch controlled risk envelope

This module NEVER places trades.

ENV:
- KILL_SWITCH=1  -> forces BLOCKED for all symbols
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List
from datetime import datetime, timezone
import os
import json
import traceback


# =========================
# Canonical Output
# =========================

@dataclass(frozen=True)
class RiskEnvelope:
    symbol: str
    intent: str                  # LONG / SHORT / NONE
    max_risk_pct: float          # 0..1
    position_scale: float        # 0..1
    risk_mode: str               # CONSERVATIVE / NORMAL / AGGRESSIVE / BLOCKED
    kill_switch: bool
    reason: str
    as_of_utc: str
    ttl_seconds: int
    diagnostics: Dict[str, Any]


# =========================
# Helpers
# =========================

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _round2(x: float) -> float:
    return float(f"{x:.2f}")


def _env_bool(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or default).strip() in ("1", "true", "TRUE", "yes", "YES")


# =========================
# Risk Engine
# =========================

class RiskEngine:
    """
    Simple, auditable rules:
    - No intent => BLOCKED
    - Confidence below floor => BLOCKED
    - Caps always win
    - Kill switch overrides everything
    """

    def __init__(
        self,
        portfolio_risk_cap: float = 0.75,
        symbol_risk_cap: float = 0.50,
        confidence_floor: float = 0.60,
        kill_switch: bool = False,
    ):
        self.portfolio_risk_cap = float(portfolio_risk_cap)
        self.symbol_risk_cap = float(symbol_risk_cap)
        self.confidence_floor = float(confidence_floor)
        self.kill_switch = bool(kill_switch)

    def evaluate(self, decisions: List[Any]) -> List[RiskEnvelope]:
        return [self._evaluate_one(d) for d in decisions]

    def _evaluate_one(self, d: Any) -> RiskEnvelope:
        symbol = str(getattr(d, "symbol", "")).strip().upper() or "UNKNOWN"
        intent = str(getattr(d, "intent", "NONE")).strip().upper()
        confidence = float(getattr(d, "confidence", 0.0))
        net_score = float(getattr(d, "net_score", 0.0))
        ttl = int(getattr(d, "ttl_seconds", 600))

        # Global block
        if self.kill_switch or intent == "NONE" or symbol == "UNKNOWN":
            return RiskEnvelope(
                symbol=symbol,
                intent="NONE",
                max_risk_pct=0.0,
                position_scale=0.0,
                risk_mode="BLOCKED",
                kill_switch=True,
                reason="Kill switch active or no actionable decision",
                as_of_utc=_utc_now(),
                ttl_seconds=ttl,
                diagnostics={"confidence": confidence, "net_score": net_score},
            )

        # Confidence gate
        if confidence < self.confidence_floor:
            return RiskEnvelope(
                symbol=symbol,
                intent="NONE",
                max_risk_pct=0.0,
                position_scale=0.0,
                risk_mode="BLOCKED",
                kill_switch=True,
                reason=f"Confidence below floor ({confidence:.2f} < {self.confidence_floor:.2f})",
                as_of_utc=_utc_now(),
                ttl_seconds=ttl,
                diagnostics={"confidence": confidence, "net_score": net_score},
            )

        # Mode + base risk
        if confidence >= 0.80:
            mode, base_risk = "AGGRESSIVE", 0.75
        elif confidence >= 0.65:
            mode, base_risk = "NORMAL", 0.50
        else:
            mode, base_risk = "CONSERVATIVE", 0.30

        max_risk = min(base_risk, self.portfolio_risk_cap, self.symbol_risk_cap)
        position_scale = _round2(confidence * max_risk)

        return RiskEnvelope(
            symbol=symbol,
            intent=intent,
            max_risk_pct=_round2(max_risk),
            position_scale=position_scale,
            risk_mode=mode,
            kill_switch=False,
            reason=f"{mode} mode from confidence {confidence:.2f}; capped to {max_risk:.2f}",
            as_of_utc=_utc_now(),
            ttl_seconds=ttl,
            diagnostics={
                "confidence": confidence,
                "net_score": net_score,
                "base_risk": base_risk,
                "portfolio_cap": self.portfolio_risk_cap,
                "symbol_cap": self.symbol_risk_cap,
            },
        )


# =========================
# SAFE STANDALONE TEST
# =========================

if __name__ == "__main__":
    print("=== MODULE 6 BOOT (STANDALONE TEST) ===", flush=True)
    print("cwd =", os.getcwd(), flush=True)
    print("file =", __file__, flush=True)
    print("KILL_SWITCH =", os.getenv("KILL_SWITCH", "0"), flush=True)

    # Dummy decisions to prove engine works (NO Module 5 dependency)
    class DummyDecision:
        def __init__(self, symbol, intent, confidence, net_score, ttl_seconds=600):
            self.symbol = symbol
            self.intent = intent
            self.confidence = confidence
            self.net_score = net_score
            self.ttl_seconds = ttl_seconds

    test_decisions = [
        DummyDecision("EURUSD", "LONG", 0.72, 1.4),
        DummyDecision("SPX", "SHORT", 0.83, -2.1),
        DummyDecision("DOWJONES", "LONG", 0.66, 0.9),
    ]

    engine = RiskEngine(kill_switch=_env_bool("KILL_SWITCH", "0"))
    envelopes = engine.evaluate(test_decisions)

    print("\n=== MODULE 6 OUTPUT ===", flush=True)
    for e in envelopes:
        print(json.dumps(e.__dict__, indent=2), flush=True)