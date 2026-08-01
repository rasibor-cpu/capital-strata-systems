"""Phase 189 — static execution firewall for multi-broker readiness package."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent

FORBIDDEN_CALLS: frozenset[str] = frozenset(
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
        "authenticate",
        "bypass_anti_bleed",
        "bypass_margin",
        "bypass_risk_governor",
        "bypass_phase152a",
    }
)


def verify_multi_broker_firewall(package_root: Path | None = None) -> dict[str, Any]:
    root = package_root or PACKAGE_ROOT
    violations: list[str] = []
    scanned: list[str] = []

    for path in sorted(root.glob("*.py")):
        if path.name == "firewall.py":
            continue
        scanned.append(path.name)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name in FORBIDDEN_CALLS:
                    violations.append(f"{path.name}: forbidden call {name}")
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod.endswith("brokers.oanda_adapter") or mod == "backend.app.brokers.oanda_adapter":
                    violations.append(f"{path.name}: forbidden import {mod}")

    return {
        "ok": len(violations) == 0,
        "scanned_files": scanned,
        "violations": violations,
        "grants_execution": False,
        "can_place_orders": False,
        "can_cancel_orders": False,
        "can_modify_orders": False,
        "can_arm_execution": False,
        "can_change_antibleed": False,
        "can_change_margin": False,
        "can_change_risk_governor": False,
        "can_change_phase152a": False,
        "can_change_live_authority": False,
    }
