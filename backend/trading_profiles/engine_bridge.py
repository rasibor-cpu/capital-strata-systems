"""Bridge from CSS engine signal producers into the governed TradingRouter (paper only).

Every CSS engine signal for CSS-Assisted, CSS Autonomous and Simulated followers must enter
through `TradingRouter.on_css_engine_signal` (and so through consent, personality, sizing,
capital governors, TQ/CAIE, R14F, R7, ExecutionGate and AntiBleed). This module is the only
supported way for an engine process to do that.

Provenance control: today no CSS producer emits a calibrated, real-data trade signal.
  * The legacy dashboard loop picks symbols at random with constant scores
    (scripts/css_live_dashboard.py select_cycle_candidates) -> LEGACY_RANDOM_CANDIDATE.
  * EngineLoop (engine/engine_loop.py) computes real direction and edge from bars, but has
    no probability and no R14F-scale signal score; it becomes routable only with an
    owner-approved CALIBRATION that maps its event to (probability, signal_score).
Only provenances in ROUTABLE_PROVENANCES reach followers; everything else is refused and the
refusal recorded. Nothing here invents a probability or a score.
"""
from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping

from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, SourceSignal
from backend.trading_profiles.router import RouteResult, TradingRouter

LOGGER = logging.getLogger(__name__)


class Provenance(str, Enum):
    ENGINE_LOOP_CALIBRATED = "ENGINE_LOOP_CALIBRATED"
    LEGACY_RANDOM_CANDIDATE = "LEGACY_RANDOM_CANDIDATE"
    UNCALIBRATED = "UNCALIBRATED"
    # Real-market-data producer (backend/signals). Never accepted through publish(): only through
    # publish_real_data(), which re-verifies the dual-control calibration approval itself.
    REAL_DATA_CALIBRATED = "REAL_DATA_CALIBRATED"


ROUTABLE_PROVENANCES = frozenset({Provenance.ENGINE_LOOP_CALIBRATED})
# Returns a mapping with REQUIRED probability (0..1) and signal_score (R14F scale), and OPTIONAL
# calibrated quality inputs (CALIBRATED_OPTIONAL); or None when the calibration declines.
# Anything the calibration does not supply keeps the conservative SourceSignal default.
Calibration = Callable[[Mapping[str, Any]], "Mapping[str, Any] | None"]
CALIBRATED_OPTIONAL = ("strategy_score", "replay_confidence", "liquidity_score", "regime_alignment", "risk_score",
                       "market_regime", "volatility_state", "confidence")


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def source_signal_from_engine_event(event: Mapping[str, Any], calibration: Calibration | None,
                                    *, asset_class: str) -> tuple[SourceSignal | None, Provenance, str]:
    """Convert an EngineLoop event. Units: EngineLoop stop is a FRACTION; SourceSignal uses PERCENT."""
    direction = str(event.get("direction") or "").upper()
    if direction not in {"BUY", "SELL"}:
        return None, Provenance.UNCALIBRATED, "engine_event_not_directional"
    price, strength, stop = event.get("price"), event.get("strength"), event.get("stop_distance_fraction")
    if not all(_finite(v) and v > 0 for v in (price, strength, stop)):
        return None, Provenance.UNCALIBRATED, "engine_event_incomplete"
    if calibration is None:
        return None, Provenance.UNCALIBRATED, "engine_signal_uncalibrated"
    try:
        calibrated = calibration(event)
    except Exception:
        calibrated = None
    if not calibrated or not isinstance(calibrated, Mapping):
        return None, Provenance.UNCALIBRATED, "engine_signal_calibration_declined"
    probability, score = calibrated.get("probability"), calibrated.get("signal_score")
    if not (_finite(probability) and 0 < probability < 1 and _finite(score) and score > 0):
        return None, Provenance.UNCALIBRATED, "engine_signal_calibration_invalid"
    extra = {k: calibrated[k] for k in CALIBRATED_OPTIONAL if k in calibrated}
    if any(not (isinstance(v, str) or (_finite(v) and v >= 0)) for v in extra.values()):
        return None, Provenance.UNCALIBRATED, "engine_signal_calibration_invalid"
    costs = {k: float(event.get(k, 0.0)) for k in ("fee_bps", "spread_bps", "slippage_bps")}
    if not all(_finite(v) and v >= 0 for v in costs.values()):
        return None, Provenance.UNCALIBRATED, "engine_event_costs_invalid"
    stop_pct = float(stop) * 100.0
    expected_move_bps = float(strength) * 100.0  # EngineLoop's own convention (engine_loop.py)
    digest = hashlib.sha256(f"{event.get('instrument')}|{event.get('step')}|{direction}|{price}".encode()).hexdigest()[:16]
    signal = SourceSignal(
        signal_id=f"eng-{digest}", trader_id=AUTONOMOUS_SOURCE_ID, symbol=str(event["instrument"]),
        asset_class=asset_class.upper(), side=direction, reference_price=float(price), probability=float(probability),
        signal_score=float(score), expected_move_bps=expected_move_bps,
        stop_distance_pct=stop_pct, risk_reward=expected_move_bps / (stop_pct * 100.0), **costs,
        regime_persistence=float(event.get("regime_persistence", 0.6)),
        **{"confidence": float(probability), **extra})
    return signal, Provenance.ENGINE_LOOP_CALIBRATED, "ok"


