from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ReconciliationMismatch:
    symbol: str
    source_a: str
    source_b: str
    details: str
    severity: str


@dataclass
class ReconciliationSummary:
    reconciled: bool

    broker_symbols: int
    position_manager_symbols: int
    ledger_symbols: int

    mismatch_count: int

    mismatches: List[ReconciliationMismatch] = field(
        default_factory=list
    )