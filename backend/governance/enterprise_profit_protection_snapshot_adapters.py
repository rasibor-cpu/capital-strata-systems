"""PPF-005 snapshot adapters for Enterprise Profit Protection inputs.

This module normalizes explicit PnL, portfolio, options, and futures snapshot
fields into PPF-001 request contracts. It does not fetch runtime state, compute
profit, compute maximum credible loss, reserve exposure, persist state, call
brokers, or grant execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping

from backend.governance.enterprise_profit_protection_contracts import (
    PPFMaturityTier,
    PPFRiskRequest,
)


SCHEMA_VERSION = "css.ppf005.enterprise_profit_protection_snapshot_adapters.v1"


class PPFSnapshotAdapterReasonCode(str, Enum):
    OK = "OK"
    ADVISORY_ONLY = "ADVISORY_ONLY"
    PNL_SNAPSHOT_USED = "PNL_SNAPSHOT_USED"
    PORTFOLIO_SNAPSHOT_USED = "PORTFOLIO_SNAPSHOT_USED"
    OPTIONS_SNAPSHOT_USED = "OPTIONS_SNAPSHOT_USED"
    FUTURES_SNAPSHOT_USED = "FUTURES_SNAPSHOT_USED"
    MISSING_PNL_SNAPSHOT = "MISSING_PNL_SNAPSHOT"
    MISSING_PORTFOLIO_SNAPSHOT = "MISSING_PORTFOLIO_SNAPSHOT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    NO_IMPLIED_BANKED_PROFIT = "NO_IMPLIED_BANKED_PROFIT"
    NO_IMPLIED_PRINCIPAL = "NO_IMPLIED_PRINCIPAL"
    REQUESTED_EXPOSURE_UNAVAILABLE = "REQUESTED_EXPOSURE_UNAVAILABLE"
    INPUT_NOT_FINITE = "INPUT_NOT_FINITE"
    INPUT_OUT_OF_RANGE = "INPUT_OUT_OF_RANGE"
    NEGATIVE_INPUT = "NEGATIVE_INPUT"
    FAIL_CLOSED = "FAIL_CLOSED"


@dataclass(frozen=True)
class EnterpriseProfitProtectionSnapshotResult:
    accepted: bool
    reason_codes: tuple[PPFSnapshotAdapterReasonCode, ...]
    risk_request: PPFRiskRequest | None
    requested_exposure: Decimal | None
    reservation_ready: bool
    source_fields: Mapping[str, str]
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "accepted": self.accepted,
            "reason_codes": [code.value for code in self.reason_codes],
            "risk_request": _risk_request_dict(self.risk_request),
            "requested_exposure": str(self.requested_exposure) if self.requested_exposure is not None else None,
            "reservation_ready": self.reservation_ready,
            "source_fields": dict(self.source_fields),
            "advisory_only": True,
            "execution_allowed": False,
        }


class EnterpriseProfitProtectionSnapshotAdapter:
    """Pure adapter from explicit enterprise snapshots to PPF risk requests."""

    def build_risk_request(
        self,
        *,
        request_id: str,
        maturity_tier: PPFMaturityTier | str | None,
        pnl_snapshot: Mapping[str, Any] | None,
        portfolio_snapshot: Mapping[str, Any] | None,
        options_snapshot: Mapping[str, Any] | None = None,
        futures_snapshot: Mapping[str, Any] | None = None,
        observed_at: str | None = None,
    ) -> EnterpriseProfitProtectionSnapshotResult:
        reasons: list[PPFSnapshotAdapterReasonCode] = [PPFSnapshotAdapterReasonCode.ADVISORY_ONLY]
        source_fields: dict[str, str] = {}
        pnl = _mapping(pnl_snapshot)
        portfolio = _mapping(portfolio_snapshot)
        options = _mapping(options_snapshot)
        futures = _mapping(futures_snapshot)

        if not pnl:
            reasons.append(PPFSnapshotAdapterReasonCode.MISSING_PNL_SNAPSHOT)
        else:
            reasons.append(PPFSnapshotAdapterReasonCode.PNL_SNAPSHOT_USED)
        if not portfolio:
            reasons.append(PPFSnapshotAdapterReasonCode.MISSING_PORTFOLIO_SNAPSHOT)
        else:
            reasons.append(PPFSnapshotAdapterReasonCode.PORTFOLIO_SNAPSHOT_USED)
        if options:
            reasons.append(PPFSnapshotAdapterReasonCode.OPTIONS_SNAPSHOT_USED)
        if futures:
            reasons.append(PPFSnapshotAdapterReasonCode.FUTURES_SNAPSHOT_USED)

        tier = _parse_tier(maturity_tier)
        if tier is None:
            reasons.append(PPFSnapshotAdapterReasonCode.MISSING_REQUIRED_FIELD)

        observed = observed_at or _text_from_sources(("observed_at", "timestamp", "updated_at"), pnl, portfolio)
        if not str(observed or "").strip():
            reasons.append(PPFSnapshotAdapterReasonCode.MISSING_REQUIRED_FIELD)

        values: dict[str, Decimal] = {}
        self._required_decimal(
            values,
            source_fields,
            reasons,
            "banked_net_profit",
            (pnl,),
            ("owner_approved_banked_net_profit", "approved_banked_net_profit", "banked_net_profit"),
            allow_negative=True,
            missing_reason=PPFSnapshotAdapterReasonCode.NO_IMPLIED_BANKED_PROFIT,
        )
        self._required_decimal(
            values,
            source_fields,
            reasons,
            "principal_capital",
            (portfolio,),
            ("owner_approved_principal_capital", "approved_principal_capital", "principal_capital"),
            allow_negative=False,
            missing_reason=PPFSnapshotAdapterReasonCode.NO_IMPLIED_PRINCIPAL,
        )
        self._required_decimal(
            values,
            source_fields,
            reasons,
            "current_drawdown_pct",
            (portfolio, pnl),
            ("current_drawdown_pct", "drawdown_pct"),
            ratio=True,
        )
        self._required_decimal(
            values,
            source_fields,
            reasons,
            "previous_drawdown_pct",
            (portfolio, pnl),
            ("previous_drawdown_pct",),
            ratio=True,
        )
        self._required_decimal(
            values,
            source_fields,
            reasons,
            "recent_loss_amount",
            (pnl, portfolio),
            ("recent_loss_amount",),
            allow_negative=False,
        )

        volatility = _aggregate_ratio(
            "volatility_score",
            (portfolio, options, futures),
            method="max",
            source_fields=source_fields,
            output_field="volatility_score",
        )
        liquidity = _aggregate_ratio(
            "liquidity_score",
            (portfolio, options, futures),
            method="min",
            source_fields=source_fields,
            output_field="liquidity_score",
        )
        confidence = _aggregate_ratio(
            "confidence_score",
            (portfolio, options, futures),
            method="min",
            source_fields=source_fields,
            output_field="confidence_score",
        )
        correlation = _aggregate_ratio(
            "correlation_score",
            (portfolio, options, futures),
            method="max",
            source_fields=source_fields,
            output_field="correlation_score",
        )
        margin = _aggregate_ratio(
            "margin_utilization",
            (portfolio, options, futures),
            method="max",
            source_fields=source_fields,
            output_field="margin_utilization",
        )
        aggregated = {
            "volatility_score": volatility,
            "liquidity_score": liquidity,
            "confidence_score": confidence,
            "correlation_score": correlation,
            "margin_utilization": margin,
        }
        for field_name, value in aggregated.items():
            if value is None:
                reasons.append(PPFSnapshotAdapterReasonCode.MISSING_REQUIRED_FIELD)
            elif value is _INVALID_DECIMAL:
                reasons.append(PPFSnapshotAdapterReasonCode.INPUT_NOT_FINITE)
            elif not Decimal("0") <= value <= Decimal("1"):
                reasons.append(PPFSnapshotAdapterReasonCode.INPUT_OUT_OF_RANGE)
            else:
                values[field_name] = value

        requested_exposure = _explicit_requested_exposure(
            portfolio,
            options,
            futures,
            source_fields=source_fields,
        )
        if requested_exposure is None:
            reasons.append(PPFSnapshotAdapterReasonCode.REQUESTED_EXPOSURE_UNAVAILABLE)

        errors = _error_reasons(reasons)
        if errors or tier is None:
            return EnterpriseProfitProtectionSnapshotResult(
                accepted=False,
                reason_codes=_dedupe((*reasons, PPFSnapshotAdapterReasonCode.FAIL_CLOSED)),
                risk_request=None,
                requested_exposure=requested_exposure,
                reservation_ready=False,
                source_fields=source_fields,
            )

        request = PPFRiskRequest(
            request_id=str(request_id or "").strip(),
            maturity_tier=tier,
            banked_net_profit=values["banked_net_profit"],
            principal_capital=values["principal_capital"],
            current_drawdown_pct=values["current_drawdown_pct"],
            previous_drawdown_pct=values["previous_drawdown_pct"],
            recent_loss_amount=values["recent_loss_amount"],
            volatility_score=values["volatility_score"],
            liquidity_score=values["liquidity_score"],
            confidence_score=values["confidence_score"],
            correlation_score=values["correlation_score"],
            margin_utilization=values["margin_utilization"],
            observed_at=str(observed),
            source="PPF005_SNAPSHOT_ADAPTER",
        )
        return EnterpriseProfitProtectionSnapshotResult(
            accepted=True,
            reason_codes=_dedupe((*reasons, PPFSnapshotAdapterReasonCode.OK)),
            risk_request=request,
            requested_exposure=requested_exposure,
            reservation_ready=requested_exposure is not None,
            source_fields=source_fields,
        )

    @staticmethod
    def _required_decimal(
        values: dict[str, Decimal],
        source_fields: dict[str, str],
        reasons: list[PPFSnapshotAdapterReasonCode],
        output_field: str,
        sources: tuple[Mapping[str, Any], ...],
        keys: tuple[str, ...],
        *,
        allow_negative: bool = True,
        ratio: bool = False,
        missing_reason: PPFSnapshotAdapterReasonCode = PPFSnapshotAdapterReasonCode.MISSING_REQUIRED_FIELD,
    ) -> None:
        found = _decimal_from_sources(keys, sources, source_fields=source_fields, output_field=output_field)
        if found is None:
            reasons.append(missing_reason)
            return
        if found is _INVALID_DECIMAL:
            reasons.append(PPFSnapshotAdapterReasonCode.INPUT_NOT_FINITE)
            return
        if not allow_negative and found < Decimal("0"):
            reasons.append(PPFSnapshotAdapterReasonCode.NEGATIVE_INPUT)
            return
        if ratio and not Decimal("0") <= found <= Decimal("1"):
            reasons.append(PPFSnapshotAdapterReasonCode.INPUT_OUT_OF_RANGE)
            return
        values[output_field] = found


_INVALID_DECIMAL = object()


def _mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _parse_tier(value: PPFMaturityTier | str | None) -> PPFMaturityTier | None:
    if isinstance(value, PPFMaturityTier):
        return value
    try:
        return PPFMaturityTier(str(value or "").strip().upper())
    except ValueError:
        return None


def _text_from_sources(keys: tuple[str, ...], *sources: Mapping[str, Any]) -> str | None:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def _decimal_from_sources(
    keys: tuple[str, ...],
    sources: tuple[Mapping[str, Any], ...],
    *,
    source_fields: dict[str, str],
    output_field: str,
) -> Decimal | object | None:
    for source in sources:
        for key in keys:
            if key in source:
                value = _decimal(source.get(key))
                if value is not None:
                    source_fields[output_field] = key
                    return value
                return _INVALID_DECIMAL
    return None


def _aggregate_ratio(
    key: str,
    sources: tuple[Mapping[str, Any], ...],
    *,
    method: str,
    source_fields: dict[str, str],
    output_field: str,
) -> Decimal | object | None:
    values: list[Decimal] = []
    field_names: list[str] = []
    for source in sources:
        if key not in source:
            continue
        value = _decimal(source.get(key))
        if value is None:
            return _INVALID_DECIMAL
        if not Decimal("0") <= value <= Decimal("1"):
            return value
        values.append(value)
        field_names.append(key)
    if not values:
        return None
    source_fields[output_field] = ",".join(field_names)
    return max(values) if method == "max" else min(values)


def _explicit_requested_exposure(
    *sources: Mapping[str, Any],
    source_fields: dict[str, str],
) -> Decimal | None:
    values: list[Decimal] = []
    for source in sources:
        found = _decimal_from_sources(
            ("maximum_credible_loss", "requested_exposure", "max_credible_loss"),
            (source,),
            source_fields=source_fields,
            output_field="requested_exposure",
        )
        if found is None:
            continue
        if found is _INVALID_DECIMAL or found <= Decimal("0"):
            continue
        values.append(found)
    if not values:
        return None
    return max(values)


def _decimal(value: Any) -> Decimal | None:
    text = repr(value) if isinstance(value, float) else str(value)
    try:
        converted = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not converted.is_finite():
        return None
    return converted


def _error_reasons(
    reasons: list[PPFSnapshotAdapterReasonCode],
) -> tuple[PPFSnapshotAdapterReasonCode, ...]:
    blocking = {
        PPFSnapshotAdapterReasonCode.MISSING_PNL_SNAPSHOT,
        PPFSnapshotAdapterReasonCode.MISSING_PORTFOLIO_SNAPSHOT,
        PPFSnapshotAdapterReasonCode.MISSING_REQUIRED_FIELD,
        PPFSnapshotAdapterReasonCode.NO_IMPLIED_BANKED_PROFIT,
        PPFSnapshotAdapterReasonCode.NO_IMPLIED_PRINCIPAL,
        PPFSnapshotAdapterReasonCode.INPUT_NOT_FINITE,
        PPFSnapshotAdapterReasonCode.INPUT_OUT_OF_RANGE,
        PPFSnapshotAdapterReasonCode.NEGATIVE_INPUT,
    }
    return tuple(reason for reason in _dedupe(reasons) if reason in blocking)


def _dedupe(
    reasons: tuple[PPFSnapshotAdapterReasonCode, ...] | list[PPFSnapshotAdapterReasonCode],
) -> tuple[PPFSnapshotAdapterReasonCode, ...]:
    result: list[PPFSnapshotAdapterReasonCode] = []
    for reason in reasons:
        if reason not in result:
            result.append(reason)
    return tuple(result)


def _risk_request_dict(request: PPFRiskRequest | None) -> dict[str, Any] | None:
    if request is None:
        return None
    return {
        "request_id": request.request_id,
        "maturity_tier": request.maturity_tier.value
        if isinstance(request.maturity_tier, PPFMaturityTier)
        else request.maturity_tier,
        "banked_net_profit": str(request.banked_net_profit),
        "principal_capital": str(request.principal_capital),
        "current_drawdown_pct": str(request.current_drawdown_pct),
        "previous_drawdown_pct": str(request.previous_drawdown_pct),
        "recent_loss_amount": str(request.recent_loss_amount),
        "volatility_score": str(request.volatility_score),
        "liquidity_score": str(request.liquidity_score),
        "confidence_score": str(request.confidence_score),
        "correlation_score": str(request.correlation_score),
        "margin_utilization": str(request.margin_utilization),
        "observed_at": request.observed_at,
        "source": request.source,
    }


__all__ = [
    "SCHEMA_VERSION",
    "EnterpriseProfitProtectionSnapshotAdapter",
    "EnterpriseProfitProtectionSnapshotResult",
    "PPFSnapshotAdapterReasonCode",
]
