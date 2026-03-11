from __future__ import annotations

from typing import Dict, Optional, Tuple


class PortfolioRiskGovernor:
    """
    CSS Portfolio Risk Governor

    Controls:
    - max single-asset exposure
    - max total portfolio exposure

    The governor now supports policy-driven limits so that session policy
    settings propagate correctly into live execution.
    """

    def __init__(
        self,
        capital: float,
        max_asset_exposure: Optional[float] = None,
        max_portfolio_exposure: Optional[float] = None,
    ) -> None:
        self.total_capital = float(capital)

        # Use provided policy values if supplied; otherwise keep safe defaults.
        self.max_asset_exposure = (
            float(max_asset_exposure) if max_asset_exposure is not None else 0.25
        )
        self.max_portfolio_exposure = (
            float(max_portfolio_exposure) if max_portfolio_exposure is not None else 1.0
        )

        self.asset_exposure: Dict[str, float] = {}
        self.portfolio_exposure = 0.0

    def approve_trade(self, asset: str, size_usd: float) -> Tuple[bool, str]:
        if self.total_capital <= 0:
            return False, "Invalid capital configuration"

        asset_limit = self.total_capital * self.max_asset_exposure
        portfolio_limit = self.total_capital * self.max_portfolio_exposure

        current_asset_exposure = self.asset_exposure.get(asset, 0.0)

        if current_asset_exposure + size_usd > asset_limit:
            return False, "Blocked: asset exposure limit exceeded"

        if self.portfolio_exposure + size_usd > portfolio_limit:
            return False, "Blocked: portfolio exposure limit exceeded"

        return True, "approved"

    def register_trade(self, asset: str, size_usd: float) -> None:
        self.asset_exposure[asset] = self.asset_exposure.get(asset, 0.0) + size_usd
        self.portfolio_exposure += size_usd

    def close_trade(self, asset: str, size_usd: float) -> None:
        if asset in self.asset_exposure:
            self.asset_exposure[asset] -= size_usd

            if self.asset_exposure[asset] <= 0:
                del self.asset_exposure[asset]

        self.portfolio_exposure -= size_usd

        if self.portfolio_exposure < 0:
            self.portfolio_exposure = 0.0