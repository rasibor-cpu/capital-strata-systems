from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from backend.trading.option_contract import CanonicalOptionContract


COVERED_CALL = "COVERED_CALL"
CASH_SECURED_PUT = "CASH_SECURED_PUT"
COLLATERAL_UNDERLYING_SHARES = "UNDERLYING_SHARES"
COLLATERAL_CASH = "CASH"
VALID_PAPER_MODES = {"paper", "dry_run", "sim", "demo"}
SHORT_INTENTS = {"SHORT", "SELL", "WRITE", "SHORT_TO_OPEN", "SELL_TO_OPEN"}
ZERO = Decimal("0")


@dataclass(frozen=True)
class CoveredCallModel:
    strategy: str
    underlying_symbol: str
    underlying_quantity: Decimal
    required_covered_quantity: Decimal
    option_contract: CanonicalOptionContract | None
    short_call_quantity: int
    strike: Decimal
    expiry: str
    premium_received: Decimal
    contract_multiplier: Decimal
    current_underlying_price: Decimal
    total_premium_received: Decimal
    maximum_profit: Decimal
    maximum_profit_per_share: Decimal
    breakeven: Decimal
    downside_exposure: Decimal
    assignment_exposure: dict[str, Any]
    capped_upside: dict[str, Any]
    collateral_type: str
    validation_status: str
    rejection_reasons: tuple[str, ...]
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    @property
    def valid(self) -> bool:
        return self.validation_status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(
            {
                "strategy": self.strategy,
                "underlying_symbol": self.underlying_symbol,
                "underlying_quantity": self.underlying_quantity,
                "required_covered_quantity": self.required_covered_quantity,
                "option_contract": _contract_payload(self.option_contract),
                "option_contract_identity": _contract_identity(self.option_contract),
                "short_call_quantity": self.short_call_quantity,
                "strike": self.strike,
                "expiry": self.expiry,
                "premium_received": self.premium_received,
                "contract_multiplier": self.contract_multiplier,
                "current_underlying_price": self.current_underlying_price,
                "total_premium_received": self.total_premium_received,
                "maximum_profit": self.maximum_profit,
                "maximum_profit_per_share": self.maximum_profit_per_share,
                "breakeven": self.breakeven,
                "downside_exposure": self.downside_exposure,
                "assignment_exposure": self.assignment_exposure,
                "capped_upside": self.capped_upside,
                "collateral_type": self.collateral_type,
                "validation_status": self.validation_status,
                "rejection_reasons": list(self.rejection_reasons),
                "valid": self.valid,
                "advisory_only": self.advisory_only,
                "execution_allowed": self.execution_allowed,
                "live_trading_blocked": self.live_trading_blocked,
                "broker_execution_armed": self.broker_execution_armed,
            }
        )

    summary = to_dict


@dataclass(frozen=True)
class CashSecuredPutModel:
    strategy: str
    underlying_symbol: str
    option_contract: CanonicalOptionContract | None
    short_put_quantity: int
    strike: Decimal
    expiry: str
    premium_received: Decimal
    contract_multiplier: Decimal
    cash_collateral_required: Decimal
    cash_collateral_available: Decimal
    total_premium_received: Decimal
    maximum_profit: Decimal
    maximum_loss: Decimal
    downside_exposure: Decimal
    breakeven: Decimal
    assignment_cost_basis: Decimal
    assignment_exposure: dict[str, Any]
    collateral_efficiency: Decimal
    collateral_type: str
    validation_status: str
    rejection_reasons: tuple[str, ...]
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    @property
    def valid(self) -> bool:
        return self.validation_status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(
            {
                "strategy": self.strategy,
                "underlying_symbol": self.underlying_symbol,
                "option_contract": _contract_payload(self.option_contract),
                "option_contract_identity": _contract_identity(self.option_contract),
                "short_put_quantity": self.short_put_quantity,
                "strike": self.strike,
                "expiry": self.expiry,
                "premium_received": self.premium_received,
                "contract_multiplier": self.contract_multiplier,
                "cash_collateral_required": self.cash_collateral_required,
                "cash_collateral_available": self.cash_collateral_available,
                "total_premium_received": self.total_premium_received,
                "maximum_profit": self.maximum_profit,
                "maximum_loss": self.maximum_loss,
                "downside_exposure": self.downside_exposure,
                "breakeven": self.breakeven,
                "assignment_cost_basis": self.assignment_cost_basis,
                "assignment_exposure": self.assignment_exposure,
                "collateral_efficiency": self.collateral_efficiency,
                "collateral_type": self.collateral_type,
                "validation_status": self.validation_status,
                "rejection_reasons": list(self.rejection_reasons),
                "valid": self.valid,
                "advisory_only": self.advisory_only,
                "execution_allowed": self.execution_allowed,
                "live_trading_blocked": self.live_trading_blocked,
                "broker_execution_armed": self.broker_execution_armed,
            }
        )

    summary = to_dict


