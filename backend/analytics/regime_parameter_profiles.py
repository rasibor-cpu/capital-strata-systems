from __future__ import annotations

from typing import Any, Mapping


class RegimeParameterProfilesError(RuntimeError):
    """Fail-closed exception for regime profile recommendations."""


class RegimeParameterProfiles:
    """Deterministic recommendation profiles by market regime."""

    _BASE_PROFILES = {
        "TREND": {
            "position_sizing_multiplier": 1.10,
            "confidence_threshold": 0.58,
            "profit_target_multiplier": 1.20,
            "stop_logic": "trail_wide",
            "holding_duration_minutes": 180,
        },
        "RANGE": {
            "position_sizing_multiplier": 0.95,
            "confidence_threshold": 0.62,
            "profit_target_multiplier": 0.95,
            "stop_logic": "tight_range_stop",
            "holding_duration_minutes": 60,
        },
        "VOLATILE": {
            "position_sizing_multiplier": 0.80,
            "confidence_threshold": 0.70,
            "profit_target_multiplier": 0.85,
            "stop_logic": "tight_volatility_stop",
            "holding_duration_minutes": 45,
        },
        "BREAKOUT": {
            "position_sizing_multiplier": 1.05,
            "confidence_threshold": 0.60,
            "profit_target_multiplier": 1.15,
            "stop_logic": "breakout_trail",
            "holding_duration_minutes": 120,
        },
        "REVERSAL": {
            "position_sizing_multiplier": 0.90,
            "confidence_threshold": 0.68,
            "profit_target_multiplier": 0.90,
            "stop_logic": "reversal_fail_fast",
            "holding_duration_minutes": 75,
        },
    }

    def recommend_profiles(self, adjustments: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
        if adjustments is not None and not isinstance(adjustments, Mapping):
            raise RegimeParameterProfilesError("adjustments must be a mapping when provided")

        output: dict[str, dict[str, Any]] = {}
        for regime in sorted(self._BASE_PROFILES.keys()):
            profile = dict(self._BASE_PROFILES[regime])
            adjust = dict((adjustments or {}).get(regime, {})) if isinstance((adjustments or {}).get(regime, {}), Mapping) else {}
            if adjust:
                profile = self._apply_adjustments(profile, adjust)
            output[regime] = profile
        return output

    def get_profile(self, regime: str) -> dict[str, Any]:
        normalized = str(regime or "").strip().upper()
        if normalized not in self._BASE_PROFILES:
            raise RegimeParameterProfilesError("unsupported regime")
        return dict(self._BASE_PROFILES[normalized])

    def _apply_adjustments(self, profile: dict[str, Any], adjust: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(profile)
        for key in ("position_sizing_multiplier", "confidence_threshold", "profit_target_multiplier"):
            if key in adjust:
                try:
                    result[key] = float(adjust[key])
                except (TypeError, ValueError) as exc:
                    raise RegimeParameterProfilesError(f"{key} adjustment must be numeric") from exc
        if "stop_logic" in adjust:
            result["stop_logic"] = str(adjust["stop_logic"] or result["stop_logic"]).strip() or result["stop_logic"]
        if "holding_duration_minutes" in adjust:
            try:
                result["holding_duration_minutes"] = int(adjust["holding_duration_minutes"])
            except (TypeError, ValueError) as exc:
                raise RegimeParameterProfilesError("holding_duration_minutes adjustment must be numeric") from exc
        return result
