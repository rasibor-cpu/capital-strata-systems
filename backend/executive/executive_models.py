"""Canonical read-only contracts for the Executive Intelligence Suite."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence
from uuid import uuid4


SCHEMA_VERSION = "css.executive.intelligence.v1"
DOCUMENT_VERSION = "1.0"


class TrafficLight(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


class PageOrientation(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class ExecutiveReportType(str, Enum):
    EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"
    EXECUTIVE_KPI_DASHBOARD = "EXECUTIVE_KPI_DASHBOARD"
    EXECUTIVE_INCOME_STATEMENT = "EXECUTIVE_INCOME_STATEMENT"
    EXECUTIVE_BALANCE_SHEET = "EXECUTIVE_BALANCE_SHEET"
    EXECUTIVE_CASH_FLOW = "EXECUTIVE_CASH_FLOW"
    CAPITAL_ALLOCATION = "CAPITAL_ALLOCATION"
    STRATEGY_PERFORMANCE = "STRATEGY_PERFORMANCE"
    PORTFOLIO_PERFORMANCE = "PORTFOLIO_PERFORMANCE"
    BROKER_PERFORMANCE = "BROKER_PERFORMANCE"
    RUN_RATE_ANALYSIS = "RUN_RATE_ANALYSIS"
    RISK_DASHBOARD = "RISK_DASHBOARD"
    OPERATIONAL_HEALTH = "OPERATIONAL_HEALTH"
    GOVERNANCE_DASHBOARD = "GOVERNANCE_DASHBOARD"
    AUDIT_REPORT = "AUDIT_REPORT"
    CERTIFICATION_REPORT = "CERTIFICATION_REPORT"
    DEPLOYMENT_REPORT = "DEPLOYMENT_REPORT"
    EXECUTIVE_COMMENTARY = "EXECUTIVE_COMMENTARY"
    BOARD_PACK = "BOARD_PACK"
    INVESTOR_REPORT = "INVESTOR_REPORT"
    REGULATORY_REPORT = "REGULATORY_REPORT"


@dataclass(frozen=True)
class ExecutiveSafetyContract:
    read_only: bool = True
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    runtime_mutation_allowed: bool = False
    broker_access_attempted: bool = False


@dataclass(frozen=True)
class MetricValue:
    key: str
    label: str
    value: float | int | None
    unit: str
    status: TrafficLight
    source: str = "canonical_metric_engine"
    as_of: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass(frozen=True)
class StatementLine:
    key: str
    label: str
    amount: float
    category: str
    subtotal: bool = False


@dataclass(frozen=True)
class FinancialStatement:
    statement_type: str
    currency: str
    period_start: str
    period_end: str
    lines: tuple[StatementLine, ...]
    balanced: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "lines": [asdict(line) for line in self.lines],
        }


@dataclass(frozen=True)
class ScoreCategory:
    key: str
    label: str
    score: float
    weight: float
    status: TrafficLight
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass(frozen=True)
class ExecutiveScorecard:
    overall_score: float
    overall_status: TrafficLight
    categories: tuple[ScoreCategory, ...]
    weights_total: float
    methodology: str = "css.executive.weighted_score.v1"

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "overall_status": self.overall_status.value,
            "categories": [category.as_dict() for category in self.categories],
            "weights_total": self.weights_total,
            "methodology": self.methodology,
        }


@dataclass(frozen=True)
class RunRateResult:
    annual_target: float
    quarterly_target: float
    monthly_target: float
    current_profit: float
    elapsed_trading_days: int
    remaining_trading_days: int
    required_daily_profit: float
    required_weekly_profit: float
    required_monthly_profit: float
    run_rate: float
    variance: float
    projected_year_end_profit: float
    probability_of_meeting_target: float
    traffic_light: TrafficLight
    commentary: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["traffic_light"] = self.traffic_light.value
        return payload


@dataclass(frozen=True)
class ReportTable:
    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    repeat_header: bool = True

    @property
    def is_wide(self) -> bool:
        return len(self.columns) > 7 or sum(len(str(column)) for column in self.columns) > 72

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "columns": list(self.columns),
            "rows": [list(row) for row in self.rows],
            "repeat_header": self.repeat_header,
        }


@dataclass(frozen=True)
class ReportSection:
    title: str
    paragraphs: tuple[str, ...] = ()
    metrics: tuple[MetricValue, ...] = ()
    tables: tuple[ReportTable, ...] = ()
    page_break_before: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "paragraphs": list(self.paragraphs),
            "metrics": [metric.as_dict() for metric in self.metrics],
            "tables": [table.as_dict() for table in self.tables],
            "page_break_before": self.page_break_before,
        }


@dataclass(frozen=True)
class ReportMetadata:
    report_id: str
    document_uuid: str
    runtime_version: str
    generation_timestamp: str
    reporting_period: str
    classification: str
    document_version: str = DOCUMENT_VERSION
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class ExecutiveReport:
    report_type: ExecutiveReportType
    title: str
    subtitle: str
    metadata: ReportMetadata
    sections: tuple[ReportSection, ...]
    orientation: PageOrientation = PageOrientation.PORTRAIT
    paper_size: str = "A4"
    safety: ExecutiveSafetyContract = field(default_factory=ExecutiveSafetyContract)

    @classmethod
    def create(
        cls,
        *,
        report_type: ExecutiveReportType,
        title: str,
        subtitle: str,
        runtime_version: str,
        reporting_period: str,
        sections: Sequence[ReportSection],
        classification: str,
        report_id: str | None = None,
        document_uuid: str | None = None,
        generated_at: datetime | None = None,
    ) -> "ExecutiveReport":
        generated = generated_at or datetime.now(timezone.utc)
        metadata = ReportMetadata(
            report_id=report_id or f"EIS-{generated:%Y%m%d}-{uuid4().hex[:10].upper()}",
            document_uuid=document_uuid or str(uuid4()),
            runtime_version=runtime_version,
            generation_timestamp=generated.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            reporting_period=reporting_period,
            classification=classification,
        )
        section_tuple = tuple(sections)
        orientation = (
            PageOrientation.LANDSCAPE
            if any(table.is_wide for section in section_tuple for table in section.tables)
            else PageOrientation.PORTRAIT
        )
        return cls(
            report_type=report_type,
            title=title,
            subtitle=subtitle,
            metadata=metadata,
            sections=section_tuple,
            orientation=orientation,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "report_type": self.report_type.value,
            "title": self.title,
            "subtitle": self.subtitle,
            "metadata": asdict(self.metadata),
            "sections": [section.as_dict() for section in self.sections],
            "paper": {
                "size": self.paper_size,
                "orientation": self.orientation.value,
            },
            "safety": asdict(self.safety),
        }


def safe_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def iso_date(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


__all__ = [
    "ExecutiveReport",
    "ExecutiveReportType",
    "ExecutiveSafetyContract",
    "ExecutiveScorecard",
    "FinancialStatement",
    "MetricValue",
    "PageOrientation",
    "ReportMetadata",
    "ReportSection",
    "ReportTable",
    "RunRateResult",
    "ScoreCategory",
    "StatementLine",
    "TrafficLight",
]
