"""Canonical institutional report catalogue (Phase 176).

Every dashboard report entry must come from this registry. Entries marked
AVAILABLE / AVAILABLE_WITH_LIMITATIONS have known producers and evidence rules.
All others are registered honestly as COMING_SOON, DATA_UNAVAILABLE, or DISABLED.
"""

from __future__ import annotations

from dataclasses import replace

from backend.reports_center.constants import EMAIL_POLICY_DISABLED, EMAIL_POLICY_EXECUTIVE_BRIEF
from backend.reports_center.definition import CSSReportDefinition, defn
from backend.reports_center.narrative import adapter_for_category

# Canonical pre-generation validator for Reports Center producers (safe filters + dispatch).
_RC_VALIDATOR = "reports_center.producers.validate_filters"


def _apply_pdf_policy(item: CSSReportDefinition) -> CSSReportDefinition:
    """Phase 176G: generatable reports require HTML+PDF with primary_human_format=PDF."""
    if item.status not in {"AVAILABLE", "AVAILABLE_WITH_LIMITATIONS"} or not item.producer:
        return replace(
            item,
            pdf_required=False,
            pdf_supported=False,
            pdf_status="NOT_APPLICABLE",
            narrative_adapter="",
            primary_human_format="HTML",
            technical_export_formats=tuple(
                f for f in item.supported_formats if f not in {"HTML", "PDF"}
            ),
        )
    formats = list(item.supported_formats)
    if "HTML" not in formats:
        formats.insert(0, "HTML")
    if "PDF" not in formats:
        formats.append("PDF")
    tech = tuple(f for f in formats if f not in {"HTML", "PDF"})
    return replace(
        item,
        supported_formats=tuple(formats),
        pdf_required=True,
        pdf_supported=True,
        pdf_status="SUPPORTED",
        narrative_adapter=item.narrative_adapter or adapter_for_category(item.category),
        primary_human_format="PDF",
        technical_export_formats=tech or ("JSON",),
        printable=True,
    )


def _coming(
    code: str,
    title: str,
    category: str,
    *,
    desc: str = "",
    financial: bool = False,
    official: bool = False,
    inventory: str = "FUTURE_CAPABILITY",
    status: str = "COMING_SOON",
    evidence: tuple[str, ...] = (),
    limitations: str = "Not safely generatable in Phase 176; registered for catalogue completeness.",
) -> CSSReportDefinition:
    return defn(
        report_type=code,
        report_code=code,
        title=title,
        description=desc or title,
        category=category,
        status=status,
        inventory_class=inventory,
        contains_financial_values=financial,
        official_report=official,
        advisory_only=True,
        evidence_sources=evidence,
        limitations=limitations,
        printable=False,
        downloadable=False,
        emailable=False,
        email_policy=EMAIL_POLICY_DISABLED,
        producer="",
        menu_path=f"Reports / {category.replace('_', ' ').title()} / {title}",
    )


