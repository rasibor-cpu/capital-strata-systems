"""Plain-English narrative adapters for institutional PDF reports (Phase 176G).

Every statement is derived from the archived report payload. Missing evidence is
stated plainly. Internal codes are translated in the main body; raw codes may
appear only in a technical appendix.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.reports_center.constants import SAFETY_LOCKS

RENDERER_VERSION = "css.report_pdf.v176g"

# Main-body translations (never fabricate beyond these mappings + payload facts).
_CODE_PLAIN: dict[str, str] = {
    "market_panel_unavailable": (
        "The report could not obtain sufficient current market information. "
        "The market section is therefore unavailable, and the report has not been finalized."
    ),
    "execution_allowed=false": "Live trade execution was not authorized when this report was generated.",
    "execution_allowed": "Live trade execution authorization status",
    "broker_execution_armed=false": "No broker was armed for order execution.",
    "broker_execution_armed": "Broker execution arming status",
    "live_trading_blocked=true": "Live trading remains blocked by safety policy.",
    "live_trading_blocked": "Live trading block status",
    "advisory_only=true": "This report is advisory only and is not an execution authorization.",
    "advisory_only": "Advisory classification",
    "AVAILABLE": "Available",
    "AVAILABLE_WITH_LIMITATIONS": "Available with limitations",
    "COMING_SOON": "Coming soon",
    "DATA_UNAVAILABLE": "Data unavailable",
    "DISABLED": "Disabled",
    "FINAL": "Final",
    "DRAFT": "Draft",
    "FAILED": "Failed",
    "PARTIAL": "Partial",
    "UNAVAILABLE": "Unavailable",
    "KNOWN": "Known",
    "INSUFFICIENT_OR_UNREGISTERED": "Insufficient or unregistered evidence",
}

_CATEGORY_ADAPTER: dict[str, str] = {
    "executive_intelligence": "executive_intelligence",
    "trading_transactions": "trading_transactions",
    "accounts_cash": "accounts_cash",
    "portfolio_performance": "portfolio_performance",
    "risk_exposure": "risk_exposure",
    "broker_execution": "broker_execution",
    "treasury": "treasury",
    "compliance_audit": "compliance_audit",
    "operations_system": "operations_system",
    "distribution_print_audit": "compliance_audit",
}


def adapter_for_category(category: str) -> str:
    return _CATEGORY_ADAPTER.get(str(category or ""), "operations_system")


def translate_code(value: Any) -> str:
    text = str(value if value is not None else "UNAVAILABLE")
    if text in _CODE_PLAIN:
        return _CODE_PLAIN[text]
    lower = text.lower()
    for key, plain in _CODE_PLAIN.items():
        if key.lower() == lower:
            return plain
    # Boolean-style flags embedded in prose
    if text.endswith("=false") and text[:-6] in {"execution_allowed", "broker_execution_armed"}:
        return _CODE_PLAIN.get(text, text)
    if text.endswith("=true") and text[:-5] in {"live_trading_blocked", "advisory_only"}:
        return _CODE_PLAIN.get(text, text)
    return text.replace("_", " ")


def _as_map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _plain_list(items: Any, *, limit: int = 12) -> list[str]:
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for item in items[:limit]:
        if isinstance(item, Mapping):
            title = item.get("title") or item.get("name") or item.get("type") or item.get("code")
            detail = item.get("detail") or item.get("message") or item.get("description") or ""
            if title and detail:
                out.append(f"{translate_code(title)} — {translate_code(detail)}")
            elif title:
                out.append(translate_code(title))
            else:
                out.append(translate_code(detail or item))
        else:
            out.append(translate_code(item))
    return out


def build_narrative(
    report: Mapping[str, Any],
    *,
    definition: Mapping[str, Any] | None = None,
    printed_by: str = "system",
    generated_at_utc: str = "",
) -> dict[str, Any]:
    """Build evidence-backed narrative sections for PDF/HTML."""
    definition = definition or {}
    category = str(
        report.get("report_family")
        or report.get("category")
        or definition.get("category")
        or "operations_system"
    )
    adapter = str(definition.get("narrative_adapter") or adapter_for_category(category))
    title = str(
        definition.get("title")
        or report.get("title")
        or report.get("report_type")
        or "CSS Report"
    )
    report_date = str(report.get("report_date") or "UNAVAILABLE")
    report_id = str(report.get("report_id") or "UNAVAILABLE")
    version = str(report.get("report_version") or report.get("version") or "UNAVAILABLE")
    status = str(report.get("report_status") or "UNAVAILABLE")
    limitations = str(
        report.get("limitations") or definition.get("limitations") or ""
    ).strip()
    official = bool(report.get("official_report", definition.get("official_report")))
    advisory = report.get("advisory_only", True) is not False
    classification = str(
        report.get("confidentiality_classification")
        or ("CONFIDENTIAL_FINANCIAL" if report.get("contains_financial_values") else "INTERNAL")
    )
    period = str(
        report.get("reporting_period")
        or report.get("period")
        or report.get("reporting_window_start_utc")
        or report_date
    )
    if report.get("reporting_window_end_utc"):
        period = f"{period} → {report.get('reporting_window_end_utc')}"

    content = report.get("content") if isinstance(report.get("content"), Mapping) else {}
    findings = _family_findings(adapter, report, content)
    key_figures = _key_figures(report, content)
    actions = _plain_list(
        report.get("recommended_actions")
        or report.get("executive_actions")
        or content.get("recommended_actions")
        or content.get("actions")
        or []
    )
    exceptions = _plain_list(
        report.get("exceptions")
        or content.get("exceptions")
        or report.get("blockers")
        or []
    )
    if limitations:
        exceptions.append(translate_code(limitations) if limitations in _CODE_PLAIN else limitations)

    freshness = str(
        report.get("freshness")
        or report.get("data_freshness")
        or content.get("freshness")
        or "Evaluated at generation time from available evidence."
    )
    provenance_lines = _provenance_lines(report)

    safety_lines = [
        translate_code("advisory_only=true") if advisory else "Advisory flag is not set to true.",
        translate_code("execution_allowed=false"),
        translate_code("live_trading_blocked=true"),
        translate_code("broker_execution_armed=false"),
    ]
    for key, expected in SAFETY_LOCKS.items():
        actual = report.get(key, expected)
        if actual != expected:
            safety_lines.append(
                f"Safety field {translate_code(key)} was recorded as {translate_code(actual)} "
                f"(expected {translate_code(expected)})."
            )

    summary = _executive_summary(adapter, title, findings, limitations, status)

    sections = [
        {"heading": "Executive summary", "paragraphs": [summary]},
        {"heading": "Key findings", "paragraphs": findings or ["No prioritized findings were present in the evidence."]},
        {"heading": "Key figures", "paragraphs": key_figures or ["No numeric figures were present in the evidence."]},
        {
            "heading": "Main report content",
            "paragraphs": _main_content(adapter, report, content),
        },
        {
            "heading": "Exceptions and limitations",
            "paragraphs": exceptions or ["No exceptions were listed."],
        },
        {
            "heading": "Recommended attention or actions",
            "paragraphs": actions or ["No recommended actions were present in the evidence."],
        },
        {"heading": "Data freshness", "paragraphs": [translate_code(freshness)]},
        {
            "heading": "Evidence provenance",
            "paragraphs": provenance_lines or ["Provenance details were not attached to this archive entry."],
        },
        {"heading": "Safety and execution status", "paragraphs": safety_lines},
        {
            "heading": "Report classification",
            "paragraphs": [
                f"Report status: {translate_code(status)}.",
                f"Classification: {'Official advisory report' if official else 'Advisory operational report'}.",
                f"Confidentiality: {translate_code(classification)}.",
                "Advisory only." if advisory else "Advisory flag unset.",
            ],
        },
        {
            "heading": "Generated by",
            "paragraphs": [
                f"Generated by: {printed_by}.",
                f"Generated / printed timestamp (UTC): {generated_at_utc or report.get('generated_at') or 'UNAVAILABLE'}.",
                f"Report ID: {report_id}.",
                f"Version: {version}.",
                f"Integrity hash: {report.get('report_hash') or 'UNAVAILABLE'}.",
                f"Narrative adapter: {adapter}.",
                f"Renderer: {RENDERER_VERSION}.",
            ],
        },
        {
            "heading": "Technical appendix",
            "paragraphs": _technical_appendix(report, definition),
        },
    ]

    return {
        "title": title,
        "report_date": report_date,
        "reporting_period": period,
        "report_id": report_id,
        "version": version,
        "status": status,
        "adapter": adapter,
        "official": official,
        "advisory": advisory,
        "classification": classification,
        "sections": sections,
        "renderer_version": RENDERER_VERSION,
    }


def _executive_summary(
    adapter: str,
    title: str,
    findings: list[str],
    limitations: str,
    status: str,
) -> str:
    lead = f"This {title} covers evidence available at generation time."
    if findings:
        lead += f" Primary finding: {findings[0]}"
    lead += f" Current report status is {translate_code(status)}."
    if limitations:
        lead += f" Known limitation: {limitations}"
    if adapter == "executive_intelligence":
        lead += " This is an executive intelligence product for decision support, not an order to trade."
    return lead


def _family_findings(adapter: str, report: Mapping[str, Any], content: Mapping[str, Any]) -> list[str]:
    candidates = (
        report.get("key_findings")
        or report.get("findings")
        or content.get("key_findings")
        or content.get("findings")
        or content.get("summary_points")
    )
    found = _plain_list(candidates)
    if found:
        return found
    # Family-specific extraction without fabrication
    if adapter == "executive_intelligence":
        overall = report.get("overall_status") or content.get("overall_status")
        if overall:
            found.append(f"Overall status: {translate_code(overall)}.")
        market = _as_map(_as_map(report.get("panels")).get("market_intelligence"))
        if market.get("status") == "UNAVAILABLE" or market.get("panel_status") == "UNAVAILABLE":
            found.append(_CODE_PLAIN["market_panel_unavailable"])
        regime = market.get("regime_current")
        if regime:
            found.append(f"Market regime recorded as {translate_code(regime)}.")
    elif adapter == "trading_transactions":
        rows = content.get("rows") or content.get("transactions") or content.get("trades") or report.get("rows")
        if isinstance(rows, list):
            found.append(f"The evidence contains {len(rows)} transaction or trade row(s).")
        elif report.get("row_count") is not None:
            found.append(f"The evidence contains {report.get('row_count')} transaction or trade row(s).")
        mode = report.get("execution_mode") or content.get("execution_mode") or content.get("mode")
        if mode:
            found.append(f"Activity is classified as {translate_code(mode)} (paper, live, or advisory as recorded).")
    elif adapter == "accounts_cash":
        found.append(
            "This statement reflects only ledger and portfolio evidence that was present. "
            "It is not a complete audited account statement where the ledger is incomplete."
        )
        for key in ("opening_balance", "closing_balance", "known_balance"):
            if key in content or key in report:
                found.append(f"{translate_code(key)}: {translate_code((content or report).get(key))}.")
    elif adapter == "portfolio_performance":
        for key in ("holdings_count", "pnl", "allocation_summary", "valuation_time"):
            if content.get(key) is not None or report.get(key) is not None:
                found.append(f"{translate_code(key)}: {translate_code(content.get(key, report.get(key)))}.")
    elif adapter == "risk_exposure":
        for key in ("risk_posture", "limit_usage", "breaches", "alerts"):
            val = content.get(key, report.get(key))
            if val is not None:
                found.append(f"{translate_code(key)}: {translate_code(val)}.")
        if report.get("report_type") == "safety_lock_report" or content.get("safety_locks"):
            found.append("Safety locks were recorded as active for advisory-only operation.")
    elif adapter == "broker_execution":
        for key in ("connectivity", "health", "readiness", "incidents"):
            val = content.get(key, report.get(key))
            if val is not None:
                found.append(f"{translate_code(key)}: {translate_code(val)}.")
    elif adapter in {"compliance_audit", "operations_system", "treasury"}:
        for key in ("status", "health", "failure_count", "service_status"):
            val = content.get(key, report.get(key))
            if val is not None:
                found.append(f"{translate_code(key)}: {translate_code(val)}.")
    text = report.get("text") or content.get("text") or report.get("markdown")
    if not found and text:
        snippet = str(text).strip().splitlines()[:3]
        found.extend(translate_code(line) for line in snippet if line.strip())
    return found[:12]


def _key_figures(report: Mapping[str, Any], content: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    kpis = report.get("executive_kpis") or content.get("kpis") or content.get("metrics")
    if isinstance(kpis, Mapping):
        for name, kpi in list(kpis.items())[:15]:
            if name == "aliases":
                continue
            if isinstance(kpi, Mapping):
                out.append(
                    f"{translate_code(name)}: {translate_code(kpi.get('value'))} "
                    f"(confidence {translate_code(kpi.get('confidence'))}, "
                    f"freshness {translate_code(kpi.get('freshness'))})."
                )
            else:
                out.append(f"{translate_code(name)}: {translate_code(kpi)}.")
    for key in ("row_count", "event_count", "pnl", "balance", "exposure"):
        if report.get(key) is not None:
            out.append(f"{translate_code(key)}: {translate_code(report.get(key))}.")
        elif content.get(key) is not None:
            out.append(f"{translate_code(key)}: {translate_code(content.get(key))}.")
    return out[:20]


def _main_content(adapter: str, report: Mapping[str, Any], content: Mapping[str, Any]) -> list[str]:
    paragraphs: list[str] = []
    desc = report.get("description") or content.get("description")
    if desc:
        paragraphs.append(translate_code(desc))
    if adapter == "trading_transactions":
        paragraphs.append(
            "Trading activity is described only from ledger or supplied execution evidence. "
            "Missing prices, quantities, fees, or rationale fields are omitted rather than invented."
        )
        rows = content.get("rows") or content.get("transactions") or content.get("trades")
        if isinstance(rows, list):
            for idx, row in enumerate(rows[:8], start=1):
                if isinstance(row, Mapping):
                    paragraphs.append(
                        f"Row {idx}: instrument {translate_code(row.get('instrument') or row.get('symbol') or 'UNAVAILABLE')}; "
                        f"quantity {translate_code(row.get('quantity') or row.get('qty') or 'UNAVAILABLE')}; "
                        f"price {translate_code(row.get('price') or 'UNAVAILABLE')}; "
                        f"status {translate_code(row.get('status') or 'UNAVAILABLE')}."
                    )
        if report.get("report_type") == "transaction_ticket":
            paragraphs.append(
                "This transaction ticket is a confirmation-style view of the supplied evidence only."
            )
    elif adapter == "accounts_cash":
        paragraphs.append(
            "Account statement figures show opening activity and closing positions only where evidence exists. "
            "Unavailable balances are stated as unavailable."
        )
    elif adapter == "risk_exposure":
        paragraphs.append(
            "Risk posture, limit usage, breaches, and alerts appear only when present in evidence."
        )
    elif adapter == "broker_execution":
        paragraphs.append(
            "Broker connectivity, health, readiness, and incidents are summarized from runtime evidence."
        )
    elif adapter == "executive_intelligence":
        paragraphs.append(
            "Executive content summarizes what happened, why it matters, current risks, and recommended attention."
        )
    text = report.get("text") or content.get("summary")
    if text and not paragraphs:
        for line in str(text).splitlines()[:20]:
            if line.strip():
                paragraphs.append(translate_code(line.strip()))
    if not paragraphs:
        paragraphs.append(
            "The canonical report object was archived successfully. "
            "Additional narrative fields were not present in the evidence payload."
        )
    return paragraphs[:24]


def _provenance_lines(report: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    prov = report.get("provenance")
    if isinstance(prov, list):
        for item in prov[:12]:
            m = _as_map(item)
            out.append(
                f"Source {translate_code(m.get('source') or 'unknown')}; "
                f"artifact {translate_code(m.get('artifact_path') or m.get('path') or 'UNAVAILABLE')}; "
                f"freshness {translate_code(m.get('freshness') or 'UNAVAILABLE')}."
            )
    elif isinstance(prov, Mapping):
        out.append(
            f"Created by {translate_code(prov.get('created_by'))}; "
            f"reason {translate_code(prov.get('created_reason'))}; "
            f"at {translate_code(prov.get('created_at'))}."
        )
    evidence = report.get("evidence_sources") or report.get("required_evidence")
    if isinstance(evidence, (list, tuple)):
        out.append("Evidence sources: " + ", ".join(translate_code(e) for e in evidence[:12]) + ".")
    return out


def _technical_appendix(report: Mapping[str, Any], definition: Mapping[str, Any]) -> list[str]:
    """Raw codes allowed only here."""
    lines = [
        f"report_type={report.get('report_type')}",
        f"report_code={definition.get('report_code') or report.get('report_type')}",
        f"category={definition.get('category') or report.get('report_family')}",
        f"report_status={report.get('report_status')}",
        f"schema_version={report.get('schema_version')}",
        f"execution_allowed={report.get('execution_allowed', False)}",
        f"live_trading_blocked={report.get('live_trading_blocked', True)}",
        f"broker_execution_armed={report.get('broker_execution_armed', False)}",
        f"advisory_only={report.get('advisory_only', True)}",
    ]
    if report.get("limitations"):
        lines.append(f"limitations_code_or_text={report.get('limitations')}")
    return lines
