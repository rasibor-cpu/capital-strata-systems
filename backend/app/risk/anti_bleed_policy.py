"""Phase 184A — immutable AntiBleed policy profiles and governed resolver.

Policies are frozen. Selection depends only on governed execution context.
No environment overrides, broker heuristics, account-size logic, or runtime mutation.

Phase 184A-R1 — every policy carries immutable policy_id + policy_version for auditability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


# Framework audit version for all shipped 184A registry profiles.
ANTIBLEED_POLICY_FRAMEWORK_VERSION = "184A.1"


class AntiBleedPolicyError(ValueError):
    """Raised when AntiBleed policy construction or selection fails closed."""


@dataclass(frozen=True)
class AntiBleedPolicy:
    """Immutable AntiBleed evaluation thresholds for one governed profile."""

    name: str
    policy_id: str
    policy_version: str
    minimum_profitable_trade_size: float
    minimum_required_net_edge_bps: float
    cooldown_minutes: int
    maximum_symbol_frequency: int
    require_complete_microstructure_inputs: bool
    allow_dev_override: bool

    def __post_init__(self) -> None:
        if not str(self.name or "").strip():
            raise AntiBleedPolicyError("policy name is required")
        if not str(self.policy_id or "").strip():
            raise AntiBleedPolicyError("policy_id is required")
        if not str(self.policy_version or "").strip():
            raise AntiBleedPolicyError("policy_version is required")
        if self.minimum_profitable_trade_size <= 0.0:
            raise AntiBleedPolicyError("minimum_profitable_trade_size must be positive")
        if self.minimum_required_net_edge_bps < 0.0:
            raise AntiBleedPolicyError("minimum_required_net_edge_bps must be non-negative")
        if self.cooldown_minutes < 0:
            raise AntiBleedPolicyError("cooldown_minutes must be non-negative")
        if self.maximum_symbol_frequency < 1:
            raise AntiBleedPolicyError("maximum_symbol_frequency must be >= 1")

    def identity(self) -> dict[str, str]:
        """Audit-safe identity fields only (no secrets, no authority)."""
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "name": self.name,
        }


# ---------------------------------------------------------------------------
# Immutable profile registry (construction-time constants only)
# ---------------------------------------------------------------------------

STANDARD = AntiBleedPolicy(
    name="STANDARD",
    policy_id="STANDARD",
    policy_version=ANTIBLEED_POLICY_FRAMEWORK_VERSION,
    minimum_profitable_trade_size=50.0,
    minimum_required_net_edge_bps=25.0,
    cooldown_minutes=10,
    maximum_symbol_frequency=1,
    require_complete_microstructure_inputs=True,
    allow_dev_override=False,
)

MICRO_PILOT = AntiBleedPolicy(
    name="MICRO_PILOT",
    policy_id="MICRO_PILOT",
    policy_version=ANTIBLEED_POLICY_FRAMEWORK_VERSION,
    # Sized to permit Phase 152A CAD 20 ceiling without changing 152A itself.
    # Edge, cooldown, input completeness, and override posture remain fail-closed.
    minimum_profitable_trade_size=20.0,
    minimum_required_net_edge_bps=25.0,
    cooldown_minutes=10,
    maximum_symbol_frequency=1,
    require_complete_microstructure_inputs=True,
    allow_dev_override=False,
)

PAPER = AntiBleedPolicy(
    name="PAPER",
    policy_id="PAPER",
    policy_version=ANTIBLEED_POLICY_FRAMEWORK_VERSION,
    minimum_profitable_trade_size=50.0,
    minimum_required_net_edge_bps=25.0,
    cooldown_minutes=10,
    maximum_symbol_frequency=1,
    require_complete_microstructure_inputs=True,
    allow_dev_override=False,
)

BACKTEST = AntiBleedPolicy(
    name="BACKTEST",
    policy_id="BACKTEST",
    policy_version=ANTIBLEED_POLICY_FRAMEWORK_VERSION,
    minimum_profitable_trade_size=50.0,
    minimum_required_net_edge_bps=25.0,
    cooldown_minutes=10,
    maximum_symbol_frequency=1,
    require_complete_microstructure_inputs=True,
    allow_dev_override=False,
)

POLICY_PROFILES: Mapping[str, AntiBleedPolicy] = {
    "STANDARD": STANDARD,
    "MICRO_PILOT": MICRO_PILOT,
    "PAPER": PAPER,
    "BACKTEST": BACKTEST,
}

# Governed execution context tokens → profile name
_CONTEXT_TO_PROFILE: Mapping[str, str] = {
    "LIVE_MICRO_PILOT": "MICRO_PILOT",
    "MICRO_PILOT": "MICRO_PILOT",
    "PAPER": "PAPER",
    "PAPER_TRADING": "PAPER",
    "BACKTEST": "BACKTEST",
    "BACKTESTING": "BACKTEST",
}


def _normalize_context(execution_context: Any) -> str:
    if execution_context is None:
        return ""
    if isinstance(execution_context, Mapping):
        for key in (
            "governed_execution_context",
            "anti_bleed_context",
            "execution_context",
            "governed_mode",
            "mode",
        ):
            value = execution_context.get(key)
            if value is not None and str(value).strip():
                return str(value).strip().upper()
        return ""
    return str(execution_context).strip().upper()


class AntiBleedPolicyResolver:
    """Resolve an immutable AntiBleed policy from governed execution context only."""

    @staticmethod
    def resolve(execution_context: Any = None) -> AntiBleedPolicy:
        token = _normalize_context(execution_context)
        profile_name = _CONTEXT_TO_PROFILE.get(token, "STANDARD")
        policy = POLICY_PROFILES[profile_name]
        # Return the registry instance (frozen); callers must not mutate.
        return policy

    @staticmethod
    def profile_names() -> tuple[str, ...]:
        return tuple(POLICY_PROFILES.keys())


__all__ = [
    "ANTIBLEED_POLICY_FRAMEWORK_VERSION",
    "AntiBleedPolicy",
    "AntiBleedPolicyError",
    "AntiBleedPolicyResolver",
    "STANDARD",
    "MICRO_PILOT",
    "PAPER",
    "BACKTEST",
    "POLICY_PROFILES",
]
