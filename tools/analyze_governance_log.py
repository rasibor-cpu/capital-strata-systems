"""
tools/analyze_governance_log.py

Governance Summary Report (Regulator-Grade)
-------------------------------------------
Registered report_id:
- governance_summary

Reads: audit_logs/governance_decisions.jsonl
Outputs: deterministic regulator-friendly summary text + JSON payload.

Authority:
- ADMIN / SUPER_USER / FINCON_REPORTING only
"""

from __future__ import annotations

import json
from collections import Counter
from statistics import mean
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.reporting.report_printer import ReportResult, register_report


def _safe_mean(xs: List[float]) -> Optional[float]:
    return mean(xs) if xs else None


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
)
def governance_summary(*, log_path: str = "audit_logs/governance_decisions.jsonl") -> ReportResult:
    LOG_PATH = Path(log_path)
    records = _load_jsonl(LOG_PATH)

    total = len(records)
    finals = Counter(str(r.get("pcc_final", "UNKNOWN")).upper() for r in records)

    # Only BLOCK reasons
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

    avg_corr_allow = _safe_mean(corr_allow)
    avg_corr_block = _safe_mean(corr_block)
    avg_mult = _safe_mean(mults)

    payload: Dict[str, Any] = {
        "log_path": str(LOG_PATH),
        "total_decisions": total,
        "allow": finals.get("ALLOW", 0),
        "block": finals.get("BLOCK", 0),
        "top_block_reasons": dict(block_reasons.most_common(10)),
        "avg_correlation_allow": avg_corr_allow,
        "avg_correlation_block": avg_corr_block,
        "avg_sizing_multiplier": avg_mult,
    }

    lines: List[str] = []
    lines.append("=== GOVERNANCE ANALYSIS SUMMARY (REGULATOR FORMAT) ===")
    lines.append(f"Log path                : {payload['log_path']}")
    lines.append(f"Total decisions         : {payload['total_decisions']}")
    lines.append(f"ALLOW                   : {payload['allow']}")
    lines.append(f"BLOCK                   : {payload['block']}")
    lines.append("")
    lines.append("Top BLOCK Reasons:")
    if block_reasons:
        for reason, count in block_reasons.most_common(5):
            lines.append(f"  {reason:30s} {count}")
    else:
        lines.append("  (none)")
    lines.append("")
    if avg_corr_allow is not None:
        lines.append(f"Avg Correlation (ALLOW) : {avg_corr_allow:.4f}")
    if avg_corr_block is not None:
        lines.append(f"Avg Correlation (BLOCK) : {avg_corr_block:.4f}")
    if avg_mult is not None:
        lines.append(f"Avg Sizing Multiplier   : {avg_mult:.4f}")

    text = "\n".join(lines) + "\n"
    return ReportResult(
        report_id="governance_summary",
        title="Governance Summary (PCC Explainability)",
        payload=payload,
        text=text,
    )


def main():
    # Developer convenience: run and print without authority layer
    r = governance_summary()
    print(r.text)


if __name__ == "__main__":
    main()