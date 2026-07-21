"""Phase 178A — sanitized advisory data cache helpers (atomic writes)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from backend.app.brokers.operational_state import sanitize_value
from backend.options.options_income_freshness import evaluate_freshness, utc_now

CACHE_SCHEMA_VERSION = "css.options_income.advisory_cache.v1"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def state_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(_json_safe(dict(payload)), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def wrap_cache_entry(
    *,
    provider: str,
    data_type: str,
    payload: Mapping[str, Any],
    provider_timestamp: str | None = None,
    broker: str | None = None,
) -> dict[str, Any]:
    ts = utc_now()
    fresh = evaluate_freshness(data_type, provider_timestamp=provider_timestamp or ts, now=ts)
    # Recursively redact credentials and account identifiers before persistence.
    body = _json_safe(sanitize_value(dict(payload)))
    entry = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "provider": provider,
        "broker": broker,
        "data_type": data_type,
        "payload": body,
        "generated_at": ts,
        "provider_timestamp": provider_timestamp,
        "received_at": ts,
        "age_seconds": fresh.get("age_seconds"),
        "freshness": fresh.get("freshness"),
        "stale": bool(fresh.get("stale")),
        "stale_reason": fresh.get("stale_reason"),
        "provenance": "CACHE",
        "source_provenance": payload.get("provenance") if isinstance(payload, Mapping) else None,
        "live_masquerade_allowed": False,
        "advisory_only": True,
        "execution_allowed": False,
    }
    entry["state_hash"] = state_hash(entry)
    return entry


def atomic_write_cache(path: Path, entry: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(_json_safe(dict(entry)), indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def read_cache_entry(path: Path, *, data_type: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    # Re-evaluate freshness against now — stale cache must not silently look live
    provider_ts = raw.get("provider_timestamp")
    fresh = evaluate_freshness(data_type, provider_timestamp=provider_ts, now=utc_now())
    # Protect consumers from legacy cache entries written before recursive redaction.
    out = dict(sanitize_value(raw))
    out["freshness"] = fresh.get("freshness")
    out["stale"] = bool(fresh.get("stale"))
    out["stale_reason"] = fresh.get("stale_reason")
    out["age_seconds"] = fresh.get("age_seconds")
    out["live_masquerade_allowed"] = False
    if out["stale"]:
        out["status"] = "STALE"
    return out


__all__ = [
    "CACHE_SCHEMA_VERSION",
    "atomic_write_cache",
    "read_cache_entry",
    "state_hash",
    "wrap_cache_entry",
]
