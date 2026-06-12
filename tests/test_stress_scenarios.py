from engine.risk.stress_scenarios import (
    CANONICAL_STRESS_SCENARIOS,
)


def test_stress_scenario_registry_not_empty():
    assert len(CANONICAL_STRESS_SCENARIOS) > 0


def test_spy_down_5_exists():
    assert "SPY_DOWN_5" in CANONICAL_STRESS_SCENARIOS


def test_vol_plus_20_exists():
    assert "VOL_PLUS_20" in CANONICAL_STRESS_SCENARIOS


def test_fx_usd_plus_10_exists():
    assert "FX_USD_PLUS_10" in CANONICAL_STRESS_SCENARIOS