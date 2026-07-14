from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from backend.options.options_income_strategy_domain import (
    CASH_SECURED_PUT,
    COVERED_CALL,
    build_cash_secured_put,
    build_covered_call,
)
from backend.trading.option_contract import CanonicalOptionContract


VALID_PAPER_MODES = {"paper", "dry_run", "sim", "demo"}


@dataclass(frozen=True)
class IncomeScannerConfig:
    min_dte: int = 7
    max_dte: int = 45
    preferred_dte: int = 30
    covered_call_min_delta: float = 0.15
    covered_call_max_delta: float = 0.45
    covered_call_target_delta: float = 0.30
    cash_secured_put_min_delta: float = 0.15
    cash_secured_put_max_delta: float = 0.45
    cash_secured_put_target_delta: float = 0.30
    min_bid: float = 0.25
    max_spread_pct: float = 0.20
    min_volume: int = 10
    min_open_interest: int = 50
    supported_multipliers: tuple[int, ...] = (100,)


@dataclass(frozen=True)
class IncomeOptionCandidate:
    strategy: str
    underlying_symbol: str
    option_contract: CanonicalOptionContract | None
    option_side: str
    option_type: str
    strike: float
    expiry: str
    dte: int
    delta: float
    bid: float
    ask: float
    midpoint: float
    spread: float
    spread_pct: float
    volume: int
    open_interest: int
    moneyness: str
    premium_per_contract: float
    total_premium: float
    annualized_premium_yield: float
    assignment_exposure: dict[str, Any]
    collateral_required: float
    collateral_efficiency: float
    underlying_coverage_required: float
    validation_status: str
    rejection_reasons: tuple[str, ...]
    ranking_score: float
    strategy_summary: dict[str, Any]
    source_index: int
    rank: int = 0
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    @property
    def valid(self) -> bool:
        return self.validation_status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "underlying_symbol": self.underlying_symbol,
            "option_contract": self.option_contract.to_dict() if self.option_contract is not None else None,
            "option_contract_identity": _contract_identity(self.option_contract),
            "option_side": self.option_side,
            "option_type": self.option_type,
            "strike": self.strike,
            "expiry": self.expiry,
            "dte": self.dte,
            "delta": self.delta,
            "bid": self.bid,
            "ask": self.ask,
            "midpoint": self.midpoint,
            "spread": self.spread,
            "spread_pct": self.spread_pct,
            "volume": self.volume,
            "open_interest": self.open_interest,
            "moneyness": self.moneyness,
            "premium_per_contract": self.premium_per_contract,
            "total_premium": self.total_premium,
            "annualized_premium_yield": self.annualized_premium_yield,
            "assignment_exposure": self.assignment_exposure,
            "collateral_required": self.collateral_required,
            "collateral_efficiency": self.collateral_efficiency,
            "underlying_coverage_required": self.underlying_coverage_required,
            "validation_status": self.validation_status,
            "rejection_reasons": list(self.rejection_reasons),
            "ranking_score": self.ranking_score,
            "strategy_summary": self.strategy_summary,
            "source_index": self.source_index,
            "rank": self.rank,
            "advisory_only": self.advisory_only,
            "execution_allowed": self.execution_allowed,
            "live_trading_blocked": self.live_trading_blocked,
            "broker_execution_armed": self.broker_execution_armed,
        }

    summary = to_dict


