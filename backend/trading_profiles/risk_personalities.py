"""Copy-trading risk personalities (issue #118 addendum).

Exactly five user-facing personalities. They are NOT the legacy internal engine modes
(SAFE / CONSERVATIVE / BALANCED / AGGRESSIVE / EXPANSION), and nothing here reads or
sets the engine mode: R7 and R14F keep using the engine mode in force, unchanged.
There is deliberately no mapping between the two vocabularies (in particular
"Ultra Aggressive" is not EXPANSION); any mapping needs a reviewed owner decision.

A personality can only make a copied trade *more* restricted than the canonical
gates. Every copied order still has to pass R7, R14F, AntiBleedGuard (including its
minimum size and cooldown), the margin gate, the risk governor, the kill switches
and the global position caps. "More aggressive" never means unlimited risk or any
live-trading permission.

The numeric values below are the proposed defaults for owner review.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RiskPersonality(str, Enum):
    SAFE = "Safe"
    CONSERVATIVE = "Conservative"
    BALANCED = "Balanced"
    AGGRESSIVE = "Aggressive"
    ULTRA_AGGRESSIVE = "Ultra Aggressive"

    @classmethod
    def parse(cls, value: object) -> "RiskPersonality":
        text = str(value or "").strip()
        for personality in cls:
            if text == personality.value or text == personality.name:
                return personality
        raise ValueError(f"unknown risk personality: {text!r}")


# No governed mapping to legacy engine modes exists; see module docstring.
LEGACY_ENGINE_MODE_MAPPING: dict[RiskPersonality, str] = {}


@dataclass(frozen=True)
class PersonalityPolicy:
    personality: RiskPersonality
    # Eligibility
    allowed_asset_classes: frozenset[str]
    allowed_quality_recommendations: frozenset[str]
    min_trade_quality_score: float
    min_probability: float
    min_caie_score: float
    margin_allowed: bool
    # Sizing: notional = equity * risk_per_trade / stop, capped by max_position_pct
    risk_per_trade_pct: float
    max_stop_distance_pct: float
    max_position_pct_of_equity: float
    # Exposure and portfolio risk
    max_open_copied_positions: int
    max_total_exposure_pct_of_equity: float
    max_symbol_exposure_pct_of_equity: float
    daily_loss_halt_pct: float
    max_drawdown_halt_pct: float
    # Exits
    take_profit_r_multiple: float
    trailing_activation_r: float
    trailing_giveback_fraction: float
    time_stop_hours: float

    def summary(self) -> dict:
        """User-facing description of what the personality does."""
        return {
            "personality": self.personality.value,
            "asset_classes": sorted(self.allowed_asset_classes),
            "minimum_trade_quality": self.min_trade_quality_score,
            "accepted_quality_recommendations": sorted(self.allowed_quality_recommendations),
            "minimum_probability": self.min_probability,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "max_stop_distance_pct": self.max_stop_distance_pct,
            "max_position_pct_of_equity": self.max_position_pct_of_equity,
            "max_open_copied_positions": self.max_open_copied_positions,
            "max_total_exposure_pct_of_equity": self.max_total_exposure_pct_of_equity,
            "daily_loss_halt_pct": self.daily_loss_halt_pct,
            "max_drawdown_halt_pct": self.max_drawdown_halt_pct,
            "take_profit_r_multiple": self.take_profit_r_multiple,
            "time_stop_hours": self.time_stop_hours,
            "margin_allowed": self.margin_allowed,
            "overrides_safety_gates": False,
            "live_trading_permission": False,
        }


_FX_CRYPTO = frozenset({"FX", "CRYPTO"})
_ALL = frozenset({"FX", "CRYPTO", "FUTURES", "OPTIONS"})

POLICIES: dict[RiskPersonality, PersonalityPolicy] = {
    RiskPersonality.SAFE: PersonalityPolicy(
        personality=RiskPersonality.SAFE,
        allowed_asset_classes=frozenset({"FX"}),
        allowed_quality_recommendations=frozenset({"EXECUTE"}),
        min_trade_quality_score=80.0,
        min_probability=0.66,
        min_caie_score=130.0,
        margin_allowed=False,
        risk_per_trade_pct=0.25,
        max_stop_distance_pct=1.0,
        max_position_pct_of_equity=2.0,
        max_open_copied_positions=2,
        max_total_exposure_pct_of_equity=5.0,
        max_symbol_exposure_pct_of_equity=2.0,
        daily_loss_halt_pct=1.0,
        max_drawdown_halt_pct=3.0,
        take_profit_r_multiple=1.5,
        trailing_activation_r=1.0,
        trailing_giveback_fraction=0.30,
        time_stop_hours=24.0,
    ),
    RiskPersonality.CONSERVATIVE: PersonalityPolicy(
        personality=RiskPersonality.CONSERVATIVE,
        allowed_asset_classes=_FX_CRYPTO,
        allowed_quality_recommendations=frozenset({"EXECUTE", "PREFERRED"}),
        min_trade_quality_score=72.0,
        min_probability=0.62,
        min_caie_score=120.0,
        margin_allowed=False,
        risk_per_trade_pct=0.50,
        max_stop_distance_pct=1.5,
        max_position_pct_of_equity=4.0,
        max_open_copied_positions=3,
        max_total_exposure_pct_of_equity=10.0,
        max_symbol_exposure_pct_of_equity=4.0,
        daily_loss_halt_pct=2.0,
        max_drawdown_halt_pct=5.0,
        take_profit_r_multiple=1.75,
        trailing_activation_r=1.0,
        trailing_giveback_fraction=0.35,
        time_stop_hours=48.0,
    ),
    RiskPersonality.BALANCED: PersonalityPolicy(
        personality=RiskPersonality.BALANCED,
        allowed_asset_classes=frozenset({"FX", "CRYPTO", "FUTURES"}),
        allowed_quality_recommendations=frozenset({"EXECUTE", "PREFERRED"}),
        min_trade_quality_score=65.0,
        min_probability=0.58,
        min_caie_score=110.0,
        margin_allowed=False,
        risk_per_trade_pct=1.00,
        max_stop_distance_pct=2.0,
        max_position_pct_of_equity=6.0,
        max_open_copied_positions=5,
        max_total_exposure_pct_of_equity=20.0,
        max_symbol_exposure_pct_of_equity=6.0,
        daily_loss_halt_pct=3.0,
        max_drawdown_halt_pct=8.0,
        take_profit_r_multiple=2.0,
        trailing_activation_r=1.25,
        trailing_giveback_fraction=0.40,
        time_stop_hours=72.0,
    ),
    RiskPersonality.AGGRESSIVE: PersonalityPolicy(
        personality=RiskPersonality.AGGRESSIVE,
        allowed_asset_classes=_ALL,
        allowed_quality_recommendations=frozenset({"EXECUTE", "PREFERRED"}),
        min_trade_quality_score=58.0,
        min_probability=0.55,
        min_caie_score=100.0,
        margin_allowed=True,
        risk_per_trade_pct=1.50,
        max_stop_distance_pct=2.5,
        max_position_pct_of_equity=8.0,
        max_open_copied_positions=7,
        max_total_exposure_pct_of_equity=30.0,
        max_symbol_exposure_pct_of_equity=8.0,
        daily_loss_halt_pct=4.0,
        max_drawdown_halt_pct=12.0,
        take_profit_r_multiple=2.5,
        trailing_activation_r=1.5,
        trailing_giveback_fraction=0.45,
        time_stop_hours=120.0,
    ),
    RiskPersonality.ULTRA_AGGRESSIVE: PersonalityPolicy(
        personality=RiskPersonality.ULTRA_AGGRESSIVE,
        allowed_asset_classes=_ALL,
        allowed_quality_recommendations=frozenset({"EXECUTE", "PREFERRED", "WATCH"}),
        min_trade_quality_score=50.0,
        min_probability=0.53,
        min_caie_score=90.0,
        margin_allowed=True,
        risk_per_trade_pct=2.00,
        max_stop_distance_pct=3.0,
        max_position_pct_of_equity=10.0,
        # Still inside the global 10-position hard cap and per-asset caps 3/3/2/2.
        max_open_copied_positions=8,
        max_total_exposure_pct_of_equity=40.0,
        max_symbol_exposure_pct_of_equity=10.0,
        daily_loss_halt_pct=5.0,
        max_drawdown_halt_pct=15.0,
        take_profit_r_multiple=3.0,
        trailing_activation_r=2.0,
        trailing_giveback_fraction=0.50,
        time_stop_hours=168.0,
    ),
}


def policy_for(personality: RiskPersonality) -> PersonalityPolicy:
    return POLICIES[RiskPersonality(personality)]
