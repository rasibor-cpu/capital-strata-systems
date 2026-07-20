"""
Phase 177 — CanonicalFinancialReportingEngine (read-only, Decimal-safe).
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from backend.financial_reporting.balance_sheet import BalanceSheet, generate_balance_sheet
from backend.financial_reporting.cash_flow import CashFlowStatement, generate_cash_flow_statement
from backend.financial_reporting.data_contracts import FinancialDataContract
from backend.financial_reporting.income_statement import IncomeStatement, generate_income_statement
from backend.financial_reporting.models import deep_freeze_dict
from backend.financial_reporting.profitability_run_rate import (
    ProfitabilityRunRate,
    ProfitabilityRunRateConfig,
    generate_profitability_run_rate,
)
from backend.financial_reporting.readiness import FinancialReportingReadiness, evaluate_readiness

SCHEMA_VERSION = "css.canonical_financial_report.v1"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class CanonicalFinancialReportingEngine:
    """
    Single authoritative read-only financial reporting foundation.

    - No broker credentials
    - No execution side effects
    - Exception-isolated statement generation
    - Deterministic serialization (Decimals as strings)
    """

    def __init__(self, *, run_rate_config: ProfitabilityRunRateConfig | None = None) -> None:
        self.run_rate_config = run_rate_config or ProfitabilityRunRateConfig()

    def validate_input_contract(self, contract: FinancialDataContract) -> list[str]:
        issues: list[str] = []
        if not contract.currency:
            issues.append("currency missing")
        if contract.reporting_period is None:
            issues.append("reporting_period missing")
        return issues

    def generate_income_statement(self, contract: FinancialDataContract) -> IncomeStatement:
        return generate_income_statement(contract)

    def generate_balance_sheet(self, contract: FinancialDataContract) -> BalanceSheet:
        return generate_balance_sheet(contract)

    def generate_cash_flow_statement(self, contract: FinancialDataContract) -> CashFlowStatement:
        return generate_cash_flow_statement(contract)

    def generate_profitability_run_rate(
        self,
        contract: FinancialDataContract,
        income: IncomeStatement | None = None,
    ) -> ProfitabilityRunRate:
        stmt = income or self.generate_income_statement(contract)
        target = contract.target_profit.for_total()
        return generate_profitability_run_rate(
            actual_net_profit=stmt.net_profit,
            target_profit=target,
            period=contract.reporting_period,
            as_of=contract.as_of,
            config=self.run_rate_config,
        )

    def generate_financial_report_package(
        self,
        contract: FinancialDataContract,
        *,
        report_id: str | None = None,
    ) -> dict[str, Any]:
        # Immutability: work on a shallow structural copy of amount fields via mapping round-trip
        frozen_input = copy.deepcopy(contract.amount_dict())

        warnings: list[str] = []
        blockers: list[str] = []
        advisories: list[str] = [
            "Advisory-only management reporting foundation.",
            "Not a substitute for audited statutory financial statements.",
        ]

        validation = self.validate_input_contract(contract)
        blockers.extend(validation)

        income: IncomeStatement | None = None
        balance: BalanceSheet | None = None
        cash_flow: CashFlowStatement | None = None
        run_rate: ProfitabilityRunRate | None = None
        readiness: FinancialReportingReadiness | None = None

        try:
            income = self.generate_income_statement(contract)
            warnings.extend(income.warnings)
        except Exception as exc:  # noqa: BLE001
            blockers.append(f"income_statement_error:{type(exc).__name__}")

        try:
            balance = self.generate_balance_sheet(contract)
            warnings.extend(balance.warnings)
        except Exception as exc:  # noqa: BLE001
            blockers.append(f"balance_sheet_error:{type(exc).__name__}")

        try:
            cash_flow = self.generate_cash_flow_statement(contract)
            warnings.extend(cash_flow.warnings)
        except Exception as exc:  # noqa: BLE001
            blockers.append(f"cash_flow_error:{type(exc).__name__}")

        try:
            if income is not None:
                run_rate = self.generate_profitability_run_rate(contract, income)
                warnings.extend(run_rate.warnings)
        except Exception as exc:  # noqa: BLE001
            blockers.append(f"profitability_run_rate_error:{type(exc).__name__}")

        try:
            if income and balance and cash_flow and run_rate:
                readiness = evaluate_readiness(
                    contract=contract,
                    income=income,
                    balance=balance,
                    cash_flow=cash_flow,
                    run_rate=run_rate,
                )
                blockers.extend(readiness.blocking_items)
                warnings.extend(readiness.warning_items)
                advisories.extend(readiness.advisories)
        except Exception as exc:  # noqa: BLE001
            blockers.append(f"readiness_error:{type(exc).__name__}")

        generated = _utc_now()
        package = {
            "schema_version": SCHEMA_VERSION,
            "report_id": report_id or str(uuid4()),
            "generated_at": generated.isoformat().replace("+00:00", "Z"),
            "reporting_period": (
                contract.reporting_period.to_dict(as_of=contract.as_of)
                if contract.reporting_period
                else None
            ),
            "currency": contract.currency,
            "income_statement": income.to_dict() if income else None,
            "balance_sheet": balance.to_dict() if balance else None,
            "cash_flow_statement": cash_flow.to_dict() if cash_flow else None,
            "profitability_run_rate": run_rate.to_dict() if run_rate else None,
            "readiness": readiness.to_dict() if readiness else {
                "overall_state": "NOT_READY",
                "overall_score": 0.0,
            },
            "data_completeness": contract.data_completeness,
            "data_freshness": contract.data_freshness or generated.isoformat().replace("+00:00", "Z"),
            "warnings": sorted(set(warnings)),
            "blockers": sorted(set(blockers)),
            "advisories": list(dict.fromkeys(advisories)),
            "evidence": list(contract.evidence_references),
            "advisory_only": True,
            "trading_impact": False,
            "input_fingerprint": {
                "source_system": contract.source_system,
                "as_of": frozen_input.get("as_of"),
                "currency": frozen_input.get("currency"),
            },
        }
        return deep_freeze_dict(package)

    def to_dict(self, package: dict[str, Any]) -> dict[str, Any]:
        return deep_freeze_dict(package)


def empty_degraded_summary() -> dict[str, Any]:
    """Safe API fallback when upstream feeds are incomplete."""
    return deep_freeze_dict(
        {
            "schema_version": SCHEMA_VERSION,
            "report_id": "degraded",
            "generated_at": _utc_now().isoformat().replace("+00:00", "Z"),
            "reporting_period": None,
            "currency": "USD",
            "income_statement": None,
            "balance_sheet": None,
            "cash_flow_statement": None,
            "profitability_run_rate": {
                "traffic_light": "NOT_AVAILABLE",
                "confidence_status": "NOT_AVAILABLE",
            },
            "readiness": {
                "overall_state": "NOT_READY",
                "overall_score": 0.0,
                "blocking_items": ["Financial reporting inputs unavailable"],
            },
            "net_profit": None,
            "target_profit": None,
            "target_achieved_percentage": None,
            "required_daily_run_rate": None,
            "projected_period_end_profit": None,
            "warnings": ["Degraded financial reporting summary"],
            "blockers": ["upstream_unavailable"],
            "advisories": [
                "Advisory-only. No trading impact.",
                "Not a substitute for audited statutory financial statements.",
            ],
            "evidence": [],
            "advisory_only": True,
            "trading_impact": False,
        }
    )