class IncomeOpportunityScanner:
    """Paper-safe covered-call and cash-secured-put opportunity scanner."""

    def __init__(self, config: IncomeScannerConfig | None = None) -> None:
        self.config = config or IncomeScannerConfig()

    def scan_covered_calls(
        self,
        contracts: Sequence[Any] | None,
        *,
        underlying_symbol: str,
        underlying_price: Any,
        underlying_quantity: Any,
        as_of: date | datetime | str,
        short_call_quantity: int = 1,
        mode: str = "paper",
        include_rejected: bool = False,
    ) -> list[IncomeOptionCandidate]:
        candidates = [
            self._evaluate(
                raw,
                strategy=COVERED_CALL,
                expected_type="CALL",
                underlying_symbol=underlying_symbol,
                underlying_price=underlying_price,
                collateral_available=underlying_quantity,
                quantity=short_call_quantity,
                as_of=as_of,
                mode=mode,
                source_index=index,
            )
            for index, raw in enumerate(contracts or [])
        ]
        return self._finalize(candidates, include_rejected=include_rejected)

    def scan_cash_secured_puts(
        self,
        contracts: Sequence[Any] | None,
        *,
        underlying_symbol: str,
        cash_collateral_available: Any,
        as_of: date | datetime | str,
        short_put_quantity: int = 1,
        mode: str = "paper",
        underlying_price: Any | None = None,
        include_rejected: bool = False,
    ) -> list[IncomeOptionCandidate]:
        candidates = [
            self._evaluate(
                raw,
                strategy=CASH_SECURED_PUT,
                expected_type="PUT",
                underlying_symbol=underlying_symbol,
                underlying_price=underlying_price,
                collateral_available=cash_collateral_available,
                quantity=short_put_quantity,
                as_of=as_of,
                mode=mode,
                source_index=index,
            )
            for index, raw in enumerate(contracts or [])
        ]
        return self._finalize(candidates, include_rejected=include_rejected)

    def _evaluate(
        self,
        raw: Any,
        *,
        strategy: str,
        expected_type: str,
        underlying_symbol: str,
        underlying_price: Any,
        collateral_available: Any,
        quantity: int,
        as_of: date | datetime | str,
        mode: str,
        source_index: int,
    ) -> IncomeOptionCandidate:
        reasons: list[str] = []
        expected_symbol = _symbol(underlying_symbol)
        as_of_date = _date_or_none(as_of)
        if as_of_date is None:
            reasons.append("MALFORMED_AS_OF")
            as_of_date = date(1970, 1, 1)

        contract = _coerce_contract(raw, reasons)
        mode_name = str(mode or "").strip().lower()
        if mode_name not in VALID_PAPER_MODES:
            reasons.append("UNSUPPORTED_LIVE_MODE")

        underlying = _symbol(getattr(contract, "underlying_symbol", "")) if contract is not None else ""
        option_type = str(getattr(contract, "option_type", "") or "").strip().upper()
        strike = _float(getattr(contract, "strike", 0.0), "strike", reasons)
        bid = _float(getattr(contract, "bid", 0.0), "bid", reasons)
        ask = _float(getattr(contract, "ask", 0.0), "ask", reasons)
        midpoint = _float(getattr(contract, "midpoint", 0.0), "midpoint", reasons)
        delta = _float(getattr(contract, "delta", 0.0), "delta", reasons)
        volume = _int(getattr(contract, "volume", 0), "volume", reasons)
        open_interest = _int(getattr(contract, "open_interest", 0), "open_interest", reasons)
        multiplier = _int(getattr(contract, "multiplier", 0), "multiplier", reasons)
        expiry = _date_or_none(getattr(contract, "expiration_date", None))
        expiry_text = expiry.isoformat() if expiry is not None else ""
        dte = (expiry - as_of_date).days if expiry is not None else 0

        if contract is None:
            reasons.append("MISSING_OPTION_CONTRACT")
        if option_type != expected_type:
            reasons.append(f"OPTION_TYPE_MUST_BE_{expected_type}")
        if expected_symbol and underlying != expected_symbol:
            reasons.append("UNDERLYING_SYMBOL_MISMATCH")
        if strike <= 0.0:
            reasons.append("MALFORMED_STRIKE")
        if multiplier <= 0:
            reasons.append("MALFORMED_MULTIPLIER")
        elif multiplier not in self.config.supported_multipliers:
            reasons.append("UNSUPPORTED_CONTRACT_MULTIPLIER")
        if not expiry_text:
            reasons.append("MALFORMED_EXPIRY")
        if dte < self.config.min_dte or dte > self.config.max_dte:
            reasons.append("INVALID_DTE")
        if bid <= 0.0 or ask <= 0.0 or midpoint <= 0.0 or ask < bid:
            reasons.append("MISSING_PRICE_FIELDS")

        spread = max(0.0, ask - bid) if ask >= bid else 0.0
        spread_pct = spread / midpoint if midpoint > 0.0 else 0.0
        if spread_pct > self.config.max_spread_pct:
            reasons.append("EXCESSIVE_SPREAD")
        if bid < self.config.min_bid or midpoint < self.config.min_bid:
            reasons.append("ZERO_OR_NEGATIVE_PREMIUM")
        if volume < self.config.min_volume:
            reasons.append("LOW_VOLUME")
        if open_interest < self.config.min_open_interest:
            reasons.append("LOW_OPEN_INTEREST")

        delta_abs = abs(delta)
        if strategy == COVERED_CALL:
            if delta <= 0.0:
                reasons.append("DELTA_OUTSIDE_RANGE")
            elif delta_abs < self.config.covered_call_min_delta or delta_abs > self.config.covered_call_max_delta:
                reasons.append("DELTA_OUTSIDE_RANGE")
        elif delta >= 0.0:
            reasons.append("DELTA_OUTSIDE_RANGE")
        elif delta_abs < self.config.cash_secured_put_min_delta or delta_abs > self.config.cash_secured_put_max_delta:
            reasons.append("DELTA_OUTSIDE_RANGE")

        contract_quantity = max(0, int(quantity or 0))
        assigned_quantity = multiplier * contract_quantity
        premium_per_contract = midpoint * multiplier
        total_premium = premium_per_contract * contract_quantity
        collateral_required = 0.0
        underlying_coverage_required = 0.0
        collateral_efficiency = 0.0

        if strategy == COVERED_CALL:
            spot = _float(underlying_price, "underlying_price", reasons)
            underlying_coverage_required = float(assigned_quantity)
            if spot <= 0.0:
                reasons.append("MALFORMED_UNDERLYING_PRICE")
            available_shares = _float(collateral_available, "underlying_quantity", reasons)
            if available_shares < underlying_coverage_required:
                reasons.append("INSUFFICIENT_UNDERLYING_COVERAGE")
            collateral_required = spot * underlying_coverage_required
            annualized_yield = _annualized(total_premium, collateral_required, dte)
            moneyness = _moneyness(expected_type, strike, spot)
            domain = build_covered_call(
                underlying_symbol=expected_symbol,
                underlying_quantity=collateral_available,
                option_contract=contract,
                short_call_quantity=contract_quantity,
                premium_received=midpoint,
                current_underlying_price=spot,
                mode=mode,
            )
        else:
            spot = _float(underlying_price, "underlying_price", []) if underlying_price is not None else strike
            cash_available = _float(collateral_available, "cash_collateral_available", reasons)
            if collateral_available is None:
                reasons.append("MISSING_COLLATERAL_EVIDENCE")
            collateral_required = strike * assigned_quantity
            if cash_available < collateral_required:
                reasons.append("INSUFFICIENT_CASH_COLLATERAL")
            collateral_efficiency = total_premium / collateral_required if collateral_required > 0 else 0.0
            annualized_yield = _annualized(total_premium, collateral_required, dte)
            moneyness = _moneyness(expected_type, strike, spot)
            domain = build_cash_secured_put(
                underlying_symbol=expected_symbol,
                option_contract=contract,
                short_put_quantity=contract_quantity,
                premium_received=midpoint,
                cash_collateral_available=collateral_available,
                mode=mode,
            )

        if not domain.valid:
            reasons.append("OI002_BUILDER_REJECTED")
            reasons.extend(str(item) for item in domain.rejection_reasons)

        valid = not reasons
        ranking_score = self._ranking_score(
            strategy=strategy,
            delta_abs=delta_abs,
            annualized_yield=annualized_yield,
            collateral_efficiency=collateral_efficiency,
            volume=volume,
            open_interest=open_interest,
            spread_pct=spread_pct,
            dte=dte,
            moneyness=moneyness,
        ) if valid else 0.0

        summary = domain.to_dict() if valid else {}
        assignment_exposure = dict(summary.get("assignment_exposure", {})) if summary else {}
        return IncomeOptionCandidate(
            strategy=strategy,
            underlying_symbol=expected_symbol,
            option_contract=contract if valid else contract,
            option_side="SHORT",
            option_type=option_type,
            strike=round(strike, 6),
            expiry=expiry_text,
            dte=int(dte),
            delta=round(delta, 6),
            bid=round(bid, 6),
            ask=round(ask, 6),
            midpoint=round(midpoint, 6),
            spread=round(spread, 6),
            spread_pct=round(spread_pct, 6),
            volume=volume,
            open_interest=open_interest,
            moneyness=moneyness,
            premium_per_contract=round(premium_per_contract, 6),
            total_premium=round(total_premium, 6),
            annualized_premium_yield=round(annualized_yield, 6),
            assignment_exposure=assignment_exposure,
            collateral_required=round(collateral_required, 6),
            collateral_efficiency=round(collateral_efficiency, 6),
            underlying_coverage_required=round(underlying_coverage_required, 6),
            validation_status="PASS" if valid else "FAIL",
            rejection_reasons=tuple(sorted(dict.fromkeys(reasons))),
            ranking_score=ranking_score,
            strategy_summary=summary,
            source_index=source_index,
        )

    def _ranking_score(
        self,
        *,
        strategy: str,
        delta_abs: float,
        annualized_yield: float,
        collateral_efficiency: float,
        volume: int,
        open_interest: int,
        spread_pct: float,
        dte: int,
        moneyness: str,
    ) -> float:
        target_delta = (
            self.config.covered_call_target_delta
            if strategy == COVERED_CALL
            else self.config.cash_secured_put_target_delta
        )
        delta_score = _clamp01(1.0 - abs(delta_abs - target_delta) / max(target_delta, 0.0001))
        yield_score = _clamp01(annualized_yield / 0.40)
        collateral_score = _clamp01(collateral_efficiency / 0.04)
        liquidity_score = _clamp01((min(volume, 500) / 500.0 * 0.45) + (min(open_interest, 1000) / 1000.0 * 0.55))
        spread_score = _clamp01(1.0 - spread_pct / max(self.config.max_spread_pct, 0.0001))
        dte_score = _clamp01(1.0 - abs(dte - self.config.preferred_dte) / max(self.config.preferred_dte, 1))
        moneyness_score = {"OTM": 1.0, "ATM": 0.75, "ITM": 0.35}.get(moneyness, 0.0)

        if strategy == COVERED_CALL:
            score = (
                delta_score * 0.26
                + yield_score * 0.22
                + liquidity_score * 0.18
                + spread_score * 0.16
                + dte_score * 0.12
                + moneyness_score * 0.06
            )
        else:
            score = (
                delta_score * 0.24
                + collateral_score * 0.24
                + yield_score * 0.16
                + liquidity_score * 0.16
                + spread_score * 0.12
                + dte_score * 0.08
            )
        return round(score * 100.0, 6)

    @staticmethod
    def _finalize(
        candidates: Sequence[IncomeOptionCandidate],
        *,
        include_rejected: bool,
    ) -> list[IncomeOptionCandidate]:
        accepted = [item for item in candidates if item.valid]
        accepted.sort(
            key=lambda item: (
                -item.ranking_score,
                item.expiry,
                item.strike,
                _option_symbol(item.option_contract),
                item.source_index,
            )
        )
        ranked = [
            IncomeOptionCandidate(**{**item.__dict__, "rank": index})
            for index, item in enumerate(accepted, start=1)
        ]
        if not include_rejected:
            return ranked
        rejected = [item for item in candidates if not item.valid]
        rejected.sort(key=lambda item: (item.source_index, _option_symbol(item.option_contract)))
        return ranked + list(rejected)


