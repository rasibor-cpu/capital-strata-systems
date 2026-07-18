"""Report producers for Phase 176 — evidence-backed only."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.reports_center.constants import SAFETY_LOCKS

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SAFE_FILTER = re.compile(r"^[A-Za-z0-9_.:@-]{0,64}$")


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def validate_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    """Reject unsafe filter values (paths, SQL, code)."""
    out: dict[str, Any] = {}
    for key, value in (filters or {}).items():
        k = str(key)
        if not _SAFE_FILTER.match(k):
            raise ValueError(f"invalid_filter_key:{k}")
        if value is None:
            continue
        if isinstance(value, (int, float, bool)):
            out[k] = value
            continue
        s = str(value)
        if any(tok in s for tok in ("../", "..\\", ";", "--", "/*", "*/", "`", "$(", "\n", "\r")):
            raise ValueError(f"unsafe_filter_value:{k}")
        max_len = 8192 if k in {"execution_evidence_json"} else 128
        if len(s) > max_len:
            raise ValueError(f"filter_too_long:{k}")
        if k.endswith("date") or k in {"from_date", "to_date", "report_date", "as_of_date"}:
            if s and not _DATE.match(s):
                raise ValueError(f"invalid_date_filter:{k}")
        out[k] = s
    return out


def _html_wrap(title: str, body: str, *, limitations: str = "", advisory: bool = True) -> str:
    banner = (
        '<div style="border:2px solid #b45309;padding:8px;margin-bottom:12px;">'
        "ADVISORY ONLY — not an execution or live-trading authorization. "
        f"{'OFFICIAL banner suppressed for advisory classification.' if advisory else ''}"
        "</div>"
    )
    lim = f'<div style="border:1px solid #666;padding:8px;margin-bottom:12px;"><strong>Limitations:</strong> {limitations}</div>' if limitations else ""
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head>"
        f"<body><h1>{title}</h1>{banner}{lim}<pre>{body}</pre></body></html>"
    )


def produce(report_code: str, *, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """Dispatch to a concrete producer. Raises ValueError for unavailable codes."""
    filters = validate_filters(filters)
    handlers = {
        "daily_executive_brief": _daily_executive_brief,
        "overnight_market_intelligence": _overnight_market,
        "executive_kpi_summary": _executive_kpi,
        "executive_actions_report": _executive_actions,
        "executive_risk_summary": _executive_risk,
        "executive_operational_health": _executive_ops,
        "historical_executive_brief_comparison": _historical_compare,
        "daily_brief_distribution_report": _brief_distribution,
        "transaction_journal": _transaction_journal,
        "trade_journal": _trade_journal,
        "transaction_ticket": _transaction_ticket,
        "account_statement": _account_statement,
        "portfolio_summary": _portfolio_summary,
        "pnl_report": _pnl_report,
        "risk_summary": _risk_summary,
        "safety_lock_report": _safety_lock,
        "broker_health_report": _broker_health,
        "report_access_audit": _audit_by_action("view"),
        "report_print_audit": _audit_by_action("print"),
        "report_email_distribution_audit": _audit_by_action("email"),
        "archived_report_manifest": _archived_manifest,
        "report_integrity_verification": _integrity,
        "governance_summary": _fincon("governance_summary"),
        "supervisory_control_pack": _fincon("supervisory_control_pack"),
        "ar_ageing": _fincon("ar_ageing"),
        "ap_ageing": _fincon("ap_ageing"),
        "gl_ageing": _fincon("gl_ageing"),
        "staff_print_grant_report": _staff_print_grants,
        "advisory_only_compliance": _advisory_compliance,
        "runtime_health": _runtime_health,
        "report_generation_failures": _generation_failures,
        "distribution_print_audit_home": _distribution_home,
    }
    fn = handlers.get(report_code)
    if fn is None:
        raise ValueError("producer_not_available")
    return fn(filters=filters, repo_root=repo_root)


def _daily_executive_brief(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    from backend.executive_intelligence.service import ExecutiveIntelligenceEngine

    engine = ExecutiveIntelligenceEngine(repo_root=repo_root)
    result = engine.generate(report_date=filters.get("report_date"), persist=True, created_reason="reports_center")
    brief = result.get("brief") or {}
    archive = result.get("archive") or {}
    status = str(brief.get("report_status") or archive.get("report_status") or "FAILED")
    return {
        "title": "Daily Executive Brief",
        "report_type": "daily_executive_brief",
        "report_date": brief.get("report_date") or filters.get("report_date") or utc_today(),
        "report_status": status,
        "official_report": status == "FINAL",
        "content": brief,
        "bridge_archive": archive,
        "formats": {"json": True, "html": True, "pdf": True, "markdown": True},
        "limitations": brief.get("limitations") or "",
        "external_identity": {
            "kind": "morning_briefing",
            "report_date": brief.get("report_date"),
            "version": brief.get("report_version") or archive.get("version"),
        },
        **SAFETY_LOCKS,
    }


def _overnight_market(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    from backend.executive_intelligence.overnight_market import produce_overnight_market_intelligence

    report_date = filters.get("report_date") or utc_today()
    payload = produce_overnight_market_intelligence()
    status = "FINAL" if str(payload.get("status") or payload.get("freshness") or "").upper() not in {"UNAVAILABLE", "FAILED"} else "FAILED"
    # Prefer explicit panel status
    if str(payload.get("availability") or "").upper() == "UNAVAILABLE":
        status = "FAILED"
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    return {
        "title": "Overnight Market Intelligence Report",
        "report_type": "overnight_market_intelligence",
        "report_date": report_date,
        "report_status": status if status == "FINAL" else "FAILED",
        "official_report": False,
        "content": payload,
        "html": _html_wrap("Overnight Market Intelligence", text),
        "markdown": f"# Overnight Market Intelligence\n\n```json\n{text}\n```\n",
        "limitations": "Advisory market evidence only.",
        **SAFETY_LOCKS,
    }


def _brief_subset(name: str, extractor) -> Any:
    def _inner(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
        from backend.executive_intelligence.service import ExecutiveIntelligenceEngine

        engine = ExecutiveIntelligenceEngine(repo_root=repo_root)
        result = engine.generate(report_date=filters.get("report_date"), persist=False, created_reason="reports_center_subset")
        brief = result.get("brief") or {}
        extracted = extractor(brief)
        text = json.dumps(extracted, indent=2, sort_keys=True, default=str)
        status = "FINAL" if brief.get("validation", {}).get("finalization_allowed") else "FAILED"
        # Subset reports are advisory even when brief would be FINAL
        return {
            "title": name,
            "report_type": filters.get("_report_type") or name.lower().replace(" ", "_"),
            "report_date": brief.get("report_date") or filters.get("report_date") or utc_today(),
            "report_status": "FINAL" if extracted is not None else "FAILED",
            "official_report": False,
            "content": extracted,
            "html": _html_wrap(name, text, limitations="Derived advisory extract from executive brief evidence."),
            "parent_brief_status": status,
            **SAFETY_LOCKS,
        }

    return _inner


def _executive_kpi(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    filters = {**filters, "_report_type": "executive_kpi_summary"}
    return _brief_subset("Executive KPI Summary", lambda b: b.get("kpis") or b.get("panels", {}).get("executive_decision"))(
        filters=filters, repo_root=repo_root
    )


def _executive_actions(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    filters = {**filters, "_report_type": "executive_actions_report"}
    return _brief_subset("Executive Actions Report", lambda b: b.get("actions") or b.get("recommended_actions"))(
        filters=filters, repo_root=repo_root
    )


def _executive_risk(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    filters = {**filters, "_report_type": "executive_risk_summary"}

    def extract(b):
        panels = b.get("panels") or {}
        return {
            "risk_stability": (b.get("kpis") or {}).get("risk_stability"),
            "operational_health": panels.get("operational_health"),
            "decision": panels.get("executive_decision"),
        }

    return _brief_subset("Executive Risk Summary", extract)(filters=filters, repo_root=repo_root)


def _executive_ops(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    filters = {**filters, "_report_type": "executive_operational_health"}
    return _brief_subset(
        "Executive Operational Health Report",
        lambda b: (b.get("panels") or {}).get("operational_health"),
    )(filters=filters, repo_root=repo_root)


def _historical_compare(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    from backend.executive_intelligence.retrieval import MorningBriefRetrieval

    from_date = filters.get("from_date") or filters.get("report_date")
    to_date = filters.get("to_date")
    if not from_date or not to_date:
        raise ValueError("from_date_and_to_date_required")
    root = repo_root / "artifacts/runtime_reports/morning_briefings"
    retrieval = MorningBriefRetrieval(root)
    a = retrieval.by_date(from_date)
    b = retrieval.by_date(to_date)
    content = {
        "from_date": from_date,
        "to_date": to_date,
        "from_present": a is not None,
        "to_present": b is not None,
        "from_status": None if a is None else a.get("report_status"),
        "to_status": None if b is None else b.get("report_status"),
        "from_kpis": None if a is None else a.get("kpis"),
        "to_kpis": None if b is None else b.get("kpis"),
        "note": "Advisory metadata/KPI comparison only.",
    }
    ok = a is not None and b is not None
    text = json.dumps(content, indent=2, sort_keys=True, default=str)
    return {
        "title": "Historical Executive Brief Comparison",
        "report_type": "historical_executive_brief_comparison",
        "report_date": to_date,
        "report_status": "FINAL" if ok else "FAILED",
        "official_report": False,
        "content": content,
        "html": _html_wrap("Historical Executive Brief Comparison", text, limitations=content["note"]),
        "limitations": content["note"],
        **SAFETY_LOCKS,
    }


def _brief_distribution(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    dist = repo_root / "artifacts/runtime_reports/executive_brief_distribution"
    events = []
    for path in (dist.rglob("*.jsonl") if dist.is_dir() else []):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))
        except Exception:
            continue
    # privacy: strip emails
    safe = []
    for e in events[-200:]:
        safe.append(
            {
                "action": e.get("action"),
                "outcome": e.get("outcome"),
                "timestamp_utc": e.get("timestamp_utc") or e.get("ts"),
                "actor_role": e.get("actor_role") or e.get("role"),
                "report_date": e.get("report_date"),
                "destination_class": e.get("destination_class") or "INTERNAL",
            }
        )
    text = json.dumps(safe, indent=2, sort_keys=True)
    return {
        "title": "Daily Brief Distribution Report",
        "report_type": "daily_brief_distribution_report",
        "report_date": filters.get("report_date") or utc_today(),
        "report_status": "FINAL",
        "official_report": False,
        "content": {"events": safe, "count": len(safe)},
        "html": _html_wrap("Daily Brief Distribution Report", text),
        **SAFETY_LOCKS,
    }


def _load_pnl_events(repo_root: Path, mode: str = "TEST") -> list[dict[str, Any]]:
    mode_u = str(mode or "TEST").upper()
    if mode_u == "LIVE":
        # Live ledger path may exist but live trading is blocked — still allow read of historical if present
        rel = os.getenv("REA_PNL_LEDGER_LIVE_PATH", "reporting_store/pnl_ledger_live.jsonl")
    else:
        rel = os.getenv("REA_PNL_LEDGER_TEST_PATH", "reporting_store/pnl_ledger_test.jsonl")
    path = Path(rel)
    if not path.is_file():
        path = repo_root / rel
    if not path.is_file():
        alt = repo_root / "reporting_store" / "pnl_ledger.jsonl"
        path = alt if alt.is_file() else path
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return events


def _match_filters(event: dict[str, Any], filters: dict[str, Any]) -> bool:
    mapping = {
        "user": ("user_id", "user", "trader_id"),
        "trader": ("trader_id", "user_id", "trader"),
        "strategy": ("strategy", "strategy_id"),
        "portfolio": ("portfolio", "portfolio_id"),
        "account": ("account", "account_id"),
        "broker": ("broker", "broker_name", "broker_id"),
        "asset_class": ("asset_class",),
        "instrument": ("instrument", "symbol"),
        "transaction_type": ("transaction_type", "txn_type", "type"),
        "status": ("status",),
        "execution_mode": ("execution_mode", "mode", "is_paper"),
    }
    for key, fields in mapping.items():
        if key not in filters or filters[key] in ("", None):
            continue
        want = str(filters[key]).lower()
        found = None
        for f in fields:
            if f in event and event[f] is not None:
                found = str(event[f]).lower()
                break
        if found is None:
            return False
        if found != want and want not in found:
            return False
    # date range on ts_utc / date
    start = filters.get("from_date")
    end = filters.get("to_date")
    ts = str(event.get("ts_utc") or event.get("date") or event.get("execution_date") or "")
    if start and ts and ts[:10] < start:
        return False
    if end and ts and ts[:10] > end:
        return False
    return True


def _transaction_journal(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    events = [e for e in _load_pnl_events(repo_root, filters.get("execution_mode") or filters.get("mode") or "TEST") if _match_filters(e, filters)]
    # strip secrets
    rows = [{k: v for k, v in e.items() if not any(t in str(k).lower() for t in ("secret", "token", "password", "key"))} for e in events]
    text = json.dumps(rows[:500], indent=2, sort_keys=True, default=str)
    csv_lines = ["ts_utc,symbol,side,qty,pnl,fees,user_id,broker"]
    for r in rows[:500]:
        csv_lines.append(
            ",".join(
                str(r.get(k, ""))
                for k in ("ts_utc", "symbol", "side", "qty", "pnl", "fees", "user_id", "broker")
            )
        )
    return {
        "title": "Transaction Journal",
        "report_type": "transaction_journal",
        "report_date": filters.get("to_date") or filters.get("report_date") or utc_today(),
        "report_status": "FINAL",
        "official_report": False,
        "content": {"rows": rows[:500], "count": len(rows), "truncated": len(rows) > 500},
        "html": _html_wrap(
            "Transaction Journal",
            text,
            limitations="Only ledger-backed events; missing fields omitted.",
        ),
        "csv": "\n".join(csv_lines) + "\n",
        "limitations": "AVAILABLE_WITH_LIMITATIONS — ledger evidence only.",
        **SAFETY_LOCKS,
    }


def _trade_journal(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    base = _transaction_journal(filters=filters, repo_root=repo_root)
    rows = []
    for r in base["content"]["rows"]:
        rows.append(
            {
                "trade_id": r.get("trade_id") or r.get("utrn") or r.get("execution_id"),
                "order_id": r.get("order_id"),
                "user": r.get("user_id") or r.get("trader_id"),
                "strategy": r.get("strategy") or r.get("strategy_id"),
                "instrument": r.get("symbol") or r.get("instrument"),
                "side": r.get("side"),
                "quantity": r.get("qty") or r.get("quantity") or r.get("filled_qty"),
                "entry": r.get("entry") or r.get("entry_price"),
                "exit": r.get("exit") or r.get("exit_price") or r.get("fill_price"),
                "timestamps": r.get("ts_utc"),
                "realized_pnl": r.get("pnl") or r.get("realized_pnl"),
                "unrealized_pnl": r.get("unrealized_pnl"),
                "fees": r.get("fees"),
                "slippage": r.get("slippage"),
                "confidence": r.get("confidence"),
                "decision_rationale": r.get("rationale") or r.get("decision_rationale"),
                "risk_decision": r.get("risk_decision"),
                "outcome": r.get("outcome") or r.get("status"),
                "notes": r.get("notes"),
                "provenance": r.get("provenance") or r.get("source"),
                "paper_live_advisory": "paper" if r.get("is_paper") else r.get("execution_mode") or "advisory",
            }
        )
    text = json.dumps(rows, indent=2, sort_keys=True, default=str)
    return {
        "title": "Trade Journal",
        "report_type": "trade_journal",
        "report_date": base["report_date"],
        "report_status": "FINAL",
        "official_report": False,
        "content": {"rows": rows, "count": len(rows)},
        "html": _html_wrap("Trade Journal", text, limitations="Fields included only when present in evidence."),
        "csv": base.get("csv"),
        "limitations": "AVAILABLE_WITH_LIMITATIONS",
        **SAFETY_LOCKS,
    }


def _transaction_ticket(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    _ = repo_root
    evidence = filters.get("execution_evidence_json")
    ledger_id = filters.get("ledger_txn_id") or filters.get("transaction_id")
    if evidence:
        try:
            data = json.loads(str(evidence))
        except Exception as exc:
            raise ValueError("invalid_execution_evidence_json") from exc
        if not isinstance(data, dict):
            raise ValueError("execution_evidence_must_be_object")
        # Never invent fills — render supplied fields only
        lines = ["TRANSACTION TICKET", "=" * 60]
        preferred = [
            "transaction_id",
            "trade_id",
            "execution_id",
            "order_id",
            "account",
            "broker",
            "broker_name",
            "instrument",
            "symbol",
            "asset_class",
            "side",
            "quantity",
            "filled_qty",
            "price",
            "fill_price",
            "notional",
            "currency",
            "order_type",
            "status",
            "execution_date",
            "fees",
            "strategy",
            "user_id",
            "trader",
            "is_paper",
            "decision_provenance",
            "risk_authorization",
        ]
        seen = set()
        for key in preferred:
            if key in data and data[key] is not None:
                lines.append(f"{key:20}: {data[key]}")
                seen.add(key)
        for key, val in sorted(data.items()):
            if key in seen:
                continue
            if any(tok in str(key).lower() for tok in ("secret", "token", "password", "key", "pem")):
                continue
            lines.append(f"{key:20}: {val}")
        mode = "PAPER" if data.get("is_paper") else str(data.get("execution_mode") or "ADVISORY").upper()
        lines.insert(2, f"MODE BANNER         : {mode} — advisory_only / live_trading_blocked")
        ticket_text = "\n".join(lines)
        return {
            "title": "Transaction Ticket",
            "report_type": "transaction_ticket",
            "report_date": utc_today(),
            "report_status": "FINAL",
            "official_report": False,
            "content": data,
            "html": _html_wrap("Transaction Ticket", ticket_text, limitations="Rendered from supplied evidence only."),
            "limitations": "One ticket per supplied transaction evidence; missing fields omitted.",
            **SAFETY_LOCKS,
        }
    if ledger_id:
        try:
            from engine.ledger.audit_reports import AuditReportEngine
            from engine.ledger.ledger_store import LedgerStore

            store = LedgerStore()
            engine = AuditReportEngine(store)
            ticket_text = engine.trade_ticket(str(ledger_id))
            return {
                "title": "Transaction Ticket",
                "report_type": "transaction_ticket",
                "report_date": utc_today(),
                "report_status": "FINAL",
                "official_report": False,
                "content": {"ledger_txn_id": ledger_id, "ticket": ticket_text},
                "html": _html_wrap("Transaction Ticket", ticket_text),
                **SAFETY_LOCKS,
            }
        except Exception as exc:
            return {
                "title": "Transaction Ticket",
                "report_type": "transaction_ticket",
                "report_date": utc_today(),
                "report_status": "FAILED",
                "official_report": False,
                "content": {"error": "ledger_ticket_unavailable", "detail": str(exc)[:200]},
                "html": _html_wrap(
                    "Transaction Ticket",
                    "FAILED: ledger evidence unavailable",
                    limitations="No fabricated ticket.",
                ),
                "limitations": "Ledger transaction not found or store unavailable.",
                **SAFETY_LOCKS,
            }
    raise ValueError("transaction_id_or_execution_evidence_required")


def _account_statement(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    events = [e for e in _load_pnl_events(repo_root, filters.get("mode") or "TEST") if _match_filters(e, filters)]
    pnl = sum(float(e.get("pnl") or 0) for e in events)
    fees = sum(float(e.get("fees") or 0) for e in events)
    content = {
        "account": filters.get("account"),
        "currency": filters.get("currency") or "UNAVAILABLE",
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "opening_balance": "UNAVAILABLE",
        "closing_balance": "UNAVAILABLE",
        "deposits": "UNAVAILABLE",
        "withdrawals": "UNAVAILABLE",
        "transfers": "UNAVAILABLE",
        "realized_pnl": pnl,
        "unrealized_pnl": "UNAVAILABLE",
        "fees": fees,
        "interest": "UNAVAILABLE",
        "dividends": "UNAVAILABLE",
        "positions": "UNAVAILABLE",
        "valuation_timestamp": "UNAVAILABLE",
        "event_count": len(events),
        "provenance": "pnl_ledger_partial",
        "limitation_banner": (
            "AVAILABLE_WITH_LIMITATIONS — full accounting ledger incomplete. "
            "This is not an official complete account statement."
        ),
    }
    text = json.dumps(content, indent=2, sort_keys=True, default=str)
    return {
        "title": "Account Statement",
        "report_type": "account_statement",
        "report_date": filters.get("to_date") or utc_today(),
        "report_status": "FINAL",
        "official_report": False,
        "content": content,
        "html": _html_wrap("Account Statement", text, limitations=content["limitation_banner"]),
        "limitations": content["limitation_banner"],
        **SAFETY_LOCKS,
    }


def _portfolio_summary(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    from backend.executive_intelligence.evidence import gather_evidence

    bundle = gather_evidence(repo_root)
    portfolio = bundle.get("portfolio") or {}
    text = json.dumps(portfolio, indent=2, sort_keys=True, default=str)
    ok = bool(portfolio) and str(portfolio.get("status") or "").upper() not in {"UNAVAILABLE", ""}
    return {
        "title": "Portfolio Summary",
        "report_type": "portfolio_summary",
        "report_date": filters.get("report_date") or utc_today(),
        "report_status": "FINAL" if ok else "FAILED",
        "official_report": False,
        "content": portfolio,
        "html": _html_wrap(
            "Portfolio Summary",
            text,
            limitations="Advisory runtime portfolio evidence; not a certified NAV statement.",
        ),
        **SAFETY_LOCKS,
    }


def _pnl_report(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    mode = filters.get("mode") or "TEST"
    content: dict[str, Any]
    try:
        from engine.reporting import pnl_report as pnl_eng

        summary, events = pnl_eng.today(mode=mode)
        content = {
            "label": summary.label,
            "trades": summary.trades,
            "wins": summary.wins,
            "losses": summary.losses,
            "win_rate": summary.win_rate,
            "pnl": summary.pnl,
            "fees": summary.fees,
            "event_count": len(events),
            "source": "engine.reporting.pnl_report.today",
        }
    except Exception:
        events = _load_pnl_events(repo_root, mode)
        content = {
            "events": len(events),
            "pnl": sum(float(e.get("pnl") or 0) for e in events),
            "source": "pnl_ledger_fallback",
        }
    text = json.dumps(content, indent=2, sort_keys=True, default=str)
    return {
        "title": "PnL Report",
        "report_type": "pnl_report",
        "report_date": filters.get("to_date") or utc_today(),
        "report_status": "FINAL",
        "official_report": False,
        "content": content,
        "html": _html_wrap("PnL Report", text, limitations="Ledger-backed PnL only."),
        **SAFETY_LOCKS,
    }


def _risk_summary(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    from backend.executive_intelligence.evidence import gather_evidence

    bundle = gather_evidence(repo_root)
    risk = bundle.get("risk") or {}
    text = json.dumps(risk, indent=2, sort_keys=True, default=str)
    return {
        "title": "Risk Summary",
        "report_type": "risk_summary",
        "report_date": filters.get("report_date") or utc_today(),
        "report_status": "FINAL" if risk else "FAILED",
        "official_report": False,
        "content": risk,
        "html": _html_wrap("Risk Summary", text, limitations="No validated VaR claimed."),
        "limitations": "Advisory risk snapshot only.",
        **SAFETY_LOCKS,
    }


def _safety_lock(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    _ = (filters, repo_root)
    content = {**SAFETY_LOCKS, "source": "reports_center.constants / executive_intelligence.constants"}
    text = json.dumps(content, indent=2, sort_keys=True)
    return {
        "title": "Safety-Lock Report",
        "report_type": "safety_lock_report",
        "report_date": utc_today(),
        "report_status": "FINAL",
        "official_report": True,
        "content": content,
        "html": _html_wrap("Safety-Lock Report", text),
        **SAFETY_LOCKS,
    }


def _broker_health(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    from backend.executive_intelligence.evidence import gather_evidence
    from backend.executive_intelligence.sanitizer import sanitize_payload

    bundle = gather_evidence(repo_root)
    broker = sanitize_payload(bundle.get("broker_health") or {})
    text = json.dumps(broker, indent=2, sort_keys=True, default=str)
    return {
        "title": "Broker Health Report",
        "report_type": "broker_health_report",
        "report_date": filters.get("report_date") or utc_today(),
        "report_status": "FINAL" if broker else "FAILED",
        "official_report": False,
        "content": broker,
        "html": _html_wrap("Broker Health Report", text, limitations="No credentials or tokens included."),
        **SAFETY_LOCKS,
    }


def _audit_by_action(action_prefix: str):
    def _inner(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
        from backend.reports_center.audit import ReportAuditLog

        log = ReportAuditLog(repo_root / "artifacts/runtime_reports/report_audit")
        events = log.list_events(limit=500)
        if action_prefix:
            events = [e for e in events if str(e.get("action", "")).startswith(action_prefix) or action_prefix in str(e.get("action", ""))]
        text = json.dumps(events, indent=2, sort_keys=True, default=str)
        code = {
            "view": "report_access_audit",
            "print": "report_print_audit",
            "email": "report_email_distribution_audit",
        }.get(action_prefix, "report_access_audit")
        return {
            "title": code.replace("_", " ").title(),
            "report_type": code,
            "report_date": utc_today(),
            "report_status": "FINAL",
            "official_report": False,
            "content": {"events": events, "count": len(events)},
            "html": _html_wrap(code, text),
            **SAFETY_LOCKS,
        }

    return _inner


def _archived_manifest(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    from backend.reports_center.archive import ReportArchiveStore

    store = ReportArchiveStore(repo_root / "artifacts/runtime_reports/reports")
    recent = store.list_recent(limit=100)
    mb_root = repo_root / "artifacts/runtime_reports/morning_briefings"
    morning = []
    if mb_root.is_dir():
        for man in list(mb_root.rglob("manifest.json"))[:100]:
            try:
                morning.append(json.loads(man.read_text(encoding="utf-8")))
            except Exception:
                continue
    content = {"reports_center": recent, "morning_briefings": morning}
    text = json.dumps(content, indent=2, sort_keys=True, default=str)
    return {
        "title": "Archived Report Manifest",
        "report_type": "archived_report_manifest",
        "report_date": utc_today(),
        "report_status": "FINAL",
        "official_report": False,
        "content": content,
        "html": _html_wrap("Archived Report Manifest", text),
        **SAFETY_LOCKS,
    }


def _integrity(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    from backend.reports_center.archive import ReportArchiveStore

    report_id = filters.get("report_id")
    if not report_id:
        raise ValueError("report_id_required")
    store = ReportArchiveStore(repo_root / "artifacts/runtime_reports/reports")
    result = store.verify_integrity(str(report_id))
    text = json.dumps(result, indent=2, sort_keys=True)
    return {
        "title": "Report Integrity Verification",
        "report_type": "report_integrity_verification",
        "report_date": utc_today(),
        "report_status": "FINAL",
        "official_report": False,
        "content": result,
        "html": _html_wrap("Report Integrity Verification", text),
        **SAFETY_LOCKS,
    }


def _fincon(report_name: str):
    def _inner(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
        _ = repo_root
        from engine.reporting.report_printer import print_report

        role = str(filters.get("role") or "ADMIN")
        text = print_report(
            report_name,
            role,
            from_date=filters.get("from_date"),
            to_date=filters.get("to_date"),
            as_of_date=filters.get("as_of_date") or filters.get("report_date"),
            filters={k: v for k, v in filters.items() if k not in {"role"}},
        )
        return {
            "title": report_name,
            "report_type": report_name,
            "report_date": filters.get("as_of_date") or filters.get("report_date") or utc_today(),
            "report_status": "FINAL",
            "official_report": False,
            "content": {"text": text},
            "html": _html_wrap(report_name, text, limitations="FinCon printer output; evidence-dependent."),
            **SAFETY_LOCKS,
        }

    return _inner


def _staff_print_grants(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    _ = filters
    from backend.executive_intelligence.rbac_grants import ExecutiveBriefAccessControl

    access = ExecutiveBriefAccessControl()
    data = access._load_grants()
    grants = data.get("grants") if isinstance(data, dict) else {}
    safe = {}
    for uid, entry in (grants or {}).items():
        if not isinstance(entry, dict):
            continue
        actions = [a for a in (entry.get("actions") or []) if a == "executive_brief_print"]
        if actions and entry.get("revoked") is not True:
            safe[uid] = {"actions": actions, "revoked": False}
    text = json.dumps(safe, indent=2, sort_keys=True)
    return {
        "title": "Staff Print-Grant Report",
        "report_type": "staff_print_grant_report",
        "report_date": utc_today(),
        "report_status": "FINAL",
        "official_report": False,
        "content": safe,
        "html": _html_wrap("Staff Print-Grant Report", text),
        **SAFETY_LOCKS,
    }


def _advisory_compliance(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    return _safety_lock(filters=filters, repo_root=repo_root) | {
        "title": "Advisory-Only Compliance Report",
        "report_type": "advisory_only_compliance",
    }


def _runtime_health(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    from backend.executive_intelligence.evidence import gather_evidence

    bundle = gather_evidence(repo_root)
    rh = bundle.get("runtime_health") or {}
    text = json.dumps(rh, indent=2, sort_keys=True, default=str)
    return {
        "title": "Runtime Health",
        "report_type": "runtime_health",
        "report_date": filters.get("report_date") or utc_today(),
        "report_status": "FINAL" if rh else "FAILED",
        "official_report": False,
        "content": rh,
        "html": _html_wrap("Runtime Health", text),
        **SAFETY_LOCKS,
    }


def _generation_failures(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    from backend.reports_center.archive import ReportArchiveStore
    from backend.reports_center.audit import ReportAuditLog

    failed = ReportArchiveStore(repo_root / "artifacts/runtime_reports/reports").list_failed(limit=50)
    audit_failed = [
        e
        for e in ReportAuditLog(repo_root / "artifacts/runtime_reports/report_audit").list_events(limit=200)
        if e.get("outcome") in {"FAILED", "DENIED", "ERROR"}
    ]
    content = {"failed_archives": failed, "failed_audit_events": audit_failed}
    text = json.dumps(content, indent=2, sort_keys=True, default=str)
    return {
        "title": "Report Generation Failures",
        "report_type": "report_generation_failures",
        "report_date": utc_today(),
        "report_status": "FINAL",
        "official_report": False,
        "content": content,
        "html": _html_wrap("Report Generation Failures", text),
        **SAFETY_LOCKS,
    }


def _distribution_home(*, filters: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    print_rep = _audit_by_action("print")(filters=filters, repo_root=repo_root)
    email_rep = _audit_by_action("email")(filters=filters, repo_root=repo_root)
    content = {
        "print_events": print_rep["content"],
        "email_events": email_rep["content"],
        "email_policy_default": "EMAIL_DISABLED",
        "executive_brief_email_policy": "ADMIN_SUPER_USER_ONLY",
    }
    text = json.dumps(content, indent=2, sort_keys=True, default=str)
    return {
        "title": "Distribution & Print Audit Summary",
        "report_type": "distribution_print_audit_home",
        "report_date": utc_today(),
        "report_status": "FINAL",
        "official_report": False,
        "content": content,
        "html": _html_wrap("Distribution & Print Audit Summary", text),
        **SAFETY_LOCKS,
    }
