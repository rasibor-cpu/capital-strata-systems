"""Deterministic, redacted broker environment bootstrap.

This module loads the canonical repository ``.env`` before broker consumers are
imported. It never authenticates a broker, reads private-key contents, grants
execution authority, or includes environment values in its diagnostics.
"""

from __future__ import annotations

import os
import re
import sys
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, MutableMapping

from dotenv import dotenv_values

CANONICAL_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

COINBASE_IDENTITY_KEYS = (
    "COINBASE_CDP_KEY_NAME",
    "COINBASE_KEY_NAME",
    "COINBASE_API_KEY",
)
COINBASE_PRIVATE_KEY_KEYS = (
    "COINBASE_CDP_PRIVATE_KEY",
    "COINBASE_PRIVATE_KEY",
    "COINBASE_API_SECRET",
    "COINBASE_CDP_PRIVATE_KEY_PATH",
    "COINBASE_PRIVATE_KEY_PATH",
    "COINBASE_KEY_FILE",
    "COINBASE_KEY_JSON_PATH",
    "COINBASE_KEY_JSON",
)
OANDA_TOKEN_KEYS = ("OANDA_API_KEY", "OANDA_ACCESS_TOKEN", "OANDA_TOKEN")
OANDA_ACCOUNT_KEYS = (
    "OANDA_ACCOUNT_ID",
    "OANDA_LIVE_ACCOUNT_ID",
    "OANDA_PRACTICE_ACCOUNT_ID",
)
PRIVATE_KEY_PATH_KEYS = (
    "COINBASE_CDP_PRIVATE_KEY_PATH",
    "COINBASE_PRIVATE_KEY_PATH",
    "COINBASE_KEY_FILE",
    "COINBASE_KEY_JSON_PATH",
)
LIVE_ENABLE_KEYS = frozenset(
    {
        "ALLOW_LIVE_TRADING",
        "BROKER_ENABLE_LIVE_ORDERS",
        "COINBASE_ENABLE_LIVE_ORDERS",
        "COINBASE_ENABLE_LIVE_TRADING",
        "CSS_ENABLE_LIVE_TRADING",
        "ENABLE_LIVE_TRADING",
        "OANDA_ENABLE_LIVE_ORDERS",
        "OANDA_ENABLE_LIVE_TRADING",
        "BINANCE_ENABLE_LIVE_ORDERS",
        "BINANCE_ENABLE_LIVE_TRADING",
        "QUESTRADE_ENABLE_LIVE_ORDERS",
        "REA_LIVE_ARM",
        "REA_CONFIRM_LIVE",
    }
)

_ENV_ASSIGNMENT = re.compile(
    r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=",
)
_LOCK = threading.RLock()
_CACHE: dict[tuple[int, str], "EnvironmentBootstrapDiagnostics"] = {}


@dataclass(frozen=True)
class PathReferenceDiagnostic:
    variable: str
    reference_present: bool
    reference_length: int
    absolute: bool
    target_exists: bool
    target_is_file: bool
    target_readable: bool


@dataclass(frozen=True)
class EnvironmentBootstrapDiagnostics:
    status: str
    repository_root_resolved: bool
    env_file: str
    env_file_exists: bool
    env_file_readable: bool
    loaded_key_count: int
    skipped_existing_key_count: int
    duplicate_keys: tuple[tuple[str, int], ...]
    blocked_live_enable_keys: tuple[str, ...]
    blocked_explicit_live_enable_keys: tuple[str, ...]
    explicit_live_enable_keys: tuple[str, ...]
    coinbase_configuration_present: bool
    oanda_configuration_present: bool
    path_references: tuple[PathReferenceDiagnostic, ...]
    idempotent: bool = True
    secrets_redacted: bool = True
    broker_authentication_attempted: bool = False
    broker_network_call_attempted: bool = False
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    advisory_only: bool = True

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["duplicate_keys"] = [
            {"name": name, "occurrences": count}
            for name, count in self.duplicate_keys
        ]
        return payload


def resolve_repository_root(project_root: str | Path | None = None) -> Path:
    """Resolve the repository root without depending on the working directory."""
    return (
        Path(project_root).expanduser().resolve()
        if project_root is not None
        else CANONICAL_REPOSITORY_ROOT
    )


