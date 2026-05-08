from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from dashboard.runtime.dashboard_state import DashboardState


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DashboardShadowDivergence:
    path: str
    legacy_value: Any
    dashboard_state_value: Any
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "legacy_value": self.legacy_value,
            "dashboard_state_value": self.dashboard_state_value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DashboardShadowComparison:
    matched: bool
    compared_count: int
    divergence_count: int
    divergences: list[DashboardShadowDivergence] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "compared_count": self.compared_count,
            "divergence_count": self.divergence_count,
            "divergences": [
                divergence.as_dict() for divergence in self.divergences
            ],
        }


def compare_dashboard_shadow(
    legacy_panel_values: Mapping[str, Any] | None,
    dashboard_state: DashboardState | Mapping[str, Any],
    *,
    paths: Iterable[str] | None = None,
    logger: logging.Logger | None = None,
) -> DashboardShadowComparison:
    """
    Compare legacy panel values with DashboardState output in shadow mode.

    This function never raises on mismatches. It reports divergences and logs
    them so callers can observe migration drift without blocking execution.
    """

    active_logger = logger or LOGGER
    legacy_payload = dict(legacy_panel_values or {})
    dashboard_payload = _dashboard_payload(dashboard_state)

    legacy_flat = _flatten_payload(legacy_payload)
    dashboard_flat = _flatten_payload(dashboard_payload)
    paths_to_compare = list(paths or legacy_flat.keys())

    divergences: list[DashboardShadowDivergence] = []

    for path in paths_to_compare:
        legacy_exists = path in legacy_flat
        dashboard_exists = path in dashboard_flat

        if not legacy_exists:
            divergences.append(
                DashboardShadowDivergence(
                    path=path,
                    legacy_value=None,
                    dashboard_state_value=dashboard_flat.get(path),
                    reason="legacy_value_missing",
                )
            )
            continue

        if not dashboard_exists:
            divergences.append(
                DashboardShadowDivergence(
                    path=path,
                    legacy_value=legacy_flat.get(path),
                    dashboard_state_value=None,
                    reason="dashboard_state_value_missing",
                )
            )
            continue

        legacy_value = legacy_flat[path]
        dashboard_value = dashboard_flat[path]

        if not _values_match(legacy_value, dashboard_value):
            divergences.append(
                DashboardShadowDivergence(
                    path=path,
                    legacy_value=legacy_value,
                    dashboard_state_value=dashboard_value,
                    reason="value_mismatch",
                )
            )

    result = DashboardShadowComparison(
        matched=not divergences,
        compared_count=len(paths_to_compare),
        divergence_count=len(divergences),
        divergences=divergences,
    )
    log_dashboard_shadow_comparison(result, logger=active_logger)
    return result


def log_dashboard_shadow_comparison(
    comparison: DashboardShadowComparison,
    *,
    logger: logging.Logger | None = None,
) -> None:
    active_logger = logger or LOGGER

    if comparison.matched:
        active_logger.info(
            "Dashboard shadow comparison matched %s value(s)",
            comparison.compared_count,
        )
        return

    for divergence in comparison.divergences:
        active_logger.warning(
            "Dashboard shadow divergence path=%s reason=%s legacy=%r "
            "dashboard_state=%r",
            divergence.path,
            divergence.reason,
            divergence.legacy_value,
            divergence.dashboard_state_value,
        )


def _dashboard_payload(
    dashboard_state: DashboardState | Mapping[str, Any],
) -> Mapping[str, Any]:
    if isinstance(dashboard_state, DashboardState):
        return dashboard_state.to_dict()

    if isinstance(dashboard_state, Mapping):
        return dashboard_state

    raise TypeError("dashboard_state must be DashboardState or mapping")


def _flatten_payload(
    payload: Mapping[str, Any],
    *,
    prefix: str = "",
) -> dict[str, Any]:
    flattened: dict[str, Any] = {}

    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else str(key)

        if isinstance(value, Mapping):
            flattened.update(_flatten_payload(value, prefix=path))
            continue

        flattened[path] = value

    return flattened


def _values_match(left: Any, right: Any) -> bool:
    left_numeric = _to_decimal(left)
    right_numeric = _to_decimal(right)

    if left_numeric is not None and right_numeric is not None:
        return left_numeric == right_numeric

    return left == right


def _to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(value, (int, float, str)):
        text = str(value).strip()
        if not text:
            return None

        try:
            return Decimal(text)
        except InvalidOperation:
            return None

    return None


__all__ = [
    "DashboardShadowComparison",
    "DashboardShadowDivergence",
    "compare_dashboard_shadow",
    "log_dashboard_shadow_comparison",
]
