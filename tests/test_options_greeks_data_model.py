import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"


class _ClusterAmplifierStub:
    cluster_map = {"OPTIONS_INDEX": ["SPY-C"]}


class _ClusterRiskGovernorStub:
    def __init__(self) -> None:
        self.recorded = []

    def record_cluster_slot(self, cluster_name):
        self.recorded.append(cluster_name)


class _CapitalGovernorStub:
    def allocate_trade(self, position_id: str) -> bool:
        return False


def _load_dashboard_slice(tmp_path):
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted_assigns = {"OPTION_GREEK_FIELDS", "VALID_GREEKS_SOURCES"}
    wanted_defs = {
        "default_option_greeks",
        "normalize_option_greeks",
        "attach_default_greeks_to_option_position",
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

    ledger_path = tmp_path / "closed_trades.jsonl"
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
        "CLOSED_TRADE_LEDGER_PATH": ledger_path,
        "CLOSED_TRADE_LEDGER_MARKER": "CLOSED_TRADE_LEDGER",
        "ENGINE_MODE": "TEST",
        "SELECTED_BROKER_MODE": "paper",
        "SELECTED_BROKER": "NONE",
        "cycle": 7,
    }
    exec(compile(module, str(DASHBOARD_PATH), "exec"), namespace)
    return namespace


def test_default_greeks_are_unavailable_none_values(tmp_path):
    ns = _load_dashboard_slice(tmp_path)

    assert ns["default_option_greeks"]() == {
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
        "rho": None,
        "greeks_source": "UNAVAILABLE",
        "greeks_status": "UNAVAILABLE",
        "greeks_reason": "NO_CANONICAL_GREEKS",
    }


def test_invalid_greeks_source_normalizes_to_unavailable(tmp_path):
    ns = _load_dashboard_slice(tmp_path)

    normalized = ns["normalize_option_greeks"]({"delta": 0.5, "greeks_source": "BAD"})

    assert normalized["greeks_source"] == "UNAVAILABLE"
    assert normalized["delta"] == 0.5
    assert normalized["greeks_status"] == "PARTIAL"


def test_valid_greeks_source_is_preserved(tmp_path):
    ns = _load_dashboard_slice(tmp_path)

    normalized = ns["normalize_option_greeks"]({"delta": 0.5, "greeks_source": "BROKER"})

    assert normalized["greeks_source"] == "BROKER"
    assert normalized["delta"] == 0.5
    assert normalized["greeks_status"] == "RESOLVED"


def test_options_register_position_receives_greeks(tmp_path):
    ns = _load_dashboard_slice(tmp_path)
    engine = ns["MarkToMarketEngine"]()

    position = engine.register_position("OPTIONS", "SPY-C", 12.0, 0.7)

    assert position["greeks_source"] in {"PAPER_MODEL_FALLBACK", "UNAVAILABLE"}
    assert "greeks_status" in position
    assert "greeks_reason" in position


def test_non_options_register_position_do_not_receive_greeks(tmp_path):
    ns = _load_dashboard_slice(tmp_path)

    for asset_class in ("CRYPTO", "FX", "FUTURES"):
        engine = ns["MarkToMarketEngine"]()
        position = engine.register_position(asset_class, f"{asset_class}-TEST", 12.0, 0.7)

        assert "greeks_source" not in position
        assert all(field not in position for field in ("delta", "gamma", "theta", "vega", "rho"))


def test_legacy_options_position_missing_greeks_normalizes_safely(tmp_path):
    ns = _load_dashboard_slice(tmp_path)
    position = {"asset_class": "OPTIONS", "symbol": "SPY-C"}

    normalized = ns["attach_default_greeks_to_option_position"](position)

    assert normalized["greeks_source"] in {"PAPER_MODEL_FALLBACK", "UNAVAILABLE"}
    assert "greeks_status" in normalized
    assert "greeks_reason" in normalized


def test_closed_trade_ledger_preserves_options_greeks_when_present(tmp_path):
    ns = _load_dashboard_slice(tmp_path)
    position = {
        "symbol": "SPY-C",
        "asset_class": "OPTIONS",
        "floating": 1.25,
        "delta": 0.42,
        "gamma": 0.03,
        "theta": -0.02,
        "vega": 0.11,
        "rho": 0.01,
        "greeks_source": "MARKET_DATA",
    }

    ns["append_closed_trade_ledger"](position, "TAKE_PROFIT", 1.25)

    [record] = ns["CLOSED_TRADE_LEDGER_PATH"].read_text(encoding="utf-8").splitlines()
    payload = json.loads(record)
    assert payload["greeks_source"] == "MARKET_DATA"
    assert payload["delta"] == 0.42
    assert payload["gamma"] == 0.03
    assert payload["theta"] == -0.02
    assert payload["vega"] == 0.11
    assert payload["rho"] == 0.01
