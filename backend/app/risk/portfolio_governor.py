from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class PortfolioGovernanceDecision:
    approved: bool
    reason: str
    total_requested_exposure: float
    max_allowed_exposure: float
    asset_class: str
    symbol: str
    mode: str


class PortfolioGovernor:
    """
    Institutional portfolio governance authority.

    PCNRASS SAFE:
    - Governance only
    - No broker calls
    - No order placement
    - Cross-asset exposure control
    """

    DEFAULT_MAX_PORTFOLIO_EXPOSURE_PCT = 0.25

    DEFAULT_MAX_ASSET_CLASS_EXPOSURE: Dict[str, float] = {
        "CRYPTO": 0.10,
        "FX": 0.10,
        "FUTURES": 0.05,
        "OPTIONS": 0.05,
    }

    def __init__(self) -> None:
        pass

    def evaluate(
        self,
        *,
        asset_class: str,
        symbol: str,
        requested_exposure: float,
        current_portfolio_exposure: float,
        account_equity: float,
        mode: str,
    ) -> PortfolioGovernanceDecision:

        normalized_asset = str(asset_class or "").strip().upper()

        if float(account_equity or 0.0) <= 0.0:
            return PortfolioGovernanceDecision(
                approved=False,
                reason="INVALID_ACCOUNT_EQUITY",
                total_requested_exposure=0.0,
                max_allowed_exposure=0.0,
                asset_class=normalized_asset,
                symbol=str(symbol).upper(),
                mode=str(mode).lower(),
            )

        max_total = (
            float(account_equity)
            * self.DEFAULT_MAX_PORTFOLIO_EXPOSURE_PCT
        )

        projected_total = (
            float(current_portfolio_exposure)
            + float(requested_exposure)
        )

        if projected_total > max_total:

            return PortfolioGovernanceDecision(
                approved=False,
                reason="PORTFOLIO_MAX_EXPOSURE_EXCEEDED",
                total_requested_exposure=projected_total,
                max_allowed_exposure=max_total,
                asset_class=normalized_asset,
                symbol=str(symbol).upper(),
                mode=str(mode).lower(),
            )

        asset_cap_pct = self.DEFAULT_MAX_ASSET_CLASS_EXPOSURE.get(
            normalized_asset,
            0.0,
        )

        if asset_cap_pct <= 0.0:

            return PortfolioGovernanceDecision(
                approved=False,
                reason="UNKNOWN_OR_UNSUPPORTED_ASSET_CLASS",
                total_requested_exposure=projected_total,
                max_allowed_exposure=max_total,
                asset_class=normalized_asset,
                symbol=str(symbol).upper(),
                mode=str(mode).lower(),
            )

        asset_cap_value = (
            float(account_equity)
            * float(asset_cap_pct)
        )

        if float(requested_exposure) > asset_cap_value:

            return PortfolioGovernanceDecision(
                approved=False,
                reason="ASSET_CLASS_EXPOSURE_LIMIT_EXCEEDED",
                total_requested_exposure=projected_total,
                max_allowed_exposure=asset_cap_value,
                asset_class=normalized_asset,
                symbol=str(symbol).upper(),
                mode=str(mode).lower(),
            )

        return PortfolioGovernanceDecision(
            approved=True,
            reason="PORTFOLIO_GOVERNANCE_APPROVED",
            total_requested_exposure=projected_total,
            max_allowed_exposure=max_total,
            asset_class=normalized_asset,
            symbol=str(symbol).upper(),
            mode=str(mode).lower(),
        )

    def decision_to_dict(
        self,
        decision: PortfolioGovernanceDecision,
    ) -> Dict[str, Any]:

        return {
            "approved": decision.approved,
            "reason": decision.reason,
            "total_requested_exposure": (
                decision.total_requested_exposure
            ),
            "max_allowed_exposure": (
                decision.max_allowed_exposure
            ),
            "asset_class": decision.asset_class,
            "symbol": decision.symbol,
            "mode": decision.mode,
        }
