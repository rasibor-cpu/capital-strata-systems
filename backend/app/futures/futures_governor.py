from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from backend.app.futures.futures_contract_registry import (
    get_futures_contract,
    normalize_futures_symbol,
)


@dataclass(frozen=True)
class FuturesGovernanceDecision:
    allowed: bool
    symbol: str
    reason: str
    mode: str
    max_contracts: int
    requested_contracts: int
    margin_class: str | None = None


class FuturesGovernor:
    """
    PCNRASS futures governance layer.

    This governor is intentionally dry-run safe:
    - It does not place trades.
    - It does not enable live futures execution.
    - It validates contract support, mode, quantity, and margin class.
    """

    DEFAULT_MAX_CONTRACTS_BY_MARGIN_CLASS: Dict[str, int] = {
        "EQUITY_INDEX": 1,
        "ENERGY": 1,
        "METALS": 1,
        "RATES": 1,
        "FX_FUTURES": 1,
    }

    def __init__(self, live_futures_enabled: bool = False) -> None:
        self.live_futures_enabled = bool(live_futures_enabled)

    def evaluate(
        self,
        *,
        symbol: str,
        mode: str,
        requested_contracts: int = 1,
        account_equity: float = 0.0,
    ) -> FuturesGovernanceDecision:
        normalized = normalize_futures_symbol(symbol)
        selected_mode = str(mode or "paper").strip().lower()

        contract = get_futures_contract(normalized)
        if contract is None:
            return FuturesGovernanceDecision(
                allowed=False,
                symbol=normalized,
                reason="UNKNOWN_FUTURES_CONTRACT",
                mode=selected_mode,
                max_contracts=0,
                requested_contracts=int(requested_contracts or 0),
            )

        max_contracts = self.DEFAULT_MAX_CONTRACTS_BY_MARGIN_CLASS.get(
            contract.margin_class,
            0,
        )

        requested = int(requested_contracts or 0)

        if requested <= 0:
            return FuturesGovernanceDecision(
                allowed=False,
                symbol=normalized,
                reason="INVALID_CONTRACT_QUANTITY",
                mode=selected_mode,
                max_contracts=max_contracts,
                requested_contracts=requested,
                margin_class=contract.margin_class,
            )

        if requested > max_contracts:
            return FuturesGovernanceDecision(
                allowed=False,
                symbol=normalized,
                reason="FUTURES_CONTRACT_LIMIT_EXCEEDED",
                mode=selected_mode,
                max_contracts=max_contracts,
                requested_contracts=requested,
                margin_class=contract.margin_class,
            )

        if selected_mode == "live":
            if not self.live_futures_enabled:
                return FuturesGovernanceDecision(
                    allowed=False,
                    symbol=normalized,
                    reason="LIVE_FUTURES_EXECUTION_NOT_ENABLED",
                    mode=selected_mode,
                    max_contracts=max_contracts,
                    requested_contracts=requested,
                    margin_class=contract.margin_class,
                )

            if float(account_equity or 0.0) <= 0.0:
                return FuturesGovernanceDecision(
                    allowed=False,
                    symbol=normalized,
                    reason="LIVE_FUTURES_REQUIRES_POSITIVE_ACCOUNT_EQUITY",
                    mode=selected_mode,
                    max_contracts=max_contracts,
                    requested_contracts=requested,
                    margin_class=contract.margin_class,
                )

        return FuturesGovernanceDecision(
            allowed=True,
            symbol=normalized,
            reason="FUTURES_GOVERNANCE_APPROVED",
            mode=selected_mode,
            max_contracts=max_contracts,
            requested_contracts=requested,
            margin_class=contract.margin_class,
        )

    def decision_to_dict(self, decision: FuturesGovernanceDecision) -> Dict[str, Any]:
        return {
            "allowed": decision.allowed,
            "symbol": decision.symbol,
            "reason": decision.reason,
            "mode": decision.mode,
            "max_contracts": decision.max_contracts,
            "requested_contracts": decision.requested_contracts,
            "margin_class": decision.margin_class,
        }
