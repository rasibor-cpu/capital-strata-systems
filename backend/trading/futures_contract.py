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


def _to_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    raise ValueError(f"{field_name} must be boolean")


@dataclass(frozen=True)
class CanonicalFuturesContract:
    root_symbol: str
    contract_symbol: str
    expiration: date
    exchange: str
    tick_size: float
    point_value: float
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    active_contract: bool
    rollover_date: date
    timestamp: datetime

    def __post_init__(self) -> None:
        if self.tick_size <= 0.0:
            raise ValueError("tick_size must be positive")
        if self.point_value <= 0.0:
            raise ValueError("point_value must be positive")
        if self.bid < 0.0 or self.ask < 0.0 or self.last < 0.0:
            raise ValueError("bid, ask, and last must be non-negative")
        if self.ask < self.bid:
            raise ValueError("ask must be greater than or equal to bid")
        if self.volume < 0 or self.open_interest < 0:
            raise ValueError("volume and open_interest must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["expiration"] = self.expiration.isoformat()
        payload["rollover_date"] = self.rollover_date.isoformat()
        payload["timestamp"] = self.timestamp.isoformat()
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CanonicalFuturesContract":
        return cls(
            root_symbol=_non_empty_text(data.get("root_symbol"), "root_symbol"),
            contract_symbol=_non_empty_text(data.get("contract_symbol"), "contract_symbol"),
            expiration=_parse_date(data.get("expiration"), "expiration"),
            exchange=_non_empty_text(data.get("exchange"), "exchange"),
            tick_size=_to_float(data.get("tick_size"), "tick_size"),
            point_value=_to_float(data.get("point_value"), "point_value"),
            bid=_to_float(data.get("bid"), "bid"),
            ask=_to_float(data.get("ask"), "ask"),
            last=_to_float(data.get("last"), "last"),
            volume=_to_int(data.get("volume"), "volume"),
            open_interest=_to_int(data.get("open_interest"), "open_interest"),
            active_contract=_to_bool(data.get("active_contract"), "active_contract"),
            rollover_date=_parse_date(data.get("rollover_date"), "rollover_date"),
            timestamp=_parse_datetime(data.get("timestamp"), "timestamp"),
        )
