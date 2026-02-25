"""
tools/analyze_governance_log.py

Report: governance_summary (FinCon-grade)
-----------------------------------------
- Reproducible
- Authority-gated
- Timeframe filter (date range or ts range)
- Explicit content control via sections
- Includes sign-off metadata (caller + generation time)

Reads:
  audit_logs/governance_decisions.jsonl
"""

from __future__ import annotations

import json
import time
from collections import Counter
from statistics import mean
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from engine.reporting.report_printer import ReportResult, register_report
from engine.reporting.report_request import ReportRequest


def _safe_mean(xs: List[float]) -> Optional[float]:
    return mean(xs) if xs else None


def _date_to_ts(date_str: str, *, end_of_day: bool) -> float:
    dt = datetime.fromisoformat(date_str)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=0)
    else:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.timestamp()


def _within_timeframe(r: Dict[str, Any], req: ReportRequest) -> bool:
    ts = r.get("timestamp")
    if ts is None:
        return True

    try:
        ts = float(ts)
    except Exception:
        return True

    tf = req.timeframe

    if tf.start_ts is not None and ts < float(tf.start_ts):
        return False
    if tf.end_ts is not None and ts > float(tf.end_ts):
        return False

    if tf.start_date:
        if ts < _date_to_ts(tf.start_date, end_of_day=False):
            return False
    if tf.end_date:
        if ts > _date_to_ts(tf.end_date, end_of_day=True):
            return False

    return True


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


@register_report(
    "governance_summary",
    title="Governance Summary (PCC Explainability)",
    required_roles={"ADMIN", "SUPER_USER", "FINCON_REPORTING"},
    required_permissions={"FINCON_REPORTING"},
    default_sections={"summary", "top_reasons", "correlation", "sizing", "signoff"},
)
def governance_summary(req: ReportRequest) -> ReportResult:
    log_path = str(req.params.get("log_path", "audit_logs/governance_decisions.jsonl"))
    LOG_PATH = Path(log_path)

    all_records = _load_jsonl(LOG_PATH)
    records = [r for r in all_records if _within_timeframe(r, req)]

    sections = set(req.sections)

    finals = Counter(str(r.get("pcc_final", "UNKNOWN")).upper() for r in records)

    block_reasons = Counter(
        str(r.get("pcc_reason", "UNKNOWN"))
        for r in records
        if str(r.get("pcc_final", "")).upper() == "BLOCK"
    )

    corr_allow = [
        float(r.get("correlation_score"))
        for r in records
        if str(r.get("pcc_final", "")).upper() == "ALLOW"
        and r.get("correlation_score") is not None
    ]
    corr_block = [
        float(r.get("correlation_score"))
        for r in records
        if str(r.get("pcc_final", "")).upper() == "BLOCK"
        and r.get("correlation_score") is not None
    ]

    mults = [
        float(r.get("sizing_multiplier"))
        for r in records
        if r.get("sizing_multiplier") is not None
    ]

    payload: Dict[str, Any] = {
        "report_id": "governance_summary",
        "title": "Governance Summary (PCC Explainability)",
        "log_path": str(LOG_PATH),
        "filtered_records": len(records),
        "total_records_in_log": len(all_records),
        "allow": finals.get("ALLOW", 0),
        "block": finals.get("BLOCK", 0),
    }

    if "top_reasons" in sections:
        payload["top_block_reasons"] = dict(block_reasons.most_common(10))

    if "correlation" in sections:
        payload["avg_correlation_allow"] = _safe_mean(corr_allow)
        payload["avg_correlation_block"] = _safe_mean(corr_block)

    if "sizing" in sections:
        payload["avg_sizing_multiplier"] = _safe_mean(mults)

    if "signoff" in sections:
        payload["generated_at_ts"] = float(time.time())
        payload["caller"] = {
            "user_id": req.caller.user_id,
            "display_name": req.caller.display_name,
            "roles": sorted(req.caller.roles),
            "permissions": sorted(req.caller.permissions),
        }
        payload["timeframe"] = {
            "start_date": req.timeframe.start_date,
            "end_date": req.timeframe.end_date,
            "start_ts": req.timeframe.start_ts,
            "end_ts": req.timeframe.end_ts,
        }

    # ---- TEXT FORMAT ----
    lines: List[str] = []
    lines.append("=== GOVERNANCE ANALYSIS SUMMARY (REGULATOR FORMAT) ===")
    lines.append(f"Log path                : {payload['log_path']}")
    lines.append(f"Records (filtered)      : {payload['filtered_records']} / {payload['total_records_in_log']}")
    lines.append(f"ALLOW                   : {payload['allow']}")
    lines.append(f"BLOCK                   : {payload['block']}")

    if "top_reasons" in sections:
        lines.append("")
        lines.append("Top BLOCK Reasons:")
        if block_reasons:
            for reason, count in block_reasons.most_common(5):
                lines.append(f"  {reason:30s} {count}")
        else:
            lines.append("  (none)")

    if "correlation" in sections:
        lines.append("")
        a = payload.get("avg_correlation_allow")
        b = payload.get("avg_correlation_block")
        if a is not None:
            lines.append(f"Avg Correlation (ALLOW) : {float(a):.4f}")
        if b is not None:
            lines.append(f"Avg Correlation (BLOCK) : {float(b):.4f}")

    if "sizing" in sections:
        lines.append("")
        m = payload.get("avg_sizing_multiplier")
        if m is not None:
            lines.append(f"Avg Sizing Multiplier   : {float(m):.4f}")

    if "signoff" in sections:
        lines.append("")
        lines.append("Sign-off:")
        lines.append(f"  Printed by            : {req.caller.display_name} ({req.caller.user_id})")
        lines.append(f"  Roles                 : {', '.join(sorted(req.caller.roles)) or '(none)'}")
        lines.append(f"  Permissions           : {', '.join(sorted(req.caller.permissions)) or '(none)'}")
        lines.append(f"  Generated (ts)        : {payload.get('generated_at_ts')}")

    text = "\n".join(lines) + "\n"

    return ReportResult(
        report_id="governance_summary",
        title="Governance Summary (PCC Explainability)",
        payload=payload,
        text=text,
    )