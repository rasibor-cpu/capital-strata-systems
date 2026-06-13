from __future__ import annotations

from backend.intelligence.regime_intelligence_engine import (
    RegimeDecision,
    RegimeIntelligenceEngine,
)


def _sample_candles(count: int = 25) -> list[dict[str, float]]:
    return [
        {
            "close": 100.0 + (i * 0.01),
            "high": 100.5 + (i * 0.01),
            "low": 99.5 + (i * 0.01),
            "volume": 1.0,
        }
        for i in range(count)
    ]


def main() -> None:
    engine = RegimeIntelligenceEngine()

    insufficient = engine.evaluate(_sample_candles(5))
    assert isinstance(insufficient, RegimeDecision)
    assert insufficient.allow_trade is False
    assert insufficient.regime == "UNKNOWN"

    result_one = engine.evaluate(_sample_candles())
    result_two = engine.evaluate(_sample_candles())

    assert isinstance(result_one, RegimeDecision)
    assert result_one.regime == result_two.regime
    assert result_one.allow_trade == result_two.allow_trade
    assert isinstance(result_one.reason, str)

    print("Regime governance test PASSED")


if __name__ == "__main__":
    main()