def _coerce_contract(raw: Any, reasons: list[str]) -> CanonicalOptionContract | None:
    if isinstance(raw, CanonicalOptionContract):
        return raw
    if isinstance(raw, Mapping):
        _preflight_raw_mapping(raw, reasons)
        try:
            return CanonicalOptionContract.from_dict(dict(raw))
        except (TypeError, ValueError):
            reasons.append("MALFORMED_CHAIN_ROW")
            return None
    reasons.append("MALFORMED_CHAIN_ROW")
    return None


def _preflight_raw_mapping(raw: Mapping[str, Any], reasons: list[str]) -> None:
    multiplier = raw.get("multiplier")
    if multiplier is not None:
        try:
            if int(multiplier) <= 0:
                reasons.append("MALFORMED_MULTIPLIER")
        except (TypeError, ValueError):
            reasons.append("MALFORMED_MULTIPLIER")
    bid = raw.get("bid")
    ask = raw.get("ask")
    midpoint = raw.get("midpoint")
    if bid in (None, "") or ask in (None, "") or midpoint in (None, ""):
        reasons.append("MISSING_PRICE_FIELDS")


def _symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _date_or_none(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip()).date()
        except (TypeError, ValueError):
            return None
    return None


def _float(value: Any, field: str, reasons: list[str]) -> float:
    try:
        if value is None or isinstance(value, bool):
            raise ValueError
        number = float(value)
    except (TypeError, ValueError):
        reasons.append(f"MALFORMED_{field.upper()}")
        return 0.0
    if number != number or number in {float("inf"), float("-inf")}:
        reasons.append(f"MALFORMED_{field.upper()}")
        return 0.0
    return number


