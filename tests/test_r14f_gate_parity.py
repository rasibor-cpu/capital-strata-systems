"""R14F and position-cap parity between the reusable modules and the live dashboard.

The dashboard script cannot be imported in tests (it is the runtime itself), so its
R14F functions and cap constants are extracted from the source with `ast` and executed
or evaluated in isolation. Any drift fails these tests.
"""
from __future__ import annotations

import ast
import itertools
from pathlib import Path

import pytest

from backend.governance.css_unified_trade_gate import MAX_POSITIONS_BY_ASSET
from backend.governance.r14f_profitability_gate import R14F_MODE_THRESHOLDS, evaluate_r14f
from backend.trading_profiles.copy_engine import HARD_TOTAL_OPEN_POSITION_CAP

DASHBOARD = Path(__file__).resolve().parents[1] / "scripts" / "css_live_dashboard.py"
_TREE = ast.parse(DASHBOARD.read_text(encoding="utf-8"))


def _dashboard_r14f(engine_mode: str):
    wanted = {"_legacy_css_profitability_threshold", "_legacy_css_profitability_allows"}
    nodes = [n for n in _TREE.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in nodes} == wanted
    namespace = {"ENGINE_MODE": engine_mode, "print": lambda *a, **k: None}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(DASHBOARD), "exec"), namespace)
    return namespace["_legacy_css_profitability_allows"]


def _dashboard_constant(name: str):
    for node in _TREE.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in dashboard")


MODES = list(R14F_MODE_THRESHOLDS) + ["UNKNOWN_MODE"]
ASSETS = ["CRYPTO", "FX", "FUTURES", "OPTIONS", "crypto", ""]
SIGNALS = [0.0, 9.9, 10.0, 11.6, 12.5, 13.0, 14.2, 15.5, 16.0, 20.0]
PROBS = [0.0, 0.32, 0.5, 0.58, 0.62, 0.7, 1.0]


@pytest.mark.parametrize("mode", MODES)
def test_r14f_matches_dashboard_for_every_mode_asset_and_value(mode):
    dashboard_allows = _dashboard_r14f(mode)
    for asset, sig, prob in itertools.product(ASSETS, SIGNALS, PROBS):
        ok, composite, threshold = dashboard_allows(symbol="X", asset_class=asset, sig=sig, prob=prob)
        mine = evaluate_r14f(engine_mode=mode, asset_class=asset, signal_score=sig, probability=prob)
        assert (mine.allowed, mine.composite, mine.threshold) == (ok, composite, threshold), (mode, asset, sig, prob)


def test_r14f_boundary_is_inclusive_like_dashboard():
    dashboard_allows = _dashboard_r14f("BALANCED")
    # FUTURES threshold 15.8: composite exactly equal passes in both.
    assert dashboard_allows(symbol="X", asset_class="FUTURES", sig=15.8, prob=0.0)[0] is True
    assert evaluate_r14f(engine_mode="BALANCED", asset_class="FUTURES", signal_score=15.8, probability=0.0).allowed is True


def test_global_position_caps_match_dashboard_and_r7():
    assert _dashboard_constant("HARD_TOTAL_OPEN_POSITION_CAP") == HARD_TOTAL_OPEN_POSITION_CAP == 10
    dashboard_caps = {k.lower(): v for k, v in _dashboard_constant("HARD_ASSET_OPEN_CAPS").items()}
    assert dashboard_caps == {k.lower(): v for k, v in MAX_POSITIONS_BY_ASSET.items()} == {
        "crypto": 3, "fx": 3, "futures": 2, "options": 2}