def bootstrap_broker_environment(
    project_root: str | Path | None = None,
    *,
    env: MutableMapping[str, str] | None = None,
) -> EnvironmentBootstrapDiagnostics:
    """Load canonical ``.env`` once with explicit environment precedence.

    Truthy live-enable values are forced to ``false`` regardless of source.
    This is the sole precedence exception and enforces the fail-closed policy.
    All other existing process values take precedence. Returned diagnostics
    are metadata-only.
    """

    root = resolve_repository_root(project_root)
    target_env = env if env is not None else os.environ
    cache_key = (id(target_env), str(root))

    with _LOCK:
        cached = _CACHE.get(cache_key)
        if cached is not None:
            return cached

        if env is None and root == CANONICAL_REPOSITORY_ROOT and _is_test_process():
            diagnostics = _diagnostics(
                status="SKIPPED_TEST_PROCESS",
                root=root,
                env_file=root / ".env",
                target_env=target_env,
            )
            _CACHE[cache_key] = diagnostics
            return diagnostics

        env_file = root / ".env"
        blocked_explicit_live: list[str] = []
        for key in sorted(LIVE_ENABLE_KEYS):
            if key in target_env and _truthy(target_env.get(key)):
                target_env[key] = "false"
                blocked_explicit_live.append(key)

        if not env_file.is_file():
            diagnostics = _diagnostics(
                status="MISSING",
                root=root,
                env_file=env_file,
                target_env=target_env,
                blocked_explicit_live_enable_keys=blocked_explicit_live,
            )
            _CACHE[cache_key] = diagnostics
            return diagnostics

        try:
            parsed = dotenv_values(env_file)
            duplicate_keys = _duplicate_key_counts(env_file)
        except Exception:
            diagnostics = _diagnostics(
                status="READ_ERROR",
                root=root,
                env_file=env_file,
                target_env=target_env,
                blocked_explicit_live_enable_keys=blocked_explicit_live,
            )
            _CACHE[cache_key] = diagnostics
            return diagnostics

        loaded_keys: list[str] = []
        skipped_existing: list[str] = []
        blocked_live: list[str] = []
        for raw_key, raw_value in parsed.items():
            key = str(raw_key)
            if raw_value is None:
                continue
            value = str(raw_value)
            if key in LIVE_ENABLE_KEYS and _truthy(value):
                blocked_live.append(key)
                if key not in target_env:
                    target_env[key] = "false"
                    loaded_keys.append(key)
                continue
            if key in target_env:
                skipped_existing.append(key)
                continue
            target_env[key] = value
            loaded_keys.append(key)

        diagnostics = _diagnostics(
            status="LOADED",
            root=root,
            env_file=env_file,
            target_env=target_env,
            loaded_key_count=len(loaded_keys),
            skipped_existing_key_count=len(skipped_existing),
            duplicate_keys=duplicate_keys,
            blocked_live_enable_keys=blocked_live,
            blocked_explicit_live_enable_keys=blocked_explicit_live,
        )
        _CACHE[cache_key] = diagnostics
        return diagnostics


def _diagnostics(
    *,
    status: str,
    root: Path,
    env_file: Path,
    target_env: MutableMapping[str, str],
    loaded_key_count: int = 0,
    skipped_existing_key_count: int = 0,
    duplicate_keys: dict[str, int] | None = None,
    blocked_live_enable_keys: list[str] | None = None,
    blocked_explicit_live_enable_keys: list[str] | None = None,
) -> EnvironmentBootstrapDiagnostics:
    explicit_live = tuple(
        sorted(
            key
            for key in LIVE_ENABLE_KEYS
            if key in target_env and _truthy(target_env.get(key))
        )
    )
    return EnvironmentBootstrapDiagnostics(
        status=status,
        repository_root_resolved=root.is_dir(),
        env_file=".env",
        env_file_exists=env_file.is_file(),
        env_file_readable=os.access(env_file, os.R_OK) if env_file.exists() else False,
        loaded_key_count=loaded_key_count,
        skipped_existing_key_count=skipped_existing_key_count,
        duplicate_keys=tuple(sorted((duplicate_keys or {}).items())),
        blocked_live_enable_keys=tuple(sorted(blocked_live_enable_keys or [])),
        blocked_explicit_live_enable_keys=tuple(
            sorted(blocked_explicit_live_enable_keys or [])
        ),
        explicit_live_enable_keys=explicit_live,
        coinbase_configuration_present=(
            _any_present(target_env, COINBASE_IDENTITY_KEYS)
            and _any_present(target_env, COINBASE_PRIVATE_KEY_KEYS)
        ),
        oanda_configuration_present=(
            _any_present(target_env, OANDA_TOKEN_KEYS)
            and _any_present(target_env, OANDA_ACCOUNT_KEYS)
        ),
        path_references=_path_reference_diagnostics(root, target_env),
    )


def _duplicate_key_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            match = _ENV_ASSIGNMENT.match(line)
            if match:
                key = match.group(1)
                counts[key] = counts.get(key, 0) + 1
    return {key: count for key, count in counts.items() if count > 1}


def _path_reference_diagnostics(
    root: Path,
    env: MutableMapping[str, str],
) -> tuple[PathReferenceDiagnostic, ...]:
    diagnostics: list[PathReferenceDiagnostic] = []
    for key in PRIVATE_KEY_PATH_KEYS:
        value = str(env.get(key, "") or "")
        reference = Path(value).expanduser() if value else None
        if reference is not None and not reference.is_absolute():
            reference = root / reference
        diagnostics.append(
            PathReferenceDiagnostic(
                variable=key,
                reference_present=bool(value),
                reference_length=len(value),
                absolute=bool(value and Path(value).is_absolute()),
                target_exists=bool(reference and reference.exists()),
                target_is_file=bool(reference and reference.is_file()),
                target_readable=bool(
                    reference and reference.is_file() and os.access(reference, os.R_OK)
                ),
            )
        )
    return tuple(diagnostics)


def _any_present(env: MutableMapping[str, str], keys: tuple[str, ...]) -> bool:
    return any(str(env.get(key, "") or "").strip() for key in keys)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
        "enable",
    }


def _is_test_process() -> bool:
    return "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ


def _reset_environment_bootstrap_for_tests() -> None:
    with _LOCK:
        _CACHE.clear()


__all__ = [
    "CANONICAL_REPOSITORY_ROOT",
    "EnvironmentBootstrapDiagnostics",
    "LIVE_ENABLE_KEYS",
    "PathReferenceDiagnostic",
    "bootstrap_broker_environment",
    "resolve_repository_root",
]
