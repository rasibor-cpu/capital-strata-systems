from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping


def _parse_date(value: Any, field_name: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            raise ValueError(f"{field_name} must be non-empty")
        return datetime.fromisoformat(trimmed).date()
    raise ValueError(f"{field_name} must be a date, datetime, or ISO string")


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        ts = value
    elif isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            raise ValueError(f"{field_name} must be non-empty")
        ts = datetime.fromisoformat(trimmed)
    else:
        raise ValueError(f"{field_name} must be a datetime or ISO string")
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _non_empty_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _to_float(value: Any, field_name: str) -> float:
    if value is None:
        raise ValueError(f"{field_name} is required")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


def _to_int(value: Any, field_name: str) -> int:
    if value is None:
        raise ValueError(f"{field_name} is required")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


@dataclass(frozen=True)
class CanonicalOptionContract:
    underlying_symbol: str
    option_symbol: str
    expiration_date: date
    strike: float
    option_type: str
    bid: float
    ask: float
    midpoint: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    intrinsic_value: float
    extrinsic_value: float
    probability_itm: float
    exchange: str
    multiplier: int
    currency: str
    timestamp: datetime

    def __post_init__(self) -> None:
        option_type = str(self.option_type or "").strip().upper()
        if option_type not in {"CALL", "PUT"}:
            raise ValueError("option_type must be CALL or PUT")
        object.__setattr__(self, "option_type", option_type)

        if self.bid < 0.0 or self.ask < 0.0:
            raise ValueError("bid and ask must be non-negative")
        if self.ask < self.bid:
            raise ValueError("ask must be greater than or equal to bid")
        if self.midpoint < 0.0 or self.last < 0.0:
            raise ValueError("midpoint and last must be non-negative")
        if self.volume < 0 or self.open_interest < 0:
            raise ValueError("volume and open_interest must be non-negative")
        if self.multiplier <= 0:
            raise ValueError("multiplier must be positive")
        if not 0.0 <= self.probability_itm <= 1.0:
            raise ValueError("probability_itm must be in range [0.0, 1.0]")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["expiration_date"] = self.expiration_date.isoformat()
        payload["timestamp"] = self.timestamp.isoformat()
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CanonicalOptionContract":
        return cls(
            underlying_symbol=_non_empty_text(data.get("underlying_symbol"), "underlying_symbol"),
            option_symbol=_non_empty_text(data.get("option_symbol"), "option_symbol"),
            expiration_date=_parse_date(data.get("expiration_date"), "expiration_date"),
            strike=_to_float(data.get("strike"), "strike"),
            option_type=_non_empty_text(data.get("option_type"), "option_type"),
            bid=_to_float(data.get("bid"), "bid"),
            ask=_to_float(data.get("ask"), "ask"),
            midpoint=_to_float(data.get("midpoint"), "midpoint"),
            last=_to_float(data.get("last"), "last"),
            volume=_to_int(data.get("volume"), "volume"),
            open_interest=_to_int(data.get("open_interest"), "open_interest"),
            implied_volatility=_to_float(data.get("implied_volatility"), "implied_volatility"),
            delta=_to_float(data.get("delta"), "delta"),
            gamma=_to_float(data.get("gamma"), "gamma"),
            theta=_to_float(data.get("theta"), "theta"),
            vega=_to_float(data.get("vega"), "vega"),
            rho=_to_float(data.get("rho"), "rho"),
            intrinsic_value=_to_float(data.get("intrinsic_value"), "intrinsic_value"),
            extrinsic_value=_to_float(data.get("extrinsic_value"), "extrinsic_value"),
            probability_itm=_to_float(data.get("probability_itm"), "probability_itm"),
            exchange=_non_empty_text(data.get("exchange"), "exchange"),
            multiplier=_to_int(data.get("multiplier"), "multiplier"),
            currency=_non_empty_text(data.get("currency"), "currency"),
            timestamp=_parse_datetime(data.get("timestamp"), "timestamp"),
        )