def build_catalogue() -> tuple[CSSReportDefinition, ...]:
    items: list[CSSReportDefinition] = []

    # ------------------------------------------------------------------ A. Executive Intelligence
    items.extend(
        [
            defn(
                report_type="daily_executive_brief",
                report_code="daily_executive_brief",
                title="Daily Executive Brief",
                description="Canonical Executive Morning Brief (Phases 174/175).",
                category="executive_intelligence",
                supported_scopes=("report_date",),
                supported_formats=("HTML", "PDF", "JSON", "Markdown"),
                producer="executive_intelligence.ExecutiveIntelligenceEngine",
                evidence_sources=(
                    "runtime_health",
                    "broker_health",
                    "portfolio",
                    "risk",
                    "overnight_market_intelligence",
                    "trading_intelligence",
                    "learning",
                ),
                validator="executive_intelligence.validator.validate_brief_for_final",
                archive_policy="morning_briefings_immutable_v1",
                official_report=True,
                advisory_only=True,
                contains_financial_values=True,
                printable=True,
                downloadable=True,
                emailable=True,
                email_policy=EMAIL_POLICY_EXECUTIVE_BRIEF,
                required_view_permission="reports_view",
                required_generate_permission="reports_generate",
                required_print_permission="executive_brief_print",
                required_email_permission="executive_brief_email",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                limitations="Market panel UNAVAILABLE blocks FINAL (fail-closed).",
                implementation_phase="174/175/176",
                menu_path="Reports / Executive Intelligence / Daily Executive Brief",
            ),
            defn(
                report_type="overnight_market_intelligence",
                report_code="overnight_market_intelligence",
                title="Overnight Market Intelligence Report",
                description="Standalone overnight market intelligence evidence report.",
                category="executive_intelligence",
                supported_scopes=("report_date",),
                supported_formats=("HTML", "JSON", "Markdown"),
                producer="executive_intelligence.overnight_market.produce_overnight_market_intelligence",
                evidence_sources=("regime", "runtime_advisory_snapshot", "portfolio_decision", "markets"),
                official_report=False,
                advisory_only=True,
                contains_financial_values=False,
                printable=True,
                downloadable=True,
                emailable=False,
                email_policy=EMAIL_POLICY_DISABLED,
                required_print_permission="executive_brief_print",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                implementation_phase="175/176",
                menu_path="Reports / Executive Intelligence / Overnight Market Intelligence",
            ),
            defn(
                report_type="executive_kpi_summary",
                report_code="executive_kpi_summary",
                title="Executive KPI Summary",
                description="KPI board extracted from Daily Executive Brief evidence.",
                category="executive_intelligence",
                supported_scopes=("report_date",),
                supported_formats=("HTML", "JSON"),
                producer="reports_center.producers.executive_kpi_summary",
                evidence_sources=("daily_executive_brief", "scoring"),
                official_report=False,
                advisory_only=True,
                contains_financial_values=True,
                printable=True,
                downloadable=True,
                required_print_permission="executive_brief_print",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                implementation_phase="176",
            ),
            defn(
                report_type="executive_actions_report",
                report_code="executive_actions_report",
                title="Executive Actions Report",
                description="Recommended executive actions from brief generation.",
                category="executive_intelligence",
                supported_scopes=("report_date",),
                supported_formats=("HTML", "JSON"),
                producer="reports_center.producers.executive_actions_report",
                evidence_sources=("daily_executive_brief", "actions"),
                official_report=False,
                advisory_only=True,
                printable=True,
                downloadable=True,
                required_print_permission="executive_brief_print",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                implementation_phase="176",
            ),
            defn(
                report_type="executive_risk_summary",
                report_code="executive_risk_summary",
                title="Executive Risk Summary",
                description="Risk posture summary derived from executive brief panels.",
                category="executive_intelligence",
                supported_scopes=("report_date",),
                supported_formats=("HTML", "JSON"),
                producer="reports_center.producers.executive_risk_summary",
                evidence_sources=("daily_executive_brief", "risk"),
                contains_financial_values=True,
                official_report=False,
                advisory_only=True,
                printable=True,
                downloadable=True,
                required_print_permission="executive_brief_print",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                implementation_phase="176",
            ),
            defn(
                report_type="executive_operational_health",
                report_code="executive_operational_health",
                title="Executive Operational Health Report",
                description="Operational health panel from executive brief evidence.",
                category="executive_intelligence",
                supported_scopes=("report_date",),
                supported_formats=("HTML", "JSON"),
                producer="reports_center.producers.executive_operational_health",
                evidence_sources=("runtime_health", "broker_health"),
                printable=True,
                downloadable=True,
                required_print_permission="executive_brief_print",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                implementation_phase="176",
            ),
            defn(
                report_type="historical_executive_brief_comparison",
                report_code="historical_executive_brief_comparison",
                title="Historical Executive Brief Comparison",
                description="Compare two archived FINAL morning briefs by date.",
                category="executive_intelligence",
                supported_scopes=("from_date", "to_date"),
                supported_formats=("HTML", "JSON"),
                producer="reports_center.producers.historical_brief_comparison",
                evidence_sources=("morning_briefings_archive",),
                printable=True,
                downloadable=True,
                required_print_permission="executive_brief_print",
                status="AVAILABLE_WITH_LIMITATIONS",
                inventory_class="PARTIAL",
                limitations="Comparison is advisory metadata/KPI delta; not a full narrative diff.",
                implementation_phase="176",
            ),
            defn(
                report_type="daily_brief_distribution_report",
                report_code="daily_brief_distribution_report",
                title="Daily Brief Distribution Report",
                description="Distribution and print audit summary for executive briefs.",
                category="executive_intelligence",
                supported_scopes=("report_date",),
                supported_formats=("HTML", "JSON"),
                producer="reports_center.producers.daily_brief_distribution_report",
                evidence_sources=("executive_brief_distribution_audit",),
                printable=True,
                downloadable=True,
                required_view_permission="reports_audit_view",
                required_print_permission="reports_print_all",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                implementation_phase="175/176",
            ),
        ]
    )

    # ------------------------------------------------------------------ B. Trading & Transactions
    items.append(
        defn(
            report_type="transaction_journal",
            report_code="transaction_journal",
            title="Transaction Journal",
            description="Filtered journal of canonical transaction / PnL ledger events.",
            category="trading_transactions",
            supported_scopes=(
                "date_range",
                "user",
                "trader",
                "strategy",
                "portfolio",
                "account",
                "broker",
                "asset_class",
                "instrument",
                "transaction_type",
                "status",
                "execution_mode",
            ),
            supported_formats=("HTML", "JSON", "CSV"),
            producer="reports_center.producers.transaction_journal",
            evidence_sources=("pnl_ledger", "reporting_store"),
            contains_financial_values=True,
            contains_personal_data=True,
            printable=True,
            downloadable=True,
            required_print_permission="trade_journal_print",
            status="AVAILABLE_WITH_LIMITATIONS",
            inventory_class="PARTIAL",
            limitations="Only events present in configured PnL ledger JSONL; missing fields are omitted, never invented.",
            implementation_phase="176",
        )
    )
    items.append(
        defn(
            report_type="trade_journal",
            report_code="trade_journal",
            title="Trade Journal",
            description="Trade-oriented view of ledger/execution evidence.",
            category="trading_transactions",
            supported_scopes=("date_range", "user", "instrument", "strategy", "broker"),
            supported_formats=("HTML", "JSON", "CSV"),
            producer="reports_center.producers.trade_journal",
            evidence_sources=("pnl_ledger",),
            contains_financial_values=True,
            contains_personal_data=True,
            printable=True,
            downloadable=True,
            required_print_permission="trade_journal_print",
            status="AVAILABLE_WITH_LIMITATIONS",
            inventory_class="PARTIAL",
            limitations="Derived from PnL ledger events; entry/exit/slippage fields included only when present.",
            implementation_phase="176",
        )
    )
    items.append(
        defn(
            report_type="transaction_ticket",
            report_code="transaction_ticket",
            title="Transaction Ticket / Trade Ticket",
            description="Printer-friendly ticket for a single execution/ledger transaction.",
            category="trading_transactions",
            supported_scopes=("transaction_id", "execution_id", "ledger_txn_id"),
            supported_formats=("HTML", "JSON"),
            producer="reports_center.producers.transaction_ticket",
            evidence_sources=("execution_report", "ledger_transaction"),
            contains_financial_values=True,
            contains_personal_data=True,
            printable=True,
            downloadable=True,
            required_print_permission="transaction_ticket_print",
            status="AVAILABLE_WITH_LIMITATIONS",
            inventory_class="IMPLEMENTED_BUT_NOT_REGISTERED",
            limitations="Requires supplied execution/ledger evidence; does not fabricate fills.",
            implementation_phase="176",
        )
    )
    for code, title in [
        ("order_journal", "Order Journal"),
        ("fill_execution_report", "Fill and Execution Report"),
        ("cancelled_rejected_orders", "Cancelled and Rejected Orders Report"),
        ("open_orders_report", "Open Orders Report"),
        ("closed_trades_report", "Closed Trades Report"),
        ("trade_exception_report", "Trade Exception Report"),
        ("trade_correction_audit", "Trade Correction/Amendment Audit"),
        ("strategy_trade_activity", "Strategy Trade Activity Report"),
        ("user_trader_activity", "User/Trader Activity Report"),
        ("instrument_activity", "Instrument Activity Report"),
        ("daily_trade_blotter", "Daily Trade Blotter"),
        ("historical_trade_blotter", "Historical Trade Blotter"),
        ("paper_trading_activity", "Paper Trading Activity Report"),
        ("live_execution_activity", "Live Execution Activity Report"),
        ("advisory_recommendations_journal", "Advisory Recommendations Journal"),
    ]:
        status = "DISABLED" if code == "live_execution_activity" else "COMING_SOON"
        inventory = "PROHIBITED_OR_NOT_APPLICABLE" if code == "live_execution_activity" else "FUTURE_CAPABILITY"
        limitations = (
            "Live execution reports are disabled while live_trading_blocked=true."
            if code == "live_execution_activity"
            else "Registered; producer/evidence incomplete for official catalogue generation."
        )
        items.append(
            _coming(
                code,
                title,
                "trading_transactions",
                financial=True,
                status=status,
                inventory=inventory,
                limitations=limitations,
            )
        )

    # ------------------------------------------------------------------ C. Accounts & Cash
    items.append(
        defn(
            report_type="account_statement",
            report_code="account_statement",
            title="Account Statement",
            description="Account activity statement from available ledger evidence.",
            category="accounts_cash",
            supported_scopes=("account", "user", "portfolio", "broker", "currency", "date_range"),
            supported_formats=("HTML", "JSON"),
            producer="reports_center.producers.account_statement",
            evidence_sources=("pnl_ledger", "portfolio_snapshot"),
            contains_financial_values=True,
            printable=True,
            downloadable=True,
            required_print_permission="account_statement_print",
            status="AVAILABLE_WITH_LIMITATIONS",
            inventory_class="PARTIAL",
            limitations=(
                "Full double-entry account ledger is incomplete. Statement is advisory with "
                "limitation banner; not an official complete accounting statement."
            ),
            official_report=False,
            advisory_only=True,
            implementation_phase="176",
        )
    )
    for code, title, inv in [
        ("cash_statement", "Cash Statement", "DATA_AVAILABLE_BUT_NO_REPORT"),
        ("cash_movement_journal", "Cash Movement Journal", "DATA_AVAILABLE_BUT_NO_REPORT"),
        ("deposit_withdrawal_report", "Deposit and Withdrawal Report", "DATA_INSUFFICIENT"),
        ("multi_currency_cash_balance", "Multi-Currency Cash Balance Report", "DATA_INSUFFICIENT"),
        ("account_activity_report", "Account Activity Report", "DATA_AVAILABLE_BUT_NO_REPORT"),
        ("account_reconciliation", "Account Reconciliation Report", "DATA_INSUFFICIENT"),
        ("broker_statement_reconciliation", "Broker Statement Reconciliation Report", "DATA_INSUFFICIENT"),
        ("fees_charges_report", "Fees and Charges Report", "PARTIAL"),
        ("interest_financing_report", "Interest and Financing Report", "DATA_INSUFFICIENT"),
        ("dividend_distribution_report", "Dividend and Distribution Report", "DATA_INSUFFICIENT"),
        ("tax_lot_report", "Tax-Lot Report", "DATA_INSUFFICIENT"),
        ("realized_gain_loss", "Realized Gain/Loss Report", "PARTIAL"),
        ("unrealized_gain_loss", "Unrealized Gain/Loss Report", "PARTIAL"),
        ("currency_translation", "Currency Translation Report", "DATA_INSUFFICIENT"),
        ("nav_statement", "NAV Statement", "DATA_INSUFFICIENT"),
        ("investor_client_statement", "Investor/Client Statement", "FUTURE_CAPABILITY"),
    ]:
        st = "COMING_SOON"
        if inv == "FUTURE_CAPABILITY" and code == "investor_client_statement":
            st = "COMING_SOON"
        items.append(
            _coming(
                code,
                title,
                "accounts_cash",
                financial=True,
                inventory=inv,
                status=st,
                limitations="Not exposed as GENERATABLE until accounting evidence and validation exist.",
            )
        )

    # FinCon ageing via existing printer (limitations)
    for code, title in [
        ("ar_ageing", "AR Ageing Report"),
        ("ap_ageing", "AP Ageing Report"),
        ("gl_ageing", "GL Ageing Report"),
    ]:
        items.append(
            defn(
                report_type=code,
                report_code=code,
                title=title,
                description=f"FinCon {title} via report_printer.",
                category="accounts_cash",
                supported_scopes=("as_of_date",),
                supported_formats=("HTML",),
                producer="engine.reporting.report_printer",
                evidence_sources=("ageing_reports",),
                contains_financial_values=True,
                printable=True,
                downloadable=True,
                required_print_permission="account_statement_print",
                status="AVAILABLE_WITH_LIMITATIONS",
                inventory_class="IMPLEMENTED_BUT_NOT_REGISTERED",
                limitations="Depends on ageing input filters; empty when no AR/AP/GL evidence supplied.",
                implementation_phase="176",
            )
        )

    # ------------------------------------------------------------------ D. Portfolio & Performance
    items.append(
        defn(
            report_type="portfolio_summary",
            report_code="portfolio_summary",
            title="Portfolio Summary",
            description="Portfolio equity/cash/exposure summary from runtime evidence.",
            category="portfolio_performance",
            supported_scopes=("report_date", "portfolio"),
            supported_formats=("HTML", "JSON"),
            producer="reports_center.producers.portfolio_summary",
            evidence_sources=("portfolio_snapshot", "runtime_state"),
            contains_financial_values=True,
            printable=True,
            downloadable=True,
            required_print_permission="portfolio_report_print",
            status="AVAILABLE_WITH_LIMITATIONS",
            inventory_class="PARTIAL",
            limitations="Uses advisory runtime/portfolio evidence only; not a certified NAV statement.",
            implementation_phase="176",
        )
    )
    items.append(
        defn(
            report_type="pnl_report",
            report_code="pnl_report",
            title="PnL Report",
            description="PnL period summary from PnL ledger events.",
            category="portfolio_performance",
            supported_scopes=("date_range", "mode"),
            supported_formats=("HTML", "JSON"),
            producer="reports_center.producers.pnl_report",
            evidence_sources=("pnl_ledger", "pnl_report_engine"),
            contains_financial_values=True,
            printable=True,
            downloadable=True,
            required_print_permission="portfolio_report_print",
            status="AVAILABLE_WITH_LIMITATIONS",
            inventory_class="IMPLEMENTED_BUT_NOT_REGISTERED",
            limitations="Ledger-backed only; empty ledger yields empty FINAL with limitation banner.",
            implementation_phase="176",
        )
    )
    # Phase 178 — Executive Financial Reporting Suite (Phase 177-backed)
    for code, title, desc, view_hint in [
        (
            "executive_financial_summary",
            "Executive Financial Summary",
            "Executive financial summary derived from the Phase 177 Canonical Financial Reporting Engine.",
            "summary",
        ),
        (
            "canonical_income_statement",
            "Income Statement",
            "Canonical income statement from Phase 177 (management reporting).",
            "income",
        ),
        (
            "canonical_balance_sheet",
            "Balance Sheet",
            "Canonical balance sheet from Phase 177 (management reporting).",
            "balance",
        ),
        (
            "canonical_cash_flow_statement",
            "Cash-Flow Statement",
            "Canonical cash-flow statement from Phase 177 (management reporting).",
            "cash",
        ),
        (
            "profitability_run_rate_report",
            "Profitability Run-Rate Report",
            "Target profit versus actual run-rate from Phase 177.",
            "run_rate",
        ),
    ]:
        items.append(
            defn(
                report_type=code,
                report_code=code,
                title=title,
                description=desc,
                category="portfolio_performance",
                supported_scopes=("report_date", "period"),
                supported_formats=("HTML", "JSON", "PDF"),
                producer=f"reports_center.producers.{code}",
                evidence_sources=(
                    "canonical_financial_reporting",
                    "mission_control.portfolio",
                ),
                contains_financial_values=True,
                printable=True,
                downloadable=True,
                required_print_permission="portfolio_report_print",
                status="AVAILABLE_WITH_LIMITATIONS",
                inventory_class="PARTIAL",
                limitations=(
                    "Advisory management reporting from Phase 177. "
                    "Not audited statutory statements. "
                    f"Producer view={view_hint}."
                ),
                implementation_phase="178",
                menu_path=f"Reports / Portfolio Performance / {title}",
            )
        )
    for code, title in [
        ("portfolio_holdings", "Portfolio Holdings Report"),
        ("position_statement", "Position Statement"),
        ("open_positions_report", "Open Positions Report"),
        ("closed_positions_report", "Closed Positions Report"),
        ("exposure_by_asset_class", "Exposure by Asset Class"),
        ("exposure_by_currency", "Exposure by Currency"),
        ("exposure_by_strategy", "Exposure by Strategy"),
        ("exposure_by_broker", "Exposure by Broker"),
        ("exposure_by_instrument", "Exposure by Instrument"),
        ("daily_pnl", "Daily PnL"),
        ("period_pnl", "Period PnL"),
        ("realized_unrealized_pnl", "Realized/Unrealized PnL"),
        ("performance_summary", "Performance Summary"),
        ("performance_attribution", "Performance Attribution"),
        ("strategy_attribution", "Strategy Attribution"),
        ("asset_class_attribution", "Asset-Class Attribution"),
        ("broker_execution_attribution", "Broker/Execution Attribution"),
        ("return_history", "Return History"),
        ("drawdown_report_portfolio", "Drawdown Report"),
        ("capital_allocation", "Capital Allocation Report"),
        ("capital_efficiency", "Capital Efficiency Report"),
        ("concentration_report", "Concentration Report"),
        ("turnover_report", "Turnover Report"),
        ("benchmark_comparison", "Benchmark Comparison"),
        ("portfolio_valuation", "Portfolio Valuation Report"),
        ("portfolio_snapshot", "Portfolio Snapshot"),
        ("portfolio_decision_report", "Portfolio Decision Report"),
        ("position_aging", "Position Aging Report"),
    ]:
        items.append(
            _coming(
                code,
                title,
                "portfolio_performance",
                financial=True,
                inventory="DATA_AVAILABLE_BUT_NO_REPORT" if "exposure" in code or "position" in code else "FUTURE_CAPABILITY",
            )
        )

    # ------------------------------------------------------------------ E. Risk
    items.append(
        defn(
            report_type="risk_summary",
            report_code="risk_summary",
            title="Risk Summary",
            description="Risk posture from runtime/executive risk evidence.",
            category="risk_exposure",
            supported_scopes=("report_date",),
            supported_formats=("HTML", "JSON"),
            producer="reports_center.producers.risk_summary",
            evidence_sources=("risk_snapshot", "executive_brief"),
            contains_financial_values=True,
            printable=True,
            downloadable=True,
            required_print_permission="risk_report_print",
            status="AVAILABLE_WITH_LIMITATIONS",
            inventory_class="PARTIAL",
            limitations="No validated VaR engine is claimed; summary is advisory.",
            implementation_phase="176",
        )
    )
    items.append(
        defn(
            report_type="safety_lock_report",
            report_code="safety_lock_report",
            title="Safety-Lock Report",
            description="Canonical advisory/safety lock confirmation.",
            category="risk_exposure",
            supported_scopes=(),
            supported_formats=("HTML", "JSON"),
            producer="reports_center.producers.safety_lock_report",
            evidence_sources=("SAFETY_LOCKS",),
            printable=True,
            downloadable=True,
            required_print_permission="risk_report_print",
            status="AVAILABLE",
            inventory_class="IMPLEMENTED_AND_RELIABLE",
            official_report=True,
            advisory_only=True,
            implementation_phase="176",
        )
    )
    for code, title, inv in [
        ("risk_limit_utilization", "Risk Limit Utilization", "PARTIAL"),
        ("var_report", "VaR Report", "DATA_INSUFFICIENT"),
        ("stress_test_report", "Stress-Test Report", "DATA_INSUFFICIENT"),
        ("scenario_analysis", "Scenario Analysis", "DATA_INSUFFICIENT"),
        ("drawdown_report_risk", "Drawdown Report", "PARTIAL"),
        ("exposure_report", "Exposure Report", "PARTIAL"),
        ("concentration_risk", "Concentration Risk", "PARTIAL"),
        ("liquidity_risk", "Liquidity Risk", "DATA_INSUFFICIENT"),
        ("counterparty_risk", "Counterparty Risk", "DATA_INSUFFICIENT"),
        ("broker_risk", "Broker Risk", "PARTIAL"),
        ("currency_risk", "Currency Risk", "DATA_INSUFFICIENT"),
        ("interest_rate_risk", "Interest Rate Risk", "DATA_INSUFFICIENT"),
        ("options_greeks_report", "Options Greeks Report", "PARTIAL"),
        ("futures_margin_report", "Futures Margin Report", "DATA_INSUFFICIENT"),
        ("margin_utilization", "Margin Utilization", "PARTIAL"),
        ("leverage_report", "Leverage Report", "DATA_INSUFFICIENT"),
        ("stop_loss_risk_breach", "Stop-Loss and Risk-Breach Report", "PARTIAL"),
        ("antibleedguard_activity", "AntiBleedGuard Activity Report", "PARTIAL"),
        ("risk_committee_decisions", "Risk Committee Decisions", "DATA_INSUFFICIENT"),
        ("trade_veto_report", "Trade Veto Report", "PARTIAL"),
        ("risk_exceptions", "Risk Exceptions", "PARTIAL"),
        ("risk_alerts", "Risk Alerts", "PARTIAL"),
        ("risk_trend_report", "Risk Trend Report", "DATA_INSUFFICIENT"),
        ("pre_trade_risk_decisions", "Pre-Trade Risk Decisions", "PARTIAL"),
        ("post_trade_risk_review", "Post-Trade Risk Review", "DATA_INSUFFICIENT"),
    ]:
        st = "DATA_UNAVAILABLE" if inv == "DATA_INSUFFICIENT" else "COMING_SOON"
        items.append(_coming(code, title, "risk_exposure", financial=True, inventory=inv, status=st))

    # ------------------------------------------------------------------ F. Broker
    items.append(
        defn(
            report_type="broker_health_report",
            report_code="broker_health_report",
            title="Broker Health Report",
            description="Sanitized broker health/connectivity summary (no secrets).",
            category="broker_execution",
            supported_scopes=("report_date",),
            supported_formats=("HTML", "JSON"),
            producer="reports_center.producers.broker_health_report",
            evidence_sources=("broker_health", "broker_registry"),
            printable=True,
            downloadable=True,
            required_print_permission="reports_print_all",
            status="AVAILABLE",
            inventory_class="IMPLEMENTED_AND_RELIABLE",
            limitations="Credentials and tokens are never included.",
            implementation_phase="176",
        )
    )
    for code, title in [
        ("broker_connectivity", "Broker Connectivity Report"),
        ("broker_readiness", "Broker Readiness Report"),
        ("broker_credential_readiness", "Broker Credential-Readiness Summary"),
        ("execution_quality", "Execution Quality Report"),
        ("slippage_report", "Slippage Report"),
        ("fill_quality", "Fill Quality Report"),
        ("quote_freshness", "Quote Freshness Report"),
        ("broker_latency", "Broker Latency Report"),
        ("broker_disconnect", "Broker Disconnect Report"),
        ("broker_recovery", "Broker Recovery Report"),
        ("broker_reconciliation", "Broker Reconciliation Report"),
        ("broker_performance_comparison", "Broker Performance Comparison"),
        ("venue_activity", "Venue Activity Report"),
        ("broker_capability", "Broker Capability Report"),
        ("broker_advisory_authority", "Broker Advisory/Execution Authority Report"),
        ("broker_incident", "Broker Incident Report"),
        ("commission_fee_comparison", "Commission and Fee Comparison"),
    ]:
        items.append(_coming(code, title, "broker_execution", inventory="PARTIAL" if "readiness" in code or "capability" in code else "FUTURE_CAPABILITY"))

    # ------------------------------------------------------------------ G. Treasury
    items.append(
        defn(
            report_type="treasury_instrument_aggregate",
            report_code="treasury_instrument_aggregate",
            title="Treasury Instrument Aggregate",
            description="FinCon treasury aggregate — books not implemented.",
            category="treasury",
            supported_scopes=("date_range", "as_of_date"),
            supported_formats=("HTML",),
            producer="engine.reporting.treasury_instrument_aggregate",
            evidence_sources=(),
            status="DATA_UNAVAILABLE",
            inventory_class="DATA_INSUFFICIENT",
            limitations="Module restored as fail-closed stub; does not synthesize treasury books.",
            printable=False,
            downloadable=False,
            implementation_phase="176",
        )
    )
    for code, title in [
        ("cash_position_report", "Cash Position Report"),
        ("liquidity_position", "Liquidity Position"),
        ("currency_exposure_treasury", "Currency Exposure"),
        ("fx_position_report", "FX Position Report"),
        ("fx_gain_loss", "FX Gain/Loss"),
        ("funding_financing", "Funding and Financing"),
        ("cash_forecast", "Cash Forecast"),
        ("maturity_ladder", "Maturity Ladder"),
        ("interest_rate_exposure", "Interest Rate Exposure"),
        ("hedge_position_report", "Hedge Position Report"),
        ("hedge_effectiveness", "Hedge Effectiveness"),
        ("fx_forward_report", "FX Forward Report"),
        ("fx_swap_report", "FX Swap Report"),
        ("cross_currency_swap_report", "Cross-Currency Swap Report"),
        ("treasury_transaction_journal", "Treasury Transaction Journal"),
        ("treasury_counterparty_exposure", "Treasury Counterparty Exposure"),
        ("treasury_limit_utilization", "Treasury Limit Utilization"),
        ("multi_currency_position", "Multi-Currency Position Report"),
    ]:
        items.append(
            _coming(
                code,
                title,
                "treasury",
                financial=True,
                inventory="FUTURE_CAPABILITY",
                status="COMING_SOON",
                limitations="Treasury books not implemented; registered only.",
            )
        )

    # ------------------------------------------------------------------ H. Compliance & Audit
    items.extend(
        [
            defn(
                report_type="report_access_audit",
                report_code="report_access_audit",
                title="Report Access Audit",
                description="Unified report access/view audit trail.",
                category="compliance_audit",
                supported_scopes=("date_range",),
                supported_formats=("HTML", "JSON"),
                producer="reports_center.producers.report_access_audit",
                evidence_sources=("report_audit_log",),
                printable=True,
                downloadable=True,
                required_view_permission="reports_audit_view",
                required_print_permission="reports_print_all",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                implementation_phase="176",
            ),
            defn(
                report_type="report_print_audit",
                report_code="report_print_audit",
                title="Report Print Audit",
                description="Print events across Reports Center and executive brief.",
                category="compliance_audit",
                supported_scopes=("date_range",),
                supported_formats=("HTML", "JSON"),
                producer="reports_center.producers.report_print_audit",
                evidence_sources=("report_audit_log", "executive_brief_print_audit"),
                printable=True,
                downloadable=True,
                required_view_permission="reports_audit_view",
                required_print_permission="reports_print_all",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                implementation_phase="175/176",
            ),
            defn(
                report_type="report_email_distribution_audit",
                report_code="report_email_distribution_audit",
                title="Report Email Distribution Audit",
                description="Email distribution audit (privacy-safe).",
                category="compliance_audit",
                supported_scopes=("date_range",),
                supported_formats=("HTML", "JSON"),
                producer="reports_center.producers.report_email_distribution_audit",
                evidence_sources=("executive_brief_email_audit",),
                printable=True,
                downloadable=True,
                required_view_permission="reports_audit_view",
                required_print_permission="reports_print_all",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                implementation_phase="175/176",
            ),
            defn(
                report_type="archived_report_manifest",
                report_code="archived_report_manifest",
                title="Archived Report Manifest",
                description="Manifest of archived institutional and morning brief reports.",
                category="compliance_audit",
                supported_scopes=("date_range", "category"),
                supported_formats=("HTML", "JSON"),
                producer="reports_center.producers.archived_report_manifest",
                evidence_sources=("reports_archive", "morning_briefings_archive"),
                printable=True,
                downloadable=True,
                required_view_permission="reports_audit_view",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                implementation_phase="176",
            ),
            defn(
                report_type="report_integrity_verification",
                report_code="report_integrity_verification",
                title="Report Integrity/Hash Verification Report",
                description="Verify archived report hashes.",
                category="compliance_audit",
                supported_scopes=("report_id",),
                supported_formats=("HTML", "JSON"),
                producer="reports_center.producers.report_integrity_verification",
                evidence_sources=("manifest", "report_hash"),
                printable=True,
                downloadable=True,
                required_view_permission="reports_audit_view",
                status="AVAILABLE",
                inventory_class="IMPLEMENTED_AND_RELIABLE",
                implementation_phase="176",
            ),
            defn(
                report_type="governance_summary",
                report_code="governance_summary",
                title="Governance Summary",
                description="FinCon governance allow/block summary.",
                category="compliance_audit",
                supported_scopes=("date_range",),
                supported_formats=("HTML",),
                producer="engine.reporting.report_printer",
                evidence_sources=("audit_logs/governance_decisions.jsonl",),
                printable=True,
                downloadable=True,
                status="AVAILABLE_WITH_LIMITATIONS",
                inventory_class="IMPLEMENTED_BUT_NOT_REGISTERED",
                limitations="Empty when governance log is absent.",
                implementation_phase="176",
            ),
            defn(
                report_type="supervisory_control_pack",
                report_code="supervisory_control_pack",
                title="Supervisory Control Pack",
                description="Daily supervisory control pack (FinCon SCP).",
                category="compliance_audit",
                supported_scopes=("date", "mode"),
                supported_formats=("HTML",),
                producer="engine.reporting.supervisory_control_pack",
                evidence_sources=("supervisory_control_pack",),
                printable=True,
                downloadable=True,
                status="AVAILABLE_WITH_LIMITATIONS",
                inventory_class="IMPLEMENTED_BUT_NOT_REGISTERED",
                implementation_phase="176",
            ),
        ]
    )
    for code, title, inv in [
        ("user_activity_audit", "User Activity Audit", "PARTIAL"),
        ("role_permission_report", "Role and Permission Report", "PARTIAL"),
        ("login_session_audit", "Login and Session Audit", "PARTIAL"),
        ("trade_authorization_audit", "Trade Authorization Audit", "PARTIAL"),
        ("execution_authority_report", "Execution Authority Report", "PARTIAL"),
        ("rbac_changes_report", "RBAC Changes Report", "PARTIAL"),
        ("staff_print_grant_report", "Staff Print-Grant Report", "IMPLEMENTED_AND_RELIABLE"),
        ("admin_super_distribution_report", "Admin/Super-User Distribution Report", "PARTIAL"),
        ("configuration_change_audit", "Configuration Change Audit", "PARTIAL"),
        ("runtime_change_audit", "Runtime Change Audit", "PARTIAL"),
        ("decision_provenance_report", "Decision Provenance Report", "PARTIAL"),
        ("model_strategy_decision_audit", "Model/Strategy Decision Audit", "PARTIAL"),
        ("exception_report", "Exception Report", "PARTIAL"),
        ("incident_report_compliance", "Incident Report", "PARTIAL"),
        ("recovery_report_compliance", "Recovery Report", "PARTIAL"),
        ("data_freshness_audit", "Data-Freshness Audit", "PARTIAL"),
        ("advisory_only_compliance", "Advisory-Only Compliance Report", "IMPLEMENTED_AND_RELIABLE"),
        ("data_retention_report", "Data-Retention Report", "FUTURE_CAPABILITY"),
    ]:
        if code == "staff_print_grant_report":
            items.append(
                defn(
                    report_type=code,
                    report_code=code,
                    title=title,
                    description="Staff executive-brief print grant inventory (no email grants).",
                    category="compliance_audit",
                    supported_formats=("HTML", "JSON"),
                    producer="reports_center.producers.staff_print_grant_report",
                    evidence_sources=("executive_brief_grants",),
                    required_view_permission="reports_audit_view",
                    printable=True,
                    downloadable=True,
                    status="AVAILABLE",
                    inventory_class=inv,
                    implementation_phase="175/176",
                )
            )
        elif code == "advisory_only_compliance":
            items.append(
                defn(
                    report_type=code,
                    report_code=code,
                    title=title,
                    description="Confirms advisory-only / live-trading-blocked posture.",
                    category="compliance_audit",
                    supported_formats=("HTML", "JSON"),
                    producer="reports_center.producers.advisory_only_compliance",
                    evidence_sources=("SAFETY_LOCKS",),
                    status="AVAILABLE",
                    inventory_class=inv,
                    printable=True,
                    downloadable=True,
                    implementation_phase="176",
                )
            )
        else:
            items.append(_coming(code, title, "compliance_audit", inventory=inv))

    # ------------------------------------------------------------------ I. Operations
    items.append(
        defn(
            report_type="runtime_health",
            report_code="runtime_health",
            title="Runtime Health",
            description="Runtime health / heartbeat continuity from evidence.",
            category="operations_system",
            supported_scopes=("report_date",),
            supported_formats=("HTML", "JSON"),
            producer="reports_center.producers.runtime_health",
            evidence_sources=("runtime_health", "supervisor"),
            printable=True,
            downloadable=True,
            status="AVAILABLE",
            inventory_class="IMPLEMENTED_AND_RELIABLE",
            implementation_phase="176",
        )
    )
    items.append(
        defn(
            report_type="report_generation_failures",
            report_code="report_generation_failures",
            title="Report Generation Failures",
            description="FAILED report generations from Reports Center audit/archive.",
            category="operations_system",
            supported_scopes=("date_range",),
            supported_formats=("HTML", "JSON"),
            producer="reports_center.producers.report_generation_failures",
            evidence_sources=("report_audit_log", "reports_archive"),
            printable=True,
            downloadable=True,
            required_view_permission="reports_audit_view",
            status="AVAILABLE",
            inventory_class="IMPLEMENTED_AND_RELIABLE",
            implementation_phase="176",
        )
    )
    for code, title in [
        ("runtime_supervisor", "Runtime Supervisor"),
        ("heartbeat_continuity", "Heartbeat Continuity"),
        ("runtime_cycle_summary", "Runtime Cycle Summary"),
        ("system_availability", "System Availability"),
        ("service_status", "Service Status"),
        ("restart_recovery", "Restart and Recovery"),
        ("runtime_error_report", "Runtime Error Report"),
        ("alert_summary", "Alert Summary"),
        ("operational_incident", "Operational Incident Report"),
        ("artifact_freshness", "Artifact Freshness"),
        ("data_availability", "Data Availability"),
        ("mission_control_status", "Mission Control Status"),
        ("mobile_dashboard_status", "Mobile Dashboard Status"),
        ("system_readiness", "System Readiness"),
        ("production_readiness", "Production Readiness"),
        ("endurance_test_report", "Endurance Test Report"),
        ("environment_diagnostics", "Environment Diagnostics"),
        ("compatibility_report", "Compatibility Report"),
        ("capability_matrix", "Capability Matrix"),
        ("release_certification", "Release Certification Report"),
        ("test_execution_report", "Test Execution Report"),
        ("backup_recovery_status", "Backup/Recovery Status"),
        ("storage_archive_health", "Storage and Archive Health"),
    ]:
        items.append(_coming(code, title, "operations_system", inventory="PARTIAL" if "runtime" in code or "readiness" in code else "FUTURE_CAPABILITY"))

    # ------------------------------------------------------------------ Distribution & Print Audit (menu family)
    items.append(
        defn(
            report_type="distribution_print_audit_home",
            report_code="distribution_print_audit_home",
            title="Distribution & Print Audit Summary",
            description="Roll-up of print and email distribution audits.",
            category="distribution_print_audit",
            supported_formats=("HTML", "JSON"),
            producer="reports_center.producers.distribution_print_audit_home",
            evidence_sources=("report_audit_log",),
            required_view_permission="reports_audit_view",
            printable=True,
            downloadable=True,
            status="AVAILABLE",
            inventory_class="IMPLEMENTED_AND_RELIABLE",
            implementation_phase="176",
        )
    )

    # uniqueness check
    codes = [i.report_code for i in items]
    if len(codes) != len(set(codes)):
        dupes = sorted({c for c in codes if codes.count(c) > 1})
        raise RuntimeError(f"duplicate report codes: {dupes}")

    # Ensure every AVAILABLE / AVAILABLE_WITH_LIMITATIONS entry has a defined validator.
    # Daily executive brief already carries its Phase 174 FINAL validator.
    filled: list[CSSReportDefinition] = []
    for item in items:
        if item.status in {"AVAILABLE", "AVAILABLE_WITH_LIMITATIONS"} and not item.validator:
            item = replace(item, validator=_RC_VALIDATOR)
        filled.append(_apply_pdf_policy(item))
    return tuple(filled)


CATALOGUE: tuple[CSSReportDefinition, ...] = build_catalogue()
