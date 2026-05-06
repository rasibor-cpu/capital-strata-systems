from __future__ import annotations

from typing import List, Optional

from dashboard.trade_warehouse.trade_record_contract import (
    TradeRecord,
)
from dashboard.trade_warehouse.warehouse_reader_contract import (
    TradeWarehouseReader,
)
from dashboard.trade_warehouse.json_trade_storage import (
    JSONTradeWarehouseStorage,
)


class JSONTradeWarehouseReader(TradeWarehouseReader):
    """
    JSON-backed warehouse reader implementation.
    """

    def __init__(
        self,
        storage: JSONTradeWarehouseStorage | None = None,
    ) -> None:

        self.storage = (
            storage
            if storage is not None
            else JSONTradeWarehouseStorage()
        )

    # =====================================================
    # GET BY ID
    # =====================================================

    def get_trade_by_id(
        self,
        trade_id: str,
    ) -> Optional[TradeRecord]:

        trades = self.storage.read_all_trade_records()

        for trade in trades:
            if trade.trade_id == trade_id:
                return trade

        return None

    # =====================================================
    # GET BY ASSET CLASS
    # =====================================================

    def get_trades_by_asset_class(
        self,
        asset_class: str,
    ) -> List[TradeRecord]:

        normalized = asset_class.upper()

        trades = self.storage.read_all_trade_records()

        return [
            trade
            for trade in trades
            if trade.asset_class.upper() == normalized
        ]

    # =====================================================
    # GET ALL
    # =====================================================

    def get_all_trades(
        self,
    ) -> List[TradeRecord]:

        return self.storage.read_all_trade_records()