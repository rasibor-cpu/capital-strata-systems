from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from backend.execution.unified_execution_pipeline import (
    UnifiedExecutionPipeline,
    UnifiedExecutionPipelineError,
    UnifiedExecutionRequest,
)
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate
from backend.governance.enterprise_execution_gateway import (
    EnterpriseExecutionGateway,
    EnterpriseExecutionGatewayReasonCode,
    EnterpriseExecutionGatewayStatus,
    EnterpriseExecutionRequest,
)
from backend.governance.enterprise_profit_protection_contracts import PPFRiskRequest
from engine.execution.execution_gate import ExecutionGate
from engine.execution_decision import GateResult, build_execution_decision


class CanonicalExecutionIntegrationError(RuntimeError):
    """Fail-closed exception for canonical execution integration."""


@dataclass(frozen=True)
class CanonicalExecutionResult:
    canonical_decision: dict[str, Any]
    execution_decision: dict[str, Any]
    execution_result: dict[str, Any]
    profit_protection_governance: dict[str, Any] | None = None


class CanonicalExecutionIntegration:
    """Single canonical execution path that consolidates governance, risk gates, and routing."""

    def __init__(
        self,
        *,
        trade_gate: CSSUnifiedTradeGate | None = None,
        execution_gate: ExecutionGate | None = None,
        unified_pipeline: UnifiedExecutionPipeline | None = None,
        enterprise_execution_gateway: EnterpriseExecutionGateway | None = None,
    ) -> None:
        self.trade_gate = trade_gate or CSSUnifiedTradeGate()
        self.execution_gate = execution_gate or ExecutionGate()
        self.unified_pipeline = unified_pipeline or UnifiedExecutionPipeline()
        self._enterprise_execution_gateway = enterprise_execution_gateway

    @property
    def enterprise_execution_gateway(self) -> EnterpriseExecutionGateway:
        """Lazily compose the advisory PPF gateway for backward-compatible callers.

        Production integrations should inject a process-owned gateway so registry
        lifetime and future persistence are explicit. The default remains private
        to this integration instance to preserve test isolation and existing
        advisory-only behavior.
        """
        if self._enterprise_execution_gateway is None:
            self._enterprise_execution_gateway = EnterpriseExecutionGateway()
        return self._enterprise_execution_gateway

    @enterprise_execution_gateway.setter
    def enterprise_execution_gateway(self, value: EnterpriseExecutionGateway) -> None:
        self._enterprise_execution_gateway = value

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

        profit_protection_governance = self._evaluate_profit_protection_governance(
            engine_run_id=engine_run_id,
            canonical_decision=canonical_decision,
            candidate=candidate,
            execution_request=execution_request,
            execution_context=execution_context,
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
            profit_protection_governance=profit_protection_governance,
        )

    def _evaluate_profit_protection_governance(
        self,
        *,
        engine_run_id: str,
        canonical_decision: Mapping[str, Any],
        candidate: Mapping[str, Any],
        execution_request: Mapping[str, Any],
        execution_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        try:
            risk_request = _extract_ppf_risk_request(
                execution_request,
                execution_context,
                canonical_decision,
                candidate,
            )
            requested_exposure = _extract_decimal(
                "requested_exposure",
                "maximum_credible_loss",
                "max_credible_loss",
                sources=(execution_request, execution_context, canonical_decision, candidate),
            )
            reservation_id = _extract_text(
                "ppf_reservation_id",
                "reservation_id",
                sources=(execution_request, execution_context, canonical_decision, candidate),
            )
            module = _extract_text(
                "ppf_module",
                "module",
                sources=(execution_request, execution_context, canonical_decision, candidate),
            )
            owner_id = _extract_text(
                "ppf_owner_id",
                "owner_id",
                "engine_id",
                sources=(execution_request, execution_context, canonical_decision, candidate),
            )

            if risk_request is None:
                return _advisory_fail_closed(
                    reason_codes=(
                        EnterpriseExecutionGatewayReasonCode.INVALID_RISK_REQUEST,
                    ),
                    requested_exposure=requested_exposure,
                    reservation_id=reservation_id,
                )

            if requested_exposure is None or not reservation_id or not module or not owner_id:
                return _advisory_fail_closed(
                    reason_codes=(
                        EnterpriseExecutionGatewayReasonCode.INVALID_EXECUTION_REQUEST,
                    ),
                    requested_exposure=requested_exposure,
                    reservation_id=reservation_id,
                )

            advisory_request = EnterpriseExecutionRequest(
                request_id=f"{engine_run_id}:ppf-004",
                reservation_id=reservation_id,
                module=module,
                owner_id=owner_id,
                requested_exposure=requested_exposure,
                risk_request=risk_request,
                metadata={
                    "engine_run_id": engine_run_id,
                    "integration_phase": "PPF-004",
                },
            )
            decision = self.enterprise_execution_gateway.request_exposure_reservation(advisory_request)
            return _advisory_from_gateway_decision(
                decision,
                requested_exposure=requested_exposure,
                reservation_id=reservation_id,
            )
        except Exception as exc:
            return _advisory_fail_closed(
                reason_codes=(
                    EnterpriseExecutionGatewayReasonCode.INVALID_RISK_REQUEST,
                ),
                error=str(exc),
            )


_PPF_RISK_REQUEST_FIELDS = (
    "request_id",
    "maturity_tier",
    "banked_net_profit",
    "principal_capital",
    "current_drawdown_pct",
    "previous_drawdown_pct",
    "recent_loss_amount",
    "volatility_score",
    "liquidity_score",
    "confidence_score",
    "correlation_score",
    "margin_utilization",
    "observed_at",
)


def _extract_ppf_risk_request(*sources: Mapping[str, Any]) -> PPFRiskRequest | None:
    payload = _extract_object(
        "ppf_risk_request",
        "profit_protection_risk_request",
        sources=sources,
    )
    if isinstance(payload, PPFRiskRequest):
        return payload
    if not isinstance(payload, Mapping):
        return None
    if any(field not in payload for field in _PPF_RISK_REQUEST_FIELDS):
        return None
    try:
        return PPFRiskRequest(**{field: payload.get(field) for field in _PPF_RISK_REQUEST_FIELDS})
    except TypeError:
        return None


def _extract_object(
    *keys: str,
    sources: tuple[Mapping[str, Any], ...],
) -> Any:
    for source in sources:
        for key in keys:
            if key in source and source.get(key) is not None:
                return source.get(key)
    return None


def _extract_text(
    *keys: str,
    sources: tuple[Mapping[str, Any], ...],
) -> str | None:
    value = _extract_object(*keys, sources=sources)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _extract_decimal(
    *keys: str,
    sources: tuple[Mapping[str, Any], ...],
) -> Decimal | None:
    value = _extract_object(*keys, sources=sources)
    if value is None:
        return None
    text = repr(value) if isinstance(value, float) else str(value)
    try:
        converted = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not converted.is_finite() or converted <= Decimal("0"):
        return None
    return converted


def _advisory_from_gateway_decision(
    decision: Any,
    *,
    requested_exposure: Decimal,
    reservation_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": "css.ppf004.canonical_execution_advisory.v1",
        "status": str(decision.status.value),
        "accepted": bool(decision.accepted),
        "reason_codes": list(decision.as_dict().get("reason_codes", [])),
        "upstream_reason_codes": list(decision.as_dict().get("upstream_reason_codes", [])),
        "requested_exposure": str(requested_exposure),
        "reservation_id": reservation_id,
        "gateway_decision": decision.as_dict(),
        "advisory_only": True,
        "execution_allowed": False,
    }


def _advisory_fail_closed(
    *,
    reason_codes: tuple[EnterpriseExecutionGatewayReasonCode, ...],
    requested_exposure: Decimal | None = None,
    reservation_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "css.ppf004.canonical_execution_advisory.v1",
        "status": EnterpriseExecutionGatewayStatus.FAIL_CLOSED.value,
        "accepted": False,
        "reason_codes": [
            EnterpriseExecutionGatewayReasonCode.ADVISORY_ONLY.value,
            *[reason.value for reason in _dedupe_gateway_reasons(reason_codes)],
        ],
        "upstream_reason_codes": [],
        "requested_exposure": str(requested_exposure) if requested_exposure is not None else None,
        "reservation_id": reservation_id,
        "gateway_decision": None,
        "advisory_only": True,
        "execution_allowed": False,
    }
    if error:
        payload["error"] = error
    return payload


def _dedupe_gateway_reasons(
    reasons: tuple[EnterpriseExecutionGatewayReasonCode, ...],
) -> tuple[EnterpriseExecutionGatewayReasonCode, ...]:
    result: list[EnterpriseExecutionGatewayReasonCode] = []
    for reason in reasons:
        if reason not in result:
            result.append(reason)
    return tuple(result)