def build_covered_call(
    *,
    underlying_symbol: str,
    underlying_quantity: Any,
    option_contract: CanonicalOptionContract | None,
    short_call_quantity: Any,
    premium_received: Any,
    current_underlying_price: Any,
    option_position: str = "SHORT",
    mode: str = "paper",
) -> CoveredCallModel:
    reasons: list[str] = []
    symbol = _symbol(underlying_symbol)
    mode_name = str(mode or "").strip().lower()
    if mode_name not in VALID_PAPER_MODES:
        reasons.append("UNSUPPORTED_LIVE_MODE")
    if str(option_position or "").strip().upper() not in SHORT_INTENTS:
        reasons.append("SHORT_CALL_INTENT_REQUIRED")

    underlying_qty = _decimal_field(underlying_quantity, "underlying_quantity", reasons)
    short_qty = _int_field(short_call_quantity, "short_call_quantity", reasons)
    premium = _decimal_field(premium_received, "premium_received", reasons)
    current_price = _decimal_field(current_underlying_price, "current_underlying_price", reasons)
    strike, expiry, multiplier = _contract_terms(option_contract, "CALL", symbol, reasons)

    if not symbol:
        reasons.append("MISSING_UNDERLYING_SYMBOL")
    if underlying_qty <= ZERO:
        reasons.append("INVALID_UNDERLYING_QUANTITY")
    if short_qty <= 0:
        reasons.append("INVALID_SHORT_CALL_QUANTITY")
    if premium < ZERO:
        reasons.append("NEGATIVE_PREMIUM")
    if current_price <= ZERO:
        reasons.append("INVALID_CURRENT_UNDERLYING_PRICE")

    required_covered = multiplier * Decimal(max(short_qty, 0))
    if required_covered <= ZERO:
        reasons.append("INVALID_REQUIRED_COVERED_QUANTITY")
    elif underlying_qty < required_covered:
        reasons.append("INSUFFICIENT_UNDERLYING_COVERAGE")

    valid = not reasons
    total_premium = premium * required_covered if valid else ZERO
    capped_upside_per_share = max(strike - current_price, ZERO) if valid else ZERO
    capped_upside_total = capped_upside_per_share * required_covered if valid else ZERO
    max_profit = capped_upside_total + total_premium if valid else ZERO
    breakeven = current_price - premium if valid else ZERO
    downside = max(current_price - premium, ZERO) * required_covered if valid else ZERO
    assignment = {
        "assigned_underlying_quantity": required_covered,
        "assignment_sale_value": strike * required_covered if valid else ZERO,
        "assignment_price": strike,
        "assignment_risk": "SHORT_CALL_ASSIGNMENT_CAN_CALL_AWAY_COVERED_SHARES",
    }
    capped = {
        "capped": True,
        "maximum_upside_per_share": capped_upside_per_share,
        "maximum_upside_total": capped_upside_total,
        "cap_strike": strike,
    }
    return CoveredCallModel(
        strategy=COVERED_CALL,
        underlying_symbol=symbol,
        underlying_quantity=_money(underlying_qty),
        required_covered_quantity=_money(required_covered),
        option_contract=option_contract,
        short_call_quantity=short_qty,
        strike=_money(strike),
        expiry=expiry,
        premium_received=_money(premium),
        contract_multiplier=_money(multiplier),
        current_underlying_price=_money(current_price),
        total_premium_received=_money(total_premium),
        maximum_profit=_money(max_profit),
        maximum_profit_per_share=_money(max_profit / required_covered) if valid and required_covered > ZERO else ZERO,
        breakeven=_money(breakeven),
        downside_exposure=_money(downside),
        assignment_exposure=_json_safe(assignment),
        capped_upside=_json_safe(capped),
        collateral_type=COLLATERAL_UNDERLYING_SHARES,
        validation_status="PASS" if valid else "FAIL",
        rejection_reasons=tuple(sorted(dict.fromkeys(reasons))),
    )


