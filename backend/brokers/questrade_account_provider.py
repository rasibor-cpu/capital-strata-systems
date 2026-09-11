from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.brokers.questrade_readonly import parse_questrade_readonly_response

from .questrade_client import QuestradeReadOnlyClient


class QuestradeAccountProvider:
    def __init__(self, client: QuestradeReadOnlyClient) -> None:
        self.client = client

    def discover_accounts(self) -> dict[str, Any]:
        return self.client.get_accounts()

    def snapshot(self, account_id: str) -> dict[str, Any]:
        account_payload = self.client.get_accounts()
        accounts = account_payload.get("accounts", [])
        account = next((item for item in accounts if str(item.get("number")) == str(account_id)), None)
        if account is None:
            raise LookupError("Questrade account was not found")
        balances = self.client.get_balances(account_id)
        positions = self.client.get_positions(account_id)
        normalized = parse_questrade_readonly_response({
            "status": "AVAILABLE",
            "account": account,
            "balances": balances,
            "positions": positions.get("positions", []),
            "data_timestamp": datetime.now(timezone.utc).isoformat(),
            "broker_name": "QUESTRADE",
            "capital_provenance": "REAL_BROKER",
            "read_only": True,
        })
        normalized["provenance"] = "QUESTRADE"
        normalized["observation_timestamp"] = datetime.now(timezone.utc).isoformat()
        return normalized

    def get_executions(self, account_id: str, **query: Any) -> Any:
        return self.client.get_executions(account_id, **query)

    def get_orders(self, account_id: str, **query: Any) -> Any:
        return self.client.get_orders(account_id, **query)

    def get_activities(self, account_id: str, start_time: datetime, end_time: datetime) -> list[Any]:
        return self.client.get_activities(account_id, start_time, end_time)


__all__ = ["QuestradeAccountProvider"]
