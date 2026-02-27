"""
engine/reporting/report_printer.py

Central Report Registry (FinCon Grade)
---------------------------------------
Single source of truth for report registration and printing.

Exports (stable API):
- register_report(name, handler, roles, default_sections=None)
- list_reports() -> dict
- print_report(report_name, role, ...filters...) -> str

Design goals:
- Fail-closed authority gating
- Extensible report registry
- Supports: timeframe, as_of_date, explicit sections, arbitrary filters
- Minimal coupling (wrappers use lazy imports to avoid circulars)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import json

# ============================================================
# Types / Registry
# ============================================================

ReportHandler = Callable[..., str]


@dataclass(frozen=True)
class ReportMeta:
    handler: ReportHandler
    roles: List[str]
    default_sections: List[str]


_REPORT_REGISTRY: Dict[str, ReportMeta] = {}

# Common roles (keep consistent with backend/app/reporting_api.py)
COMMON_ROLES = ["ADMIN", "SUPER_USER", "FINCON_REPORTING"]

# Treasury-eligible roles: “treasury aggregates should be available to treasury + supervisors + fincon reporting”
TREASURY_ROLES = ["TREASURY", "TREASURY_SUPERVISOR", "SUPER_USER", "FINCON_REPORTING", "ADMIN"]


def register_report(
    name: str,
    handler: ReportHandler,
    roles: List[str],
    default_sections: Optional[List[str]] = None,
) -> None:
    key = str(name).strip()
    if not key:
        raise ValueError("report name cannot be empty")

    _REPORT_REGISTRY[key] = ReportMeta(
        handler=handler,
        roles=[str(r).strip().upper() for r in (roles or [])],
        default_sections=[str(s).strip() for s in (default_sections or [])],
    )


def list_reports() -> Dict[str, Any]:
    return {
        name: {
            "roles": meta.roles,
            "default_sections": meta.default_sections,
        }
        for name, meta in sorted(_REPORT_REGISTRY.items(), key=lambda kv: kv[0])
    }


# ============================================================
# Authority Gate
# ============================================================

def _check_role(report_name: str, role: str) -> None:
    meta = _REPORT_REGISTRY.get(report_name)
    if not meta:
        raise ValueError(f"Unknown report '{report_name}'")

    role_u = (role or "").strip().upper()
    if role_u not in meta.roles:
        raise PermissionError(
            f"Insufficient authority to print '{report_name}'. "
            f"Requires one of: {meta.roles}"
        )


# ============================================================
# Print Engine
# ============================================================

def print_report(
    report_name: str,
    role: str,
    user_id: Optional[str] = None,
    department: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
    sections: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Returns the report as a printable text block (string).

    Notes:
    - Role gating is enforced here (fail-closed).
    - Handlers are responsible for interpreting filters/sections.
    """
    report_name = (report_name or "").strip()
    role_u = (role or "").strip().upper()
    user_id = (user_id or "").strip() or "UNKNOWN"
    department = (department or "").strip() or "UNKNOWN"
    sections = sections or []
    filters = filters or {}

    _check_role(report_name, role_u)

    meta = _REPORT_REGISTRY[report_name]
    handler = meta.handler

    content = handler(
        from_date=from_date,
        to_date=to_date,
        as_of_date=as_of_date,
        sections=sections,
        filters=filters,
        role=role_u,
        user_id=user_id,
        department=department,
        report_name=report_name,
    )

    footer = (
        "\n\n"
        "Sign-off:\n"
        f"  Printed by : {role_u}\n"
        f"  User ID    : {user_id}\n"
        f"  Department : {department}\n"
        f"  Generated  : {datetime.now(timezone.utc).isoformat()}\n"
    )
    return content.rstrip() + footer


# ============================================================
# Built-in handlers (lightweight / safe defaults)
# ============================================================

def _safe_read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
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


def _governance_summary_handler(**kwargs) -> str:
    path = Path("audit_logs") / "governance_decisions.jsonl"
    rows = _safe_read_jsonl(path)

    allow = 0
    block = 0
    for obj in rows:
        d = str(obj.get("decision") or "").strip().upper()
        if d == "ALLOW":
            allow += 1
        elif d == "BLOCK":
            block += 1

    return (
        "=== GOVERNANCE ANALYSIS SUMMARY ===\n"
        f"ALLOW : {allow}\n"
        f"BLOCK : {block}\n"
        f"SOURCE: {path.as_posix()}\n"
    )