def build_cash_secured_put(
    *,
    underlying_symbol: str,
    option_contract: CanonicalOptionContract | None,
    short_put_quantity: Any,
    premium_received: Any,
    cash_collateral_available: Any,
    option_position: str = "SHORT",
    mode: str = "paper",
) -> CashSecuredPutModel:
    reasons: list[str] = []
    symbol = _symbol(underlying_symbol)
    mode_name = str(mode or "").strip().lower()
    if mode_name not in VALID_PAPER_MODES:
        reasons.append("UNSUPPORTED_LIVE_MODE")
    if str(option_position or "").strip().upper() not in SHORT_INTENTS:
        reasons.append("SHORT_PUT_INTENT_REQUIRED")

    short_qty = _int_field(short_put_quantity, "short_put_quantity", reasons)
    premium = _decimal_field(premium_received, "premium_received", reasons)
    cash_available = _decimal_field(cash_collateral_available, "cash_collateral_available", reasons)
    strike, expiry, multiplier = _contract_terms(option_contract, "PUT", symbol, reasons)

    if not symbol:
        reasons.append("MISSING_UNDERLYING_SYMBOL")
    if short_qty <= 0:
        reasons.append("INVALID_SHORT_PUT_QUANTITY")
    if premium < ZERO:
        reasons.append("NEGATIVE_PREMIUM")
    if cash_collateral_available is None:
        reasons.append("MISSING_COLLATERAL_EVIDENCE")

    assigned_quantity = multiplier * Decimal(max(short_qty, 0))
    collateral_required = strike * assigned_quantity
    if assigned_quantity <= ZERO:
        reasons.append("INVALID_ASSIGNMENT_QUANTITY")
    if collateral_required <= ZERO:
        reasons.append("INVALID_CASH_COLLATERAL_REQUIRED")
    elif cash_available < collateral_required:
        reasons.append("INSUFFICIENT_CASH_COLLATERAL")

    valid = not reasons
    total_premium = premium * assigned_quantity if valid else ZERO
    max_loss = max(collateral_required - total_premium, ZERO) if valid else ZERO
    breakeven = strike - premium if valid else ZERO
    efficiency = total_premium / collateral_required if valid and collateral_required > ZERO else ZERO
    assignment = {
        "assigned_underlying_quantity": assigned_quantity,
        "assignment_purchase_value": collateral_required if valid else ZERO,
        "assignment_price": strike,
        "assignment_cost_basis": breakeven,
        "assignment_risk": "SHORT_PUT_ASSIGNMENT_CAN_REQUIRE_SHARE_PURCHASE",
    }
    return CashSecuredPutModel(
        strategy=CASH_SECURED_PUT,
        underlying_symbol=symbol,
        option_contract=option_contract,
        short_put_quantity=short_qty,
        strike=_money(strike),
        expiry=expiry,
        premium_received=_money(premium),
        contract_multiplier=_money(multiplier),
        cash_collateral_required=_money(collateral_required),
        cash_collateral_available=_money(cash_available),
        total_premium_received=_money(total_premium),
        maximum_profit=_money(total_premium),
        maximum_loss=_money(max_loss),
        downside_exposure=_money(max_loss),
        breakeven=_money(breakeven),
        assignment_cost_basis=_money(breakeven),
        assignment_exposure=_json_safe(assignment),
        collateral_efficiency=_ratio(efficiency),
        collateral_type=COLLATERAL_CASH,
        validation_status="PASS" if valid else "FAIL",
        rejection_reasons=tuple(sorted(dict.fromkeys(reasons))),
    )


