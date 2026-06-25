from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from backend.execution.unified_execution_pipeline import (
    UnifiedExecutionPipeline,
    UnifiedExecutionPipelineError,
    UnifiedExecutionRequest,
)
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate
from engine.execution.execution_gate import ExecutionGate
from engine.execution_decision import GateResult, build_execution_decision


class CanonicalExecutionIntegrationError(RuntimeError):
    """Fail-closed exception for canonical execution integration."""


@dataclass(frozen=True)
class CanonicalExecutionResult:
    canonical_decision: dict[str, Any]
    execution_decision: dict[str, Any]
    execution_result: dict[str, Any]


class CanonicalExecutionIntegration:
    """Single canonical execution path that consolidates governance, risk gates, and routing."""

    def __init__(
        self,
        *,
        trade_gate: CSSUnifiedTradeGate | None = None,
        execution_gate: ExecutionGate | None = None,
        unified_pipeline: UnifiedExecutionPipeline | None = None,
    ) -> None:
        self.trade_gate = trade_gate or CSSUnifiedTradeGate()
        self.execution_gate = execution_gate or ExecutionGate()
        self.unified_pipeline = unified_pipeline or UnifiedExecutionPipeline()

    def execute(
        self,
        *,
        engine_run_id: str,
        canonical_decision: Mapping[str, Any],
        candidate: Mapping[str, Any],
        session: Mapping[str, Any],
        portfolio_state: Mapping[str, Any],
        engine_mode: str,
        execution_request: Mapping[str, Any],
        execution_context: Mapping[str, Any],
        mode: str = "TEST",
        override_used: bool = False,
        override_reason: str | None = None,
    ) -> CanonicalExecutionResult:
        if not engine_run_id:
            raise CanonicalExecutionIntegrationError("engine_run_id is required")
        if not isinstance(canonical_decision, Mapping):
            raise CanonicalExecutionIntegrationError("canonical_decision must be a mapping")
        if not isinstance(candidate, Mapping):
            raise CanonicalExecutionIntegrationError("candidate must be a mapping")
        if not isinstance(session, Mapping):
            raise CanonicalExecutionIntegrationError("session must be a mapping")
        if not isinstance(portfolio_state, Mapping):
            raise CanonicalExecutionIntegrationError("portfolio_state must be a mapping")
        if not isinstance(execution_request, Mapping):
            raise CanonicalExecutionIntegrationError("execution_request must be a mapping")
        if not isinstance(execution_context, Mapping):
            raise CanonicalExecutionIntegrationError("execution_context must be a mapping")

        trade_gate_decision = self.trade_gate.approve_trade(
            dict(candidate),
            dict(session),
            dict(portfolio_state),
            str(engine_mode),
        )

        gate_results: dict[str, GateResult] = {
            "css_unified_trade_gate": GateResult(
                gate_name="css_unified_trade_gate",
                decision="ALLOW" if trade_gate_decision.approved else "BLOCK",
                reason=str(trade_gate_decision.reason),
            )
        }

        if trade_gate_decision.approved:
            engine_gate_decision = self.execution_gate.evaluate_trade(**dict(execution_context))
            engine_gate_final = str((engine_gate_decision.get("decision") or {}).get("final") or "BLOCK").upper()
            if engine_gate_final not in {"ALLOW", "BLOCK"}:
                engine_gate_final = "BLOCK"
            gate_results["execution_gate"] = GateResult(
                gate_name="execution_gate",
                decision=engine_gate_final,
                reason=str(engine_gate_decision.get("reason") or "execution_gate_rejected"),
            )
        else:
            gate_results["execution_gate"] = GateResult(
                gate_name="execution_gate",
                decision="BLOCK",
                reason="blocked_by_governance",
            )

        execution_decision = build_execution_decision(
            engine_run_id=engine_run_id,
            gate_results=gate_results,
            mode=str(mode).upper(),
            override_used=bool(override_used),
            override_reason=override_reason,
        )

        execution_result: dict[str, Any]
        if execution_decision.can_execute:
            try:
                routed = self.unified_pipeline.execute(
                    UnifiedExecutionRequest(
                        asset_class=str(execution_request.get("asset_class") or ""),
                        symbol=str(execution_request.get("symbol") or ""),
                        side=str(execution_request.get("side") or ""),
                        quantity=int(execution_request.get("quantity") or 0),
                        mode=str(execution_request.get("mode") or ""),
                    )
                )
            except (UnifiedExecutionPipelineError, ValueError, TypeError) as exc:
                raise CanonicalExecutionIntegrationError(f"Unified execution rejected request: {exc}") from exc
            execution_result = routed.to_dict()
        else:
            execution_result = {
                "status": "blocked",
                "reason": execution_decision.primary_reason,
                "trade_id": "",
                "symbol": str(execution_request.get("symbol") or ""),
                "asset_class": str(execution_request.get("asset_class") or ""),
                "side": str(execution_request.get("side") or ""),
                "quantity": int(execution_request.get("quantity") or 0),
                "mode": str(execution_request.get("mode") or ""),
            }

        return CanonicalExecutionResult(
            canonical_decision=dict(canonical_decision),
            execution_decision=execution_decision.as_dict(),
            execution_result=execution_result,
        )
