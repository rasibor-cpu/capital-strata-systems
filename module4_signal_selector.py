# -*- coding: utf-8 -*-
"""
REA Capital — Module 4: Global Signal Aggregator + Connectors (Prompt-only, No Execution)

Modes (single-setting deployment):
- ENV_MODE=TEST (default): all connectors return deterministic stubs
- ENV_MODE=LIVE: connectors are gated and DEFAULT to returning nothing until wired to real APIs

Extra safety/testing bridge:
- LIVE_SANDBOX=1
  LIVE mode behavior (enable-gating enforced) but uses stubs so we can test pipeline end-to-end
  before we wire real APIs. This is how we avoid breaking deployment later.

Enable gating in LIVE or LIVE_SANDBOX:
- ENABLE_CONNECTORS=Reuters,Bloomberg,Nasdaq
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Protocol, Tuple
from datetime import datetime, timezone
import os
import json


# =========================
# ENV / SETTINGS CONTROL
# =========================

def env_mode() -> str:
    mode = (os.getenv("ENV_MODE", "TEST") or "TEST").strip().upper()
    return "LIVE" if mode == "LIVE" else "TEST"


def is_live() -> bool:
    return env_mode() == "LIVE"


def live_sandbox() -> bool:
    """
    LIVE_SANDBOX=1 => in LIVE mode, return stubs but still enforce ENABLE_CONNECTORS gating.
    This allows safe end-to-end testing of the LIVE pathway.
    """
    return (os.getenv("LIVE_SANDBOX", "0") or "0").strip() == "1"


def enabled_connectors_csv() -> List[str]:
    raw = os.getenv("ENABLE_CONNECTORS", "") or ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts


def connector_enabled(name: str) -> bool:
    """
    - TEST: all enabled (stubs)
    - LIVE / LIVE_SANDBOX: enabled only if in ENABLE_CONNECTORS
    """
    if not is_live():
        return True
    allow = set(enabled_connectors_csv())
    return name in allow


# =========================
# CANONICAL MODELS
# =========================

@dataclass(frozen=True)
class RawExternalSignal:
    provider: str
    received_at_utc: str
    payload: Dict[str, Any]


@dataclass(frozen=True)
class NormalizedSignal:
    provider: str
    symbol: str
    signal_type: str
    direction: str
    confidence: float
    as_of_utc: str
    meta: Dict[str, Any]


@dataclass(frozen=True)
class TradeIntent:
    symbol: str
    intent: str
    signal_type: str
    confidence: float
    reason: str
    as_of_utc: str
    ttl_seconds: int
    sources: List[str]


# =========================
# CONNECTOR INTERFACE
# =========================

class Connector(Protocol):
    name: str
    def fetch_signals(self) -> List[RawExternalSignal]:
        ...


# =========================
# UTILITIES
# =========================

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _mk_news(provider: str, symbol: str, sig_type: str, sentiment: str, conf: float, headline: str) -> RawExternalSignal:
    return RawExternalSignal(
        provider=provider,
        received_at_utc=_utc_now(),
        payload={
            "symbol": symbol,
            "type": sig_type,
            "sentiment": sentiment,
            "confidence": conf,
            "as_of_utc": _utc_now(),
            "headline": headline,
        },
    )


def _mk_feed(provider: str, symbol: str, sig_type: str, direction: str, conf: float, **meta: Any) -> RawExternalSignal:
    payload = {
        "symbol": symbol,
        "signal_type": sig_type,
        "direction": direction,
        "confidence": conf,
        "as_of_utc": _utc_now(),
    }
    payload.update(meta)
    return RawExternalSignal(provider=provider, received_at_utc=_utc_now(), payload=payload)


# =========================
# CONNECTORS (Verified Sources) — stubs now, live later
# =========================

class BloombergConnector:
    name = "Bloomberg"
    def fetch_signals(self) -> List[RawExternalSignal]:
        if not connector_enabled(self.name):
            return []
        # TEST => stubs
        if not is_live():
            return [_mk_news(self.name, "SPY", "NEWS_SENTIMENT", "POSITIVE", 0.68, "Macro data surprises to upside")]
        # LIVE => if sandbox, stubs; else empty until real API wired
        if live_sandbox():
            return [_mk_news(self.name, "SPY", "NEWS_SENTIMENT", "POSITIVE", 0.68, "[SANDBOX] Bloomberg stub signal")]
        return []


class ReutersConnector:
    name = "Reuters"
    def fetch_signals(self) -> List[RawExternalSignal]:
        if not connector_enabled(self.name):
            return []
        if not is_live():
            return [_mk_news(self.name, "SPY", "MACRO_NEWS", "RISK_ON", 0.72, "Global markets rise amid easing inflation fears")]
        if live_sandbox():
            return [_mk_news(self.name, "SPY", "MACRO_NEWS", "RISK_ON", 0.72, "[SANDBOX] Reuters stub signal")]
        return []


class NasdaqConnector:
    name = "Nasdaq"
    def fetch_signals(self) -> List[RawExternalSignal]:
        if not connector_enabled(self.name):
            return []
        if not is_live():
            return [_mk_feed(self.name, "SPY", "INDEX_BREAKOUT", "LONG", 0.62, level=487.10)]
        if live_sandbox():
            return [_mk_feed(self.name, "SPY", "INDEX_BREAKOUT", "LONG", 0.62, level=487.10, note="[SANDBOX] Nasdaq stub feed")]
        return []


# (Global set — always available in TEST, and in LIVE_SANDBOX when enabled)
class FOMCConnector:
    name = "FOMC"
    def fetch_signals(self) -> List[RawExternalSignal]:
        if not connector_enabled(self.name) and is_live():
            return []
        if not is_live():
            return [_mk_news(self.name, "SPY", "MONETARY_POLICY", "NEUTRAL", 0.60, "Fed reiterates data-dependent stance")]
        if live_sandbox():
            return [_mk_news(self.name, "SPY", "MONETARY_POLICY", "NEUTRAL", 0.60, "[SANDBOX] FOMC stub")]
        return []


# =========================
# NORMALIZATION
# =========================

class Normalizer:
    def normalize(self, raw: RawExternalSignal) -> Optional[NormalizedSignal]:
        p = raw.payload
        prov = raw.provider
        try:
            if "type" in p and "sentiment" in p:
                return self._norm_news(raw)
            return self._norm_generic(raw)
        except Exception:
            return None

    def _norm_news(self, raw: RawExternalSignal) -> NormalizedSignal:
        p = raw.payload
        symbol = str(p.get("symbol", "")).strip().upper()
        sig_type = str(p.get("type", "NEWS")).strip().upper()

        sentiment = str(p.get("sentiment", "NEUTRAL")).upper()
        direction = "NONE"
        if sentiment in ("POSITIVE", "BULLISH", "RISK_ON"):
            direction = "LONG"
        elif sentiment in ("NEGATIVE", "BEARISH", "RISK_OFF"):
            direction = "SHORT"

        conf = _clamp01(float(p.get("confidence", 0.5)))
        as_of = p.get("as_of_utc") or raw.received_at_utc
        meta = {k: v for k, v in p.items() if k not in ("symbol", "type", "sentiment", "confidence", "as_of_utc")}
        return NormalizedSignal(raw.provider, symbol, sig_type, direction, conf, str(as_of), meta)

    def _norm_generic(self, raw: RawExternalSignal) -> NormalizedSignal:
        p = raw.payload
        symbol = str(p.get("symbol") or p.get("ticker") or "").strip().upper()
        sig_type = str(p.get("signal_type") or p.get("signal") or "UNKNOWN").strip().upper()
        direction = str(p.get("direction", "NONE")).strip().upper()
        if direction not in ("LONG", "SHORT"):
            direction = "NONE"
        conf = _clamp01(float(p.get("confidence", 0.5)))
        as_of = p.get("as_of_utc") or raw.received_at_utc
        meta = {k: v for k, v in p.items() if k not in ("symbol", "ticker", "signal_type", "signal", "direction", "confidence", "as_of_utc")}
        return NormalizedSignal(raw.provider, symbol, sig_type, direction, conf, str(as_of), meta)


# =========================
# AGGREGATOR
# =========================

class SignalAggregator:
    def __init__(self, connectors: List[Connector], min_confidence: float = 0.60):
        self.connectors = connectors
        self.normalizer = Normalizer()
        self.min_confidence = min_confidence

    def collect(self) -> List[NormalizedSignal]:
        raw: List[RawExternalSignal] = []
        for c in self.connectors:
            raw.extend(c.fetch_signals())

        norm: List[NormalizedSignal] = []
        for r in raw:
            ns = self.normalizer.normalize(r)
            if ns is not None and ns.symbol:
                norm.append(ns)
        return norm

    def interpret(self, signals: List[NormalizedSignal]) -> List[TradeIntent]:
        by_symbol: Dict[str, List[NormalizedSignal]] = {}
        for s in signals:
            by_symbol.setdefault(s.symbol, []).append(s)

        intents: List[TradeIntent] = []
        for symbol, sigs in by_symbol.items():
            ti = self._select_best(symbol, sigs)
            if ti is not None:
                intents.append(ti)
        return intents

    def _select_best(self, symbol: str, sigs: List[NormalizedSignal]) -> Optional[TradeIntent]:
        candidates: List[Tuple[float, NormalizedSignal]] = []
        for s in sigs:
            if s.direction in ("LONG", "SHORT") and s.confidence >= self.min_confidence:
                candidates.append((s.confidence, s))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_conf, best = candidates[0]
        ttl = 600
        reason = f"{best.provider}:{best.signal_type}->{best.direction} (conf={best_conf:.2f})"
        sources = sorted({s.provider for _, s in candidates})

        return TradeIntent(
            symbol=symbol,
            intent=best.direction,
            signal_type=best.signal_type,
            confidence=round(best_conf, 2),
            reason=reason,
            as_of_utc=best.as_of_utc,
            ttl_seconds=ttl,
            sources=sources,
        )


def default_connectors() -> List[Connector]:
    return [
        BloombergConnector(),
        ReutersConnector(),
        NasdaqConnector(),
        FOMCConnector(),
    ]


# =========================
# DEMO
# =========================

if __name__ == "__main__":
    print("ENV_MODE =", env_mode())
    print("LIVE_SANDBOX =", "1" if live_sandbox() else "0")
    if is_live():
        print("ENABLE_CONNECTORS =", ",".join(enabled_connectors_csv()) or "(none)")

    agg = SignalAggregator(connectors=default_connectors(), min_confidence=0.60)
    normalized = agg.collect()
    intents = agg.interpret(normalized)

    print("\n=== MODULE 4: SIGNAL AGGREGATOR OUTPUT ===")
    print("Normalized signals:", len(normalized))
    for s in normalized:
        print(json.dumps(s.__dict__, indent=2))

    print("\nTrade intents:", len(intents))
    for i in intents:
        print(json.dumps(i.__dict__, indent=2))