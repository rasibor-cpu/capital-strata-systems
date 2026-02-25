"""
engine/reporting/report_printer.py

CSS Report Printer (Regulator-Grade + Authority Gated)
------------------------------------------------------
Single entry point to generate reproducible reports on demand.

Key requirements:
- Registry of report generators
- Deterministic output formatting
- Authority gating (Admin/Super User/FinCon Reporting authority)
- Fail-closed: if a report requires authority and caller provides none -> BLOCK
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Dict, Any, Optional, Iterable, Set, Tuple


@dataclass(frozen=True)
class ReportResult:
    report_id: str
    title: str
    payload: Dict[str, Any]
    text: str


@dataclass(frozen=True)
class ReportMeta:
    report_id: str
    title: str
    required_roles: Set[str]
    required_permissions: Set[str]


# Registry: report_id -> (meta, generator)
_REPORTS: Dict[str, Tuple[ReportMeta, Callable[..., ReportResult]]] = {}


def register_report(
    report_id: str,
    *,
    title: str,
    required_roles: Optional[Iterable[str]] = None,
    required_permissions: Optional[Iterable[str]] = None,
):
    """
    Decorator to register a report generator with authority gating.

    required_roles example:
      {"ADMIN", "SUPER_USER", "FINCON_REPORTING"}

    required_permissions example:
      {"FINCON_REPORTING"}  (if your auth model is permission-based)
    """

    def decorator(fn: Callable[..., ReportResult]):
        meta = ReportMeta(
            report_id=str(report_id),
            title=str(title),
            required_roles=set(required_roles or []),
            required_permissions=set(required_permissions or []),
        )
        _REPORTS[str(report_id)] = (meta, fn)
        return fn

    return decorator


def list_reports() -> Dict[str, Dict[str, Any]]:
    """
    Returns report catalog for UI/journal listing.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for rid, (meta, fn) in _REPORTS.items():
        out[rid] = {
            "title": meta.title,
            "required_roles": sorted(meta.required_roles),
            "required_permissions": sorted(meta.required_permissions),
        }
    return out


def _normalize_set(v: Any) -> Set[str]:
    if v is None:
        return set()
    if isinstance(v, (set, list, tuple)):
        return {str(x) for x in v}
    return {str(v)}


def _has_authority(
    *,
    user_roles: Set[str],
    user_permissions: Set[str],
    required_roles: Set[str],
    required_permissions: Set[str],
) -> bool:
    # If nothing required => open report
    if not required_roles and not required_permissions:
        return True

    # If requirements exist but no caller context => fail closed
    if not user_roles and not user_permissions:
        return False

    # Role gate (any-of)
    if required_roles and (user_roles.intersection(required_roles)):
        return True

    # Permission gate (any-of)
    if required_permissions and (user_permissions.intersection(required_permissions)):
        return True

    return False


def print_report(
    report_id: str,
    *,
    user_roles: Optional[Iterable[str]] = None,
    user_permissions: Optional[Iterable[str]] = None,
    **kwargs,
) -> ReportResult:
    """
    Canonical print entrypoint used by FinCon journal/print flows.

    - Enforces authority gating per report meta.
    - Returns ReportResult (text + payload) for printing/export.
    """
    if report_id not in _REPORTS:
        known = ", ".join(sorted(_REPORTS.keys())) or "(none)"
        raise ValueError(f"Unknown report_id='{report_id}'. Known: {known}")

    meta, fn = _REPORTS[report_id]

    roles = _normalize_set(user_roles)
    perms = _normalize_set(user_permissions)

    if not _has_authority(
        user_roles=roles,
        user_permissions=perms,
        required_roles=meta.required_roles,
        required_permissions=meta.required_permissions,
    ):
        raise PermissionError(
            f"Insufficient authority to print '{report_id}'. "
            f"Requires roles={sorted(meta.required_roles)} or permissions={sorted(meta.required_permissions)}."
        )

    return fn(**kwargs)