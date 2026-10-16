"""RC1 R3: legacy random candidate generation is retired; launcher request logs are labelled as
non-orders that point to the governed ticket."""
from __future__ import annotations

import ast
from pathlib import Path

from launcher.css_mobile_launcher import validate_mobile_paper_trade_request

REPO = Path(__file__).resolve().parents[1]


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def test_legacy_loop_generates_no_random_candidates():
    fn = _function(REPO / "scripts" / "css_live_dashboard.py", "select_cycle_candidates")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    assert calls == []  # no random.choice / shuffle, no other source
    (ret,) = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
    assert isinstance(ret.value, ast.List) and ret.value.elts == []


def test_launcher_request_log_is_explicitly_not_an_order():
    rec = validate_mobile_paper_trade_request({"symbol": "EUR_USD", "asset_class": "FX", "side": "BUY",
                                               "quantity": "1", "broker": "PAPER"})
    assert rec["record_kind"] == "REQUEST_LOG_ONLY_NOT_AN_ORDER"
    assert rec["order_submitted"] is False and rec["execution_allowed"] is False
    assert rec["governed_order_path"] == "/trade"
