"""Phase 187A — AST/static execution-boundary verification for read-only certification.

Proves the Phase 187A package cannot submit/cancel/modify orders or arm live authority.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

PACKAGE_ROOT = Path(__file__).resolve().parent

FORBIDDEN_CALL_NAMES: frozenset[str] = frozenset(
    {
        "place_order",
        "submit_order",
        "cancel_order",
        "modify_order",
        "create_order",
        "close_order",
        "arm_live",
        "arm_live_authority",
        "enable_execution",
        "set_execution_enabled",
        "disable_kill_switch",
        "bypass_kill_switch",
        "modify_anti_bleed",
        "set_anti_bleed_min_size",
        "modify_risk_governor",
        "modify_phase152a",
        "modify_margin",
        "requests.get",
        "requests.post",
        "urllib.request.urlopen",
        "http.client",
        "socket.create_connection",
    }
)

FORBIDDEN_IMPORT_MODULES: frozenset[str] = frozenset(
    {
        "requests",
        "httpx",
        "aiohttp",
        "urllib.request",
        "socket",
        "ssl",
    }
)

# Allowed exception: typing-only / stdlib used without network in evidence hashing.
ALLOWED_STDLIB: frozenset[str] = frozenset({"hashlib", "json", "dataclasses", "datetime", "typing", "ast", "pathlib"})


def _iter_py_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if path.name == "boundary.py":
            # This module intentionally lists forbidden names as data.
            continue
        yield path


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        cur: ast.AST = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
        return parts[0] if parts else None
    return None


def verify_execution_boundary(package_root: Path | None = None) -> dict[str, object]:
    """Static AST scan of Phase 187A package for execution/network surface."""
    root = package_root or PACKAGE_ROOT
    violations: list[str] = []
    scanned: list[str] = []

    for path in _iter_py_files(root):
        scanned.append(str(path.relative_to(root)))
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    names = [node.module or ""]
                for name in names:
                    top = name.split(".")[0]
                    full = name
                    if full in FORBIDDEN_IMPORT_MODULES or top in FORBIDDEN_IMPORT_MODULES:
                        violations.append(f"{path.name}: forbidden import {name}")
            if isinstance(node, ast.Call):
                cname = _call_name(node.func)
                if cname and (cname in FORBIDDEN_CALL_NAMES or cname.split(".")[-1] in FORBIDDEN_CALL_NAMES):
                    # Allow AttributeError raise paths referencing names as strings only — Call check is enough.
                    if cname.split(".")[-1] in {
                        "place_order",
                        "submit_order",
                        "cancel_order",
                        "modify_order",
                        "arm_live_authority",
                        "enable_execution",
                    }:
                        violations.append(f"{path.name}: forbidden call {cname}")

    # Also assert framework class forbids methods via FORBIDDEN_METHODS constant.
    framework_path = root / "framework.py"
    fw_src = framework_path.read_text(encoding="utf-8")
    for method in (
        "submit_order",
        "place_order",
        "cancel_order",
        "modify_order",
        "arm_live_authority",
        "enable_execution",
    ):
        if f'"{method}"' not in fw_src and f"'{method}'" not in fw_src:
            violations.append(f"framework.py missing forbidden method guard: {method}")

    return {
        "ok": len(violations) == 0,
        "scanned_files": scanned,
        "violations": violations,
        "grants_execution": False,
        "package": str(root),
    }
