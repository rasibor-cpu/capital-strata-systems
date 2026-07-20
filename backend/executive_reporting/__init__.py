"""
Phase 178 — Executive Financial Reporting Suite.

Derives exclusively from Phase 177 Canonical Financial Reporting Engine.
Advisory management reporting only — not audited statutory statements.
trading_impact=false. No trading / broker / execution authority.
"""

from backend.executive_reporting.package import (
    ExecutiveFinancialReportPackage,
    build_executive_financial_report_package,
)
from backend.executive_reporting.service import ExecutiveFinancialReportingService
from backend.executive_reporting.summary import ExecutiveFinancialSummary, build_executive_financial_summary

__all__ = [
    "ExecutiveFinancialReportPackage",
    "ExecutiveFinancialReportingService",
    "ExecutiveFinancialSummary",
    "build_executive_financial_report_package",
    "build_executive_financial_summary",
]
