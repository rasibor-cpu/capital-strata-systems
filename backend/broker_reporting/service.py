"""
Phase 177C — Broker executive report builders.

Re-export package entrypoints for Reports Center / Mission Control consumers.
"""

from __future__ import annotations

from backend.broker_reporting import (
    BrokerExecutiveReportPackage,
    build_broker_executive_report_package,
)

__all__ = [
    "BrokerExecutiveReportPackage",
    "build_broker_executive_report_package",
]
