from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from dashboard.trade_warehouse.trade_record_contract import TradeRecord


class TradeWarehouseReader(ABC):
    """
    Canonical trade warehouse reader contract.

    PURPOSE
    -------
    Read and query historical trade records from the CSS trade warehouse.

    RULES
    -----
    - readers must not mutate records
    - readers must not rewrite history
    - readers must not override accounting truth
    - readers provide historical access only
    """

    @abstractmethod
    def get_trade_by_id(
        self,
        trade_id: str,
    ) -> Optional[TradeRecord]:
        """
        Retrieve single trade by identifier.
        """
        pass

    @abstractmethod
    def get_trades_by_asset_class(
        self,
        asset_class: str,
    ) -> List[TradeRecord]:
        """
        Retrieve trades for a given asset class.
        """
        pass

    @abstractmethod
    def get_all_trades(self) -> List[TradeRecord]:
        """
        Retrieve all historical trades.
        """
        pass