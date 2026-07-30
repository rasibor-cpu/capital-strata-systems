from __future__ import annotations

import json
import os
import time

from decimal import Decimal
from typing import Any, Dict, List
from uuid import uuid4

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.market_regime_detector import MarketRegimeDetector
from backend.intelligence.opportunity_momentum_window_engine import OpportunityMomentumWindowEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.probability_prediction_engine import ProbabilityPredictionEngine
from backend.intelligence.profitability_guard import ProfitabilityGuard
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.intelligence.adaptive_exit_engine import AdaptiveExitEngine

from backend.app.persistence.repositories.session_repository import SessionRepository
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.services.session_runtime_service import SessionRuntimeService
from backend.app.persistence.services.trade_runtime_service import TradeRuntimeService
from backend.app.persistence.services.pnl_runtime_service import PnlRuntimeService
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate


class TradeDecisionOrchestrator:

    def __init__(
        self,
        total_capital: float = 10000.0,
        mode: str = "paper",
        broker_name: str = "internal",
        broker_mode: str = "paper",
    ) -> None:

        total_capital_raw = os.getenv(
            "CSS_TOTAL_CAPITAL",
            os.getenv("ACCOUNT_EQUITY", str(total_capital)),
        )

        try:
            resolved_total_capital = float(total_capital_raw)
        except Exception:
            resolved_total_capital = total_capital

        if resolved_total_capital <= 0:
            resolved_total_capital = total_capital

        self.total_capital = resolved_total_capital

        self.regime_detector = MarketRegimeDetector()
        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()

        self.capital_allocator = CapitalAllocator(
            total_capital=self.total_capital
        )

        self.exit_engine = AdaptiveExitEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()
        self.probability_engine = ProbabilityPredictionEngine()
        self.profitability_guard = ProfitabilityGuard()

        self.trade_gate = CSSUnifiedTradeGate()

        self.session_repository = SessionRepository()
        self.persistence_service = PersistenceService()
        self.session_runtime_service = SessionRuntimeService()
        self.trade_runtime_service = TradeRuntimeService()
        self.pnl_runtime_service = PnlRuntimeService()

        self.session_id = self._initialize_runtime_session(
            mode=mode,
            broker_name=broker_name,
            broker_mode=broker_mode,
        )

    def _initialize_runtime_session(
        self,
        mode: str,
        broker_name: str,
        broker_mode: str,
    ) -> str:

        active_sessions = (
            self.session_repository
            .get_active_sessions()
        )

        if active_sessions:
            active_session = active_sessions[0]

            return str(
                active_session["session_id"]
            )

        return (
            self.session_runtime_service
            .create_runtime_session(
                mode=mode,
                broker_name=broker_name,
                broker_mode=broker_mode,
            )
        )

    def _safe_float(
        self,
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:
            if value is None:
                return default

            return float(value)

        except Exception:
            return default

    def _trade_already_exists(
        self,
        symbol: str,
        direction: str = "long",
    ) -> bool:

        return (
            self.trade_runtime_service
            .trade_exists(
                session_id=self.session_id,
                symbol=symbol,
                direction=direction,
            )
        )

    def _persist_trade_open(
        self,
        symbol: str,
        market_data: Dict[str, Any] | None = None,
    ) -> str | None:

        if self._trade_already_exists(
            symbol=symbol,
            direction="long",
        ):
            return None

        from engine.risk.canonical_volatility_price import coerce_finite_positive_price

        source = market_data if isinstance(market_data, dict) else {}
        price = coerce_finite_positive_price(
            source.get("price", source.get("last_price", source.get("current_price", source.get("market_price"))))
        )
        # MW-004: never fabricate entry_price=0. Skip ledger write when no price.
        if price is None:
            return None

        trade_id = str(uuid4())

        self.trade_runtime_service.open_trade(
            trade_id=trade_id,
            session_id=self.session_id,
            broker_name="internal",
            broker_mode="paper",
            symbol=symbol,
            direction="long",
            order_type="market",
            quantity=Decimal("1"),
            filled_quantity=Decimal("1"),
            entry_price=Decimal(str(price)),
            raw_payload_json=json.dumps(
                {
                    "source": "trade_decision_orchestrator_stub",
                    "execution_economics": {
                        "schema_version": "css.paper.execution_economics.v1",
                        "status": "open",
                        "requested_quantity": "1",
                        "filled_quantity": "1",
                        "entry_price": str(price),
                        "quantity_contract": "requested_quantity_authoritative",
                        "note": "orchestrator_tracking_stub",
                    },
                },
                sort_keys=True,
            ),
            status="open",
        )

        return trade_id

    def _persist_trade_close(
        self,
        trade_id: str | None,
        *,
        exit_price: Decimal | None = None,
    ) -> None:

        if trade_id is None:
            return

        self.trade_runtime_service.close_trade(
            trade_id=trade_id,
            exit_price=exit_price if exit_price is not None else Decimal("0"),
            realized_pnl=Decimal("0"),
        )

    def _persist_runtime_snapshot(self) -> None:

        self.pnl_runtime_service.create_snapshot(
            session_id=self.session_id,
            broker_name="internal",
            broker_mode="paper",
            equity=Decimal(str(self.total_capital)),
            cash_balance=Decimal(str(self.total_capital)),
            buying_power=Decimal(str(self.total_capital)),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            open_positions=0,
            payload_json=None,
        )

    def _evaluate_governance_gate(
        self,
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        engine_mode = str(
            market_data.get("engine_mode", "SAFE")
        ).strip().upper()

        candidate = {
            "symbol": str(market_data.get("symbol", "UNKNOWN")),
            "asset_class": str(market_data.get("asset_class", "")).strip().lower(),
            "expected_value": self._safe_float(
                market_data.get("expected_value"),
            ),
            "cost": self._safe_float(
                market_data.get("cost"),
            ),
            "probability": self._safe_float(
                market_data.get("probability"),
            ),
        }

        try:
            decision = self.trade_gate.approve_trade(
                candidate=candidate,
                session={
                    "role": "TRADER",
                    "created": time.time(),
                },
                portfolio_state={
                    "crypto": 0,
                    "fx": 0,
                    "futures": 0,
                    "options": 0,
                },
                engine_mode=engine_mode,
            )
        except Exception as exc:
            return {
                "approved": False,
                "reason": f"canonical_gate_error:{type(exc).__name__}",
                "details": {},
            }

        details = getattr(decision, "details", {})
        if not isinstance(details, dict):
            details = {}

        return {
            "approved": bool(getattr(decision, "approved", False)),
            "reason": str(getattr(decision, "reason", "UNKNOWN")),
            "details": details,
        }

    def _build_decision_payload(
        self,
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        symbol = str(
            market_data.get("symbol", "UNKNOWN")
        )

        already_open = self._trade_already_exists(
            symbol=symbol,
            direction="long",
        )
        trade_id = None if already_open else self._persist_trade_open(
            symbol=symbol,
            market_data=market_data,
        )

        self._persist_trade_close(
            trade_id=trade_id,
            exit_price=None,
        )

        self._persist_runtime_snapshot()

        duplicate_trade_blocked = already_open

        governance_decision = self._evaluate_governance_gate(
            market_data
        )

        return {
            "symbol": symbol,
            "trade_id": trade_id,
            "execute_trade": False,
            "decision_score": 0.0,
            "raw_score": 0.0,
            "regime": "SAFE",
            "components": {},
            "filters": {
                "governance_approved": governance_decision["approved"],
                "governance_reason": governance_decision["reason"],
                "governance_details": governance_decision["details"],
                "governance_source": "CSSUnifiedTradeGate",
                "persistence_enabled": True,
                "duplicate_trade_blocked": duplicate_trade_blocked,
            },
            "runtime": {
                "session_id": self.session_id,
                "persistence_ready": True,
                "session_tracking": True,
                "trade_tracking": True,
                "pnl_tracking": True,
                "startup_recovery_enabled": True,
            },
        }

    def evaluate_trade(
        self,
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        return self._build_decision_payload(
            market_data
        )

    def evaluate_market_batch(
        self,
        market_dataset: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        results = []

        for data in market_dataset:
            decision = self.evaluate_trade(
                data
            )

            results.append(decision)

        return {
            "session_id": self.session_id,
            "total_scanned": len(results),
            "executed_trades": [],
            "all_decisions": results,
        }