def _ageing_wrapper(report_title: str, **kwargs) -> str:
    # Lazy import to avoid circulars
    from engine.reporting.ageing_reports import compute_ageing, format_ageing_report

    as_of = kwargs.get("as_of_date")
    filters = kwargs.get("filters") or {}

    if as_of:
        as_of_dt = datetime.strptime(str(as_of), "%Y-%m-%d").date()
    else:
        as_of_dt = datetime.now(timezone.utc).date()

    data = compute_ageing(filters, as_of_dt)
    return format_ageing_report(report_title, data)


def _ar_ageing_handler(**kwargs) -> str:
    return _ageing_wrapper("AR AGEING REPORT", **kwargs)


def _ap_ageing_handler(**kwargs) -> str:
    return _ageing_wrapper("AP AGEING REPORT", **kwargs)


def _gl_ageing_handler(**kwargs) -> str:
    return _ageing_wrapper("GL AGEING REPORT", **kwargs)


def _delegate_module_report(module_path: str, preferred_funcs: List[str], **kwargs) -> str:
    """
    Delegates to an existing report module without tightly binding to a single function name.
    We try a few conventional function names to keep your build resilient.
    """
    mod = __import__(module_path, fromlist=["*"])
    for fn in preferred_funcs:
        f = getattr(mod, fn, None)
        if callable(f):
            return str(f(**kwargs))
    raise AttributeError(
        f"{module_path} does not expose any of {preferred_funcs} (callable)."
    )


def _supervisory_control_pack_handler(**kwargs) -> str:
    # engine/reporting/supervisory_control_pack.py (already in your tree)
    return _delegate_module_report(
        "engine.reporting.supervisory_control_pack",
        preferred_funcs=["render", "generate", "build", "build_report", "printable"],
        **kwargs,
    )


def _treasury_instrument_aggregate_handler(**kwargs) -> str:
    # engine/reporting/treasury_instrument_aggregate.py (you created/registered earlier)
    return _delegate_module_report(
        "engine.reporting.treasury_instrument_aggregate",
        preferred_funcs=["render", "generate", "build", "build_report", "printable"],
        **kwargs,
    )


def _approval_queue_snapshot_handler(**kwargs) -> str:
    # If you later split this into a module, we keep this delegator stable.
    # For now, we attempt to delegate; if module missing, we print a clear fail-closed message.
    try:
        return _delegate_module_report(
            "engine.reporting.approval_queue_snapshot",
            preferred_funcs=["render", "generate", "build", "build_report", "printable"],
            **kwargs,
        )
    except Exception:
        return (
            "APPROVAL QUEUE SNAPSHOT\n"
            "-----------------------\n"
            "Report module not found: engine.reporting.approval_queue_snapshot\n"
            "Expected: a callable (render/generate/build/build_report/printable)\n"
        )


# ============================================================
# Register Reports (single place)
# ============================================================

def _register_builtin_reports() -> None:
    # Ageing + governance (FinCon-grade)
    register_report("ar_ageing", _ar_ageing_handler, COMMON_ROLES)
    register_report("ap_ageing", _ap_ageing_handler, COMMON_ROLES)
    register_report("gl_ageing", _gl_ageing_handler, COMMON_ROLES)
    register_report("governance_summary", _governance_summary_handler, COMMON_ROLES)

    # Control Pack (supervisor review)
    register_report("supervisory_control_pack", _supervisory_control_pack_handler, COMMON_ROLES)

    # Treasury aggregate (instrument-level)
    register_report("treasury_instrument_aggregate", _treasury_instrument_aggregate_handler, TREASURY_ROLES)

    # Unclosed approvals queue snapshot (next-day action list)
    register_report("approval_queue_snapshot", _approval_queue_snapshot_handler, COMMON_ROLES)


_register_builtin_reports()

__all__ = ["register_report", "list_reports", "print_report"]