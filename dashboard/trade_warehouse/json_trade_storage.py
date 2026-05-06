from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import List

from dashboard.trade_warehouse.trade_record_contract import TradeRecord
from dashboard.trade_warehouse.warehouse_storage_contract import (
    TradeWarehouseStorage,
)


class JSONTradeWarehouseStorage(TradeWarehouseStorage):
    """
    JSON append-only warehouse storage implementation.

    PURPOSE
    -------
    Simple institutional baseline storage backend for CSS.

    RULES
    -----
    - append-only writes
    - no silent overwrite of history
    - preserve auditability
    """

    def __init__(
        self,
        storage_file: str = "dashboard/trade_warehouse/reports/trades.json",
    ) -> None:

        self.storage_path = Path(storage_file)

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.storage_path.exists():
            self.storage_path.write_text(
                "[]",
                encoding="utf-8",
            )

    # =====================================================
    # APPEND RECORD
    # =====================================================

    def append_trade_record(
        self,
        record: TradeRecord,
    ) -> None:

        existing = self.read_all_trade_records_as_dicts()

        existing.append(
            asdict(record)
        )

        self.storage_path.write_text(
            json.dumps(existing, indent=2),
            encoding="utf-8",
        )

    # =====================================================
    # READ RECORDS
    # =====================================================

    def read_all_trade_records(
        self,
    ) -> List[TradeRecord]:

        raw = self.read_all_trade_records_as_dicts()

        records: List[TradeRecord] = []

        for item in raw:
            try:
                records.append(
                    TradeRecord(**item)
                )
            except Exception:
                continue

        return records

    def read_all_trade_records_as_dicts(self):

        try:
            return json.loads(
                self.storage_path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            return []

    # =====================================================
    # FLUSH
    # =====================================================

    def flush(self) -> None:
        """
        JSON implementation writes immediately.
        """
        return