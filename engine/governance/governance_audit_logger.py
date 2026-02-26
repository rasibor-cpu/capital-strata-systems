"""
Governance Audit Logger
-----------------------
Institutional-grade structured governance decision logger.

Purpose:
- Capture every portfolio governance decision
- Provide explainability spine for CSS
- Support regulatory / audit / NIW documentation use

Non-blocking:
- Logger never interferes with execution path
- Fail-silent if logging fails
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class GovernanceDecisionRecord:
    timestamp: float
    instrument: str
    asset_class: str

    signal_strength: float
    requested_notional: float
    effective_notional: float

    equity: float
    portfolio_dd_pct: float
    total_exposure: float
    asset_class_exposure: float

    correlation_score: Optional[float]

    pcc_final: str
    pcc_reason: str
    sizing_multiplier: float


class GovernanceAuditLogger:

    def __init__(self, output_path: str = "audit_logs/governance_decisions.jsonl"):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, record: GovernanceDecisionRecord) -> None:
        try:
            with self.output_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(record)) + "\n")
        except Exception:
            # Fail-silent by design
            pass