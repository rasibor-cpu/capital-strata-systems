from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime._utils import safe_float
from engine.ledger import CANONICAL_PNL_SOURCE


PNL_PARITY_FIELDS = (
    "realized_pnl",
    "unrealized_pnl",
    "net_pnl",
)


def compare_pnl_summary_parity(
    dashboard_summary: Dict[str, Any] | None,
    canonical_summary: Dict[str, Any] | None,
    *,
    tolerance: float = 1e-9,
) -> Dict[str, Any]:
    """
    Compare dashboard PnL summary values with canonical adapter output.

    This helper is intentionally read-only and non-runtime. It does not import
    or invoke the live dashboard script, broker adapters, or risk controls.
    """

    dashboard = dashboard_summary or {}
    canonical = canonical_summary or {}

    field_diffs = {
        field: _diff(dashboard.get(field), canonical.get(field))
        for field in PNL_PARITY_FIELDS
    }
    asset_realized_diffs = _map_diffs(
        dashboard.get("asset_realized_pnl", {}),
        canonical.get("asset_realized_pnl", {}),
    )
    asset_unrealized_diffs = _map_diffs(
        dashboard.get("asset_unrealized_pnl", {}),
        canonical.get("asset_unrealized_pnl", {}),
    )

    all_diffs = [
        *field_diffs.values(),
        *asset_realized_diffs.values(),
        *asset_unrealized_diffs.values(),
    ]
    matches = all(abs(value) <= tolerance for value in all_diffs)

    return {
        "matches": matches,
        "field_diffs": field_diffs,
        "asset_realized_diffs": asset_realized_diffs,
        "asset_unrealized_diffs": asset_unrealized_diffs,
        "canonical_source": str(canonical.get("source", "")),
        "canonical_source_expected": CANONICAL_PNL_SOURCE,
    }


def _map_diffs(
    dashboard_map: Any,
    canonical_map: Any,
) -> Dict[str, float]:
    left = _safe_map(dashboard_map)
    right = _safe_map(canonical_map)
    keys = sorted(set(left) | set(right))

    return {
        key: _diff(left.get(key, 0.0), right.get(key, 0.0))
        for key in keys
    }


def _safe_map(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}

    return {
        str(key): safe_float(amount)
        for key, amount in value.items()
    }


def _diff(left: Any, right: Any) -> float:
    return safe_float(left) - safe_float(right)
