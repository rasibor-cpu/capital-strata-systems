# -*- coding: utf-8 -*-
"""
REA Capital — Module 5: Signal Arbitrator (Conflict Resolver) — Prompt-only, No Execution

Purpose:
- Consume NormalizedSignal objects from Module 4
- Resolve conflicts across sources/types into a single EngineDecision per symbol
- Output is deterministic and auditable (NO execution)

Inputs:
- normalized_signals: List[NormalizedSignal] from module4_signal_selector.py

Outputs:
- EngineDecision: (symbol, intent, confidence, net_score, reason, as_of_utc, ttl_seconds, sources_used)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone
import json


# =========================
# Canonical outputs
# =========================

@dataclass(frozen=True)
class EngineDecision:
    symbol: str
    intent: str                 # LONG / SHORT / NONE
    confidence: float           # 0..1
    net_score: float            # signed: + => LONG bias, - => SHORT bias
    reason: str
    as_of_utc: str
    ttl_seconds: int
    sources_used: List[str]
    diagnostics: Dict[str, Any]


# =========================
# Arbitration policy
# =========================

class SignalArbitrator:
    """
    Policy:
    - Convert each NormalizedSignal into a signed contribution:
        dir_sign = +1 for LONG, -1 for SHORT, 0 for NONE
        contribution = dir_sign * confidence * source_weight * type_weight
    - Aggregate net_score across signals for the same symbol.
    - Decision:
        if abs(net_score) < decision_threshold -> NONE
        else LONG if net_score > 0 else SHORT
    - confidence is derived from abs(net_score) clamped to 0..1 (with soft scaling)
    """

    def __init__(
        self,
        decision_threshold: float = 0.35,
        min_signal_confidence: float = 0.60,
        ttl_seconds: int = 600
    ):
        self.decision_threshold = decision_threshold
        self.min_signal_confidence = min_signal_confidence
        self.ttl_seconds = ttl_seconds

        # Source weights (Tier-1 wires > press > aggregators)
        self.source_weight = {
            "Bloomberg": 1.00,
            "Reuters": 1.00,

            "WSJ": 0.85,
            "FinancialTimes": 0.85,
            "CNBC": 0.75,
            "MarketWatch": 0.70,

            "FOMC": 0.90,
            "US_Treasury": 0.85,
            "ECB": 0.80,
            "BoE": 0.80,
            "BoJ": 0.80,
            "IMF": 0.70,
            "WorldBank": 0.65,

            "Nasdaq": 0.90,
            "S&P": 0.90,
            "LSE": 0.70,
            "Euronext": 0.70,
            "HKEX": 0.70,
            "NGX": 0.60,
            "JSE_SA": 0.60,
            "TSX": 0.70,

            "YahooFinance": 0.55,
        }

        # Type weights (technical tends to be faster; macro/policy slower)
        self.type_weight = {
            "INDEX_BREAKOUT": 1.00,
            "MARKET_BREADTH": 0.95,
            "INDEX_TREND": 0.85,
            "LOCAL_BREADTH": 0.75,

            "NEWS_SENTIMENT": 0.80,
            "BREAKING_NEWS": 0.80,
            "MARKET_OVERVIEW": 0.75,
            "MARKET_COMMENTARY": 0.70,
            "GLOBAL_MARKETS": 0.75,
            "MACRO_NEWS": 0.85,

            "MONETARY_POLICY": 0.65,
            "YIELD_SIGNAL": 0.70,
            "GLOBAL_MACRO": 0.65,
        }

    def arbitrate(self, normalized_signals: List[Any]) -> List[EngineDecision]:
        by_symbol: Dict[str, List[Any]] = {}
        for s in normalized_signals:
            sym = (getattr(s, "symbol", "") or "").strip().upper()
            if not sym:
                continue
            by_symbol.setdefault(sym, []).append(s)

        out: List[EngineDecision] = []
        for sym, sigs in by_symbol.items():
            decision = self._decide_one(sym, sigs)
            if decision is not None:
                out.append(decision)
        return out

    def _decide_one(self, symbol: str, sigs: List[Any]) -> Optional[EngineDecision]:
        contributions: List[Tuple[float, str]] = []
        sources_used: List[str] = []
        kept = 0
        dropped = 0

        # As-of time: latest as_of_utc we saw
        latest_asof = None

        for s in sigs:
            direction = str(getattr(s, "direction", "NONE")).upper()
            conf = float(getattr(s, "confidence", 0.0))
            prov = str(getattr(s, "provider", "UNKNOWN"))
            stype = str(getattr(s, "signal_type", "UNKNOWN")).upper()
            asof = str(getattr(s, "as_of_utc", ""))

            if asof:
                latest_asof = max(latest_asof or asof, asof)

            if direction not in ("LONG", "SHORT") or conf < self.min_signal_confidence:
                dropped += 1
                continue

            kept += 1
            dir_sign = 1.0 if direction == "LONG" else -1.0
            sw = float(self.source_weight.get(prov, 0.60))
            tw = float(self.type_weight.get(stype, 0.70))
            contrib = dir_sign * conf * sw * tw

            contributions.append((contrib, f"{prov}:{stype}:{direction} (c={conf:.2f}, sw={sw:.2f}, tw={tw:.2f})"))
            sources_used.append(prov)

        if not contributions:
            return EngineDecision(
                symbol=symbol,
                intent="NONE",
                confidence=0.0,
                net_score=0.0,
                reason="No actionable signals above threshold",
                as_of_utc=latest_asof or _utc_now(),
                ttl_seconds=self.ttl_seconds,
                sources_used=[],
                diagnostics={"kept": kept, "dropped": dropped},
            )

        net = sum(c for c, _ in contributions)

        # Decision threshold
        if abs(net) < self.decision_threshold:
            intent = "NONE"
        else:
            intent = "LONG" if net > 0 else "SHORT"

        # Confidence (soft scaling): map abs(net) -> 0..1
        conf_out = _clamp01(abs(net) / 1.25)

        # Keep reason short but auditable: top 3 contributions by absolute size
        top = sorted(contributions, key=lambda x: abs(x[0]), reverse=True)[:3]
        reason = " | ".join([t[1] for t in top])

        # Diagnostics
        diag = {
            "net_score": round(net, 4),
            "decision_threshold": self.decision_threshold,
            "min_signal_confidence": self.min_signal_confidence,
            "kept": kept,
            "dropped": dropped,
            "top_contributions": [{"contrib": round(c, 4), "detail": d} for c, d in top],
        }

        return EngineDecision(
            symbol=symbol,
            intent=intent,
            confidence=round(conf_out, 2),
            net_score=round(net, 4),
            reason=reason,
            as_of_utc=latest_asof or _utc_now(),
            ttl_seconds=self.ttl_seconds,
            sources_used=sorted(list(set(sources_used))),
            diagnostics=diag,
        )


# =========================
# Helpers
# =========================

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


# =========================
# Demo (Safe): pulls Module 4 output and arbitrates
# =========================

if __name__ == "__main__":
    # Import module 4 types + run its pipeline
    import module4_signal_selector as m4

    agg = m4.SignalAggregator(connectors=m4.default_connectors(), min_confidence=0.60)
    normalized = agg.collect()

    arb = SignalArbitrator(decision_threshold=0.35, min_signal_confidence=0.60, ttl_seconds=600)
    decisions = arb.arbitrate(normalized)

    print("=== MODULE 5: ARBITRATOR OUTPUT ===")
    print("Normalized signals:", len(normalized))
    print("Decisions:", len(decisions))
    for d in decisions:
        print(json.dumps(d.__dict__, indent=2))