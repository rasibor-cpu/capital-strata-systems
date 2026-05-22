from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from backend.app.futures.futures_governor import (
    FuturesGovernor,
    FuturesGovernanceDecision,
)


@dataclass(frozen=True)
class FuturesExecutionResult:
    approved: bool
    symbol: str
    side: str
    contracts: int
    mode: str
    broker: str
    reason: str
    execution_id: str
    dry_run: bool = True


class FuturesExecutionAdapter:
    """
    Institutional futures execution abstraction layer.

    PCNRASS SAFE:
    - DRY RUN ONLY
    - NO LIVE ORDER PLACEMENT
    - NO EXTERNAL BROKER CALLS
    - GOVERNANCE-FIRST VALIDATION
    """

    def __init__(
        self,
        *,
        broker_name: str = "FUTURES_ADAPTER",
        live_futures_enabled: bool = False,
    ) -> None:

        self.broker_name = broker_name
        self.live_futures_enabled = bool(live_futures_enabled)

        self.governor = FuturesGovernor(
            live_futures_enabled=self.live_futures_enabled
        )

    def execute_futures_order(
        self,
        *,
        symbol: str,
        side: str,
        contracts: int,
        mode: str,
        account_equity: float = 0.0,
    ) -> FuturesExecutionResult:

        governance: FuturesGovernanceDecision = self.governor.evaluate(
            symbol=symbol,
            mode=mode,
            requested_contracts=contracts,
            account_equity=account_equity,
        )

        if not governance.allowed:

            return FuturesExecutionResult(
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
            f"FUTSIM-"
            f"{str(symbol).upper()}-"
            f"{str(side).upper()}-"
            f"{int(contracts)}"
        )

        print(
            f"[FUTURES DRY RUN EXECUTION] "
            f"symbol={symbol} "
            f"side={side} "
            f"contracts={contracts} "
            f"mode={mode} "
            f"broker={self.broker_name}"
        )

        return FuturesExecutionResult(
            approved=True,
            symbol=str(symbol).upper(),
            side=str(side).upper(),
            contracts=int(contracts),
            mode=str(mode).lower(),
            broker=self.broker_name,
            reason="FUTURES_DRY_RUN_APPROVED",
            execution_id=execution_id,
            dry_run=True,
        )

    def result_to_dict(
        self,
        result: FuturesExecutionResult,
    ) -> Dict[str, Any]:

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
