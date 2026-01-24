from signals.vwap_mean_reversion import VWAPMeanReversionPrompt
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from data.models import Bar
from data.controller import DataController, ControllerConfig
from regime.gate import RegimeGate, RegimeResult, RegimeDecision
from signals.vwap_mean_reversion import VWAPMeanReversionEngine, SignalPolicy, SignalPrompt
from signals.queue import SignalApprovalQueue, QueuePolicy

from module3_signal import VWAPMeanReversionSignal


@dataclass
class EngineConfig:
    symbol: str = "SPY"

    # How many 5m bars to keep in memory (rolling)
    max_5m_history: int = 500

    # Dataclass-safe defaults (Python 3.14+)
    signal_policy: SignalPolicy = field(default_factory=SignalPolicy)
    queue_policy: QueuePolicy = field(default_factory=QueuePolicy)

    # Default operating risk level (advisory only, 1–5)
    default_risk_level: int = 2

    # -------------------------------
    # Module 3 prompt-generation knobs
    # -------------------------------
    vwap_reversion_bps: float = 12.0
    min_confidence: float = 0.65
    prompt_cooldown_bars: int = 5


@dataclass(frozen=True)
class SignalState:
    """
    Minimal state passed to Module 3 prompt generator.
    Python 3.14 safe (immutable).
    """
    symbol: str
    ts: str
    bar_index: int
    price: float
    vwap: float
    regime_allow: bool
    regime_reason: str
    momentum_slowing: bool


