from __future__ import annotations

import pytest

from backend.trading.opportunity_ranking_engine import (
    OpportunityRankingEngine,
    OpportunityRankingEngineError,
)


class _StubUniverse:
    def __init__(self, rows):
        self.rows = rows

    def all_instruments(self):
        return list(self.rows)

    def instruments_by_asset_class(self, asset_class: str):
        if asset_class not in {"CRYPTO", "FX", "OPTIONS", "FUTURES", "EQUITIES"}:
            raise OpportunityRankingEngineError("unsupported asset class")
        return [row for row in self.rows if row.get("asset_class") == asset_class]

    def instruments_by_broker(self, broker: str):
        return [row for row in self.rows if str(row.get("broker", "")).lower() == str(broker).lower()]


class _StubDecision:
    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        return dict(self.payload)


class _StubOrchestrator:
    def __init__(self, by_symbol):
        self.by_symbol = by_symbol

    def decide(self, candidate):
        return _StubDecision(self.by_symbol[candidate["symbol"]])


class _StubGate:
    def __init__(self, approved_symbols=None):
        self.approved_symbols = set(approved_symbols or [])

    def approve_trade(self, candidate, session, portfolio_state, engine_mode):
        symbol = str(candidate.get("symbol", "")).upper()
        approved = symbol in self.approved_symbols

        class _Decision:
            def __init__(self, approved):
                self.approved = approved
                self.reason = "approved" if approved else "blocked"
                self.engine_mode = engine_mode
                self.timestamp = 0.0
                self.details = {}

        return _Decision(approved)


@pytest.fixture
def ranked_engine() -> OpportunityRankingEngine:
    rows = [
        {
            "symbol": "BTC-USD",
            "display_name": "Bitcoin",
            "asset_class": "CRYPTO",
            "broker": "coinbase",
            "tradable": True,
            "paper_supported": True,
            "live_supported": True,
            "status": "ACTIVE",
        },
        {
            "symbol": "EUR_USD",
            "display_name": "EURUSD",
            "asset_class": "FX",
            "broker": "oanda",
            "tradable": True,
            "paper_supported": True,
            "live_supported": True,
            "status": "ACTIVE",
        },
        {
            "symbol": "AAPL",
            "display_name": "Apple",
            "asset_class": "EQUITIES",
            "broker": "alpaca",
            "tradable": False,
            "paper_supported": True,
            "live_supported": False,
            "status": "PLACEHOLDER_UNVERIFIED",
        },
    ]

    decisions = {
        "BTC-USD": {
            "entry_decision": "ALLOW",
            "decision": "ALLOW",
            "confidence": 0.82,
            "signal_strength": 0.78,
            "strategy_score": 0.79,
            "expected_reward": 120.0,
            "expected_risk": 45.0,
            "portfolio_risk": 0.22,
            "concentration_score": 0.15,
            "market_regime": "TRENDING",
            "selected_strategy": "momentum_breakout",
            "allocation": {"allocation_amount": 2000.0},
            "position_size": {"recommended_position_size": 0.25},
        },
        "EUR_USD": {
            "entry_decision": "BLOCK",
            "decision": "BLOCK",
            "confidence": 0.61,
            "signal_strength": 0.44,
            "strategy_score": 0.48,
            "expected_reward": 40.0,
            "expected_risk": 55.0,
            "portfolio_risk": 0.65,
            "concentration_score": 0.70,
            "market_regime": "UNKNOWN",
            "selected_strategy": "macro_trend",
            "allocation": {"allocation_amount": 800.0},
            "position_size": {"recommended_position_size": 1000.0},
        },
        "AAPL": {
            "entry_decision": "DEFER",
            "decision": "DEFER",
            "confidence": 0.30,
            "signal_strength": 0.25,
            "strategy_score": 0.25,
            "expected_reward": 20.0,
            "expected_risk": 40.0,
            "portfolio_risk": 0.45,
            "concentration_score": 0.35,
            "market_regime": "RANGING",
            "selected_strategy": "alpha",
            "allocation": {"allocation_amount": 300.0},
            "position_size": {"recommended_position_size": 5.0},
        },
    }

    return OpportunityRankingEngine(
        instrument_universe=_StubUniverse(rows),
        intelligence_orchestrator=_StubOrchestrator(decisions),
        unified_trade_gate=_StubGate(approved_symbols={"BTC-USD"}),
    )


def test_ranks_opportunities_deterministically(ranked_engine: OpportunityRankingEngine) -> None:
    first = ranked_engine.rank_all()
    second = ranked_engine.rank_all()

    assert [row["symbol"] for row in first] == [row["symbol"] for row in second]
    assert [row["opportunity_score"] for row in first] == [row["opportunity_score"] for row in second]


def test_top_opportunities_sorted_descending(ranked_engine: OpportunityRankingEngine) -> None:
    rows = ranked_engine.rank_all()
    assert rows[0]["opportunity_score"] >= rows[1]["opportunity_score"]


def test_blocked_opportunities_excluded_from_top_list(ranked_engine: OpportunityRankingEngine) -> None:
    top = ranked_engine.top_opportunities(limit=10)
    assert all(row["action"] != "BLOCK" for row in top)


def test_paper_opportunities_prefer_paper_supported(ranked_engine: OpportunityRankingEngine) -> None:
    rows = ranked_engine.paper_opportunities(limit=5)
    assert rows
    assert rows[0]["paper_supported"] is True


def test_unknown_regime_reduces_score(ranked_engine: OpportunityRankingEngine) -> None:
    rows = ranked_engine.rank_all()
    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["EUR_USD"]["market_regime"] == "UNKNOWN"
    assert by_symbol["EUR_USD"]["opportunity_score"] < by_symbol["BTC-USD"]["opportunity_score"]


def test_high_risk_reduces_score(ranked_engine: OpportunityRankingEngine) -> None:
    rows = ranked_engine.rank_all()
    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["EUR_USD"]["risk_score"] > by_symbol["BTC-USD"]["risk_score"]


def test_empty_universe_returns_empty_list() -> None:
    engine = OpportunityRankingEngine(
        instrument_universe=_StubUniverse([]),
        intelligence_orchestrator=_StubOrchestrator({}),
        unified_trade_gate=_StubGate(set()),
    )
    assert engine.rank_all() == []


def test_invalid_asset_class_fails_closed(ranked_engine: OpportunityRankingEngine) -> None:
    with pytest.raises(OpportunityRankingEngineError):
        ranked_engine.rank_by_asset_class("BONDS")


def test_explain_opportunity_returns_diagnostics(ranked_engine: OpportunityRankingEngine) -> None:
    payload = ranked_engine.explain_opportunity("BTC-USD")
    assert payload["symbol"] == "BTC-USD"
    assert "diagnostics" in payload


def test_ranking_v2_fields_and_explainability_present(ranked_engine: OpportunityRankingEngine) -> None:
    rows = ranked_engine.rank_all()
    first = rows[0]

    assert "weighted_intelligence_score" in first
    assert "regime_confidence" in first
    assert "regime_stability" in first
    assert "liquidity_rating" in first
    assert "liquidity_score" in first
    assert "cross_asset_confidence" in first
    assert "correlation_score" in first
    assert "confirmation_score" in first
    assert "session_name" in first
    assert "session_confidence_adjustment" in first
    assert "calibrated_confidence_percent" in first
    assert "expected_holding_time" in first
    assert "expected_reward_risk" in first
    assert "risk_level" in first
    assert "explainability" in first
    assert "why_selected" in first["explainability"]
