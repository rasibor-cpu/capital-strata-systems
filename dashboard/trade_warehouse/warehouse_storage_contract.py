from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from dashboard.trade_warehouse.trade_record_contract import TradeRecord


class TradeWarehouseStorage(ABC):
    """
    Canonical warehouse storage backend contract.

    PURPOSE
    -------
    Define the physical persistence/storage interface used
    by the CSS trade warehouse.

    POSSIBLE IMPLEMENTATIONS
    ------------------------
    - JSON storage
    - CSV storage
    - SQLite storage
    - PostgreSQL storage
    - Parquet storage
    - Cloud object storage

    RULES
    -----
    - storage backends must preserve append-only integrity
    - storage backends must not silently mutate history
    - storage backends must preserve auditability
    """

    @abstractmethod
    def append_trade_record(
        self,
        record: TradeRecord,
    ) -> None:
        """
        Persist a trade record.
        """
        pass

    @abstractmethod
    def read_all_trade_records(self) -> List[TradeRecord]:
        """
        Read all historical trade records.
        """
        pass

    @abstractmethod
    def flush(self) -> None:
        """
        Flush buffered writes if applicable.
        """
        pass