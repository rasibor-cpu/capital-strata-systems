from __future__ import annotations

from typing import Dict, Any

from backend.intelligence.regime_intelligence_engine import RegimeIntelligenceEngine
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine


class TradeDecisionEngine:
    """
    CSS Trade Decision Engine

    Combines regime intelligence and signal confluence
    to determine whether a trade should be executed.
    """

    def __init__(self) -> None:
        self.regime_engine = RegimeIntelligenceEngine()
        self.confluence_engine = SignalConfluenceEngine()

    def evaluate_trade(self, symbol: str, candles: list[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate a potential trade opportunity.
        """

        regime_result = self.regime_engine.evaluate(candles)
        confluence_result = self.confluence_engine.evaluate(candles)

        decision = {
            "symbol": symbol,
            "regime_allowed": regime_result.allow_trade,
            "regime_reason": regime_result.reason,
            "confluence_allowed": confluence_result.allow_trade,
            "confluence_score": confluence_result.confluence_score,
            "passed_checks": confluence_result.passed_checks,
            "total_checks": confluence_result.total_checks,
        }

        decision["execute_trade"] = (
            regime_result.allow_trade and confluence_result.allow_trade
        )

        return decision


if __name__ == "__main__":

    sample_candles = [
        {"open": 1.08, "high": 1.081, "low": 1.079, "close": 1.0805, "volume": 900}
    ] * 20

    engine = TradeDecisionEngine()

    result = engine.evaluate_trade("EUR_USD", sample_candles)

    print(result)