"""
Broker dependency checks for CSS bootstrap.

This module only verifies whether approved broker SDK packages are importable.
It does not auto-install dependencies during bootstrap.
"""

from __future__ import annotations

import importlib.util
from typing import Dict

from .broker_registry import get_broker_spec


PACKAGE_IMPORT_NAME_MAP: Dict[str, str] = {
    "coinbase-advanced-py": "coinbase",
    "oandapyV20": "oandapyV20",
    "alpaca-py": "alpaca",
}


class BrokerDependencyError(Exception):
    """Raised when a broker dependency is unavailable or unapproved."""


def _resolve_import_name(pip_package: str) -> str:
    if pip_package not in PACKAGE_IMPORT_NAME_MAP:
        raise BrokerDependencyError(f"Unrecognized broker package '{pip_package}'.")
    return PACKAGE_IMPORT_NAME_MAP[pip_package]


def is_package_installed(pip_package: str) -> bool:
    import_name = _resolve_import_name(pip_package)
    return importlib.util.find_spec(import_name) is not None


def ensure_package_installed(pip_package: str) -> Dict[str, object]:
    installed = is_package_installed(pip_package)
    return {
        "ok": installed,
        "installed": installed,
        "action": "none" if installed else "install_required",
        "package": pip_package,
    }


def ensure_broker_dependencies(broker_name: str) -> Dict[str, object]:
    spec = get_broker_spec(broker_name)
    return ensure_package_installed(spec.pip_package)
