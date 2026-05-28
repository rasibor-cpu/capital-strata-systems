from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from backend.app.futures.futures_execution_adapter import (
    FuturesExecutionAdapter,
)

from backend.app.options.options_execution_adapter import (
    OptionsExecutionAdapter,
)

from backend.app.audit.execution_audit_ledger import (
    ExecutionAuditLedger,
)


@dataclass(frozen=True)
class CrossAssetExecutionDecision:
    approved: bool
    asset_class: str
    symbol: str
    broker: str
    mode: str
    reason: str
    execution_id: str
    dry_run: bool = True


class CrossAssetExecutionOrchestrator:
    """
    Institutional cross-asset orchestration layer.

    PCNRASS SAFE:
    - DRY RUN ONLY for futures/options
    - NO LIVE FUTURES EXECUTION
    - NO LIVE OPTIONS EXECUTION
    - GOVERNANCE-FIRST
    - AUDIT-RECORDED DECISIONS
    """

    def __init__(self) -> None:

        self.futures_adapter = FuturesExecutionAdapter(
            live_futures_enabled=False
        )

        self.options_adapter = OptionsExecutionAdapter(
            live_options_enabled=False
        )

        self.audit_ledger = ExecutionAuditLedger()

    def _audit_decision(
        self,
        decision: CrossAssetExecutionDecision,
        *,
        metadata: Dict[str, Any] | None = None,
    ) -> CrossAssetExecutionDecision:

        self.audit_ledger.record_execution(
            asset_class=decision.asset_class,
            symbol=decision.symbol,
            mode=decision.mode,
            broker=decision.broker,
            approved=decision.approved,
            reason=decision.reason,
            execution_id=decision.execution_id,
            dry_run=decision.dry_run,
            metadata=metadata or {},
        )

        return decision

    def execute(
        self,
        *,
        asset_class: str,
        symbol: str,
        side: str,
        quantity: int,
        mode: str,
        account_equity: float = 0.0,
    ) -> CrossAssetExecutionDecision:

        normalized_asset = str(asset_class or "").strip().upper()

        metadata = {
            "requested_side": str(side).upper(),
            "requested_quantity": int(quantity),
            "account_equity": float(account_equity or 0.0),
        }

        # -----------------------------------------------------
        # FUTURES
        # -----------------------------------------------------
        if normalized_asset == "FUTURES":

            result = self.futures_adapter.execute_futures_order(
                symbol=symbol,
                side=side,
                contracts=quantity,
                mode=mode,
                account_equity=account_equity,
            )

            return self._audit_decision(
                CrossAssetExecutionDecision(
                    approved=result.approved,
                    asset_class=normalized_asset,
                    symbol=result.symbol,
                    broker=result.broker,
                    mode=result.mode,
                    reason=result.reason,
                    execution_id=result.execution_id,
                    dry_run=result.dry_run,
                ),
                metadata=metadata,
            )

        # -----------------------------------------------------
        # OPTIONS
        # -----------------------------------------------------
        if normalized_asset == "OPTIONS":

            result = self.options_adapter.execute_options_order(
                symbol=symbol,
                side=side,
                contracts=quantity,
                mode=mode,
                account_equity=account_equity,
            )

            return self._audit_decision(
                CrossAssetExecutionDecision(
                    approved=result.approved,
                    asset_class=normalized_asset,
                    symbol=result.symbol,
                    broker=result.broker,
                    mode=result.mode,
                    reason=result.reason,
                    execution_id=result.execution_id,
                    dry_run=result.dry_run,
                ),
                metadata=metadata,
            )

        # -----------------------------------------------------
        # FX + CRYPTO PLACEHOLDER
        # -----------------------------------------------------
        if normalized_asset in {"FX", "CRYPTO"}:

            return self._audit_decision(
                CrossAssetExecutionDecision(
                    approved=True,
                    asset_class=normalized_asset,
                    symbol=str(symbol).upper(),
                    broker="LIVE_ROUTE_RESOLVER",
                    mode=str(mode).lower(),
                    reason="LIVE_ROUTE_RESOLUTION_REQUIRED",
                    execution_id="ROUTE_ONLY",
                    dry_run=True,
                ),
                metadata=metadata,
            )

        # -----------------------------------------------------
        # UNKNOWN
        # -----------------------------------------------------
        return self._audit_decision(
            CrossAssetExecutionDecision(
                approved=False,
                asset_class=normalized_asset,
                symbol=str(symbol).upper(),
                broker="NO_ROUTE",
                mode=str(mode).lower(),
                reason="UNKNOWN_ASSET_CLASS",
                execution_id="BLOCKED",
                dry_run=True,
            ),
            metadata=metadata,
        )

    def decision_to_dict(
        self,
        decision: CrossAssetExecutionDecision,
    ) -> Dict[str, Any]:

        return {
            "approved": decision.approved,
            "asset_class": decision.asset_class,
            "symbol": decision.symbol,
            "broker": decision.broker,
            "mode": decision.mode,
            "reason": decision.reason,
            "execution_id": decision.execution_id,
            "dry_run": decision.dry_run,
        }

    def audit_records(self) -> list[Dict[str, Any]]:
        return self.audit_ledger.export_records()
