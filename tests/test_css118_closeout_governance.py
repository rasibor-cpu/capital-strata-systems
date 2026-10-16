"""Closeout governance invariants (owner directions 1, 5, 6, 7, 9)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from backend.app.risk.capital_allocation_governor import CapitalAllocationGovernor
from backend.app.risk.portfolio_governor import PortfolioGovernor
from backend.runtime import pilot_min_size_exception
from backend.trading_profiles.ledger_anchor import ANCHOR_KEY_ENV
from backend.trading_profiles.trader_registry import TraderRegistry

REPO = Path(__file__).resolve().parents[1]
EVIDENCE = REPO / "docs" / "evidence" / "CSS118_ANTIBLEED_CAD20_EVIDENCE.json"
SOURCE_DIRS = ("backend", "engine", "dashboard", "launcher", "scripts")


def _py_sources():
    for d in SOURCE_DIRS:
        yield from (REPO / d).rglob("*.py")


# ---------------------------------------------------------------- direction 6: AntiBleed
def test_antibleed_minimum_is_still_50():
    assert AntiBleedGuard(state_file="/nonexistent/never-written.json").minimum_profitable_trade_size == 50.0


def test_min_size_exception_remains_disabled_and_unused():
    assert pilot_min_size_exception.PILOT_MIN_SIZE_EXCEPTION_ENABLED is False
    callers = []
    for path in _py_sources():
        if path.name in {"anti_bleed_guard.py", "pilot_min_size_exception.py"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "pilot_min_size_exception":
                callers.append(str(path.relative_to(REPO)))
    assert callers == []  # no automatic CAD 20 exception anywhere


def test_evidence_report_is_reproducible(monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("ev", REPO / "tools" / "antibleed_cad20_evidence.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    regenerated = ev.build_report()
    committed = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert regenerated == committed
    assert committed["router_replay"]["outcomes"] == {"execution_gate:anti_bleed_guard:trade_size_too_small": 6}


# ---------------------------------------------------------------- directions 1 and 5: ceilings
def test_capital_governor_ceilings_unchanged():
    assert CapitalAllocationGovernor.DEFAULT_MAX_SINGLE_TRADE_ALLOCATION_PCT == 0.05
    assert CapitalAllocationGovernor.DEFAULT_MAX_ALLOCATION_BY_ASSET_CLASS == {
        "CRYPTO": 0.05, "FX": 0.05, "FUTURES": 0.02, "OPTIONS": 0.02}
    assert PortfolioGovernor.DEFAULT_MAX_PORTFOLIO_EXPOSURE_PCT == 0.25


# ---------------------------------------------------------------- directions 7 and 9: no enrolment
def test_registry_ships_empty_and_no_signing_material_is_committed(tmp_path):
    assert TraderRegistry(tmp_path).list() == []
    committed = {p.name for p in REPO.rglob("*") if ".git" not in p.parts and p.is_file()}
    for forbidden in ("trader_registry.jsonl", "trader_registry.head.json", "signal_feed.jsonl",
                      "ledger_anchor_checkpoints.jsonl"):
        assert forbidden not in committed


def test_no_anchor_signing_key_is_configured_or_defaulted():
    for path in _py_sources():
        text = path.read_text(encoding="utf-8", errors="replace")
        if ANCHOR_KEY_ENV in text and path.name != "ledger_anchor.py":
            raise AssertionError(f"anchor key referenced outside ledger_anchor.py: {path}")
    for config in REPO.glob("**/*.env*"):
        if ".git" not in config.parts:
            assert ANCHOR_KEY_ENV not in config.read_text(encoding="utf-8", errors="replace")
