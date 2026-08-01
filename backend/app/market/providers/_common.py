"""Phase 186A — shared offline provider constants and parsing helpers.

Freshness cutoff rule (inclusive):
  age_seconds <= max_age_seconds → FRESH
  age_seconds >  max_age_seconds → STALE
  age_seconds <  0               → FUTURE (fail-closed)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROVIDER_FRAMEWORK_VERSION = "186A.1"

OANDA_FIXTURE_PROVIDER_NAME = "OANDA_FIXTURE_MARKET_PROVIDER"
FX_FIXTURE_PROVIDER_NAME = "FIXTURE_FX_CONVERSION_PROVIDER"
FEE_FIXTURE_PROVIDER_NAME = "FIXTURE_FEE_MODEL_PROVIDER"
SLIPPAGE_FIXTURE_PROVIDER_NAME = "FIXTURE_SLIPPAGE_PROVIDER"
COMPOSITE_PROVIDER_NAME = "OFFLINE_CERTIFICATION_MICROSTRUCTURE_PROVIDER"

DEFAULT_QUOTE_MAX_AGE_SECONDS = 30.0
DEFAULT_FX_MAX_AGE_SECONDS = 86400.0
DEFAULT_TRIANGULATION_TIMESTAMP_WINDOW_SECONDS = 3600.0

# Approved fixture root for Phase 186A offline adapters (tests may override via ctor).
DEFAULT_FIXTURE_ROOT_NAME = "phase186a"


def resolve_approved_fixture_path(
    path: Path | str,
    *,
    approved_root: Path | None = None,
) -> Path:
    """Resolve path and reject traversal outside the approved fixture root."""
    candidate = Path(path).resolve()
    if approved_root is None:
        # Default: path must live under a directory named phase186a.
        if DEFAULT_FIXTURE_ROOT_NAME not in candidate.parts:
            raise ValueError("fixture path outside approved phase186a root")
        return candidate
    root = Path(approved_root).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("fixture path outside approved fixture root") from exc
    return candidate


def load_json_mapping(path: Path | str, *, approved_root: Path | None = None) -> Mapping[str, Any]:
    resolved = resolve_approved_fixture_path(path, approved_root=approved_root)
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fixture root must be an object")
    return data


def parse_utc_timestamp(value: Any) -> datetime:
    if value is None or not str(value).strip():
        raise ValueError("timestamp missing")
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_seconds(quote_time: datetime, evaluation_time: datetime) -> float:
    return (evaluation_time - quote_time).total_seconds()


def classify_freshness(
    *,
    quote_time: datetime,
    evaluation_time: datetime,
    max_age_seconds: float,
) -> tuple[str, float]:
    """Inclusive cutoff: age <= max_age → FRESH; age > max_age → STALE."""
    age = age_seconds(quote_time, evaluation_time)
    if age < 0:
        return "FUTURE", age
    if age > float(max_age_seconds):
        return "STALE", age
    return "FRESH", age


def require_positive_finite(name: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} invalid") from exc
    if number != number or number <= 0.0:
        raise ValueError(f"{name} must be positive finite")
    return number


def canonical_pair(base: str, quote: str) -> str:
    return f"{base.strip().upper()}/{quote.strip().upper()}"


def context_float(context: Mapping[str, Any] | None, key: str, default: float) -> float:
    if not isinstance(context, Mapping) or key not in context or context[key] is None:
        return float(default)
    return float(context[key])


def evaluation_time_from_context(context: Mapping[str, Any] | None) -> datetime:
    if isinstance(context, Mapping) and context.get("evaluation_time"):
        return parse_utc_timestamp(context["evaluation_time"])
    return datetime.now(timezone.utc)