class REACapitalEngineLoop:
    """
    REA Capital – Trading Engine
    Engine Loop (Broker-Free, Prompt-Only)

    Wires together:
    - Module 1: DataController (1m validation, safe mode, 5m builder, session gating)
    - Module 2: RegimeGate (vol, trend, macro/political gate)
    - Module 3a: VWAPMeanReversionEngine (existing prompt-only engine)
    - Module 3b: VWAPMeanReversionSignal (new prompt generator)
    - SignalApprovalQueue (stores pending prompts)

    Non-negotiable:
    - No auto execution
    - No auto risk escalation
    - Mode/risk level persists until user changes it
    """

    def __init__(self, cfg: Optional[EngineConfig] = None):
        self.cfg = cfg or EngineConfig()

        # Module 1
        self.data = DataController(ControllerConfig(symbol=self.cfg.symbol))

        # Module 2
        self.regime = RegimeGate()

        # Module 3a (existing)
        self.signal_engine = VWAPMeanReversionEngine(self.cfg.signal_policy)

        # Module 3b (new prompt generator)
        self.prompt_engine = VWAPMeanReversionSignal(self.cfg)

        # Queue
        self.queue = SignalApprovalQueue(self.cfg.queue_policy)

        # State: persists until user changes it
        self.risk_level: int = self.cfg.default_risk_level

        # Rolling 5m history
        self._bars_5m: List[Bar] = []

        # Last known regime result (visibility)
        self.last_regime: Optional[RegimeResult] = None

        # 5m bar counter for prompt state indexing
        self._bar5m_index: int = 0

    def set_risk_level(self, level: int) -> None:
        """
        Manual only. This does NOT execute anything.
        """
        if level < 1 or level > 5:
            raise ValueError("risk_level must be between 1 and 5")
        self.risk_level = level

    def bars_5m(self) -> List[Bar]:
        return list(self._bars_5m)

    def _compute_vwap_5m(self, bars_5m: List[Bar]) -> float:
        total_v = sum(b.v for b in bars_5m)
        if total_v <= 0:
            return sum(b.c for b in bars_5m) / len(bars_5m)
        return sum(b.c * b.v for b in bars_5m) / total_v

    def _momentum_slowing_5m(self, bars_5m: List[Bar]) -> bool:
        """
        Simple, robust momentum-slowing proxy:
        last 3 absolute returns are decreasing: |r3| < |r2| < |r1|
        """
        if len(bars_5m) < 4:
            return False
        c0 = bars_5m[-4].c
        c1 = bars_5m[-3].c
        c2 = bars_5m[-2].c
        c3 = bars_5m[-1].c
        r1 = c1 - c0
        r2 = c2 - c1
        r3 = c3 - c2
        return abs(r3) < abs(r2) < abs(r1)

    def on_bar_1m(self, bar1m: Bar, received_at_utc: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Ingest one 1-minute bar and return a structured snapshot.
        """
        if received_at_utc is None:
            received_at_utc = datetime.now(timezone.utc)

        ok_1m, bar5m, issue = self.data.ingest_1m(bar1m, received_at_utc)

        snap: Dict[str, Any] = {
            "ok_1m": ok_1m,
            "issue": None if issue is None else {"code": issue.code, "message": issue.message, "at": issue.at.isoformat()},
            "eligibility": self.data.eligibility_snapshot(bar1m.ts),
            "bar5m_created": False,
            "regime": None,
            "prompt_queued": False,
            "prompt_summary": None,
            "queue_pending_count": 0,
            "queue_top": [],
            "risk_level": self.risk_level,
        }

        if not ok_1m:
            snap["queue_pending_count"] = len(self.queue.list_pending())
            snap["queue_top"] = [x.prompt.summary() for x in self.queue.top_n(3)]
            return snap

        if bar5m is not None:
            snap["bar5m_created"] = True
            self._bars_5m.append(bar5m)
            if len(self._bars_5m) > self.cfg.max_5m_history:
                self._bars_5m = self._bars_5m[-self.cfg.max_5m_history :]

            self._bar5m_index += 1

            # Evaluate regime on each completed 5m bar
            self.last_regime = self.regime.evaluate(self._bars_5m, as_of_utc=received_at_utc)

            snap["regime"] = {
                "decision": self.last_regime.decision.value,
                "reasons": list(self.last_regime.reasons),
                "risk_recommendation": self.last_regime.risk_recommendation,
                "as_of_utc": self.last_regime.as_of_utc.isoformat(),
            }

            # Attempt signals only if eligible and regime allows
            elig = snap["eligibility"]
            if elig["time_ok"] and elig["data_ok"] and self.last_regime.decision == RegimeDecision.ALLOW:
                # Module 3a: existing prompt engine
                prompt_a = self.signal_engine.evaluate(
                    symbol=self.cfg.symbol,
                    bars_5m=self._bars_5m,
                    regime=self.last_regime,
                    as_of_utc=received_at_utc,
                    current_risk_level=self.risk_level,
                )

                # Module 3b: new prompt generator
                vwap = self._compute_vwap_5m(self._bars_5m)
                price = self._bars_5m[-1].c
                momentum_slowing = self._momentum_slowing_5m(self._bars_5m)

                state = SignalState(
                    symbol=self.cfg.symbol,
                    ts=received_at_utc.isoformat(),
                    bar_index=self._bar5m_index,
                    price=price,
                    vwap=vwap,
                    regime_allow=True,
                    regime_reason="; ".join(self.last_regime.reasons),
                    momentum_slowing=momentum_slowing,
                )

                prompt_b = self.prompt_engine.evaluate(state)

                # Queue whichever prompt fires (priority: new prompt engine first)
                if isinstance(prompt_b, dict):
                    accepted, msg = self.queue.enqueue(
                        SignalPrompt(
                            symbol=prompt_b["symbol"],
                            direction="LONG_REVERT" if prompt_b["bias"] == "LONG" else "SHORT_REVERT",
                            zscore=0.0,
                            vwap=prompt_b["vwap"],
                            last_price=prompt_b["price"],
                            volatility=0.0,
                            suggested_risk_level=self.risk_level,
                            confidence=prompt_b["confidence"],
                            as_of_utc=received_at_utc.replace(tzinfo=None),
                            rationale=[prompt_b["regime_reason"], f"dist_bps={prompt_b['dist_bps']}"],
                        ),
                        now_utc=received_at_utc.replace(tzinfo=None),
                    )
                    snap["prompt_queued"] = bool(accepted)
                    snap["prompt_summary"] = f"Module3B queued: {prompt_b} | Queue: {msg}"

                elif isinstance(prompt_a, SignalPrompt):
                    accepted, msg = self.queue.enqueue(prompt_a, now_utc=received_at_utc.replace(tzinfo=None))
                    snap["prompt_queued"] = bool(accepted)
                    snap["prompt_summary"] = prompt_a.summary() + (f"\nQueue: {msg}" if msg else "")

        snap["queue_pending_count"] = len(self.queue.list_pending())
        snap["queue_top"] = [x.prompt.summary() for x in self.queue.top_n(3)]
        return snap
