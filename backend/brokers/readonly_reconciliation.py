from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from .readonly_domain import PortfolioSnapshot, BrokerActivity, BrokerPosition


class ReconciliationCategory(str, Enum):
    MATCH = "MATCH"
    MISSING_IN_CSS = "MISSING_IN_CSS"
    MISSING_AT_BROKER = "MISSING_AT_BROKER"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    COST_BASIS_MISMATCH = "COST_BASIS_MISMATCH"
    CASH_MISMATCH = "CASH_MISMATCH"
    EQUITY_MISMATCH = "EQUITY_MISMATCH"
    DUPLICATE_ACTIVITY = "DUPLICATE_ACTIVITY"
    STALE_DATA = "STALE_DATA"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ReconciliationFinding:
    category: ReconciliationCategory
    severity: str
    entity: str
    broker_value: Any
    css_value: Any
    explanation: str
    as_of_utc: datetime

    def as_dict(self) -> dict[str, Any]:
        def value(item: Any) -> Any:
            return str(item) if isinstance(item, Decimal) else item.isoformat() if isinstance(item, datetime) else item
        return {"category": self.category.value, "severity": self.severity, "entity": self.entity, "broker_value": value(self.broker_value), "css_value": value(self.css_value), "explanation": self.explanation, "as_of_utc": self.as_of_utc.isoformat()}


@dataclass(frozen=True)
class ReconciliationResult:
    status: str
    findings: tuple[ReconciliationFinding, ...]
    as_of_utc: datetime

    @property
    def issue_count(self) -> int:
        return len(self.findings)

    @property
    def highest_severity(self) -> str:
        order = {"critical": 3, "error": 2, "warning": 1, "info": 0}
        return max((item.severity for item in self.findings), key=lambda item: order.get(item, 0), default="info")

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "issue_count": self.issue_count, "highest_severity": self.highest_severity, "as_of_utc": self.as_of_utc.isoformat(), "findings": [item.as_dict() for item in self.findings]}


def _finding(category: ReconciliationCategory, entity: str, broker: Any, css: Any, explanation: str, as_of: datetime, severity: str = "error") -> ReconciliationFinding:
    return ReconciliationFinding(category, severity, entity, broker, css, explanation, as_of)


def reconcile_portfolios(broker: PortfolioSnapshot, css: PortfolioSnapshot | None, *, activities: Sequence[BrokerActivity] = ()) -> ReconciliationResult:
    as_of = broker.as_of_utc
    findings: list[ReconciliationFinding] = []
    if broker.snapshot_source == broker.snapshot_source.STALE or broker.broker_data_freshness == "STALE":
        findings.append(_finding(ReconciliationCategory.STALE_DATA, "snapshot", broker.broker_data_freshness, "current", "Broker snapshot is stale and cannot be treated as current.", as_of, "warning"))
    if css is None:
        findings.append(_finding(ReconciliationCategory.INSUFFICIENT_DATA, "css_snapshot", broker.as_dict(), None, "CSS comparison snapshot is unavailable.", as_of, "warning"))
    else:
        for category, entity, broker_value, css_value in (
            (ReconciliationCategory.CASH_MISMATCH, "cash", broker.cash, css.cash),
            (ReconciliationCategory.EQUITY_MISMATCH, "total_equity", broker.total_equity, css.total_equity),
        ):
            if broker_value is None or css_value is None:
                findings.append(_finding(ReconciliationCategory.INSUFFICIENT_DATA, entity, broker_value, css_value, "A required financial field is unavailable.", as_of, "warning"))
            elif broker_value != css_value:
                findings.append(_finding(category, entity, broker_value, css_value, "Broker value remains authoritative; CSS value is reported without correction.", as_of))
        broker_positions = {item.symbol: item for item in broker.positions}
        css_positions = {item.symbol: item for item in css.positions}
        for symbol in sorted(set(broker_positions) - set(css_positions)):
            findings.append(_finding(ReconciliationCategory.MISSING_IN_CSS, symbol, broker_positions[symbol].quantity, None, "Broker holding is absent from CSS snapshot.", as_of))
        for symbol in sorted(set(css_positions) - set(broker_positions)):
            findings.append(_finding(ReconciliationCategory.MISSING_AT_BROKER, symbol, None, css_positions[symbol].quantity, "CSS holding is absent from broker snapshot.", as_of))
        for symbol in sorted(set(broker_positions) & set(css_positions)):
            broker_position, css_position = broker_positions[symbol], css_positions[symbol]
            if broker_position.quantity != css_position.quantity:
                findings.append(_finding(ReconciliationCategory.QUANTITY_MISMATCH, symbol, broker_position.quantity, css_position.quantity, "Broker-reported held quantity is authoritative.", as_of))
            if broker_position.average_cost is not None and css_position.average_cost is not None and broker_position.average_cost != css_position.average_cost:
                findings.append(_finding(ReconciliationCategory.COST_BASIS_MISMATCH, symbol, broker_position.average_cost, css_position.average_cost, "Cost basis differs; no silent correction applied.", as_of))
    seen: set[str] = set()
    for activity in activities:
        if activity.activity_id in seen:
            findings.append(_finding(ReconciliationCategory.DUPLICATE_ACTIVITY, activity.activity_id, activity.activity_id, None, "Activity identifier appeared more than once.", activity.occurred_at_utc))
        seen.add(activity.activity_id)
    return ReconciliationResult("MATCH" if not findings else "ISSUES", tuple(findings), as_of)


__all__ = ["ReconciliationCategory", "ReconciliationFinding", "ReconciliationResult", "reconcile_portfolios"]
