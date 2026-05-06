from __future__ import annotations

from dashboard.trade_warehouse.trade_record_contract import (
    TradeRecord,
)
from dashboard.trade_warehouse.warehouse_writer_contract import (
    TradeWarehouseWriter,
)
from dashboard.trade_warehouse.json_trade_storage import (
    JSONTradeWarehouseStorage,
)


class JSONTradeWarehouseWriter(TradeWarehouseWriter):
    """
    JSON-backed append-only warehouse writer.
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
    # WRITE RECORD
    # =====================================================

    def write_trade_record(
        self,
        record: TradeRecord,
    ) -> None:

        self.storage.append_trade_record(
            record
        )

    # =====================================================
    # ARCHIVE RECORD
    # =====================================================

    def archive_trade_record(
        self,
        record: TradeRecord,
    ) -> None:

        self.storage.append_trade_record(
            record
        )

        self.storage.flush()