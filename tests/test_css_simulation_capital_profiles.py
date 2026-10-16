"""Capital-profile safeguards for paper-only CSS accounts."""
import pytest

from backend.simulation.capital_profiles import (
    DEFAULT_USER_CAPITAL_CAD, ENGINEERING_CAPITAL_CAD, PRESETS_CAD,
    reference_comparison, starting_capital, validate_capital,
)


def test_default_and_engineering_capital_are_separate():
    assert starting_capital() == 100_000
    assert starting_capital(profile="engineering") == 14_600
    assert DEFAULT_USER_CAPITAL_CAD == 100_000
    assert ENGINEERING_CAPITAL_CAD == 14_600


@pytest.mark.parametrize("profile,expected", [
    ("small", 10_000), ("intermediate", 25_000),
    ("standard", 100_000), ("advanced", 250_000),
])
def test_presets(profile, expected):
    assert starting_capital(profile=profile) == expected


@pytest.mark.parametrize("amount", [1000, 14600, 1000000, "25000.50"])
def test_custom_valid(amount):
    assert starting_capital(profile="custom", custom_cad=amount) == float(amount)


@pytest.mark.parametrize("amount", [None, 0, 146, 999, 1000001, -100, "NaN", "Infinity", "oops", True, "1234.567"])
def test_custom_invalid(amount):
    with pytest.raises(ValueError):
        starting_capital(profile="custom", custom_cad=amount)


def test_unknown_profile_or_mixed_custom_rejected():
    with pytest.raises(ValueError):
        starting_capital(profile="unknown")
    with pytest.raises(ValueError):
        starting_capital(profile="standard", custom_cad=25000)


def test_reference_comparison_100_to_1_is_illustrative():
    result = reference_comparison(300, simulation_capital_cad=14600)
    assert result["scale_ratio"] == 100
    assert result["illustrative_reference_pnl_cad"] == 3
    assert result["executable_at_reference_capital"] is False


def test_negative_pnl_and_non_100_ratio():
    result = reference_comparison(-250, simulation_capital_cad=100000)
    assert result["illustrative_reference_pnl_cad"] == -0.37


def test_invalid_reference_and_pnl():
    with pytest.raises(ValueError):
        reference_comparison(10, simulation_capital_cad=14600, reference_capital_cad=0)
    with pytest.raises(ValueError):
        reference_comparison(float("nan"), simulation_capital_cad=14600)


def test_presets_cover_approved_options():
    assert tuple(map(float, PRESETS_CAD)) == (10000, 25000, 100000, 250000)
