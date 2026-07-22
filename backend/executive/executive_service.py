"""Read-only orchestration service for the Executive Intelligence Suite."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from typing import Any

from backend.common.branding import get_brand_service

from .business_calendar import BusinessCalendar
from .executive_alerts import build_executive_alerts
from .executive_balance_sheet import build_balance_sheet
from .executive_capital import build_capital_view
from .executive_cashflow import build_cashflow_statement
from .executive_commentary import ExecutiveCommentaryEngine
from .executive_forecast import build_forecast
from .executive_income_statement import build_income_statement
from .executive_kpis import select_executive_kpis
from .executive_metrics import ExecutiveMetricEngine, serialize_metrics
from .executive_models import (
    ExecutiveReport,
    ExecutiveReportType,
    ExecutiveSafetyContract,
    MetricValue,
    ReportSection,
    ReportTable,
)
from .executive_risk import build_risk_view
from .executive_run_rate import ExecutiveRunRateEngine, RunRateInputs
from .executive_scorecard import ExecutiveScorecardEngine


StateProvider = Callable[[], Mapping[str, Any] | None]


class ExecutiveIntelligenceService:
    """Build one immutable executive package from one provider snapshot."""

    def __init__(
        self,
        *,
        state_provider: StateProvider | None = None,
        runtime_version: str = "RC1.1",
        calendar_factory: Callable[[int], BusinessCalendar] | None = None,
    ) -> None:
        self.state_provider = state_provider or (lambda: {})
        self.runtime_version = runtime_version
        self.calendar_factory = calendar_factory or BusinessCalendar.for_year
        self.metrics = ExecutiveMetricEngine()
        self.scorecards = ExecutiveScorecardEngine()
        self.run_rates = ExecutiveRunRateEngine()
        self.commentary = ExecutiveCommentaryEngine()

    def build_package(self) -> dict[str, Any]:
        snapshot = self._snapshot()
        today = _date(snapshot.get("current_date"))
        period_start = str(snapshot.get("period_start") or date(today.year, 1, 1).isoformat())
        period_end = str(snapshot.get("period_end") or today.isoformat())
        currency = str(snapshot.get("currency") or "CAD")
        metrics = self.metrics.calculate(snapshot)
        scorecard = self.scorecards.calculate(
            snapshot.get("executive_scores") or _derived_scores(metrics, snapshot)
        )
        run_rate = self.run_rates.calculate(
            RunRateInputs(
                annual_target=_number(snapshot.get("annual_target")),
                quarterly_target=_number(snapshot.get("quarterly_target")),
                monthly_target=_number(snapshot.get("monthly_target")),
                current_profit=_metric_number(metrics, "net_profit"),
                current_date=today,
                trading_days=_optional_int(snapshot.get("trading_days")),
            ),
            calendar=self.calendar_factory(today.year),
        )
        income = build_income_statement(
            snapshot,
            period_start=period_start,
            period_end=period_end,
            currency=currency,
        )
        balance = build_balance_sheet(snapshot, as_of=period_end, currency=currency)
        cashflow = build_cashflow_statement(
            snapshot,
            period_start=period_start,
            period_end=period_end,
            currency=currency,
        )
        comments = self.commentary.generate(
            metrics=metrics,
            scorecard=scorecard,
            run_rate=run_rate,
        )
        safety = ExecutiveSafetyContract()
        return {
            "schema_version": "css.executive.intelligence.v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "reporting_period": {"start": period_start, "end": period_end},
            "currency": currency,
            "metrics": serialize_metrics(metrics),
            "kpis": {
                key: metric.as_dict()
                for key, metric in select_executive_kpis(metrics).items()
            },
            "scorecard": scorecard.as_dict(),
            "income_statement": income.as_dict(),
            "balance_sheet": balance.as_dict(),
            "cashflow": cashflow.as_dict(),
            "run_rate": run_rate.as_dict(),
            "capital": build_capital_view(snapshot),
            "risk": build_risk_view(metrics, snapshot),
            "forecast": build_forecast(run_rate),
            "alerts": list(build_executive_alerts(scorecard, run_rate)),
            "commentary": list(comments),
            "safety": safety.__dict__,
            "_objects": {
                "metrics": metrics,
                "scorecard": scorecard,
                "run_rate": run_rate,
            },
        }

    def summary(self) -> dict[str, Any]:
        package = self.build_package()
        return _public(
            package,
            keys=(
                "schema_version",
                "generated_at",
                "reporting_period",
                "currency",
                "kpis",
                "scorecard",
                "run_rate",
                "alerts",
                "commentary",
                "safety",
            ),
        )

    def kpis(self) -> dict[str, Any]:
        return self._view("kpis")

    def scorecard(self) -> dict[str, Any]:
        return self._view("scorecard")

    def income(self) -> dict[str, Any]:
        return self._view("income_statement")

    def balance_sheet(self) -> dict[str, Any]:
        return self._view("balance_sheet")

    def cashflow(self) -> dict[str, Any]:
        return self._view("cashflow")

    def run_rate(self) -> dict[str, Any]:
        return self._view("run_rate")

    def risk(self) -> dict[str, Any]:
        return self._view("risk")

    def commentary_view(self) -> dict[str, Any]:
        return self._view("commentary")

    def canonical_report(
        self,
        report_type: ExecutiveReportType = ExecutiveReportType.EXECUTIVE_SUMMARY,
    ) -> ExecutiveReport:
        package = self.build_package()
        title = report_type.value.replace("_", " ").title()
        sections = (
            ReportSection(
                title="Executive Commentary",
                paragraphs=tuple(package["commentary"]),
            ),
            ReportSection(
                title="Executive KPIs",
                metrics=tuple(package["_objects"]["metrics"][key] for key in package["kpis"]),
            ),
            ReportSection(
                title="Executive Scorecard",
                tables=(
                    ReportTable(
                        title="Weighted Score Categories",
                        columns=("Category", "Score", "Weight", "Status", "Rationale"),
                        rows=tuple(
                            (
                                item["label"],
                                item["score"],
                                item["weight"],
                                item["status"],
                                item["rationale"],
                            )
                            for item in package["scorecard"]["categories"]
                        ),
                    ),
                ),
            ),
            ReportSection(
                title="Run Rate Analysis",
                tables=(
                    ReportTable(
                        title="Profitability Run Rate",
                        columns=("Measure", "Value"),
                        rows=tuple(
                            (key.replace("_", " ").title(), value)
                            for key, value in package["run_rate"].items()
                            if key != "commentary"
                        ),
                    ),
                ),
            ),
        )
        brand = get_brand_service()
        return ExecutiveReport.create(
            report_type=report_type,
            title=title,
            subtitle="Enterprise Executive Intelligence",
            runtime_version=self.runtime_version,
            reporting_period=(
                f"{package['reporting_period']['start']} to "
                f"{package['reporting_period']['end']}"
            ),
            sections=sections,
            classification=brand.document_standard.classification,
        )

    def _view(self, key: str) -> dict[str, Any]:
        package = self.build_package()
        return {
            "schema_version": package["schema_version"],
            "generated_at": package["generated_at"],
            "data": package[key],
            "safety": package["safety"],
        }

    def _snapshot(self) -> dict[str, Any]:
        try:
            value = self.state_provider()
        except Exception:
            return {}
        return dict(value) if isinstance(value, Mapping) else {}


def _public(package: Mapping[str, Any], *, keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: package[key] for key in keys}


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).date()


def _number(value: Any) -> float:
    try:
        return float(value if value not in (None, "") else 0.0)
    except (TypeError, ValueError):
        return 0.0


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _metric_number(metrics: Mapping[str, MetricValue], key: str) -> float:
    metric = metrics.get(key)
    return _number(metric.value if metric else 0.0)


def _derived_scores(
    metrics: Mapping[str, MetricValue],
    snapshot: Mapping[str, Any],
) -> dict[str, float]:
    return {
        "financial_health": _status_score(metrics["net_profit"].status.value),
        "risk_health": _status_score(metrics["maximum_drawdown"].status.value),
        "execution_quality": _number(snapshot.get("execution_quality_score", 50)),
        "capital_efficiency": _status_score(metrics["capital_efficiency"].status.value),
        "operational_health": _number(snapshot.get("operational_health_score", 50)),
        "compliance": _number(snapshot.get("compliance_score", 50)),
        "readiness": _number(snapshot.get("readiness_score", 50)),
        "infrastructure": _number(snapshot.get("infrastructure_score", 50)),
        "broker_health": _number(snapshot.get("broker_health_score", 50)),
        "data_freshness": _number(snapshot.get("data_freshness_score", 50)),
    }


def _status_score(status: str) -> float:
    return {"GREEN": 90.0, "AMBER": 60.0, "RED": 25.0}.get(status, 50.0)


__all__ = ["ExecutiveIntelligenceService", "StateProvider"]
