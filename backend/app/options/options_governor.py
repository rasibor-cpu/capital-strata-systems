from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from backend.app.options.options_contract_registry import (
    get_options_contract,
)


@dataclass(frozen=True)
class OptionsGovernanceDecision:
    allowed: bool
    symbol: str
    reason: str
    mode: str
    max_contracts: int
    requested_contracts: int
    underlying: str | None = None
    option_type: str | None = None


class OptionsGovernor:
    """
    PCNRASS options governance layer.

    Dry-run safe:
    - No live option orders.
    - No broker calls.
    - Validates contract support, type, quantity, and mode.
    """

    DEFAULT_MAX_CONTRACTS = 1

    def __init__(self, live_options_enabled: bool = False) -> None:
        self.live_options_enabled = bool(live_options_enabled)

    def evaluate(
        self,
        *,
        symbol: str,
        mode: str,
        requested_contracts: int = 1,
        account_equity: float = 0.0,
    ) -> OptionsGovernanceDecision:
        selected_mode = str(mode or "paper").strip().lower()
        contract = get_options_contract(symbol)
        requested = int(requested_contracts or 0)

        if contract is None:
            return OptionsGovernanceDecision(
                allowed=False,
                symbol=str(symbol or "").strip().upper(),
                reason="UNKNOWN_OR_UNSUPPORTED_OPTIONS_CONTRACT",
                mode=selected_mode,
                max_contracts=0,
                requested_contracts=requested,
            )

        if requested <= 0:
            return OptionsGovernanceDecision(
                allowed=False,
                symbol=contract.symbol,
                reason="INVALID_OPTIONS_CONTRACT_QUANTITY",
                mode=selected_mode,
                max_contracts=self.DEFAULT_MAX_CONTRACTS,
                requested_contracts=requested,
                underlying=contract.underlying,
                option_type=contract.option_type,
            )

        if requested > self.DEFAULT_MAX_CONTRACTS:
            return OptionsGovernanceDecision(
                allowed=False,
                symbol=contract.symbol,
                reason="OPTIONS_CONTRACT_LIMIT_EXCEEDED",
                mode=selected_mode,
                max_contracts=self.DEFAULT_MAX_CONTRACTS,
                requested_contracts=requested,
                underlying=contract.underlying,
                option_type=contract.option_type,
            )

        if selected_mode == "live":
            if not self.live_options_enabled:
                return OptionsGovernanceDecision(
                    allowed=False,
                    symbol=contract.symbol,
                    reason="LIVE_OPTIONS_EXECUTION_NOT_ENABLED",
                    mode=selected_mode,
                    max_contracts=self.DEFAULT_MAX_CONTRACTS,
                    requested_contracts=requested,
                    underlying=contract.underlying,
                    option_type=contract.option_type,
                )

            if float(account_equity or 0.0) <= 0.0:
                return OptionsGovernanceDecision(
                    allowed=False,
                    symbol=contract.symbol,
                    reason="LIVE_OPTIONS_REQUIRES_POSITIVE_ACCOUNT_EQUITY",
                    mode=selected_mode,
                    max_contracts=self.DEFAULT_MAX_CONTRACTS,
                    requested_contracts=requested,
                    underlying=contract.underlying,
                    option_type=contract.option_type,
                )

        return OptionsGovernanceDecision(
            allowed=True,
            symbol=contract.symbol,
            reason="OPTIONS_GOVERNANCE_APPROVED",
            mode=selected_mode,
            max_contracts=self.DEFAULT_MAX_CONTRACTS,
            requested_contracts=requested,
            underlying=contract.underlying,
            option_type=contract.option_type,
        )

    def decision_to_dict(self, decision: OptionsGovernanceDecision) -> Dict[str, Any]:
        return {
            "allowed": decision.allowed,
            "symbol": decision.symbol,
            "reason": decision.reason,
            "mode": decision.mode,
            "max_contracts": decision.max_contracts,
            "requested_contracts": decision.requested_contracts,
            "underlying": decision.underlying,
            "option_type": decision.option_type,
        }
