from backend.market_intelligence.regime_aware_weighting_engine import RegimeAwareWeightingEngine
import inspect


def _components() -> dict:
    return {
        "technical": {"status": "OK", "technical_score": 70},
        "fundamental": {"status": "OK", "fundamental_quality_score": 60},
        "sentiment": {"status": "OK", "sentiment_score": 55},
        "quantitative": {"status": "OK", "alpha_score": 75},
    }


def _evaluate(regime: str, **overrides):
    components = _components()
    components.update(overrides)
    return RegimeAwareWeightingEngine().evaluate(
        market_regime={"detected_regime": regime},
        portfolio_lifecycle={"portfolio_state": "ACTIVE"},
        **components,
    )


def test_trending_regime_weights_normalize_to_100() -> None:
    result = _evaluate("TRENDING_UP")

    assert result["status"] == "OK"
    assert result["weights"]["technical"] > result["weights"]["fundamental"]
    assert result["weights"]["quantitative"] > result["weights"]["sentiment"]
    assert result["weight_sum"] == 100.0


def test_high_volatility_regime_weights_normalize_to_100() -> None:
    result = _evaluate("HIGH_VOLATILITY")

    assert result["weights"]["sentiment"] > result["weights"]["technical"]
    assert result["weight_sum"] == 100.0


def test_risk_off_macro_regime_weights_normalize_to_100() -> None:
    result = _evaluate("RISK_OFF")

    assert result["weights"]["fundamental"] > result["weights"]["technical"]
    assert result["weights"]["sentiment"] > result["weights"]["quantitative"]
    assert result["weight_sum"] == 100.0


def test_unknown_regime_uses_safe_balanced_default() -> None:
    result = _evaluate("UNKNOWN")

    assert result["weights"] == {
        "technical": 25.0,
        "fundamental": 25.0,
        "sentiment": 25.0,
        "quantitative": 25.0,
    }
    assert "unknown_regime_safe_balanced_default" in result["reasons"]


def test_missing_component_reduces_confidence_and_normalizes_remaining_weights() -> None:
    result = _evaluate(
        "TRENDING_UP",
        fundamental={"status": "DATA UNAVAILABLE", "fundamental_quality_score": 0},
    )

    assert result["status"] == "PARTIAL"
    assert result["weights"]["fundamental"] == 0.0
    assert result["weight_sum"] == 100.0
    assert result["confidence_adjustment"] < 0
    assert "fundamental_component_unavailable" in result["reasons"]


def test_no_portfolio_reduces_confidence_but_does_not_fail() -> None:
    components = _components()
    result = RegimeAwareWeightingEngine().evaluate(
        market_regime={"detected_regime": "TRENDING_UP"},
        portfolio_lifecycle={"portfolio_state": "NO_PORTFOLIO"},
        **components,
    )

    assert result["status"] == "OK"
    assert result["confidence_adjustment"] < 5
    assert "portfolio_context_no_portfolio" in result["reasons"]
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_weighting_engine_has_no_broker_or_live_execution_references() -> None:
    source = inspect.getsource(RegimeAwareWeightingEngine).lower()

    assert "broker" not in source
    assert "live_trading" not in source
