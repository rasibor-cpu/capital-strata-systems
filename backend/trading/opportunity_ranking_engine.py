from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate
from backend.intelligence.intelligence_orchestrator import (
    IntelligenceDecisionError,
    IntelligenceOrchestrator,
)
from backend.trading.instrument_universe import InstrumentUniverse, InstrumentUniverseError


class OpportunityRankingEngineError(RuntimeError):
    """Fail-closed exception for opportunity ranking."""


@dataclass(frozen=True)
class RankedOpportunity:
    rank: int
    symbol: str
    display_name: str
    asset_class: str
    broker: str
    action: str
    confidence: float
    opportunity_score: float
    market_regime: str
    selected_strategy: str
    signal_strength: float
    expected_reward: float
    expected_risk: float
    risk_score: float
    allocation: dict[str, Any]
    position_size: dict[str, Any]
    portfolio_risk: float
    tradable: bool
    paper_supported: bool
    live_supported: bool
    status: str
    reason: str
    diagnostics: dict[str, Any]
    last_updated: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OpportunityRankingEngine:
    """Deterministic ranking engine for trade-tab opportunity recommendations."""

    _ALLOWED_ASSET_CLASSES = {"CRYPTO", "FX", "OPTIONS", "FUTURES", "EQUITIES"}

    def __init__(
        self,
        *,
        instrument_universe: InstrumentUniverse | None = None,
        intelligence_orchestrator: IntelligenceOrchestrator | None = None,
        unified_trade_gate: CSSUnifiedTradeGate | None = None,
    ) -> None:
        self.instrument_universe = instrument_universe or InstrumentUniverse()
        self.intelligence_orchestrator = intelligence_orchestrator or IntelligenceOrchestrator()
        self.unified_trade_gate = unified_trade_gate or CSSUnifiedTradeGate()

    def rank_all(self, *, include_blocked: bool = True) -> list[dict[str, Any]]:
        instruments = self.instrument_universe.all_instruments()
        if not instruments:
            return []

        ranked: list[RankedOpportunity] = []
        for instrument in instruments:
            opportunity = self._rank_instrument(instrument)
            if not include_blocked and opportunity.action == "BLOCK":
                continue
            ranked.append(opportunity)

        ranked_sorted = self._sort_ranked(ranked)
        return [item.to_dict() for item in ranked_sorted]

    def rank_by_asset_class(self, asset_class: str) -> list[dict[str, Any]]:
        normalized = str(asset_class or "").strip().upper()
        if normalized not in self._ALLOWED_ASSET_CLASSES:
            raise OpportunityRankingEngineError(f"unsupported asset class: {asset_class}")

        try:
            instruments = self.instrument_universe.instruments_by_asset_class(normalized)
        except InstrumentUniverseError as exc:
            raise OpportunityRankingEngineError(str(exc)) from exc

        ranked = [self._rank_instrument(instrument) for instrument in instruments]
        return [item.to_dict() for item in self._sort_ranked(ranked)]

    def rank_by_broker(self, broker: str) -> list[dict[str, Any]]:
        normalized = str(broker or "").strip().lower()
        if not normalized:
            raise OpportunityRankingEngineError("broker must be non-empty")

        try:
            instruments = self.instrument_universe.instruments_by_broker(normalized)
        except InstrumentUniverseError as exc:
            raise OpportunityRankingEngineError(str(exc)) from exc

        ranked = [self._rank_instrument(instrument) for instrument in instruments]
        return [item.to_dict() for item in self._sort_ranked(ranked)]

    def top_opportunities(self, limit: int = 10) -> list[dict[str, Any]]:
        if int(limit) <= 0:
            raise OpportunityRankingEngineError("limit must be positive")

        ranked = [
            item
            for item in self.rank_all(include_blocked=False)
            if str(item.get("action") or "").upper() != "BLOCK"
        ]
        return ranked[: int(limit)]

    def paper_opportunities(self, limit: int = 10) -> list[dict[str, Any]]:
        if int(limit) <= 0:
            raise OpportunityRankingEngineError("limit must be positive")

        ranked = self.rank_all(include_blocked=False)

        def _paper_key(row: Mapping[str, Any]) -> tuple[int, float, str]:
            paper_bonus = 1 if bool(row.get("paper_supported", False)) else 0
            return (paper_bonus, float(row.get("opportunity_score", 0.0)), str(row.get("symbol", "")))

        paper_sorted = sorted(ranked, key=_paper_key, reverse=True)
        return paper_sorted[: int(limit)]

    def explain_opportunity(self, symbol: str) -> dict[str, Any]:
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            raise OpportunityRankingEngineError("symbol must be non-empty")

        ranked = self.rank_all(include_blocked=True)
        matches = [row for row in ranked if str(row.get("symbol") or "").upper() == normalized]
        if not matches:
            raise OpportunityRankingEngineError(f"opportunity not found for symbol: {symbol}")

        best = matches[0]
        return {
            "symbol": best["symbol"],
            "opportunity": best,
            "diagnostics": dict(best.get("diagnostics", {})),
        }

    def _rank_instrument(self, instrument: Mapping[str, Any]) -> RankedOpportunity:
        symbol = str(instrument.get("symbol") or "").strip().upper()
        asset_class = str(instrument.get("asset_class") or "UNKNOWN").strip().upper()
        broker = str(instrument.get("broker") or "unknown").strip().lower()
        display_name = str(instrument.get("display_name") or symbol).strip() or symbol
        tradable = bool(instrument.get("tradable", False))
        paper_supported = bool(instrument.get("paper_supported", False))
        live_supported = bool(instrument.get("live_supported", False))

        if not symbol:
            raise OpportunityRankingEngineError("instrument symbol must be non-empty")

        candidate = self._candidate_for_instrument(instrument)
        decision = self._safe_decide(candidate)

        confidence = float(decision.get("confidence", 0.0) or 0.0)
        signal_strength = float(decision.get("signal_strength", 0.0) or 0.0)
        expected_reward = float(decision.get("expected_reward", 0.0) or 0.0)
        expected_risk = float(decision.get("expected_risk", 0.0) or 0.0)
        portfolio_risk = float(decision.get("portfolio_risk", 0.0) or 0.0)
        concentration_score = float(decision.get("concentration_score", 0.0) or 0.0)
        strategy_score = float(decision.get("strategy_score", signal_strength) or 0.0)
        market_regime = str(decision.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN"
        selected_strategy = str(decision.get("selected_strategy") or "default").strip() or "default"
        entry_decision = str(decision.get("entry_decision") or decision.get("decision") or "BLOCK").strip().upper()

        gate_result = self._safe_gate_approve(
            instrument=instrument,
            confidence=confidence,
            expected_reward=expected_reward,
            expected_risk=expected_risk,
        )
        gate_approved = bool(gate_result.get("approved", False))

        action = self._resolve_action(
            entry_decision=entry_decision,
            tradable=tradable,
            gate_approved=gate_approved,
        )

        score = self._score(
            confidence=confidence,
            signal_strength=signal_strength,
            expected_reward=expected_reward,
            expected_risk=expected_risk,
            portfolio_risk=portfolio_risk,
            concentration_score=concentration_score,
            strategy_score=strategy_score,
            market_regime=market_regime,
            tradable=tradable,
            paper_supported=paper_supported,
            action=action,
        )

        risk_score = self._risk_score(
            expected_reward=expected_reward,
            expected_risk=expected_risk,
            portfolio_risk=portfolio_risk,
            concentration_score=concentration_score,
        )

        status = str(instrument.get("status") or "UNKNOWN").strip().upper() or "UNKNOWN"
        reason = self._resolve_reason(action=action, gate_result=gate_result, entry_decision=entry_decision)

        return RankedOpportunity(
            rank=0,
            symbol=symbol,
            display_name=display_name,
            asset_class=asset_class,
            broker=broker,
            action=action,
            confidence=round(confidence, 8),
            opportunity_score=round(score, 8),
            market_regime=market_regime,
            selected_strategy=selected_strategy,
            signal_strength=round(signal_strength, 8),
            expected_reward=round(expected_reward, 8),
            expected_risk=round(expected_risk, 8),
            risk_score=round(risk_score, 8),
            allocation=dict(decision.get("allocation") or {}),
            position_size=dict(decision.get("position_size") or {}),
            portfolio_risk=round(portfolio_risk, 8),
            tradable=tradable,
            paper_supported=paper_supported,
            live_supported=live_supported,
            status=status,
            reason=reason,
            diagnostics={
                "decision": decision,
                "gate": gate_result,
                "concentration_score": round(concentration_score, 8),
                "strategy_score": round(strategy_score, 8),
            },
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    def _safe_decide(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return self.intelligence_orchestrator.decide(candidate).to_dict()
        except IntelligenceDecisionError:
            return {
                "entry_decision": "BLOCK",
                "decision": "BLOCK",
                "confidence": 0.0,
                "signal_strength": 0.0,
                "strategy_score": 0.0,
                "expected_reward": 0.0,
                "expected_risk": 0.0,
                "portfolio_risk": 1.0,
                "concentration_score": 1.0,
                "market_regime": "UNKNOWN",
                "selected_strategy": "default",
                "allocation": {},
                "position_size": {},
                "diagnostics": {"error": "intelligence_decision_error"},
            }
        except Exception:
            return {
                "entry_decision": "BLOCK",
                "decision": "BLOCK",
                "confidence": 0.0,
                "signal_strength": 0.0,
                "strategy_score": 0.0,
                "expected_reward": 0.0,
                "expected_risk": 0.0,
                "portfolio_risk": 1.0,
                "concentration_score": 1.0,
                "market_regime": "UNKNOWN",
                "selected_strategy": "default",
                "allocation": {},
                "position_size": {},
                "diagnostics": {"error": "intelligence_exception"},
            }

    def _safe_gate_approve(
        self,
        *,
        instrument: Mapping[str, Any],
        confidence: float,
        expected_reward: float,
        expected_risk: float,
    ) -> dict[str, Any]:
        try:
            gate = self.unified_trade_gate.approve_trade(
                {
                    "asset_class": str(instrument.get("asset_class") or "").strip().lower(),
                    "expected_value": max(0.0001, float(expected_reward)),
                    "cost": max(0.0, float(expected_risk)),
                    "probability": max(0.0, min(1.0, float(confidence))),
                    "symbol": str(instrument.get("symbol") or "").strip().upper(),
                },
                {
                    "created": datetime.now(timezone.utc).timestamp(),
                    "role": "TRADER",
                },
                {
                    str(instrument.get("asset_class") or "").strip().lower(): 0,
                },
                "BALANCED",
            )
            return gate.__dict__
        except Exception as exc:
            return {
                "approved": False,
                "reason": f"gate_error:{type(exc).__name__}",
                "engine_mode": "BALANCED",
                "details": {},
            }

    def _candidate_for_instrument(self, instrument: Mapping[str, Any]) -> dict[str, Any]:
        symbol = str(instrument.get("symbol") or "").strip().upper()
        asset_class = str(instrument.get("asset_class") or "UNKNOWN").strip().upper()
        display_name = str(instrument.get("display_name") or symbol).strip() or symbol
        base_price = self._base_price(symbol)

        candles = [
            {
                "open": round(base_price * 0.995, 8),
                "high": round(base_price * 1.005, 8),
                "low": round(base_price * 0.99, 8),
                "close": round(base_price * 0.998, 8),
                "volume": 1000.0,
            },
            {
                "open": round(base_price * 0.998, 8),
                "high": round(base_price * 1.01, 8),
                "low": round(base_price * 0.995, 8),
                "close": round(base_price * 1.002, 8),
                "volume": 1030.0,
            },
            {
                "open": round(base_price * 1.002, 8),
                "high": round(base_price * 1.012, 8),
                "low": round(base_price * 0.998, 8),
                "close": round(base_price * 1.006, 8),
                "volume": 1050.0,
            },
        ]

        strategy = "alpha"
        if asset_class in {"FX", "FUTURES"}:
            strategy = "macro_trend"
        elif asset_class == "OPTIONS":
            strategy = "volatility_structure"
        elif asset_class == "CRYPTO":
            strategy = "momentum_breakout"

        return {
            "trade_id": f"opp-{symbol}",
            "symbol": symbol,
            "asset_class": asset_class,
            "direction": "BUY",
            "strategy": strategy,
            "current_price": base_price,
            "market_snapshot": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "candles": candles,
                "display_name": display_name,
            },
            "portfolio_snapshot": {
                "available_capital": 100000.0,
                "positions": [],
            },
        }

    @staticmethod
    def _base_price(symbol: str) -> float:
        digest = sum(ord(ch) for ch in symbol)
        return round(50.0 + (digest % 200), 8)

    @staticmethod
    def _resolve_action(*, entry_decision: str, tradable: bool, gate_approved: bool) -> str:
        if not tradable:
            return "WATCH"
        if entry_decision == "ALLOW" and gate_approved:
            return "BUY"
        if entry_decision in {"DEFER", "REDUCE_SIZE"}:
            return "WATCH"
        return "BLOCK"

    @staticmethod
    def _resolve_reason(*, action: str, gate_result: Mapping[str, Any], entry_decision: str) -> str:
        if action == "BUY":
            return "intelligence_and_gate_approved"
        if action == "WATCH" and entry_decision in {"DEFER", "REDUCE_SIZE"}:
            return "intelligence_recommends_wait"
        if action == "WATCH":
            return "instrument_not_tradable"
        return str(gate_result.get("reason") or "blocked_by_risk_or_governance")

    @staticmethod
    def _risk_score(
        *,
        expected_reward: float,
        expected_risk: float,
        portfolio_risk: float,
        concentration_score: float,
    ) -> float:
        ratio = expected_risk / max(1.0, expected_reward + expected_risk)
        weighted = (ratio * 0.5) + (max(0.0, min(1.0, portfolio_risk)) * 0.3) + (max(0.0, min(1.0, concentration_score)) * 0.2)
        return max(0.0, min(1.0, weighted))

    @staticmethod
    def _score(
        *,
        confidence: float,
        signal_strength: float,
        expected_reward: float,
        expected_risk: float,
        portfolio_risk: float,
        concentration_score: float,
        strategy_score: float,
        market_regime: str,
        tradable: bool,
        paper_supported: bool,
        action: str,
    ) -> float:
        conf = max(0.0, min(1.0, confidence))
        signal = max(0.0, min(1.0, signal_strength))
        strategy = max(0.0, min(1.0, strategy_score))
        reward_ratio = expected_reward / max(1.0, expected_reward + expected_risk)
        risk_ratio = expected_risk / max(1.0, expected_reward + expected_risk)
        p_risk = max(0.0, min(1.0, portfolio_risk))
        concentration = max(0.0, min(1.0, concentration_score))

        regime_multiplier = 1.0
        if market_regime == "UNKNOWN":
            regime_multiplier = 0.70
        elif market_regime in {"LOW_VOLATILITY", "RANGING"}:
            regime_multiplier = 0.90

        base = (
            (conf * 25.0)
            + (signal * 20.0)
            + (reward_ratio * 15.0)
            - (risk_ratio * 10.0)
            - (p_risk * 10.0)
            - (concentration * 8.0)
            + (strategy * 8.0)
            + (8.0 if tradable else -12.0)
            + (5.0 if paper_supported else 0.0)
        )

        if action == "BLOCK":
            base -= 25.0

        score = base * regime_multiplier
        return max(0.0, min(100.0, score))

    @staticmethod
    def _sort_ranked(rows: list[RankedOpportunity]) -> list[RankedOpportunity]:
        ordered = sorted(
            rows,
            key=lambda item: (
                item.opportunity_score,
                item.confidence,
                item.signal_strength,
                item.symbol,
            ),
            reverse=True,
        )

        ranked_rows: list[RankedOpportunity] = []
        for index, item in enumerate(ordered, start=1):
            ranked_rows.append(
                RankedOpportunity(
                    rank=index,
                    symbol=item.symbol,
                    display_name=item.display_name,
                    asset_class=item.asset_class,
                    broker=item.broker,
                    action=item.action,
                    confidence=item.confidence,
                    opportunity_score=item.opportunity_score,
                    market_regime=item.market_regime,
                    selected_strategy=item.selected_strategy,
                    signal_strength=item.signal_strength,
                    expected_reward=item.expected_reward,
                    expected_risk=item.expected_risk,
                    risk_score=item.risk_score,
                    allocation=item.allocation,
                    position_size=item.position_size,
                    portfolio_risk=item.portfolio_risk,
                    tradable=item.tradable,
                    paper_supported=item.paper_supported,
                    live_supported=item.live_supported,
                    status=item.status,
                    reason=item.reason,
                    diagnostics=item.diagnostics,
                    last_updated=item.last_updated,
                )
            )
        return ranked_rows
