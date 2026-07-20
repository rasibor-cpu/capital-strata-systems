"""
Phase 177 — Canonical Financial Reporting Engine (read-only foundation).

Advisory management-reporting layer. Not a substitute for audited statutory statements.
Does not alter trading, brokers, execution, or runtime authority.
"""

from backend.financial_reporting.engine import CanonicalFinancialReportingEngine
from backend.financial_reporting.models import FinancialAmount, MissingReason, ReportingPeriodType
from backend.financial_reporting.periods import ReportingPeriod

__all__ = [
    "CanonicalFinancialReportingEngine",
    "FinancialAmount",
    "MissingReason",
    "ReportingPeriod",
    "ReportingPeriodType",
]
