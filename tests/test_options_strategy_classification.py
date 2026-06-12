import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"


class _ClusterAmplifierStub:
    cluster_map = {"OPTIONS_INDEX": ["AAPL-C-175", "SPY-P-500"]}


class _ClusterRiskGovernorStub:
    def record_cluster_slot(self, cluster_name):
        self.cluster_name = cluster_name


class _CapitalGovernorStub:
    def allocate_trade(self, position_id: str) -> bool:
        return False


def _load_dashboard_strategy_slice(tmp_path):
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted_assigns = {
        "OPTION_GREEK_FIELDS",
        "VALID_GREEKS_SOURCES",
        "SUPPORTED_OPTIONS_STRATEGIES",
        "FUTURE_OPTIONS_STRATEGY_PLACEHOLDERS",
        "OPTION_STRATEGY_FIELDS",
    }
    wanted_defs = {
        "default_option_greeks",
        "normalize_option_greeks",
        "attach_default_greeks_to_option_position",
        "parse_option_symbol",
        "classify_option_strategy",
        "attach_option_strategy_to_position",
        "MarkToMarketEngine",
        "append_closed_trade_ledger",
    }

    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            target_names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if target_names & wanted_assigns:
                nodes.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted_defs:
            nodes.append(node)

    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)

    namespace = {
        "Any": Any,
        "json": json,
        "datetime": datetime,
        "cluster_amplifier": _ClusterAmplifierStub(),
        "cluster_risk_governor": _ClusterRiskGovernorStub(),
        "capital_governor": _CapitalGovernorStub(),
        "pcnrass_get_reference_price": lambda symbol, fallback=100.0: fallback,
        "SESSION_USER_CTX": {
            "session_id": "test-session",
            "user_id": "test-user",
            "role": "TEST",
        },
        "CLOSED_TRADE_LEDGER_PATH": tmp_path / "closed_trades.jsonl",
        "CLOSED_TRADE_LEDGER_MARKER": "CLOSED_TRADE_LEDGER",
        "ENGINE_MODE": "TEST",
        "SELECTED_BROKER_MODE": "paper",
        "SELECTED_BROKER": "NONE",
        "cycle": 9,
    }
    exec(compile(module, str(DASHBOARD_PATH), "exec"), namespace)
    return namespace


def test_call_symbol_classifies_as_long_call(tmp_path):
    ns = _load_dashboard_strategy_slice(tmp_path)

    strategy = ns["classify_option_strategy"]("AAPL-C-175")

    assert strategy == {
        "options_strategy": "LONG_CALL",
        "strategy_family": "SINGLE_LEG",
        "strategy_confidence": "HIGH",
    }


def test_put_symbol_classifies_as_long_put(tmp_path):
    ns = _load_dashboard_strategy_slice(tmp_path)

    strategy = ns["classify_option_strategy"]("SPY-P-500")

    assert strategy == {
        "options_strategy": "LONG_PUT",
        "strategy_family": "SINGLE_LEG",
        "strategy_confidence": "HIGH",
    }


def test_malformed_option_symbol_classifies_unknown(tmp_path):
    ns = _load_dashboard_strategy_slice(tmp_path)

    strategy = ns["classify_option_strategy"]("NOT_AN_OPTION")

    assert strategy == {
        "options_strategy": "UNKNOWN_OPTIONS_STRATEGY",
        "strategy_family": "UNKNOWN",
        "strategy_confidence": "LOW",
    }


def test_options_position_receives_strategy_fields(tmp_path):
    ns = _load_dashboard_strategy_slice(tmp_path)
    engine = ns["MarkToMarketEngine"]()

    position = engine.register_position("OPTIONS", "AAPL-C-175", 12.0, 0.7)

    assert position["options_strategy"] == "LONG_CALL"
    assert position["strategy_family"] == "SINGLE_LEG"
    assert position["strategy_confidence"] == "HIGH"


def test_non_options_positions_remain_unchanged(tmp_path):
    ns = _load_dashboard_strategy_slice(tmp_path)
    engine = ns["MarkToMarketEngine"]()

    position = engine.register_position("CRYPTO", "BTC-USD", 12.0, 0.7)

    assert "options_strategy" not in position
    assert "strategy_family" not in position
    assert "strategy_confidence" not in position


def test_strategy_fields_survive_closed_trade_ledger_when_present(tmp_path):
    ns = _load_dashboard_strategy_slice(tmp_path)
    position = {
        "symbol": "SPY-P-500",
        "asset_class": "OPTIONS",
        "floating": 1.25,
        "options_strategy": "LONG_PUT",
        "strategy_family": "SINGLE_LEG",
        "strategy_confidence": "HIGH",
    }

    ns["append_closed_trade_ledger"](position, "TAKE_PROFIT", 1.25)

    [record] = ns["CLOSED_TRADE_LEDGER_PATH"].read_text(encoding="utf-8").splitlines()
    payload = json.loads(record)
    assert payload["options_strategy"] == "LONG_PUT"
    assert payload["strategy_family"] == "SINGLE_LEG"
    assert payload["strategy_confidence"] == "HIGH"


def test_future_placeholder_constants_exist(tmp_path):
    ns = _load_dashboard_strategy_slice(tmp_path)

    assert ns["SUPPORTED_OPTIONS_STRATEGIES"] == {
        "LONG_CALL",
        "LONG_PUT",
        "UNKNOWN_OPTIONS_STRATEGY",
    }
    assert {
        "COVERED_CALL",
        "CASH_SECURED_PUT",
        "BULL_CALL_SPREAD",
        "BEAR_CALL_SPREAD",
        "BULL_PUT_SPREAD",
        "BEAR_PUT_SPREAD",
        "IRON_CONDOR",
        "IRON_BUTTERFLY",
        "STRADDLE",
        "STRANGLE",
        "CALENDAR_SPREAD",
        "DIAGONAL_SPREAD",
    }.issubset(ns["FUTURE_OPTIONS_STRATEGY_PLACEHOLDERS"])
