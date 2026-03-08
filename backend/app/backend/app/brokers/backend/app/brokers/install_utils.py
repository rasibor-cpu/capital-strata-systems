"""
Broker Install Utilities
Capital Strata Systems (CSS)

Purpose:
- Check whether the SDK/package required for a selected broker is installed.
- Optionally install the missing package in a controlled way.
- Support startup-time broker bootstrap validation.

Rules:
- Never install an unknown package.
- Never silently switch to another package.
- Fail closed on install/check errors.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from typing import Dict


PACKAGE_IMPORT_NAME_MAP: Dict[str, str] = {
    "coinbase-advanced-py": "coinbase",
    "oandapyV20": "oandapyV20",
    "alpaca-py": "alpaca",
}


def _resolve_import_name(pip_package: str) -> str:
    """
    Resolve the Python import name from a pip package name.
    """
    if pip_package not in PACKAGE_IMPORT_NAME_MAP:
        raise KeyError(
            f"Unrecognized package '{pip_package}' for broker install utility."
        )
    return PACKAGE_IMPORT_NAME_MAP[pip_package]


def is_package_installed(pip_package: str) -> bool:
    """
    Return True if the broker package is importable in the current environment.
    """
    import_name = _resolve_import_name(pip_package)
    return importlib.util.find_spec(import_name) is not None


def install_package(pip_package: str) -> bool:
    """
    Install a broker package using pip.

    Returns:
        bool: True if installation succeeds.

    Raises:
        RuntimeError: If installation fails.
    """
    if pip_package not in PACKAGE_IMPORT_NAME_MAP:
        raise KeyError(
            f"Refusing to install unknown package '{pip_package}'."
        )

    command = [sys.executable, "-m", "pip", "install", pip_package]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Package installation failed for "
            f"'{pip_package}'. stderr={result.stderr.strip()}"
        )

    return True


def ensure_package_installed(
    pip_package: str,
    auto_install: bool = False,
) -> Dict[str, object]:
    """
    Ensure the required broker package is installed.

    Returns a structured status payload.
    """
    installed = is_package_installed(pip_package)
    if installed:
        return {
            "ok": True,
            "installed": True,
            "action": "none",
            "package": pip_package,
        }

    if not auto_install:
        return {
            "ok": False,
            "installed": False,
            "action": "install_required",
            "package": pip_package,
        }

    install_package(pip_package)
    return {
        "ok": True,
        "installed": True,
        "action": "installed",
        "package": pip_package,
    }