def _int(value: Any, field: str, reasons: list[str]) -> int:
    try:
        if value is None or isinstance(value, bool):
            raise ValueError
        number = int(value)
    except (TypeError, ValueError):
        reasons.append(f"MALFORMED_{field.upper()}")
        return 0
    return number


def _moneyness(option_type: str, strike: float, underlying_price: float) -> str:
    if strike <= 0.0 or underlying_price <= 0.0:
        return "UNKNOWN"
    distance = abs(strike - underlying_price) / underlying_price
    if distance <= 0.01:
        return "ATM"
    if option_type == "CALL":
        return "OTM" if strike > underlying_price else "ITM"
    return "OTM" if strike < underlying_price else "ITM"


def _annualized(total_premium: float, collateral_required: float, dte: int) -> float:
    if total_premium <= 0.0 or collateral_required <= 0.0 or dte <= 0:
        return 0.0
    return (total_premium / collateral_required) * (365.0 / dte)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _contract_identity(contract: CanonicalOptionContract | None) -> dict[str, Any]:
    if contract is None:
        return {}
    return {
        "underlying_symbol": contract.underlying_symbol,
        "option_symbol": contract.option_symbol,
        "expiration_date": contract.expiration_date.isoformat(),
        "strike": contract.strike,
        "option_type": contract.option_type,
        "multiplier": contract.multiplier,
    }


def _option_symbol(contract: CanonicalOptionContract | None) -> str:
    return str(getattr(contract, "option_symbol", "") or "")


__all__ = [
    "IncomeOptionCandidate",
    "IncomeOpportunityScanner",
    "IncomeScannerConfig",
]
