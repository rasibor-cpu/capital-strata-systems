from __future__ import annotations

import pytest

from backend.analytics.regime_parameter_profiles import RegimeParameterProfiles, RegimeParameterProfilesError


def test_regime_profiles_default_and_adjusted() -> None:
    engine = RegimeParameterProfiles()
    profiles = engine.recommend_profiles({"TREND": {"confidence_threshold": 0.61}})

    assert "TREND" in profiles
    assert profiles["TREND"]["confidence_threshold"] == 0.61
    assert profiles["RANGE"]["stop_logic"] == "tight_range_stop"


def test_regime_get_profile_fail_closed() -> None:
    with pytest.raises(RegimeParameterProfilesError):
        RegimeParameterProfiles().get_profile("NOT_A_REGIME")
