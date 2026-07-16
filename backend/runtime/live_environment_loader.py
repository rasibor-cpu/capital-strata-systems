from __future__ import annotations

import os
from pathlib import Path
from typing import Any, MutableMapping

from backend.runtime.broker_environment_profiles import (
    BrokerEnvironmentProfile,
    build_broker_environment,
    profile_mode_alias,
    profile_trace,
)


PAPER_ONLY_LIVE_BLOCKED_KEYS = ("COINBASE_TEST_ORDER_USD",)


def load_css_runtime_environment(
    project_root: str | Path,
    *,
    mode: str | None = None,
    profile: str | BrokerEnvironmentProfile | None = None,
    broker: str = "COINBASE",
    env: MutableMapping[str, str] | None = None,
) -> dict[str, Any]:
    target_env = env if env is not None else os.environ
    legacy_profile = profile or profile_mode_alias(mode)
    credentials = build_broker_environment(
        project_root,
        broker=broker,
        explicit_profile=legacy_profile,
        env=target_env,
        allow_legacy="PYTEST_CURRENT_TEST" not in os.environ,
    )
    trace = profile_trace(credentials)
    mode_key = _mode_from_profile(credentials.profile)
    loaded = {
        **trace,
        "env_loaded": any(Path(path).name == ".env" for path in credentials.loaded_files),
        "shared_env_loaded": any(Path(path).name == ".env.shared" for path in credentials.loaded_files),
        "paper_env_loaded": any(Path(path).name == ".env.paper" for path in credentials.loaded_files),
        "live_read_only_env_loaded": any(Path(path).name == ".env.live_read_only" for path in credentials.loaded_files),
        "live_execution_env_loaded": any(Path(path).name == ".env.live_execution" for path in credentials.loaded_files),
        "practice_env_loaded": any(Path(path).name == ".env.practice" for path in credentials.loaded_files),
        "mode": mode_key,
        "profile": credentials.profile.value if credentials.profile else "UNSELECTED",
        "canonical_broker_environment": credentials.redacted_diagnostics(),
        "removed_live_blocked_keys": [],
        "paper_only_keys_present_after_load": [],
        "secrets_redacted": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    loaded["removed_live_blocked_keys"] = [
        key for key in credentials.removed_inherited_variables if key in PAPER_ONLY_LIVE_BLOCKED_KEYS
    ]
    loaded["paper_only_keys_present_after_load"] = [
        key for key in PAPER_ONLY_LIVE_BLOCKED_KEYS if target_env.get(key) not in (None, "")
    ]
    return loaded


def sanitize_live_environment(env: MutableMapping[str, str] | None = None) -> list[str]:
    target_env = env if env is not None else os.environ
    removed: list[str] = []
    for key in PAPER_ONLY_LIVE_BLOCKED_KEYS:
        if target_env.get(key) not in (None, ""):
            target_env.pop(key, None)
            removed.append(key)
    return removed


def paper_only_coinbase_test_order_usd(
    *,
    mode: str | None = None,
    env: MutableMapping[str, str] | None = None,
    default: float = 1.0,
) -> float:
    target_env = env if env is not None else os.environ
    if _normalized_mode(mode or _mode_from_env(target_env)) == "live":
        return default
    try:
        return float(target_env.get("COINBASE_TEST_ORDER_USD", str(default)) or default)
    except (TypeError, ValueError):
        return default


def _mode_from_env(env: MutableMapping[str, str]) -> str:
    for key in ("CSS_BROKER_MODE", "SELECTED_BROKER_MODE", "BROKER_MODE", "CSS_RUNTIME_MODE"):
        value = str(env.get(key, "") or "").strip()
        if value:
            return value
    return "unknown"


def _normalized_mode(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if text in {"live", "production", "prod"}:
        return "live"
    if text in {"paper", "practice", "demo", "sim", "simulation", "safe"}:
        return "paper"
    return "unknown"


def _mode_from_profile(profile: BrokerEnvironmentProfile | None) -> str:
    if profile == BrokerEnvironmentProfile.PAPER:
        return "paper"
    if profile in {BrokerEnvironmentProfile.LIVE_READ_ONLY, BrokerEnvironmentProfile.LIVE_EXECUTION}:
        return "live"
    return "unknown"


__all__ = [
    "PAPER_ONLY_LIVE_BLOCKED_KEYS",
    "load_css_runtime_environment",
    "paper_only_coinbase_test_order_usd",
    "sanitize_live_environment",
]
