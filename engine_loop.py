from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from data.models import Bar
from data.controller import DataController, ControllerConfig
from regime.gate import RegimeGate, RegimeResult, RegimeDecision
from signals.vwap_mean_reversion import VWAPMeanReversionEngine, SignalPolicy, SignalPrompt
from signals.queue import SignalApprovalQueue, QueuePolicy


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


class REACapitalEngineLoop:
    """
    REA Capital – Trading Engine
    Engine Loop (Broker-Free, Prompt-Only)

    Wires together:
    - Module 1: DataController (1m validation, safe mode, 5m builder, session gating)
    - Module 2: RegimeGate (vol, trend, macro/political gate)
    - Module 3: VWAP mean-reversion signal engine (prompt-only)
    - SignalApprovalQueue (stores pending prompts)

    Non-negotiable:
    - No auto execution
    - No auto risk escalation
    - Mode/risk level persists until user changes it
    """

    def __init__(self, cfg: Optional[EngineConfig] = None):
        self.cfg = cfg or EngineConfig()

        # Module 1
        self.data = DataController(
            ControllerConfig(symbol=self.cfg.symbol),
        )

        # Module 2
        self.regime = RegimeGate()

        # Module 3
        self.signal_engine = VWAPMeanReversionEngine(self.cfg.signal_policy)

        # Queue
        self.queue = SignalApprovalQueue(self.cfg.queue_policy)

        # State: persists until user changes it
        self.risk_level: int = self.cfg.default_risk_level

        # Rolling 5m history
        self._bars_5m: List[Bar] = []

        # Last known regime result (visibility)
        self.last_regime: Optional[RegimeResult] = None

    # -----------------------
    # Manual controls (never auto)
    # -----------------------

    def set_risk_level(self, level: int) -> None:
        """
        Manual only. This does NOT execute anything.
        """
        if level < 1 or level > 5:
            raise ValueError("risk_level must be between 1 and 5")
        self.risk_level = level

    def bars_5m(self) -> List[Bar]:
        return list(self._bars_5m)

    # -----------------------
    # Main ingestion method
    # -----------------------

    def on_bar_1m(self, bar1m: Bar, received_at_utc: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Ingest one 1-minute bar and return a structured snapshot.

        Returns a dict with:
        - data_ok/time_ok eligibility
        - safe mode status
        - last regime decision/reasons (evaluated when 5m bar completes)
        - any prompt queued
        - queue summary
        - risk level (persistent until user changes it)
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
                prompt = self.signal_engine.evaluate(
                    symbol=self.cfg.symbol,
                    bars_5m=self._bars_5m,
                    regime=self.last_regime,
                    as_of_utc=received_at_utc,
                    current_risk_level=self.risk_level,
                )

                if isinstance(prompt, SignalPrompt):
                    accepted, msg = self.queue.enqueue(prompt, now_utc=received_at_utc.replace(tzinfo=None))
                    snap["prompt_queued"] = bool(accepted)
                    snap["prompt_summary"] = prompt.summary() + (f"\nQueue: {msg}" if msg else "")

        # Queue summary always
        snap["queue_pending_count"] = len(self.queue.list_pending())
        snap["queue_top"] = [x.prompt.summary() for x in self.queue.top_n(3)]
        return snap
