from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping, Protocol, Sequence

from backend.options.options_income_strategy_domain import CASH_SECURED_PUT, COVERED_CALL
from backend.options.paper_position_repository import SAFE_FLAGS
from backend.trading.option_contract import CanonicalOptionContract


PAPER_ONLY_FLAGS = {**SAFE_FLAGS, "paper_only": True}
SUPPORTED_PAPER_STRATEGIES = {CASH_SECURED_PUT, COVERED_CALL}
HEALTH_STATUSES = {"ONLINE", "DEGRADED", "OFFLINE", "UNAVAILABLE"}


class OptionsBrokerAbstractionError(ValueError):
    """Raised when broker-neutral options abstractions fail closed."""


class OptionsContractProviderProtocol(Protocol):
    def get_contract(self, option_symbol: str) -> CanonicalOptionContract:
        ...

    def search_contracts(self, **filters: Any) -> list[CanonicalOptionContract]:
        ...


class OptionsChainProviderProtocol(Protocol):
    def get_chain(self, underlying_symbol: str, **filters: Any) -> "OptionsChainSnapshot":
        ...


class OptionsMarketDataProviderProtocol(Protocol):
    def snapshot(self, option_symbol: str, *, now: str | None = None) -> "OptionsMarketDataSnapshot":
        ...

    def refresh(self, option_symbol: str, *, now: str | None = None) -> "OptionsMarketDataSnapshot":
        ...


@dataclass(frozen=True)
class OptionsMarketDataSnapshot:
    option_symbol: str
    underlying_symbol: str
    quote: dict[str, Any]
    greeks: dict[str, Any]
    implied_volatility: float | None
    freshness_timestamp: str
    source: str
    status: str
    quality: str
    cached: bool = False
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    paper_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), **PAPER_ONLY_FLAGS}


@dataclass(frozen=True)
class OptionsChainSnapshot:
    provider_name: str
    underlying_symbol: str
    expiries: list[str]
    strikes: list[float]
    calls: list[dict[str, Any]]
    puts: list[dict[str, Any]]
    generated_at: str
    source: str
    status: str
    quality: str
    missing_fields: list[str]
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    paper_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), **PAPER_ONLY_FLAGS}


@dataclass(frozen=True)
class PaperAccountSnapshot:
    account_id: str
    buying_power: float
    cash: float
    equity: float
    currency: str = "USD"
    option_approval_level: str = "PAPER_INCOME"
    mode: str = "PAPER"
    source: str = "paper_options_broker"
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    paper_only: bool = True

    def __post_init__(self) -> None:
        _non_negative(self.buying_power, "buying_power")
        _non_negative(self.cash, "cash")
        _non_negative(self.equity, "equity")
        if str(self.mode).upper() != "PAPER":
            raise OptionsBrokerAbstractionError("live broker mode is rejected")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["account_id"] = "PAPER-OPTIONS-ACCOUNT"
        return {**payload, **PAPER_ONLY_FLAGS}


@dataclass(frozen=True)
class PaperOrderPreview:
    strategy: str
    underlying_symbol: str
    option_symbol: str
    quantity: int
    estimated_collateral: float
    estimated_premium: float
    estimated_buying_power_impact: float
    warnings: list[str]
    reasons: list[str]
    preview_status: str
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    paper_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), **PAPER_ONLY_FLAGS}


def assert_paper_safe_posture(
    *,
    mode: str = "PAPER",
    advisory_only: bool = True,
    execution_allowed: bool = False,
    live_trading_blocked: bool = True,
    broker_execution_armed: bool = False,
) -> None:
    if str(mode or "").strip().upper() != "PAPER":
        raise OptionsBrokerAbstractionError("live broker mode is rejected")
    if advisory_only is not True or execution_allowed is not False or live_trading_blocked is not True or broker_execution_armed is not False:
        raise OptionsBrokerAbstractionError("execution-enabled posture is invalid")


def normalize_option_contract(value: Any) -> CanonicalOptionContract:
    if isinstance(value, CanonicalOptionContract):
        _validate_contract(value)
        return value
    if isinstance(value, Mapping):
        contract = CanonicalOptionContract.from_dict(dict(value))
        _validate_contract(contract)
        return contract
    raise OptionsBrokerAbstractionError("missing contract")


def contract_quote(contract: CanonicalOptionContract) -> dict[str, Any]:
    _validate_contract(contract)
    mark = round((contract.bid + contract.ask) / 2.0, 8)
    return {
        "bid": contract.bid,
        "ask": contract.ask,
        "midpoint": contract.midpoint,
        "last": contract.last,
        "mark": mark,
        "volume": contract.volume,
        "open_interest": contract.open_interest,
        "timestamp": contract.timestamp.isoformat(),
    }


def contract_greeks(contract: CanonicalOptionContract) -> dict[str, float]:
    _validate_contract(contract)
    return {
        "delta": contract.delta,
        "gamma": contract.gamma,
        "theta": contract.theta,
        "vega": contract.vega,
        "rho": contract.rho,
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp_or_now(value: str | None = None) -> str:
    if value is None:
        return utc_now_iso()
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise OptionsBrokerAbstractionError("malformed timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _validate_contract(contract: CanonicalOptionContract) -> None:
    mandatory = (
        contract.underlying_symbol,
        contract.option_symbol,
        contract.expiration_date,
        contract.option_type,
        contract.exchange,
        contract.currency,
    )
    if any(not str(item or "").strip() for item in mandatory):
        raise OptionsBrokerAbstractionError("missing mandatory contract field")
    for field in ("bid", "ask", "midpoint", "last", "implied_volatility", "delta", "gamma", "theta", "vega", "rho"):
        _finite(getattr(contract, field), field)
    if contract.implied_volatility <= 0:
        raise OptionsBrokerAbstractionError("missing IV")


def _finite(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OptionsBrokerAbstractionError(f"malformed {field}") from exc
    if not isfinite(number):
        raise OptionsBrokerAbstractionError(f"malformed {field}")
    return number


def _non_negative(value: Any, field: str) -> float:
    number = _finite(value, field)
    if number < 0.0:
        raise OptionsBrokerAbstractionError(f"negative {field}")
    return number


def stable_contract_rows(contracts: Sequence[CanonicalOptionContract]) -> list[dict[str, Any]]:
    rows = [contract.to_dict() for contract in contracts]
    rows.sort(key=lambda row: (str(row["expiration_date"]), float(row["strike"]), str(row["option_type"]), str(row["option_symbol"])))
    return rows


__all__ = [
    "HEALTH_STATUSES",
    "PAPER_ONLY_FLAGS",
    "SUPPORTED_PAPER_STRATEGIES",
    "OptionsBrokerAbstractionError",
    "OptionsChainProviderProtocol",
    "OptionsChainSnapshot",
    "OptionsContractProviderProtocol",
    "OptionsMarketDataProviderProtocol",
    "OptionsMarketDataSnapshot",
    "PaperAccountSnapshot",
    "PaperOrderPreview",
    "assert_paper_safe_posture",
    "contract_greeks",
    "contract_quote",
    "normalize_option_contract",
    "stable_contract_rows",
    "timestamp_or_now",
    "utc_now_iso",
]
