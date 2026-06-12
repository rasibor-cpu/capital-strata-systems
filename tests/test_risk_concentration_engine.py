from engine.risk.risk_concentration_engine import (
    ConcentrationExposure,
    RiskConcentrationEngine,
)


def test_concentration_by_asset_class_and_symbol():
    engine = RiskConcentrationEngine()

    result = engine.analyze(
        [
            ConcentrationExposure("BTC-USD", "CRYPTO", 5000.0),
            ConcentrationExposure("ETH-USD", "CRYPTO", 3000.0),
            ConcentrationExposure("EUR_USD", "FX", 2000.0),
        ]
    )

    assert result.total_exposure == 10000.0
    assert result.by_asset_class["CRYPTO"] == 8000.0
    assert result.by_asset_class["FX"] == 2000.0
    assert result.largest_asset_class == "CRYPTO"
    assert result.largest_asset_class_pct == 80.0
    assert result.largest_symbol == "BTC-USD"
    assert result.largest_symbol_pct == 50.0


def test_empty_concentration_returns_none_values():
    engine = RiskConcentrationEngine()

    result = engine.analyze([])

    assert result.total_exposure == 0.0
    assert result.largest_asset_class == "NONE"
    assert result.largest_symbol == "NONE"


def test_negative_exposure_uses_absolute_value():
    engine = RiskConcentrationEngine()

    result = engine.analyze(
        [
            ConcentrationExposure("SPY", "OPTIONS", -2500.0),
            ConcentrationExposure("QQQ", "OPTIONS", 2500.0),
        ]
    )

    assert result.total_exposure == 5000.0
    assert result.by_asset_class["OPTIONS"] == 5000.0