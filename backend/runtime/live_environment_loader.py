from __future__ import annotations

import os
from pathlib import Path
from typing import Any, MutableMapping

from dotenv import dotenv_values, load_dotenv


PAPER_ONLY_LIVE_BLOCKED_KEYS = ("COINBASE_TEST_ORDER_USD",)


def load_css_runtime_environment(
    project_root: str | Path,
    *,
    mode: str | None = None,
    env: MutableMapping[str, str] | None = None,
) -> dict[str, Any]:
    target_env = env if env is not None else os.environ
    root = Path(project_root)
    mode_key = _normalized_mode(mode or _mode_from_env(target_env))
    loaded = {
        "env_loaded": _load_env_file(root / ".env", target_env, override=False),
        "practice_env_loaded": False,
        "mode": mode_key,
        "removed_live_blocked_keys": [],
        "paper_only_keys_present_after_load": [],
        "secrets_redacted": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    if mode_key not in {"live", "unknown"}:
        loaded["practice_env_loaded"] = _load_env_file(root / ".env.practice", target_env, override=False)
    else:
        loaded["removed_live_blocked_keys"] = sanitize_live_environment(target_env)
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


def _load_env_file(path: Path, env: MutableMapping[str, str], *, override: bool) -> bool:
    if env is os.environ:
        return bool(load_dotenv(path, override=override))
    if not path.exists():
        return False
    loaded = False
    for key, value in dotenv_values(path).items():
        if value is None:
            continue
        if override or key not in env:
            env[str(key)] = str(value)
            loaded = True
    return loaded


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
    for key in ("CSS_BROKER_MODE", "SELECTED_BROKER_MODE", "BROKER_MODE", "CSS_RUNTIME_MODE", "ENGINE_MODE"):
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


__all__ = [
    "PAPER_ONLY_LIVE_BLOCKED_KEYS",
    "load_css_runtime_environment",
    "paper_only_coinbase_test_order_usd",
    "sanitize_live_environment",
]