class CssEngineSignalBridge:
    """Publishes engine signals into the router, refusing non-approved provenance (recorded)."""

    def __init__(self, router: TradingRouter, *, routable: frozenset[Provenance] = ROUTABLE_PROVENANCES) -> None:
        self.router = router
        self.routable = frozenset(routable) & ROUTABLE_PROVENANCES  # can narrow, never widen
        self.refusals: list[dict[str, Any]] = []

    def publish(self, signal: SourceSignal | None, provenance: Provenance, *, reason: str = "ok",
                now: datetime | None = None) -> RouteResult:
        now = now or datetime.now(timezone.utc)
        sid = signal.signal_id if signal is not None else "none"
        if signal is None or provenance not in self.routable:
            why = reason if signal is None else f"engine_signal_provenance_not_approved:{provenance.value}"
            self.refusals.append({"signal_id": sid, "provenance": provenance.value, "reason": why, "at_utc": now.isoformat()})
            LOGGER.info("CSS engine signal refused: %s %s", sid, why)
            return RouteResult(sid, False, why)
        return self.router.on_css_engine_signal(signal, now=now)

    def publish_real_data(self, produced: Any, artifact: Mapping[str, Any], approvals: Any, *,
                          now: datetime | None = None) -> RouteResult:
        """Route a backend.signals.producer signal only if its calibration is approved right now."""
        now = now or datetime.now(timezone.utc)
        signal = getattr(produced, "signal", None)
        sid = signal.signal_id if signal is not None else "none"

        def refuse(why: str) -> RouteResult:
            self.refusals.append({"signal_id": sid, "provenance": Provenance.REAL_DATA_CALIBRATED.value,
                                  "reason": why, "at_utc": now.isoformat()})
            return RouteResult(sid, False, why)

        if signal is None:
            return refuse(str(getattr(produced, "reason", "no_signal")))
        if getattr(produced, "artifact_sha256", None) != artifact.get("artifact_sha256"):
            return refuse("signal_artifact_mismatch")
        ok, why = approvals.status(artifact)
        if not ok:
            return refuse(f"calibration_not_routable:{why}")
        return self.router.on_css_engine_signal(signal, now=now)

    def engine_loop_sink(self, calibration: Calibration | None, *, asset_class: str) -> Callable[[Mapping[str, Any]], None]:
        """A callable to assign to EngineLoop.css_signal_sink."""
        def sink(event: Mapping[str, Any]) -> None:
            signal, provenance, reason = source_signal_from_engine_event(event, calibration, asset_class=asset_class)
            self.publish(signal, provenance, reason=reason)
        return sink

    def publish_legacy_candidate(self, *, symbol: str, asset_class: str, signal_score: float, probability: float,
                                 now: datetime | None = None) -> RouteResult:
        """Legacy dashboard candidates are random: always refused, never routed to followers."""
        return self.publish(None, Provenance.LEGACY_RANDOM_CANDIDATE,
                            reason="engine_signal_provenance_not_approved:LEGACY_RANDOM_CANDIDATE", now=now)
