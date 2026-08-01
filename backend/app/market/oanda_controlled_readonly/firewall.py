"""Phase 188 — static execution firewall for controlled OANDA RO certification."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

from backend.runtime.oanda_live_read_only_adapter import OandaLiveReadOnlyAdapter

PACKAGE_ROOT = Path(__file__).resolve().parent

FORBIDDEN_METHOD_NAMES: frozenset[str] = frozenset(
    {
        "place_order",
        "submit_order",
        "cancel_order",
        "modify_order",
        "create_order",
        "close_order",
        "close_trade",
        "close_position",
        "arm_live_authority",
        "enable_execution",
        "set_execution_enabled",
        "modify_anti_bleed",
        "set_anti_bleed_min_size",
        "modify_risk_governor",
        "modify_phase152a",
        "modify_margin",
        "disable_kill_switch",
    }
)

# Phase 188 modules that may perform controlled network I/O (still no orders).
NETWORK_ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "readonly_transport.py",
        "network_validators.py",
        "certified_provider.py",
    }
)

FORBIDDEN_BROKER_IMPORT = "backend.app.brokers.oanda_adapter"


def adapter_has_no_write_methods(adapter_cls: type = OandaLiveReadOnlyAdapter) -> dict[str, Any]:
    public = {
        name
        for name in dir(adapter_cls)
        if not name.startswith("_") and callable(getattr(adapter_cls, name, None))
    }
    hits = sorted(
        name
        for name in public
        if any(
            frag in name.lower()
            for frag in (
                "place_order",
                "submit_order",
                "cancel_order",
                "modify_order",
                "close_trade",
                "close_position",
                "arm_live",
                "enable_execution",
            )
        )
        or name in FORBIDDEN_METHOD_NAMES
    )
    return {
        "ok": len(hits) == 0,
        "forbidden_methods_found": hits,
        "adapter": adapter_cls.__name__,
        "execution_authority": False,
    }


def provider_forbids_execution(provider: Any) -> dict[str, Any]:
    forbidden = getattr(provider, "FORBIDDEN_METHODS", frozenset())
    missing = sorted(FORBIDDEN_METHOD_NAMES - set(forbidden))
    # Probe attribute denial if present.
    denied: list[str] = []
    for name in sorted(FORBIDDEN_METHOD_NAMES):
        try:
            getattr(provider, name)
            denied.append(name)  # accessible = bad for order methods on provider
        except AttributeError:
            pass
        except Exception:
            pass
    return {
        "ok": not missing and not denied,
        "missing_forbidden_guards": missing,
        "accidentally_accessible": denied,
        "execution_authority": False,
    }


def verify_phase188_firewall(package_root: Path | None = None) -> dict[str, Any]:
    root = package_root or PACKAGE_ROOT
    violations: list[str] = []
    scanned: list[str] = []

    for path in sorted(root.glob("*.py")):
        if path.name in {"boundary.py"}:
            continue
        scanned.append(path.name)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                else:
                    mod = ",".join(a.name for a in node.names)
                if FORBIDDEN_BROKER_IMPORT in mod or mod.endswith("brokers.oanda_adapter"):
                    if path.name in {
                        "certified_provider.py",
                        "readonly_transport.py",
                        "network_validators.py",
                        "firewall.py",
                        "__init__.py",
                    }:
                        violations.append(f"{path.name}: forbidden import {mod}")
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in FORBIDDEN_METHOD_NAMES:
                    # Skip PermissionError stub methods' bodies are raises, not calls;
                    # still flag any Call to forbidden names.
                    violations.append(f"{path.name}: forbidden call {name}")

    # Skip scanning firewall.py call-name set literals by excluding false positives from
    # transport denial stubs: ensure stubs only raise PermissionError.
    transport_path = root / "readonly_transport.py"
    if transport_path.exists():
        transport_src = transport_path.read_text(encoding="utf-8")
        for method in ("place_order", "submit_order", "cancel_order", "modify_order"):
            if f"def {method}" in transport_src and "PermissionError" not in transport_src:
                violations.append(f"readonly_transport.py: {method} must raise PermissionError")

    adapter_report = adapter_has_no_write_methods()
    if not adapter_report["ok"]:
        violations.append(f"adapter_write_methods:{adapter_report['forbidden_methods_found']}")

    # Ensure adapter source still documents no order methods (spot-check).
    adapter_src = inspect.getsource(OandaLiveReadOnlyAdapter)
    for bad in ("def place_order", "def submit_order", "def cancel_order", "def modify_order"):
        if bad in adapter_src:
            violations.append(f"adapter_source_contains:{bad}")

    return {
        "ok": len(violations) == 0 and adapter_report["ok"],
        "scanned_files": scanned,
        "violations": violations,
        "adapter_report": adapter_report,
        "grants_execution": False,
        "can_modify_antibleed": False,
        "can_modify_margin": False,
        "can_modify_risk_governor": False,
        "can_modify_phase152a": False,
        "can_arm_live_authority": False,
    }
