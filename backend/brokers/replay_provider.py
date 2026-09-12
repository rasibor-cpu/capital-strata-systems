from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Sequence

from .questrade_provider_config import mask_account_identifier, select_account
from .readonly_domain import (
    BrokerAccount, BrokerActivity, BrokerBalance, BrokerExecution, BrokerHealth,
    BrokerMalformedDataError, BrokerOrder, BrokerPosition, BrokerProviderError,
    BrokerRateLimitedError, PortfolioSnapshot, SnapshotSource,
)


class ReplayScenario(str, Enum):
    NORMAL_PORTFOLIO = "NORMAL_PORTFOLIO"
    EMPTY_PORTFOLIO = "EMPTY_PORTFOLIO"
    MULTI_ACCOUNT = "MULTI_ACCOUNT"
    STALE_DATA = "STALE_DATA"
    PARTIAL_RESPONSE = "PARTIAL_RESPONSE"
    MALFORMED_PROVIDER_DATA = "MALFORMED_PROVIDER_DATA"
    DUPLICATE_ACTIVITY = "DUPLICATE_ACTIVITY"
    POSITION_MISMATCH = "POSITION_MISMATCH"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"


_REPLAY_NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)


def _accounts() -> tuple[BrokerAccount, ...]:
    return (
        BrokerAccount("REPLAY-CAD-001", "CAD", _REPLAY_NOW, "Replay CAD"),
        BrokerAccount("REPLAY-USD-002", "USD", _REPLAY_NOW, "Replay USD"),
    )


def _positions(account_id: str) -> tuple[BrokerPosition, ...]:
    return (
        BrokerPosition(account_id, "SHOP", Decimal("10"), Decimal("80"), Decimal("90"), Decimal("900"), Decimal("100"), Decimal("20"), "CAD", _REPLAY_NOW),
        BrokerPosition(account_id, "RY", Decimal("25"), Decimal("130"), Decimal("125"), Decimal("3125"), Decimal("-125"), Decimal("0"), "CAD", _REPLAY_NOW),
        BrokerPosition(account_id, "TD", Decimal("12"), Decimal("75"), Decimal("82"), Decimal("984"), Decimal("84"), Decimal("5"), "CAD", _REPLAY_NOW),
    )


