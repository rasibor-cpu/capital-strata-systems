"""Canonical freshness / retry policy for Daily Executive Brief readiness."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from backend.executive_intelligence.constants import SAFETY_LOCKS

_DEFAULT_POLICY_PATH = Path(__file__).resolve().parent / "config" / "executive_brief_freshness.json"

# Built-in defaults used only when the policy file is missing (tests may override).
_BUILTIN_DEFAULTS: dict[str, Any] = {
    "schema_version": "css.executive_brief_freshness_policy.v1",
    "retry_interval_seconds": 60,
    "max_wait_seconds": 1800,
    "advisory_only": True,
    "gates": {
        "runtime_snapshot": {"max_age_seconds": 90, "required": True, "allow_absent_when_advisory": False},
        "executive_kpi_snapshot": {"max_age_seconds": 120, "required": True, "allow_absent_when_advisory": False},
        "portfolio_snapshot": {"max_age_seconds": 120, "required": True, "allow_absent_when_advisory": False},
        "risk_snapshot": {"max_age_seconds": 120, "required": True, "allow_absent_when_advisory": True},
        "market_snapshot": {"max_age_seconds": 300, "required": True, "allow_absent_when_advisory": False},
        "learning_snapshot": {"max_age_seconds": 1800, "required": True, "allow_absent_when_advisory": True},
        "broker_snapshot": {
            "max_age_seconds": 300,
            "required": True,
            "allow_absent_when_advisory": False,
            "never_ready_when_unavailable": True,
        },
        "system_heartbeat": {"max_age_seconds": 60, "required": True, "allow_absent_when_advisory": False},
    },
}

GATE_IDS = tuple(_BUILTIN_DEFAULTS["gates"].keys())


def load_freshness_policy(
    *,
    policy_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load freshness policy from JSON; apply optional overrides. No scheduler hard-codes."""
    path = Path(policy_path) if policy_path else _DEFAULT_POLICY_PATH
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            policy = raw if isinstance(raw, dict) else deepcopy(_BUILTIN_DEFAULTS)
        except Exception:
            policy = deepcopy(_BUILTIN_DEFAULTS)
    else:
        policy = deepcopy(_BUILTIN_DEFAULTS)

    # Align advisory flag with platform safety locks unless explicitly overridden.
    if "advisory_only" not in (overrides or {}):
        policy["advisory_only"] = bool(SAFETY_LOCKS.get("advisory_only", True))

    if overrides:
        policy = _deep_merge(policy, overrides)
    policy.setdefault("gates", {})
    for gate_id, defaults in _BUILTIN_DEFAULTS["gates"].items():
        policy["gates"].setdefault(gate_id, deepcopy(defaults))
    return policy


def gate_config(policy: dict[str, Any], gate_id: str) -> dict[str, Any]:
    gates = policy.get("gates") if isinstance(policy.get("gates"), dict) else {}
    cfg = gates.get(gate_id) if isinstance(gates.get(gate_id), dict) else {}
    base = deepcopy(_BUILTIN_DEFAULTS["gates"].get(gate_id, {}))
    base.update(cfg)
    return base


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


__all__ = ["GATE_IDS", "load_freshness_policy", "gate_config"]
