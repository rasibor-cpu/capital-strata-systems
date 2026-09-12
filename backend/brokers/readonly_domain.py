from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence


class SnapshotSource(str, Enum):
    LIVE = "LIVE"
    REPLAY = "REPLAY"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class BrokerHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"


class BrokerProviderError(RuntimeError):
    category = "PROVIDER_UNAVAILABLE"


class BrokerRateLimitedError(BrokerProviderError):
    category = "PROVIDER_RATE_LIMITED"


class BrokerMalformedDataError(BrokerProviderError):
    category = "MALFORMED_PROVIDER_DATA"


class BrokerAuthError(BrokerProviderError):
    category = "AUTH_REQUIRED"


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def money(value: Decimal | str | int | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


@dataclass(frozen=True)
class BrokerAccount:
    account_id: str
    currency: str
    as_of_utc: datetime
    display_name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of_utc", utc(self.as_of_utc))


@dataclass(frozen=True)
class BrokerBalance:
    account_id: str
    currency: str
    cash: Decimal | None
    buying_power: Decimal | None
    total_equity: Decimal | None
    as_of_utc: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "cash", money(self.cash))
        object.__setattr__(self, "buying_power", money(self.buying_power))
        object.__setattr__(self, "total_equity", money(self.total_equity))
        object.__setattr__(self, "as_of_utc", utc(self.as_of_utc))


@dataclass(frozen=True)
class BrokerPosition:
    account_id: str
    symbol: str
    quantity: Decimal
    average_cost: Decimal | None
    market_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    realized_pnl: Decimal | None
    currency: str
    as_of_utc: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", money(self.quantity) or Decimal("0"))
        for name in ("average_cost", "market_price", "market_value", "unrealized_pnl", "realized_pnl"):
            object.__setattr__(self, name, money(getattr(self, name)))
        object.__setattr__(self, "as_of_utc", utc(self.as_of_utc))


@dataclass(frozen=True)
class BrokerOrder:
    order_id: str
    account_id: str
    symbol: str
    status: str
    quantity: Decimal | None
    as_of_utc: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", money(self.quantity))
        object.__setattr__(self, "as_of_utc", utc(self.as_of_utc))


@dataclass(frozen=True)
class BrokerExecution:
    execution_id: str
    account_id: str
    symbol: str
    quantity: Decimal
    price: Decimal
    executed_at_utc: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", money(self.quantity) or Decimal("0"))
        object.__setattr__(self, "price", money(self.price) or Decimal("0"))
        object.__setattr__(self, "executed_at_utc", utc(self.executed_at_utc))


@dataclass(frozen=True)
class BrokerActivity:
    activity_id: str
    account_id: str
    activity_type: str
    symbol: str | None
    amount: Decimal | None
    occurred_at_utc: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", money(self.amount))
        object.__setattr__(self, "occurred_at_utc", utc(self.occurred_at_utc))


@dataclass(frozen=True)
class PortfolioSnapshot:
    account_id_masked: str
    as_of_utc: datetime
    base_currency: str | None
    cash: Decimal | None
    buying_power: Decimal | None
    total_equity: Decimal | None
    market_value: Decimal | None
    positions: tuple[BrokerPosition, ...] = ()
    total_realized_pnl: Decimal | None = None
    total_unrealized_pnl: Decimal | None = None
    total_pnl: Decimal | None = None
    broker_health: BrokerHealth = BrokerHealth.HEALTHY
    broker_data_freshness: str = "FRESH"
    snapshot_source: SnapshotSource = SnapshotSource.REPLAY
    last_successful_sync_utc: datetime | None = None
    reason: str | None = None
    provider: str = "REPLAY"
    snapshot_id: str = ""
    prior_snapshot_id: str | None = None
    ingestion_utc: datetime | None = None
    validation_status: str = "VALIDATED"

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of_utc", utc(self.as_of_utc))
        if self.last_successful_sync_utc is not None:
            object.__setattr__(self, "last_successful_sync_utc", utc(self.last_successful_sync_utc))
        if self.ingestion_utc is not None:
            object.__setattr__(self, "ingestion_utc", utc(self.ingestion_utc))
        for name in ("cash", "buying_power", "total_equity", "market_value", "total_realized_pnl", "total_unrealized_pnl", "total_pnl"):
            object.__setattr__(self, name, money(getattr(self, name)))

    def as_dict(self) -> dict[str, Any]:
        def serialize(value: Any) -> Any:
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, datetime):
                return value.isoformat()
            return value
        return {
            "account_id_masked": self.account_id_masked,
            "as_of_utc": self.as_of_utc.isoformat(),
            "base_currency": self.base_currency,
            "cash": serialize(self.cash),
            "buying_power": serialize(self.buying_power),
            "total_equity": serialize(self.total_equity),
            "market_value": serialize(self.market_value),
            "positions": [{key: serialize(value) for key, value in position.__dict__.items()} for position in self.positions],
            "total_realized_pnl": serialize(self.total_realized_pnl),
            "total_unrealized_pnl": serialize(self.total_unrealized_pnl),
            "total_pnl": serialize(self.total_pnl),
            "broker_health": self.broker_health.value,
            "broker_data_freshness": self.broker_data_freshness,
            "snapshot_source": self.snapshot_source.value,
            "last_successful_sync_utc": serialize(self.last_successful_sync_utc),
            "reason": self.reason,
            "provider": self.provider,
            "snapshot_id": self.snapshot_id,
            "prior_snapshot_id": self.prior_snapshot_id,
            "ingestion_utc": serialize(self.ingestion_utc),
            "validation_status": self.validation_status,
        }


class ReadOnlyBroker(Protocol):
    def get_accounts(self) -> Sequence[BrokerAccount]: ...
    def get_balances(self, account_id: str) -> BrokerBalance: ...
    def get_positions(self, account_id: str) -> Sequence[BrokerPosition]: ...
    def get_orders(self, account_id: str, **query: Any) -> Sequence[BrokerOrder]: ...
    def get_executions(self, account_id: str, **query: Any) -> Sequence[BrokerExecution]: ...
    def get_activities(self, account_id: str, **query: Any) -> Sequence[BrokerActivity]: ...


__all__ = [
    "BrokerAccount", "BrokerActivity", "BrokerAuthError", "BrokerBalance", "BrokerExecution",
    "BrokerHealth", "BrokerMalformedDataError", "BrokerOrder", "BrokerPosition", "BrokerProviderError",
    "BrokerRateLimitedError", "PortfolioSnapshot", "ReadOnlyBroker", "SnapshotSource", "money", "utc",
]
