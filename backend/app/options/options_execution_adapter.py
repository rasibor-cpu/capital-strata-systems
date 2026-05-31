from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from backend.app.options.options_governor import (
    OptionsGovernor,
    OptionsGovernanceDecision,
)


@dataclass(frozen=True)
class OptionsExecutionResult:
    approved: bool
    symbol: str
    side: str
    contracts: int
    mode: str
    broker: str
    reason: str
    execution_id: str
    dry_run: bool = True


class OptionsExecutionAdapter:
    """
    Institutional options execution abstraction layer.

    PCNRASS SAFE:
    - DRY RUN ONLY
    - NO LIVE ORDER PLACEMENT
    - NO EXTERNAL BROKER CALLS
    - GOVERNANCE-FIRST VALIDATION
    """

    def __init__(
        self,
        *,
        broker_name: str = "OPTIONS_ADAPTER",
        live_options_enabled: bool = False,
    ) -> None:
        self.broker_name = broker_name
        self.live_options_enabled = bool(live_options_enabled)
        self.governor = OptionsGovernor(
            live_options_enabled=self.live_options_enabled
        )

    def execute_options_order(
        self,
        *,
        symbol: str,
        side: str,
        contracts: int,
        mode: str,
        account_equity: float = 0.0,
    ) -> OptionsExecutionResult:
        governance: OptionsGovernanceDecision = self.governor.evaluate(
            symbol=symbol,
            mode=mode,
            requested_contracts=contracts,
            account_equity=account_equity,
        )

        if not governance.allowed:
            return OptionsExecutionResult(
                approved=False,
                symbol=str(symbol).upper(),
                side=str(side).upper(),
                contracts=int(contracts),
                mode=str(mode).lower(),
                broker=self.broker_name,
                reason=governance.reason,
                execution_id="BLOCKED",
                dry_run=True,
            )

        execution_id = (
            f"OPTSIM-"
            f"{governance.symbol}-"
            f"{str(side).upper()}-"
            f"{int(contracts)}"
        )

        print(
            f"[OPTIONS DRY RUN EXECUTION] "
            f"symbol={governance.symbol} "
            f"side={side} "
            f"contracts={contracts} "
            f"mode={mode} "
            f"broker={self.broker_name}"
        )

        return OptionsExecutionResult(
            approved=True,
            symbol=governance.symbol,
            side=str(side).upper(),
            contracts=int(contracts),
            mode=str(mode).lower(),
            broker=self.broker_name,
            reason="OPTIONS_DRY_RUN_APPROVED",
            execution_id=execution_id,
            dry_run=True,
        )

    def result_to_dict(self, result: OptionsExecutionResult) -> Dict[str, Any]:
        return {
            "approved": result.approved,
            "symbol": result.symbol,
            "side": result.side,
            "contracts": result.contracts,
            "mode": result.mode,
            "broker": result.broker,
            "reason": result.reason,
            "execution_id": result.execution_id,
            "dry_run": result.dry_run,
        }
