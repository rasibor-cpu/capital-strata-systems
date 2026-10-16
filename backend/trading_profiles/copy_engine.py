"""Copy / autonomous / simulated trade evaluation through the canonical CSS gates.

For one source signal and one follower, the engine applies:
  1. safety:       observed safety-flag verdict SAFE; live-order and global kill switches
  2. consent:      active settings accepted under the current agreement (revalidated now),
                   not paused; personality tightened by the user's own limits
  3. authority:    copy mode needs the consented, valid signed mandate for this trader;
                   autonomous mode only takes CSS engine signals; assisted mode takes CSS
                   proposals or the user's own manual orders and stops for approval
  4. personality:  asset class, probability, drawdown and daily-loss halts, margin state
  5. sizing:       risk budget / stop, capped by position, symbol, total exposure and
                   mandate allocation. Never scaled UP to satisfy any gate minimum.
  6. counts:       personality open-position limit and the global 10-position hard cap
  7. trade quality (TradeQualityScoringEngine) and CAIE score floors
  8. R14F (legacy engine mode in force, unchanged thresholds)
  9. canonical paper chain (CanonicalExecutionIntegration):
       R7 unified trade gate (real per-asset counts 3/3/2/2)
       -> ExecutionGate: AntiBleedGuard (net edge, minimum size 50, cooldown),
          MarginTradeGate, compounding, sizing, drawdown scaler, RiskGovernor
       -> UnifiedExecutionPipeline (validation only, rejects live, no broker dispatch)
 10. deterministic simulated fill and attribution record.

Nothing here can reach a live broker path: execution requests are always paper, and
simulated mode replaces even the validation pipeline with a no-route stub.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping

from backend.allocation.caie_scoring_engine import CAIEScoringEngine
from backend.allocation.opportunity_validator import validate_opportunity_proposal
from backend.analytics.trade_quality_scoring_engine import (
    TradeQualityScoringEngine,
    TradeQualityScoringEngineError,
)
from backend.app.observability.kill_switch import check_kill_switch
from backend.certification.ov002_persistence import PersistenceError, atomic_write_json, read_json_object
from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from backend.execution.canonical_execution_integration import (
    CanonicalExecutionIntegration,
    CanonicalExecutionIntegrationError,
)
from backend.execution.unified_execution_pipeline import UnifiedExecutionPipelineError, UnifiedExecutionResult
from backend.governance.css_unified_trade_gate import MAX_POSITIONS_BY_ASSET
from backend.governance.r14f_profitability_gate import evaluate_r14f
from backend.trading_profiles.attribution import AttributionLedger
from backend.trading_profiles.exits import CopiedPosition
from backend.trading_profiles.mandates import KeyProvider, MandateRegistry, evaluate_mandate
from backend.trading_profiles.operating_modes import OperatingMode, permissions_for
from backend.trading_profiles.consent import ConsentService
from backend.trading_profiles.limits import LimitsError, effective_policy
from backend.trading_profiles.manual import ControlledManual, current_manual
from backend.trading_profiles.preferences import PreferencesError, PreferencesStore
from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.trading_profiles.risk_personalities import RiskPersonality, policy_for
from engine.execution.execution_gate import ExecutionGate
from engine.execution.live_order_kill_switch import evaluate_live_order_kill_switch

AUTONOMOUS_SOURCE_ID = "CSS_AUTONOMOUS_ENGINE"
# Mirrors HARD_TOTAL_OPEN_POSITION_CAP in scripts/css_live_dashboard.py (parity-tested).
HARD_TOTAL_OPEN_POSITION_CAP = 10
LEGACY_ENGINE_MODES = frozenset({"SAFE", "CONSERVATIVE", "BALANCED", "AGGRESSIVE", "EXPANSION"})
SIMULATED_DEFAULT_PERSONALITY = RiskPersonality.BALANCED
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
MANUAL_ORDER_PREFIX = "USER_MANUAL:"
PROPOSAL_TTL = timedelta(minutes=5)
PROPOSALS_SCHEMA = "css.trading_profiles.assisted_proposals.v1"


class ProposalError(RuntimeError):
    """Fail-closed CSS-Assisted proposal error."""


@dataclass(frozen=True)
class SourceSignal:
    signal_id: str
    trader_id: str
    symbol: str
    asset_class: str
    side: str
    reference_price: float
    probability: float
    signal_score: float
    confidence: float
    expected_move_bps: float
    fee_bps: float
    spread_bps: float
    slippage_bps: float
    stop_distance_pct: float
    risk_reward: float
    market_regime: str = "TRENDING"
    strategy_score: float = 0.6
    replay_confidence: float = 0.6
    liquidity_score: float = 0.8
    regime_alignment: float = 0.8
    risk_score: float = 30.0
    volatility_state: str = "MEDIUM"
    regime_persistence: float = 0.6


@dataclass(frozen=True)
class FollowerContext:
    user_id: str
    role: str
    session_id: str
    session_created_epoch: float
    equity: float
    equity_peak: float
    day_start_equity: float
    buying_power: float
    margin_state: str = "NORMAL"
    open_positions: tuple[CopiedPosition, ...] = ()


@dataclass(frozen=True)
class SystemContext:
    engine_mode: str
    safety_flags: Mapping[str, Any] | None
    mobile_controls: Mapping[str, Any] = field(default_factory=dict)
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CopyDecision:
    follower_user_id: str
    signal_id: str
    outcome: str  # COPIED | SIMULATED | REJECTED
    stage: str
    reason: str
    operating_mode: str | None
    personality: str | None
    mandate_id: str | None = None
    position_id: str | None = None
    notional: float = 0.0
    stop_distance_pct: float = 0.0
    quality_score: float | None = None
    quality_recommendation: str | None = None
    caie_score: float | None = None
    r14f: dict | None = None
    gate_results: dict | None = None
    pipeline_status: str | None = None
    fill: dict | None = None
    proposal_id: str | None = None

    @property
    def copied(self) -> bool:
        return self.outcome in {"COPIED", "SIMULATED"}


class _SimulationOnlyPipeline:
    """Simulated mode: no route at all, not even the paper validation pipeline."""

    def execute(self, request: Any) -> UnifiedExecutionResult:
        if str(getattr(request, "mode", "")).lower() != "paper":
            raise UnifiedExecutionPipelineError("simulation accepts paper requests only")
        return UnifiedExecutionResult(
            trade_id="", symbol=request.symbol, asset_class=request.asset_class, side=request.side,
            quantity=int(request.quantity), mode="paper", status="simulated_not_routed",
            reason="simulated_trading_mode_no_broker_path",
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CopyTradeEngine:
    def __init__(
        self,
        root: Path | str,
        *,
        key_provider: KeyProvider | None,
        preferences: PreferencesStore | None = None,
        mandates: MandateRegistry | None = None,
        ledger: AttributionLedger | None = None,
        integration_factory: Callable[[ExecutionGate, bool], CanonicalExecutionIntegration] | None = None,
        manual_provider: Callable[[], ControlledManual] = current_manual,
    ) -> None:
        self.root = Path(root)
        self.key_provider = key_provider
        self.preferences = preferences or PreferencesStore(self.root)
        self.mandates = mandates or MandateRegistry(self.root, key_provider=key_provider)
        self.ledger = ledger or AttributionLedger(self.root)
        self.consent = ConsentService(self.root, preferences=self.preferences, mandates=self.mandates,
                                      manual_provider=manual_provider)
        self.proposals_path = self.root / "assisted_proposals.json"
        self._integration_factory = integration_factory or self._default_integration
        self._quality = TradeQualityScoringEngine()
        self._caie = CAIEScoringEngine()

    @staticmethod
    def _default_integration(execution_gate: ExecutionGate, simulated: bool) -> CanonicalExecutionIntegration:
        kwargs: dict[str, Any] = {"execution_gate": execution_gate}
        if simulated:
            kwargs["unified_pipeline"] = _SimulationOnlyPipeline()
        return CanonicalExecutionIntegration(**kwargs)

    def _anti_bleed_for(self, user_id: str) -> AntiBleedGuard:
        # Per-follower state so one follower's cooldown never blocks another follower.
        return AntiBleedGuard(state_file=str(self.root / "followers" / user_id / "anti_bleed_state.json"))

    # ------------------------------------------------------------------
    def evaluate(
        self,
        signal: SourceSignal,
        follower: FollowerContext,
        system: SystemContext,
        *,
        now: datetime | None = None,
    ) -> CopyDecision:
        now = now or _now()
        decision = self._evaluate(signal, follower, system, now)
        self._record(signal, decision, now)
        return decision

    def _record(self, signal: SourceSignal, decision: CopyDecision, now: datetime) -> None:
        self.ledger.record_source_signal({
            "signal_id": signal.signal_id, "trader_id": signal.trader_id, "symbol": signal.symbol,
            "asset_class": signal.asset_class.upper(), "side": signal.side.upper(),
            "reference_price": signal.reference_price, "probability": signal.probability,
            "signal_score": signal.signal_score,
        })
        record_type = "FOLLOWER_PROPOSAL" if decision.outcome == "PROPOSED" else "FOLLOWER_DECISION"
        self.ledger.append(record_type, {**asdict(decision), "at_utc": now.isoformat()})

    def _evaluate(self, signal: SourceSignal, follower: FollowerContext, system: SystemContext, now: datetime,
                  approved_proposal: Mapping[str, Any] | None = None) -> CopyDecision:
        state: dict[str, Any] = {"operating_mode": None, "personality": None, "mandate_id": None}

        def reject(stage: str, reason: str, **extra: Any) -> CopyDecision:
            return CopyDecision(follower.user_id, signal.signal_id, "REJECTED", stage, reason,
                                state["operating_mode"], state["personality"], state["mandate_id"], **extra)

        asset = signal.asset_class.upper()
        side = signal.side.upper()
        if not _SAFE_ID.match(follower.user_id or ""):
            return reject("input", "follower_user_id_invalid")
        if side not in {"BUY", "SELL"} or asset not in {"FX", "CRYPTO", "FUTURES", "OPTIONS"}:
            return reject("input", "signal_side_or_asset_invalid")
        numeric = (signal.reference_price, signal.stop_distance_pct, follower.equity, follower.equity_peak,
                   follower.day_start_equity)
        if any(not isinstance(v, (int, float)) or not v > 0 for v in numeric):
            return reject("input", "non_positive_price_stop_or_equity")

        # 1. Safety: paper layer still requires the observed safety verdict and honours kill switches.
        flags = system.safety_flags or {}
        if flags.get("verdict") != "SAFE" or flags.get("fail_closed") is not False:
            return reject("safety", "safety_flags_not_safe")
        if flags.get("execution_allowed") is not False or flags.get("live_trading_blocked") is not True:
            return reject("safety", "safety_flags_not_safe")
        kill = evaluate_live_order_kill_switch(dict(system.mobile_controls), env=dict(system.env))
        if kill.blocked:
            return reject("safety", f"kill_switch:{kill.reason}")
        global_kill = check_kill_switch(pair=signal.symbol)
        if global_kill.killed:
            return reject("safety", f"kill_switch:{global_kill.reason}")
        engine_mode = str(system.engine_mode or "").upper()
        if engine_mode not in LEGACY_ENGINE_MODES:
            return reject("safety", "engine_mode_unknown")

        # 2. Accepted settings: consent is revalidated server-side at every decision.
        try:
            user_state = self.preferences.get(follower.user_id)
        except PreferencesError:
            return reject("profile", "preferences_unreadable")
        active = user_state.active
        if active is None:
            return reject("consent", "consent_missing")
        mode = active.operating_mode
        permissions = permissions_for(mode)
        state["operating_mode"] = mode.value
        personality = active.risk_personality or SIMULATED_DEFAULT_PERSONALITY
        state["personality"] = personality.value
        if user_state.paused:
            return reject("profile", "trading_paused_by_user")
        consent_ok, consent_reason = self.consent.verify_active(follower.user_id, user_state)
        if not consent_ok:
            return reject("consent", consent_reason)
        try:
            policy = effective_policy(policy_for(personality), active.limits)
        except LimitsError:
            return reject("consent", "active_limits_invalid")

        # 3. Authority for the signal source.
        mandate = None
        if mode is OperatingMode.COPY_CSS_TRADER:
            if signal.trader_id == AUTONOMOUS_SOURCE_ID or signal.trader_id.startswith(MANUAL_ORDER_PREFIX):
                return reject("authority", "copy_mode_requires_trader_signal")
            mandate = self.mandates.get(active.mandate_id) if active.mandate_id else None
            md = evaluate_mandate(mandate, key_provider=self.key_provider, follower_user_id=follower.user_id,
                                  trader_id=signal.trader_id, personality=personality, asset_class=asset,
                                  session_id=follower.session_id, now=now)
            state["mandate_id"] = md.mandate_id
            if not md.valid_for_new_trades:
                return reject("authority", md.reason)
        elif mode is OperatingMode.CSS_AUTONOMOUS_TRADING:
            if signal.trader_id != AUTONOMOUS_SOURCE_ID:
                return reject("authority", "autonomous_mode_accepts_css_engine_signals_only")
        elif mode is OperatingMode.CSS_ASSISTED_TRADING:
            if signal.trader_id not in {AUTONOMOUS_SOURCE_ID, MANUAL_ORDER_PREFIX + follower.user_id}:
                return reject("authority", "assisted_mode_accepts_css_proposals_or_own_manual_orders")

        # 4. Personality eligibility and portfolio-risk halts.
        if asset not in policy.allowed_asset_classes:
            return reject("personality", "asset_class_not_allowed")
        if signal.probability < policy.min_probability:
            return reject("personality", "probability_below_personality_floor")
        state_margin = str(follower.margin_state).upper()
        if state_margin != "NORMAL" and not (policy.margin_allowed and state_margin == "WARNING"):
            return reject("personality", "margin_state_not_allowed")
        drawdown_pct = (1 - follower.equity / follower.equity_peak) * 100
        if drawdown_pct >= policy.max_drawdown_halt_pct:
            return reject("personality", "drawdown_halt")
        daily_loss_pct = (1 - follower.equity / follower.day_start_equity) * 100
        if daily_loss_pct >= policy.daily_loss_halt_pct:
            return reject("personality", "daily_loss_halt")

        # 5. Sizing (only ever reduced by caps).
        stop_pct = min(signal.stop_distance_pct, policy.max_stop_distance_pct)
        equity = follower.equity
        open_positions = list(follower.open_positions)
        total_exposure = sum(p.notional for p in open_positions)
        symbol_exposure = sum(p.notional for p in open_positions if p.symbol == signal.symbol)
        caps = [
            equity * policy.risk_per_trade_pct / stop_pct,
            equity * policy.max_position_pct_of_equity / 100,
            equity * policy.max_symbol_exposure_pct_of_equity / 100 - symbol_exposure,
            equity * policy.max_total_exposure_pct_of_equity / 100 - total_exposure,
        ]
        if mandate is not None:
            mandate_exposure = sum(p.notional for p in open_positions if p.mandate_id == mandate.mandate_id)
            caps.append(mandate.max_allocation - mandate_exposure)
        if approved_proposal is not None:
            # An approval never authorizes more than the size the user approved.
            caps.append(float(approved_proposal["notional"]))
        notional = int(min(caps) * 100) / 100.0
        if notional <= 0:
            return reject("sizing", "exposure_limit_reached", stop_distance_pct=stop_pct)

        # 6. Position counts.
        if len(open_positions) >= policy.max_open_copied_positions:
            return reject("exposure", "personality_open_position_limit", notional=notional, stop_distance_pct=stop_pct)
        if len(open_positions) >= HARD_TOTAL_OPEN_POSITION_CAP:
            return reject("exposure", "global_open_position_cap", notional=notional, stop_distance_pct=stop_pct)
        sized = {"notional": notional, "stop_distance_pct": stop_pct}

        # 7. Trade quality and CAIE.
        try:
            quality = self._quality.score_candidate({
                "trade_id": signal.signal_id, "symbol": signal.symbol, "asset_class": asset,
                "market_regime": signal.market_regime, "strategy_score": signal.strategy_score,
                "replay_confidence": signal.replay_confidence,
                "concentration_risk": min(1.0, (symbol_exposure + notional) / equity),
                "allocation_weight": notional / equity, "recommended_position_size": notional,
                "exit_action": "HOLD", "exit_confidence": signal.confidence, "risk_reward": signal.risk_reward,
            })
        except TradeQualityScoringEngineError as exc:
            return reject("trade_quality", f"trade_quality_unavailable:{exc}", **sized)
        q = {"quality_score": round(float(quality.quality_score), 4), "quality_recommendation": quality.recommendation}
        if quality.recommendation not in policy.allowed_quality_recommendations:
            return reject("trade_quality", "quality_recommendation_not_accepted", **sized, **q)
        if quality.quality_score < policy.min_trade_quality_score:
            return reject("trade_quality", "quality_score_below_personality_floor", **sized, **q)
        validated = validate_opportunity_proposal({
            "proposal_id": f"{signal.signal_id}:{follower.user_id}", "symbol": signal.symbol, "asset_class": asset,
            "probability": signal.probability, "confidence": signal.confidence,
            "expected_drawdown_pct": stop_pct / 100.0, "risk_score": signal.risk_score, "requested_capital": notional,
        })
        caie = self._caie.score(validated, context={"liquidity_score": signal.liquidity_score,
                                                     "regime_alignment": signal.regime_alignment})
        if not caie.get("valid"):
            return reject("caie", f"caie_invalid:{caie.get('reason')}", **sized, **q)
        caie_score = round(float(caie["score"]), 4)
        if caie_score < policy.min_caie_score:
            return reject("caie", "caie_score_below_personality_floor", **sized, **q, caie_score=caie_score)

        # 8. R14F under the legacy engine mode in force (thresholds unchanged).
        r14f = evaluate_r14f(engine_mode=engine_mode, asset_class=asset, signal_score=signal.signal_score,
                             probability=signal.probability)
        r14f_info = {"allowed": r14f.allowed, "composite": round(r14f.composite, 4), "threshold": round(r14f.threshold, 4)}
        if not r14f.allowed:
            return reject("r14f", "r14f_profitability_below_threshold", **sized, **q, caie_score=caie_score, r14f=r14f_info)

        # 8b. CSS-Assisted: stop here and ask the user. The full canonical chain runs only on approval.
        if permissions.requires_per_order_approval and approved_proposal is None:
            return self._create_proposal(signal, follower, now, mode=mode.value, personality=personality.value,
                                         sized=sized, quality=q, caie_score=caie_score, r14f=r14f_info)

        # 9. Canonical paper chain: R7 -> ExecutionGate (AntiBleed, margin, risk) -> validation pipeline.
        counts = {k: 0 for k in MAX_POSITIONS_BY_ASSET}
        for p in open_positions:
            counts[p.asset_class.lower()] = counts.get(p.asset_class.lower(), 0) + 1
        simulated = mode is OperatingMode.SIMULATED_TRADING
        integration = self._integration_factory(ExecutionGate(anti_bleed_guard=self._anti_bleed_for(follower.user_id)), simulated)
        total_cost_bps = signal.fee_bps + signal.spread_bps + signal.slippage_bps
        try:
            result = integration.execute(
                engine_run_id=f"tp-{signal.signal_id}-{follower.user_id}",
                canonical_decision={"source": "trading_profiles", "operating_mode": mode.value,
                                    "personality": personality.value, "trader_id": signal.trader_id},
                candidate={"asset_class": asset.lower(), "symbol": signal.symbol,
                           "expected_value": signal.expected_move_bps / 10_000.0, "cost": total_cost_bps / 10_000.0,
                           "probability": signal.probability, "capital_state": "SIMULATED_CAPITAL_READY"},
                session={"created": follower.session_created_epoch, "role": follower.role},
                portfolio_state=counts,
                engine_mode=engine_mode,
                execution_request={"asset_class": asset, "symbol": signal.symbol, "side": side,
                                   # The validation pipeline takes whole units; the notional is carried in currency units.
                                   "quantity": max(1, int(notional)), "mode": "paper"},
                execution_context={
                    "instrument": signal.symbol, "side": side, "notional": notional,
                    "stop_distance_pct": stop_pct / 100.0, "equity": equity, "equity_peak": follower.equity_peak,
                    "regime_persistence": signal.regime_persistence, "policy": "core",
                    "volatility_state": signal.volatility_state, "regime_state": "NORMAL",
                    "expected_move_bps": signal.expected_move_bps, "fee_bps": signal.fee_bps,
                    "spread_bps": signal.spread_bps, "slippage_bps": signal.slippage_bps,
                    "margin_snapshot": SimpleNamespace(buying_power=follower.buying_power,
                                                       margin_state=state_margin, margin_ratio=0.0),
                    "broker_mode": "PAPER",
                },
                mode="PAPER",
            )
        except CanonicalExecutionIntegrationError as exc:
            return reject("canonical_pipeline", f"pipeline_error:{exc}", **sized, **q, caie_score=caie_score, r14f=r14f_info)
        gate_results = {k: v.get("reason") for k, v in (result.execution_decision.get("gate_results") or {}).items()}
        pipeline_status = str(result.execution_result.get("status"))
        if not result.execution_decision.get("can_execute"):
            blocked = result.execution_decision.get("blocked_by") or []
            first = blocked[0] if blocked else "canonical_pipeline"
            return reject(first, str(gate_results.get(first) or result.execution_decision.get("primary_reason")),
                          **sized, **q, caie_score=caie_score, r14f=r14f_info, gate_results=gate_results,
                          pipeline_status=pipeline_status)
        expected_status = "simulated_not_routed" if simulated else "validated_not_executed"
        if pipeline_status != expected_status:
            return reject("canonical_pipeline", f"unexpected_pipeline_status:{pipeline_status}", **sized, **q,
                          caie_score=caie_score, r14f=r14f_info, gate_results=gate_results, pipeline_status=pipeline_status)
        if not permissions.simulated_fills_only:  # pragma: no cover - invariant
            raise RuntimeError("only simulated fills are supported")

        # 10. Deterministic simulated fill (adverse slippage, entry fee).
        direction = 1 if side == "BUY" else -1
        fill_price = signal.reference_price * (1 + direction * signal.slippage_bps / 10_000.0)
        fill = {"price": round(fill_price, 8), "notional": notional,
                "fees": round(notional * signal.fee_bps / 10_000.0, 2), "source": "SIMULATED_PAPER_FILL",
                "stop_price": round(fill_price * (1 - direction * stop_pct / 100.0), 8),
                "take_profit_price": round(fill_price * (1 + direction * stop_pct / 100.0 * policy.take_profit_r_multiple), 8)}
        return CopyDecision(
            follower.user_id, signal.signal_id, "SIMULATED" if simulated else "COPIED", "filled", "all_gates_passed",
            mode.value, personality.value, state["mandate_id"], position_id="pos-" + secrets.token_hex(8),
            notional=notional, stop_distance_pct=stop_pct, quality_score=q["quality_score"],
            quality_recommendation=q["quality_recommendation"], caie_score=caie_score, r14f=r14f_info,
            gate_results=gate_results, pipeline_status=pipeline_status, fill=fill,
        )

    # ------------------------------------------------------------------ CSS-Assisted proposals
    def _read_proposals(self) -> dict[str, Any]:
        if not self.proposals_path.exists():
            return {}
        try:
            document = read_json_object(self.proposals_path)
        except PersistenceError as exc:
            raise ProposalError(f"proposals_unreadable:{exc}") from exc
        if document.get("schema") != PROPOSALS_SCHEMA or not isinstance(document.get("proposals"), dict):
            raise ProposalError("proposals_schema_mismatch")
        return document["proposals"]

    def _write_proposals(self, proposals: dict[str, Any]) -> None:
        atomic_write_json(self.proposals_path, {"schema": PROPOSALS_SCHEMA, "proposals": proposals}, expected_root=self.root)

    @staticmethod
    def _proposal_hash(proposal: Mapping[str, Any]) -> str:
        body = {k: proposal[k] for k in ("proposal_id", "user_id", "session_id", "signal", "notional",
                                         "stop_distance_pct", "created_at_utc", "expires_at_utc")}
        return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _create_proposal(self, signal: SourceSignal, follower: FollowerContext, now: datetime, *, mode: str,
                         personality: str, sized: dict, quality: dict, caie_score: float, r14f: dict) -> CopyDecision:
        proposal = {
            "proposal_id": "prp-" + secrets.token_hex(10), "user_id": follower.user_id,
            "session_id": follower.session_id, "signal": asdict(signal), "notional": sized["notional"],
            "stop_distance_pct": sized["stop_distance_pct"], "created_at_utc": now.isoformat(),
            "expires_at_utc": (now + PROPOSAL_TTL).isoformat(), "status": "PENDING_USER_APPROVAL",
        }
        proposal["proposal_hash"] = self._proposal_hash(proposal)
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.root / "assisted_proposals.lock", timeout_seconds=10.0):
            proposals = self._read_proposals()
            proposals[proposal["proposal_id"]] = proposal
            self._write_proposals(proposals)
        return CopyDecision(
            follower.user_id, signal.signal_id, "PROPOSED", "awaiting_user_approval",
            "css_assisted_requires_user_approval", mode, personality, None, notional=sized["notional"],
            stop_distance_pct=sized["stop_distance_pct"], quality_score=quality["quality_score"],
            quality_recommendation=quality["quality_recommendation"], caie_score=caie_score, r14f=r14f,
            proposal_id=proposal["proposal_id"],
        )

    def decide_proposal(self, proposal_id: str, follower: FollowerContext, system: SystemContext, *,
                        approve: bool, now: datetime | None = None) -> CopyDecision:
        """The user's individual decision on one proposal. Approval re-runs every gate now."""
        now = now or _now()
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.root / "assisted_proposals.lock", timeout_seconds=10.0):
            proposals = self._read_proposals()
            proposal = proposals.get(proposal_id)
            if proposal is None or proposal["user_id"] != follower.user_id or proposal["session_id"] != follower.session_id:
                raise ProposalError("proposal_not_found")
            if proposal.get("proposal_hash") != self._proposal_hash(proposal):
                raise ProposalError("proposal_tampered")
            if proposal["status"] != "PENDING_USER_APPROVAL":
                raise ProposalError(f"proposal_already_decided:{proposal['status']}")  # replay protection
            if now >= datetime.fromisoformat(proposal["expires_at_utc"]):
                proposal["status"] = "EXPIRED"
                self._write_proposals(proposals)
                raise ProposalError("proposal_expired")
            proposal["status"] = "DECIDING"
            self._write_proposals(proposals)
        signal = SourceSignal(**proposal["signal"])
        if approve:
            decision = self._evaluate(signal, follower, system, now, approved_proposal=proposal)
        else:
            decision = CopyDecision(follower.user_id, signal.signal_id, "REJECTED", "user_decision",
                                    "rejected_by_user", None, None, None, proposal_id=proposal_id)
        decision = replace(decision, proposal_id=proposal_id)
        with exclusive_file_lock(self.root / "assisted_proposals.lock", timeout_seconds=10.0):
            proposals = self._read_proposals()
            proposals[proposal_id]["status"] = (
                "APPROVED_EXECUTED" if decision.copied else ("REJECTED_BY_USER" if not approve else "APPROVED_BLOCKED"))
            proposals[proposal_id]["decided_at_utc"] = now.isoformat()
            self._write_proposals(proposals)
        self._record(signal, decision, now)
        return decision

    # ------------------------------------------------------------------
    def position_from_decision(self, decision: CopyDecision, signal: SourceSignal, *, opened_at: datetime) -> CopiedPosition:
        if not decision.copied or not decision.fill or not decision.position_id:
            raise ValueError("decision did not open a position")
        return CopiedPosition(
            position_id=decision.position_id, follower_user_id=decision.follower_user_id, symbol=signal.symbol,
            asset_class=signal.asset_class.upper(), side=signal.side.upper(), notional=decision.notional,
            entry_price=decision.fill["price"], stop_distance_pct=decision.stop_distance_pct, opened_at=opened_at,
            best_price=decision.fill["price"], signal_id=signal.signal_id, mandate_id=decision.mandate_id,
            trader_id=signal.trader_id,
        )

    def record_exit(self, position: CopiedPosition, *, exit_price: float, reason: str, pnl: float, now: datetime) -> None:
        self.ledger.append("FOLLOWER_EXIT", {
            "position_id": position.position_id, "follower_user_id": position.follower_user_id,
            "signal_id": position.signal_id, "exit_price": exit_price, "reason": reason, "pnl": pnl,
            "at_utc": now.isoformat(),
        })
