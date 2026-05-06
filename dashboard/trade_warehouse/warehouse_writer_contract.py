from __future__ import annotations

from abc import ABC, abstractmethod

from dashboard.trade_warehouse.trade_record_contract import TradeRecord


class TradeWarehouseWriter(ABC):
    """
    Canonical trade warehouse writer contract.

    PURPOSE
    -------
    Persist append-only trade records into the CSS trade warehouse.

    RULES
    -----
    - trade history must be append-only
    - historical records must not be silently overwritten
    - warehouse writes must not execute trades
    - warehouse writes must not mutate accounting truth
    - warehouse writes must not override governance decisions
    """

    @abstractmethod
    def write_trade_record(
        self,
        record: TradeRecord,
    ) -> None:
        """
        Persist a single trade record.
        """
        pass

    @abstractmethod
    def archive_trade_record(
        self,
        record: TradeRecord,
    ) -> None:
        """
        Archive historical trade record.
        """
        pass