class ReplayBrokerProvider:
    """Deterministic read-only broker substitute with static scenario behavior."""

    def __init__(self, scenario: ReplayScenario = ReplayScenario.NORMAL_PORTFOLIO, *, now: datetime = _REPLAY_NOW) -> None:
        self.scenario = ReplayScenario(scenario)
        self.now = now.astimezone(timezone.utc)
        self._selected_account: str | None = None

    def _fail_if_unavailable(self) -> None:
        if self.scenario == ReplayScenario.PROVIDER_UNAVAILABLE:
            raise BrokerProviderError("replay provider unavailable")
        if self.scenario == ReplayScenario.PROVIDER_RATE_LIMITED:
            raise BrokerRateLimitedError("replay provider rate limited")
        if self.scenario == ReplayScenario.MALFORMED_PROVIDER_DATA:
            raise BrokerMalformedDataError("replay provider payload malformed")

    def get_accounts(self) -> Sequence[BrokerAccount]:
        self._fail_if_unavailable()
        if self.scenario == ReplayScenario.EMPTY_PORTFOLIO:
            return ()
        if self.scenario == ReplayScenario.MULTI_ACCOUNT:
            return _accounts()
        return (_accounts()[0],)

    def select_account(self, configured_id: str | None = None) -> BrokerAccount:
        accounts = self.get_accounts()
        raw = [{"number": item.account_id} for item in accounts]
        selected = select_account(raw, configured_id)
        self._selected_account = str(selected["number"])
        return next(item for item in accounts if item.account_id == self._selected_account)

    def _account_id(self, account_id: str) -> str:
        self._fail_if_unavailable()
        if not account_id:
            raise BrokerMalformedDataError("account identifier is required")
        return account_id

    def get_balances(self, account_id: str) -> BrokerBalance:
        account_id = self._account_id(account_id)
        if self.scenario == ReplayScenario.PARTIAL_RESPONSE:
            return BrokerBalance(account_id, "CAD", Decimal("1000"), None, None, self.now)
        return BrokerBalance(account_id, "CAD", Decimal("5000"), Decimal("7000"), Decimal("10000"), self.now - (timedelta(hours=2) if self.scenario == ReplayScenario.STALE_DATA else timedelta(0)))

    def get_positions(self, account_id: str) -> Sequence[BrokerPosition]:
        account_id = self._account_id(account_id)
        if self.scenario == ReplayScenario.EMPTY_PORTFOLIO:
            return ()
        positions = list(_positions(account_id))
        if self.scenario == ReplayScenario.PARTIAL_RESPONSE:
            return positions[:1]
        if self.scenario == ReplayScenario.POSITION_MISMATCH:
            positions[0] = BrokerPosition(account_id, "SHOP", Decimal("99"), Decimal("80"), Decimal("90"), Decimal("8910"), Decimal("990"), Decimal("20"), "CAD", self.now)
        return tuple(positions)

    def get_orders(self, account_id: str, **query: Any) -> Sequence[BrokerOrder]:
        account_id = self._account_id(account_id)
        return (BrokerOrder("order-001", account_id, "SHOP", "OPEN", Decimal("2"), self.now), BrokerOrder("order-002", account_id, "RY", "CLOSED", Decimal("5"), self.now - timedelta(days=1)))

    def get_executions(self, account_id: str, **query: Any) -> Sequence[BrokerExecution]:
        account_id = self._account_id(account_id)
        return (BrokerExecution("exec-001", account_id, "SHOP", Decimal("10"), Decimal("80"), self.now - timedelta(days=2)), BrokerExecution("exec-002", account_id, "RY", Decimal("25"), Decimal("130"), self.now - timedelta(days=1)))

    def get_activities(self, account_id: str, **query: Any) -> Sequence[BrokerActivity]:
        account_id = self._account_id(account_id)
        activities = (BrokerActivity("activity-001", account_id, "BUY", "SHOP", Decimal("800"), self.now - timedelta(days=2)), BrokerActivity("activity-002", account_id, "DIVIDEND", "TD", Decimal("5"), self.now - timedelta(days=1)))
        return activities + (activities[:1] if self.scenario == ReplayScenario.DUPLICATE_ACTIVITY else ())

    def snapshot(self, configured_account_id: str | None = None) -> PortfolioSnapshot:
        account = self.select_account(configured_account_id)
        balance = self.get_balances(account.account_id)
        positions = tuple(self.get_positions(account.account_id))
        market_value = sum((item.market_value for item in positions if item.market_value is not None), Decimal("0")) if positions else Decimal("0")
        realized = sum((item.realized_pnl for item in positions if item.realized_pnl is not None), Decimal("0")) if positions else Decimal("0")
        unrealized = sum((item.unrealized_pnl for item in positions if item.unrealized_pnl is not None), Decimal("0")) if positions else Decimal("0")
        stale = self.scenario == ReplayScenario.STALE_DATA
        partial = self.scenario == ReplayScenario.PARTIAL_RESPONSE
        return PortfolioSnapshot(
            account_id_masked=mask_account_identifier(account.account_id),
            as_of_utc=balance.as_of_utc,
            base_currency=balance.currency,
            cash=balance.cash,
            buying_power=balance.buying_power,
            total_equity=balance.total_equity,
            market_value=market_value if not partial else None,
            positions=positions,
            total_realized_pnl=realized,
            total_unrealized_pnl=unrealized,
            total_pnl=realized + unrealized,
            broker_health=BrokerHealth.DEGRADED if partial else BrokerHealth.HEALTHY,
            broker_data_freshness="STALE" if stale else "FRESH",
            snapshot_source=SnapshotSource.STALE if stale else SnapshotSource.REPLAY,
            last_successful_sync_utc=balance.as_of_utc,
            reason="PARTIAL_RESPONSE" if partial else None,
        )


__all__ = ["ReplayBrokerProvider", "ReplayScenario"]
