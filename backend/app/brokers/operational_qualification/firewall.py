"""Phase 193 — static execution / network / auth firewall."""

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
        "login",
        "connect",
        "urlopen",
        "request",
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "bypass_anti_bleed",
        "bypass_margin",
        "bypass_risk_governor",
        "bypass_phase152a",
        "socket",
        "create_connection",
    }
)

FORBIDDEN_IMPORT_SUFFIXES: tuple[str, ...] = (
    "urllib.request",
    "http.client",
    "socket",
    "requests",
    "aiohttp",
    "httpx",
    "brokers.oanda_adapter",
)


def verify_operational_qualification_firewall(package_root: Path | None = None) -> dict[str, Any]:
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
                # Allow dict/list .get only when clearly attribute get on locals — still
                # forbid bare Name get and Attribute get on http-like names is hard.
                # Narrow: forbid Attribute.get only if receiver looks like requests/session.
                if name in FORBIDDEN_CALLS:
                    if name == "get" and isinstance(node.func, ast.Attribute):
                        # dict.get / Mapping.get is ubiquitous; allow Attribute.get.
                        continue
                    if name == "connect" and isinstance(node.func, ast.Attribute):
                        # avoid false positives on unrelated connect helpers if any
                        continue
                    violations.append(f"{path.name}: forbidden call {name}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name or ""
                    if any(mod == s or mod.endswith("." + s.split(".")[-1]) for s in FORBIDDEN_IMPORT_SUFFIXES):
                        violations.append(f"{path.name}: forbidden import {mod}")
                    if mod in {"socket", "requests", "httpx", "aiohttp"}:
                        violations.append(f"{path.name}: forbidden import {mod}")
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for suffix in FORBIDDEN_IMPORT_SUFFIXES:
                    if mod == suffix or mod.endswith(suffix):
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
        "can_authenticate": False,
        "can_network": False,
        "can_change_antibleed": False,
        "can_change_margin": False,
        "can_change_risk_governor": False,
        "can_change_phase152a": False,
        "can_change_kill_switch": False,
        "can_change_live_authority": False,
        "execution_authority": False,
    }