def _contract_terms(
    contract: CanonicalOptionContract | None,
    expected_type: str,
    expected_underlying: str,
    reasons: list[str],
) -> tuple[Decimal, str, Decimal]:
    if contract is None:
        reasons.append("MISSING_OPTION_CONTRACT")
        return ZERO, "", ZERO
    try:
        option_type = str(contract.option_type or "").strip().upper()
        underlying = _symbol(contract.underlying_symbol)
        strike = _decimal_field(contract.strike, "strike", reasons)
        multiplier = _decimal_field(contract.multiplier, "multiplier", reasons)
        expiry = _expiry_text(contract.expiration_date)
    except (AttributeError, TypeError, ValueError):
        reasons.append("MALFORMED_OPTION_CONTRACT")
        return ZERO, "", ZERO

    if option_type != expected_type:
        reasons.append(f"OPTION_TYPE_MUST_BE_{expected_type}")
    if expected_underlying and underlying != expected_underlying:
        reasons.append("UNDERLYING_SYMBOL_MISMATCH")
    if strike <= ZERO:
        reasons.append("MALFORMED_STRIKE")
    if multiplier <= ZERO:
        reasons.append("MALFORMED_MULTIPLIER")
    if not expiry:
        reasons.append("MALFORMED_EXPIRY")
    return strike, expiry, multiplier


def _symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _expiry_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        return ""
    return datetime.fromisoformat(text).date().isoformat()


def _decimal_field(value: Any, field_name: str, reasons: list[str]) -> Decimal:
    try:
        if value is None or isinstance(value, bool):
            raise InvalidOperation
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        reasons.append(f"MALFORMED_{field_name.upper()}")
        return ZERO
    if not number.is_finite():
        reasons.append(f"MALFORMED_{field_name.upper()}")
        return ZERO
    return number


def _int_field(value: Any, field_name: str, reasons: list[str]) -> int:
    try:
        if value is None or isinstance(value, bool):
            raise ValueError
        number = Decimal(str(value))
        if number != number.to_integral_value():
            raise ValueError
        return int(number)
    except (InvalidOperation, ValueError):
        reasons.append(f"MALFORMED_{field_name.upper()}")
        return 0


def _contract_payload(contract: CanonicalOptionContract | None) -> dict[str, Any] | None:
    if contract is None:
        return None
    if hasattr(contract, "to_dict"):
        return contract.to_dict()
    return None


def _contract_identity(contract: CanonicalOptionContract | None) -> dict[str, Any]:
    if contract is None:
        return {}
    strike = ZERO
    multiplier = 0
    try:
        strike = _decimal_field(getattr(contract, "strike", 0), "strike", [])
    except (AttributeError, TypeError, ValueError):
        strike = ZERO
    try:
        multiplier = int(getattr(contract, "multiplier", 0) or 0)
    except (TypeError, ValueError):
        multiplier = 0
    try:
        expiry = _expiry_text(getattr(contract, "expiration_date", ""))
    except (TypeError, ValueError):
        expiry = ""
    return {
        "underlying_symbol": getattr(contract, "underlying_symbol", ""),
        "option_symbol": getattr(contract, "option_symbol", ""),
        "expiration_date": expiry,
        "strike": _float(strike),
        "option_type": str(getattr(contract, "option_type", "")).upper(),
        "multiplier": multiplier,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _float(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _ratio(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _float(value: Decimal) -> float:
    return float(_money(value))


__all__ = [
    "CASH_SECURED_PUT",
    "COLLATERAL_CASH",
    "COLLATERAL_UNDERLYING_SHARES",
    "COVERED_CALL",
    "CashSecuredPutModel",
    "CoveredCallModel",
    "build_cash_secured_put",
    "build_covered_call",
]
