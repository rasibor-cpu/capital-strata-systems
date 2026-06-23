from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PositionReconciliationReport:
    broker_count: int
    position_manager_count: int
    ledger_count: int

    broker_symbols: List[str] = field(default_factory=list)
    position_manager_symbols: List[str] = field(default_factory=list)
    ledger_symbols: List[str] = field(default_factory=list)

    missing_from_position_manager: List[str] = field(default_factory=list)
    missing_from_ledger: List[str] = field(default_factory=list)

    reconciled: bool = True


class PositionReconciliationService:
    """
    Read-only reconciliation service.

    Version 1:
    - No broker calls
    - No trade execution
    - No position modification
    - No ledger modification

    Only compares supplied position snapshots.
    """

    @staticmethod
    def _normalize_symbols(
        positions: List[Dict[str, Any]],
    ) -> List[str]:
        symbols = []

        for position in positions or []:
            symbol = str(
                position.get("symbol", "")
            ).strip().upper()

            if symbol:
                symbols.append(symbol)

        return sorted(set(symbols))

    def reconcile(
        self,
        broker_positions: List[Dict[str, Any]],
        position_manager_positions: List[Dict[str, Any]],
        ledger_positions: List[Dict[str, Any]],
    ) -> PositionReconciliationReport:

        broker_symbols = self._normalize_symbols(
            broker_positions
        )

        position_manager_symbols = self._normalize_symbols(
            position_manager_positions
        )

        ledger_symbols = self._normalize_symbols(
            ledger_positions
        )

        missing_from_position_manager = sorted(
            set(broker_symbols)
            - set(position_manager_symbols)
        )

        missing_from_ledger = sorted(
            set(broker_symbols)
            - set(ledger_symbols)
        )

        reconciled = (
            len(missing_from_position_manager) == 0
            and len(missing_from_ledger) == 0
        )

        return PositionReconciliationReport(
            broker_count=len(broker_symbols),
            position_manager_count=len(
                position_manager_symbols
            ),
            ledger_count=len(ledger_symbols),
            broker_symbols=broker_symbols,
            position_manager_symbols=position_manager_symbols,
            ledger_symbols=ledger_symbols,
            missing_from_position_manager=missing_from_position_manager,
            missing_from_ledger=missing_from_ledger,
            reconciled=reconciled,
        )