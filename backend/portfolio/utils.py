from __future__ import annotations

import math
from typing import Any, Iterable, Mapping


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric if math.isfinite(numeric) else default


to_float = safe_float


def clamp(value: Any, low: float, high: float, default: float | None = None) -> float:
    numeric = safe_float(value, low if default is None else default)
    return max(low, min(high, numeric))


bounded = clamp


def safe_series(values: Iterable[Any] | None) -> list[float]:
    if values is None or isinstance(values, (str, bytes)):
        return []
    result: list[float] = []
    try:
        for value in values:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric):
                result.append(numeric)
    except TypeError:
        return []
    return result


to_series = safe_series


def normalize_allocations(values: Mapping[str, Any] | None) -> dict[str, float]:
    if not isinstance(values, Mapping):
        return {}

    rows = []
    for key, value in values.items():
        name = str(key or "").strip().upper()
        if not name:
            continue
        weight = max(0.0, safe_float(value))
        rows.append({"name": name, "weight": weight})

    total = sum(row["weight"] for row in rows)
    if total <= 0.0:
        return {}

    basis_rows = []
    allocated = 0
    for row in sorted(rows, key=lambda item: item["name"]):
        exact = (row["weight"] / total) * 10000.0
        whole = int(exact)
        allocated += whole
        basis_rows.append({"name": row["name"], "basis_points": whole, "remainder": exact - whole})

    remaining = 10000 - allocated
    for row in sorted(basis_rows, key=lambda item: (-item["remainder"], item["name"]))[:remaining]:
        row["basis_points"] += 1

    return {row["name"]: round(row["basis_points"] / 100.0, 2) for row in sorted(basis_rows, key=lambda item: item["name"])}


def advisory_response(status: str, **payload: Any) -> dict[str, Any]:
    response = {"status": status, "advisory_only": True, "execution_allowed": False}
    response.update(payload)
    return response
