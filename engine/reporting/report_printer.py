"""
engine/reporting/report_printer.py

CSS Report Printer (FinCon-grade + Authority + Sign-off)
--------------------------------------------------------
- Registry of report generators
- Deterministic output formatting
- Authority gating (Admin / Super User / FinCon Reporting)
- Standard ReportRequest input for timeframe + sections + scope + sign-off
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Any, Optional, Iterable, Set, Tuple

from engine.reporting.report_request import ReportRequest, ReportCaller


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
    default_sections: Set[str]


_REPORTS: Dict[str, Tuple[ReportMeta, Callable[[ReportRequest], ReportResult]]] = {}


def register_report(
    report_id: str,
    *,
    title: str,
    required_roles: Optional[Iterable[str]] = None,
    required_permissions: Optional[Iterable[str]] = None,
    default_sections: Optional[Iterable[str]] = None,
):
    def decorator(fn: Callable[[ReportRequest], ReportResult]):
        meta = ReportMeta(
            report_id=str(report_id),
            title=str(title),
            required_roles=set(required_roles or []),
            required_permissions=set(required_permissions or []),
            default_sections=set(default_sections or []),
        )
        _REPORTS[str(report_id)] = (meta, fn)
        return fn

    return decorator


def list_reports() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for rid, (meta, _) in _REPORTS.items():
        out[rid] = {
            "title": meta.title,
            "required_roles": sorted(meta.required_roles),
            "required_permissions": sorted(meta.required_permissions),
            "default_sections": sorted(meta.default_sections),
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
    # Open report if no requirements
    if not required_roles and not required_permissions:
        return True

    # Fail-closed if requirements exist but caller context absent
    if not user_roles and not user_permissions:
        return False

    # Role gate (any-of)
    if required_roles and user_roles.intersection(required_roles):
        return True

    # Permission gate (any-of)
    if required_permissions and user_permissions.intersection(required_permissions):
        return True

    return False


def print_report(request: ReportRequest) -> ReportResult:
    if request.report_id not in _REPORTS:
        known = ", ".join(sorted(_REPORTS.keys())) or "(none)"
        raise ValueError(f"Unknown report_id='{request.report_id}'. Known: {known}")

    meta, fn = _REPORTS[request.report_id]

    roles = _normalize_set(request.caller.roles)
    perms = _normalize_set(request.caller.permissions)

    if not _has_authority(
        user_roles=roles,
        user_permissions=perms,
        required_roles=meta.required_roles,
        required_permissions=meta.required_permissions,
    ):
        raise PermissionError(
            f"Insufficient authority to print '{request.report_id}'. "
            f"Requires roles={sorted(meta.required_roles)} or permissions={sorted(meta.required_permissions)}."
        )

    # If caller didn’t specify sections, apply defaults (if defined)
    if not request.sections and meta.default_sections:
        request = ReportRequest(
            report_id=request.report_id,
            caller=request.caller,
            timeframe=request.timeframe,
            sections=set(meta.default_sections),
            scope_id=request.scope_id,
            account_ref=request.account_ref,
            currency=request.currency,
            target_user_id=request.target_user_id,
            params=dict(request.params),
        )

    return fn(request)


def build_caller(
    *,
    user_id: str,
    display_name: str = "",
    roles: Optional[Iterable[str]] = None,
    permissions: Optional[Iterable[str]] = None,
) -> ReportCaller:
    return ReportCaller(
        user_id=str(user_id),
        display_name=str(display_name or user_id),
        roles=set(roles or []),
        permissions=set(permissions or []),
    )