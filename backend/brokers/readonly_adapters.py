from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Sequence

from .questrade_client import QuestradeReadOnlyClient
from .readonly_domain import BrokerAccount, BrokerActivity, BrokerBalance, BrokerExecution, BrokerOrder, BrokerPosition


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc) if value else datetime.now(timezone.utc)


def _decimal(value: Any) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


class QuestradeReadOnlyBrokerAdapter:
    """Converts Questrade client payloads to the canonical read-only contract."""

    def __init__(self, client: QuestradeReadOnlyClient) -> None:
        self.client = client

    def get_accounts(self) -> Sequence[BrokerAccount]:
        payload = self.client.get_accounts()
        observed = datetime.now(timezone.utc)
        return tuple(BrokerAccount(str(item.get("number", item.get("accountId"))), str(item.get("currency", "UNKNOWN")), observed) for item in payload.get("accounts", []) if isinstance(item, dict))

    def get_balances(self, account_id: str) -> BrokerBalance:
        payload = self.client.get_balances(account_id)
        return BrokerBalance(account_id, str(payload.get("currency", "CAD")), _decimal(payload.get("cash")), _decimal(payload.get("buying_power")), _decimal(payload.get("equity", payload.get("total_equity"))), datetime.now(timezone.utc))

    def get_positions(self, account_id: str) -> Sequence[BrokerPosition]:
        payload = self.client.get_positions(account_id)
        observed = datetime.now(timezone.utc)
        return tuple(BrokerPosition(account_id, str(item.get("symbol", "UNKNOWN")), _decimal(item.get("quantity", 0)) or Decimal("0"), _decimal(item.get("averageEntryPrice", item.get("average_cost"))), _decimal(item.get("currentPrice", item.get("market_price"))), _decimal(item.get("currentMarketValue", item.get("market_value"))), _decimal(item.get("openPnl", item.get("unrealized_pnl"))), _decimal(item.get("closedPnl", item.get("realized_pnl"))), str(item.get("currency", "CAD")), observed) for item in payload.get("positions", []) if isinstance(item, dict))

    def get_orders(self, account_id: str, **query: Any) -> Sequence[BrokerOrder]:
        payload = self.client.get_orders(account_id, **query)
        observed = datetime.now(timezone.utc)
        return tuple(BrokerOrder(str(item.get("id", item.get("orderId", "unknown"))), account_id, str(item.get("symbol", "UNKNOWN")), str(item.get("status", "UNKNOWN")), _decimal(item.get("totalQuantity", item.get("quantity"))), observed) for item in payload.get("orders", []) if isinstance(item, dict))

    def get_executions(self, account_id: str, **query: Any) -> Sequence[BrokerExecution]:
        payload = self.client.get_executions(account_id, **query)
        return tuple(BrokerExecution(str(item.get("id", item.get("executionId", "unknown"))), account_id, str(item.get("symbol", "UNKNOWN")), _decimal(item.get("quantity", 0)) or Decimal("0"), _decimal(item.get("price", 0)) or Decimal("0"), _timestamp(item.get("executionTime"))) for item in payload.get("executions", []) if isinstance(item, dict))

    def get_activities(self, account_id: str, **query: Any) -> Sequence[BrokerActivity]:
        payload = self.client.get_activities(account_id, query.get("start_time"), query.get("end_time"))
        return tuple(BrokerActivity(str(item.get("id", item.get("activityId", "unknown"))), account_id, str(item.get("type", "UNKNOWN")), item.get("symbol"), _decimal(item.get("amount")), _timestamp(item.get("tradeDate", item.get("transactionDate")))) for item in payload if isinstance(item, dict))


__all__ = ["QuestradeReadOnlyBrokerAdapter"]
