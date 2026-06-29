from __future__ import annotations

from backend.portfolio.market_regime_intelligence import MarketRegimeIntelligence


def test_market_regime_detects_trending_up() -> None:
    result = MarketRegimeIntelligence().detect(returns=[0.012, 0.014, -0.002, 0.011, 0.01])

    assert result["status"] == "OK"
    assert result["detected_regime"] == "TRENDING_UP"
    assert result["risk_bias"] == "OPPORTUNISTIC"


def test_market_regime_detects_high_volatility() -> None:
    result = MarketRegimeIntelligence().detect(returns=[0.08, -0.07, 0.06, -0.05, 0.04])

    assert result["detected_regime"] == "HIGH_VOLATILITY"
    assert result["volatility_state"] == "HIGH"
    assert result["risk_bias"] == "DEFENSIVE"


def test_market_regime_detects_correlation_stress() -> None:
    result = MarketRegimeIntelligence().detect(
        returns=[0.01, -0.005, 0.004, 0.002],
        correlation_matrix={
            "EQUITIES": {"EQUITIES": 1.0, "CRYPTO": 0.86},
            "CRYPTO": {"EQUITIES": 0.86, "CRYPTO": 1.0},
        },
    )

    assert result["detected_regime"] == "CORRELATION_STRESS"
    assert result["correlation_state"] == "STRESS"


def test_market_regime_unknown_on_insufficient_inputs() -> None:
    result = MarketRegimeIntelligence().detect(returns=[0.01])

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["detected_regime"] == "UNKNOWN"
    assert result["risk_bias"] == "DEFENSIVE"
