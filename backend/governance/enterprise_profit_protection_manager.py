"""PPF-001 Adaptive Enterprise Profit Protection manager.

This module is advisory-only and side-effect free. It does not reserve capital,
write state, call brokers, modify readiness, or grant execution authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Mapping

from backend.governance.enterprise_profit_protection_contracts import (
    CONSTITUTIONAL_TIER_CEILINGS,
    SCHEMA_VERSION,
    EnterpriseProfitProtectionPolicy,
    PPFEnforcementStatus,
    PPFMaturityTier,
    PPFPosture,
    PPFReasonCode,
    PPFRiskDecision,
    PPFRiskRequest,
    ProfitProtectionState,
    NormalizedEnterpriseRiskSignals,
)
from backend.governance.enterprise_risk_signal_normalizer import (
    EnterpriseRiskSignalNormalizer,
)


REQUIRED_NUMERIC_FIELDS = (
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
)

ADAPTIVE_FIELDS = (
    "current_drawdown_pct",
    "previous_drawdown_pct",
    "volatility_score",
    "liquidity_score",
    "confidence_score",
    "correlation_score",
    "margin_utilization",
)

MONEY_FIELDS = {
    "banked_net_profit",
    "principal_capital",
    "recent_loss_amount",
}

MULTIPLIER_KEYS = (
    "drawdown_adjustment",
    "volatility_adjustment",
    "liquidity_adjustment",
    "confidence_adjustment",
    "correlation_adjustment",
    "margin_adjustment",
)


class EnterpriseProfitProtectionManager:
    """Pure PPF-001 governance calculator."""

    def __init__(
        self,
        policy: EnterpriseProfitProtectionPolicy | None = None,
        signal_normalizer: EnterpriseRiskSignalNormalizer | None = None,
    ) -> None:
        self.policy = policy or EnterpriseProfitProtectionPolicy()
        self.signal_normalizer = signal_normalizer or EnterpriseRiskSignalNormalizer()

    def evaluate(
        self,
        request: PPFRiskRequest,
        *,
        policy: EnterpriseProfitProtectionPolicy | None = None,
        now: datetime | None = None,
    ) -> PPFRiskDecision:
        active_policy = policy or self.policy
        reasons: list[PPFReasonCode] = [PPFReasonCode.ADVISORY_ONLY]

        tier = self._parse_tier(request.maturity_tier)
        if tier is None:
            return self._fail_closed(
                request=request,
                policy=active_policy,
                tier=PPFMaturityTier.STARTUP,
                reasons=(*reasons, PPFReasonCode.MISSING_REQUIRED_DATA),
            )

        validated = self._validate_request(request, active_policy, now=now)
        if validated["errors"]:
            return self._fail_closed(
                request=request,
                policy=active_policy,
                tier=tier,
                reasons=(*reasons, *validated["errors"]),
            )

        values: dict[str, Decimal] = validated["values"]
        ceiling_result = self._effective_ceiling(active_policy, tier)
        if ceiling_result["errors"]:
            return self._fail_closed(
                request=request,
                policy=active_policy,
                tier=tier,
                reasons=(*reasons, *ceiling_result["errors"]),
            )
        if ceiling_result["clamped"]:
            reasons.append(PPFReasonCode.CEILING_CLAMPED_TO_CONSTITUTIONAL)

        banked_profit = values["banked_net_profit"]
        principal = values["principal_capital"]
        constitutional_ceiling = CONSTITUTIONAL_TIER_CEILINGS[tier]
        effective_ceiling = ceiling_result["ceiling"]

        if banked_profit <= Decimal("0"):
            reasons.extend(
                (
                    PPFReasonCode.PRINCIPAL_EXCLUDED,
                    PPFReasonCode.ZERO_OR_NEGATIVE_BANKED_PROFIT,
                )
            )
            state = self._state(
                tier=tier,
                banked_net_profit=banked_profit,
                principal_capital=principal,
                constitutional_ceiling=constitutional_ceiling,
                effective_ceiling=effective_ceiling,
                base_budget=Decimal("0.00"),
                adjusted_budget=Decimal("0.00"),
                multipliers=self._zero_multipliers(active_policy),
                reasons=tuple(_dedupe(reasons)),
                posture=PPFPosture.ZERO_BUDGET,
            )
            return PPFRiskDecision(
                request_id=request.request_id,
                enforcement_status=PPFEnforcementStatus.ADVISORY_BLOCKED,
                posture=PPFPosture.ZERO_BUDGET,
                maturity_tier=tier,
                effective_ceiling=effective_ceiling,
                base_budget=state.base_budget,
                adjusted_budget=state.adjusted_budget,
                multipliers=state.multipliers,
                reason_codes=state.reason_codes,
                state=state,
            )

        base_budget = self._money(banked_profit * effective_ceiling, active_policy)
        signals = self.signal_normalizer.normalize(values, active_policy)
        signal_errors = self._validate_normalized_signals(signals)
        if signal_errors:
            return self._fail_closed(
                request=request,
                policy=active_policy,
                tier=tier,
                reasons=(*reasons, *signal_errors),
            )
        multipliers = signals.multipliers()
        adjusted = base_budget
        for key in MULTIPLIER_KEYS:
            adjusted *= multipliers[key]
        adjusted_budget = min(self._money(adjusted, active_policy), base_budget)

        reasons.append(PPFReasonCode.PRINCIPAL_EXCLUDED)
        if adjusted_budget < base_budget:
            reasons.append(PPFReasonCode.BUDGET_REDUCED_BY_ADAPTIVE_MULTIPLIERS)
        reasons.append(PPFReasonCode.FINAL_BUDGET_CAPPED_BY_BASE_CEILING)
        if signals.recent_loss_reduces_risk:
            reasons.append(PPFReasonCode.RECENT_LOSS_REDUCED_RISK)
        if signals.worsening_drawdown_reduces_risk:
            reasons.append(PPFReasonCode.WORSENING_DRAWDOWN_REDUCED_RISK)
        reasons.append(PPFReasonCode.OK)

        posture = (
            PPFPosture.REDUCED_BY_ADAPTIVE_RISK
            if adjusted_budget < base_budget
            else PPFPosture.PROFIT_PROTECTED
        )
        state = self._state(
            tier=tier,
            banked_net_profit=banked_profit,
            principal_capital=principal,
            constitutional_ceiling=constitutional_ceiling,
            effective_ceiling=effective_ceiling,
            base_budget=base_budget,
            adjusted_budget=adjusted_budget,
            multipliers=multipliers,
            reasons=tuple(_dedupe(reasons)),
            posture=posture,
        )
        return PPFRiskDecision(
            request_id=request.request_id,
            enforcement_status=PPFEnforcementStatus.ADVISORY_APPROVED
            if adjusted_budget > Decimal("0")
            else PPFEnforcementStatus.ADVISORY_BLOCKED,
            posture=posture,
            maturity_tier=tier,
            effective_ceiling=effective_ceiling,
            base_budget=base_budget,
            adjusted_budget=adjusted_budget,
            multipliers=multipliers,
            reason_codes=state.reason_codes,
            state=state,
        )

    def _validate_request(
        self,
        request: PPFRiskRequest,
        policy: EnterpriseProfitProtectionPolicy,
        *,
        now: datetime | None,
    ) -> dict[str, Any]:
        errors: list[PPFReasonCode] = []
        values: dict[str, Decimal] = {}
        for field_name in REQUIRED_NUMERIC_FIELDS:
            raw = getattr(request, field_name)
            if raw is None:
                errors.append(PPFReasonCode.MISSING_REQUIRED_DATA)
                continue
            converted = _decimal(raw)
            if converted is None:
                errors.append(PPFReasonCode.INPUT_NOT_FINITE)
                continue
            if field_name != "banked_net_profit" and converted < Decimal("0"):
                errors.append(PPFReasonCode.NEGATIVE_INPUT)
                continue
            if field_name in ADAPTIVE_FIELDS and not Decimal("0") <= converted <= Decimal("1"):
                errors.append(PPFReasonCode.INPUT_OUT_OF_RANGE)
                continue
            values[field_name] = converted

        observed_at = _parse_time(request.observed_at)
        if observed_at is None:
            errors.append(PPFReasonCode.MISSING_REQUIRED_DATA)
        else:
            now_dt = now or datetime.now(timezone.utc)
            if now_dt.tzinfo is None:
                now_dt = now_dt.replace(tzinfo=timezone.utc)
            age = (now_dt.astimezone(timezone.utc) - observed_at).total_seconds()
            if age < 0 or age > int(policy.max_input_age_seconds):
                errors.append(PPFReasonCode.INPUT_STALE)

        return {"values": values, "errors": tuple(_dedupe(errors))}

    def _effective_ceiling(
        self,
        policy: EnterpriseProfitProtectionPolicy,
        tier: PPFMaturityTier,
    ) -> dict[str, Any]:
        errors: list[PPFReasonCode] = []
        constitutional = CONSTITUTIONAL_TIER_CEILINGS[tier]
        raw = _lookup_tier(policy.tier_ceilings, tier)
        if raw is None:
            raw = constitutional
        configured = _decimal(raw)
        if configured is None:
            errors.append(PPFReasonCode.POLICY_INVALID)
            return {"ceiling": Decimal("0"), "clamped": False, "errors": tuple(errors)}
        if not Decimal("0") <= configured <= Decimal("1"):
            errors.append(PPFReasonCode.POLICY_INVALID)
            return {"ceiling": Decimal("0"), "clamped": False, "errors": tuple(errors)}
        ceiling = min(configured, constitutional)
        return {
            "ceiling": ceiling,
            "clamped": configured > constitutional,
            "errors": tuple(errors),
        }

    def _zero_multipliers(
        self,
        policy: EnterpriseProfitProtectionPolicy,
    ) -> dict[str, Decimal]:
        zero = Decimal("0").quantize(policy.multiplier_quantum)
        return {key: zero for key in MULTIPLIER_KEYS}

    @staticmethod
    def _validate_normalized_signals(
        signals: NormalizedEnterpriseRiskSignals,
    ) -> tuple[PPFReasonCode, ...]:
        errors: list[PPFReasonCode] = []
        multipliers = signals.multipliers()
        for key in MULTIPLIER_KEYS:
            value = multipliers.get(key)
            if value is None or not value.is_finite():
                errors.append(PPFReasonCode.INPUT_NOT_FINITE)
            elif not Decimal("0") <= value <= Decimal("1"):
                errors.append(PPFReasonCode.INPUT_OUT_OF_RANGE)
        return _dedupe(errors)

    def _fail_closed(
        self,
        *,
        request: PPFRiskRequest,
        policy: EnterpriseProfitProtectionPolicy,
        tier: PPFMaturityTier,
        reasons: tuple[PPFReasonCode, ...],
    ) -> PPFRiskDecision:
        constitutional = CONSTITUTIONAL_TIER_CEILINGS[tier]
        state = self._state(
            tier=tier,
            banked_net_profit=Decimal("0.00"),
            principal_capital=Decimal("0.00"),
            constitutional_ceiling=constitutional,
            effective_ceiling=Decimal("0"),
            base_budget=Decimal("0.00"),
            adjusted_budget=Decimal("0.00"),
            multipliers=self._zero_multipliers(policy),
            reasons=tuple(_dedupe((*reasons, PPFReasonCode.PRINCIPAL_EXCLUDED))),
            posture=PPFPosture.FAIL_CLOSED,
        )
        return PPFRiskDecision(
            request_id=request.request_id,
            enforcement_status=PPFEnforcementStatus.FAIL_CLOSED,
            posture=PPFPosture.FAIL_CLOSED,
            maturity_tier=tier,
            effective_ceiling=Decimal("0"),
            base_budget=Decimal("0.00"),
            adjusted_budget=Decimal("0.00"),
            multipliers=state.multipliers,
            reason_codes=state.reason_codes,
            state=state,
        )

    def _state(
        self,
        *,
        tier: PPFMaturityTier,
        banked_net_profit: Decimal,
        principal_capital: Decimal,
        constitutional_ceiling: Decimal,
        effective_ceiling: Decimal,
        base_budget: Decimal,
        adjusted_budget: Decimal,
        multipliers: Mapping[str, Decimal],
        reasons: tuple[PPFReasonCode, ...],
        posture: PPFPosture,
    ) -> ProfitProtectionState:
        return ProfitProtectionState(
            schema_version=SCHEMA_VERSION,
            maturity_tier=tier,
            banked_net_profit=banked_net_profit,
            principal_capital=principal_capital,
            constitutional_ceiling=constitutional_ceiling,
            effective_ceiling=effective_ceiling,
            base_budget=base_budget,
            adjusted_budget=adjusted_budget,
            multipliers=dict(multipliers),
            reason_codes=reasons,
            posture=posture,
        )

    @staticmethod
    def _parse_tier(value: PPFMaturityTier | str | None) -> PPFMaturityTier | None:
        if isinstance(value, PPFMaturityTier):
            return value
        try:
            return PPFMaturityTier(str(value or "").strip().upper())
        except ValueError:
            return None

    @staticmethod
    def _money(value: Decimal, policy: EnterpriseProfitProtectionPolicy) -> Decimal:
        return value.quantize(policy.money_quantum, rounding=ROUND_DOWN)


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, float):
        text = repr(value)
    else:
        text = str(value)
    try:
        converted = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not converted.is_finite():
        return None
    return converted


def _lookup_tier(
    ceilings: Mapping[PPFMaturityTier | str, Decimal | str | int | float],
    tier: PPFMaturityTier,
) -> Any:
    return ceilings.get(tier, ceilings.get(tier.value, ceilings.get(tier.value.lower())))


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _dedupe(reasons: tuple[PPFReasonCode, ...] | list[PPFReasonCode]) -> tuple[PPFReasonCode, ...]:
    result: list[PPFReasonCode] = []
    for reason in reasons:
        if reason not in result:
            result.append(reason)
    return tuple(result)


__all__ = ["EnterpriseProfitProtectionManager"]
