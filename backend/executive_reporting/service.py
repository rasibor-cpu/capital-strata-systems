"""Phase 178 — ExecutiveFinancialReportingService (orchestration only; no accounting)."""

from __future__ import annotations

from typing import Any

from backend.executive_reporting.ei_adapter import executive_intelligence_financial_provider
from backend.executive_reporting.evidence_bridge import financial_evidence_for_176j
from backend.executive_reporting.html_render import render_executive_financial_html
from backend.executive_reporting.package import build_executive_financial_report_package
from backend.executive_reporting.summary import build_executive_financial_summary
from backend.financial_reporting.adapters import contract_from_mission_control_state
from backend.financial_reporting.engine import CanonicalFinancialReportingEngine, empty_degraded_summary
from backend.financial_reporting.models import deep_freeze_dict


class ExecutiveFinancialReportingService:
    """
    Read-only suite: Phase 177 engine → executive package → formats / adapters.
    """

    def __init__(self, *, engine: CanonicalFinancialReportingEngine | None = None) -> None:
        self.engine = engine or CanonicalFinancialReportingEngine()

    def generate_from_contract(self, contract: Any, *, report_id: str | None = None) -> dict[str, Any]:
        pkg177 = self.engine.generate_financial_report_package(contract, report_id=report_id)
        return build_executive_financial_report_package(pkg177, report_id=report_id)

    def generate_from_state(self, state: dict[str, Any] | None, *, report_id: str | None = None) -> dict[str, Any]:
        try:
            contract = contract_from_mission_control_state(state)
            return self.generate_from_contract(contract, report_id=report_id)
        except Exception:
            return self.degraded_package()

    def generate_from_phase177_package(
        self, phase177_package: dict[str, Any], *, report_id: str | None = None
    ) -> dict[str, Any]:
        return build_executive_financial_report_package(phase177_package, report_id=report_id)

    def financial_summary(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            package = self.generate_from_state(state)
            return package.get("financial_summary") or build_executive_financial_summary({})
        except Exception:
            return build_executive_financial_summary(empty_degraded_summary())

    def financial_narrative(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        package = self.generate_from_state(state)
        return package.get("narrative") or {}

    def management_actions(self, state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        package = self.generate_from_state(state)
        return list(package.get("management_actions") or [])

    def to_html(self, package: dict[str, Any]) -> str:
        return render_executive_financial_html(package)

    def to_json(self, package: dict[str, Any]) -> dict[str, Any]:
        return deep_freeze_dict(package)

    def ei_provider(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        package = self.generate_from_state(state)
        return executive_intelligence_financial_provider(package)

    def readiness_evidence_176j(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        package = self.generate_from_state(state)
        # Prefer Phase 177 nested statements for 176J keys
        return financial_evidence_for_176j(package)

    def degraded_package(self) -> dict[str, Any]:
        return build_executive_financial_report_package(
            empty_degraded_summary(),
            report_id="degraded-executive-financial",
        )


def produce_report_center_payload(
    *,
    report_code: str,
    title: str,
    filters: dict[str, Any],
    repo_root: Any = None,
    view: str = "full",
) -> dict[str, Any]:
    """Thin Reports Center producer helper."""
    from backend.reports_center.constants import SAFETY_LOCKS
    from backend.reports_center.producers import utc_today

    _ = repo_root
    service = ExecutiveFinancialReportingService()
    # Optional: filters may carry financial_reporting mapping via state_json omitted for safety
    state: dict[str, Any] = {}
    if isinstance(filters.get("target_profit"), (int, float, str)):
        state["target_profit"] = filters["target_profit"]
    package = service.generate_from_state(state)
    if view == "summary":
        content = package.get("financial_summary")
    elif view == "income":
        content = package.get("income_statement")
    elif view == "balance":
        content = package.get("balance_sheet")
    elif view == "cash":
        content = package.get("cash_flow_statement")
    elif view == "run_rate":
        content = package.get("profitability_run_rate")
    else:
        content = package

    html = service.to_html(package) if view == "full" else service.to_html(package)
    status = "FINAL"
    readiness = package.get("readiness") if isinstance(package.get("readiness"), dict) else {}
    if str(readiness.get("overall_state") or "").upper() == "NOT_READY":
        status = "PARTIAL"

    return {
        "title": title,
        "report_type": report_code,
        "report_date": filters.get("report_date") or utc_today(),
        "report_status": status,
        "official_report": False,
        "content": content,
        "executive_financial_package": package if view == "full" else None,
        "html": html,
        "formats": {"json": True, "html": True, "pdf": True},
        "limitations": (
            "Advisory management report from Phase 177 engine. "
            "Not audited statutory statements. Partial when MC financial feeds are thin."
        ),
        "readiness": readiness,
        "data_completeness": (package.get("financial_summary") or {}).get("data_completeness"),
        "evidence_index": package.get("evidence_index") or [],
        **SAFETY_LOCKS,
        "advisory_only": True,
        "trading_impact": False,
    }
