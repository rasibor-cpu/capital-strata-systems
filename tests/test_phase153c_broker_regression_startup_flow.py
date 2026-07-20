from __future__ import annotations

import json
import re
from pathlib import Path

from backend.runtime.broker_startup_selection import (
    CANONICAL_STARTUP_SEQUENCE,
    broker_summary_from_artifacts,
    build_startup_broker_selection,
    cancelled_startup_selection,
    persist_broker_selection,
    startup_broker_from_choice,
    startup_broker_mode_from_choice,
)
import launcher.css_mobile_launcher as launcher


def _script_source() -> str:
    return Path("scripts/css_live_dashboard.py").read_text(encoding="utf-8")


def _top_level_position(pattern: str) -> int:
    source = _script_source()
    marker = source.index("# === PCNRASS RESTORED CSS AUTHENTICATION ===")
    tail = source[marker:]
    match = re.search(pattern, tail, flags=re.MULTILINE)
    assert match is not None, f"Missing startup pattern: {pattern}"
    return marker + match.start()


def test_phase153c_canonical_startup_sequence_is_restored() -> None:
    assert CANONICAL_STARTUP_SEQUENCE == (
        "authenticate_startup_user",
        "select_global_broker_mode",
        "select_startup_broker_selection",
        "select_broker_execution_config",
        "select_engine_mode",
        "select_cycle_mode",
    )

    positions = [
        _top_level_position(r"^SESSION_USER_CTX = authenticate_startup_user\(\)"),
        _top_level_position(r"^GLOBAL_BROKER_MODE = select_global_broker_mode\(\)"),
        _top_level_position(r"^SELECTED_BROKER, SELECTED_BROKER_MODE = select_startup_broker_selection\(\)"),
        _top_level_position(r"^BROKER_EXECUTION_ARMED, SELECTED_BROKER, SELECTED_BROKER_MODE = select_broker_execution_config\("),
        _top_level_position(r"^ENGINE_MODE = select_engine_mode\(\)"),
        _top_level_position(r"^select_cycle_mode\(\)"),
    ]

    assert positions == sorted(positions)


def test_phase153c_broker_selection_cannot_be_skipped_when_execution_disabled() -> None:
    source = _script_source()
    assert "select_broker_execution_config(\n    SELECTED_BROKER,\n    SELECTED_BROKER_MODE,\n)" in source
    assert 'return False, "NONE", "paper"' not in source[source.index("def select_broker_execution_config") : source.index("def select_engine_mode")]
    assert "return False, selected_broker, selected_broker_mode" in source


def test_phase153c_invalid_broker_and_disabled_ibkr_fail_closed() -> None:
    from backend.runtime.broker_startup_selection import normalize_broker

    assert startup_broker_from_choice("bad") == "NONE"
    # Phase 177C Revision B: choice 4 is BINANCE (not IBKR). IBKR maps to NONE.
    assert startup_broker_from_choice("4", ibkr_supported=False) == "BINANCE"
    assert normalize_broker("IBKR") == "NONE"
    assert startup_broker_mode_from_choice("2", selected_broker="NONE", global_mode="live") == "paper"


def test_phase153c_startup_cancellation_returns_safe_paper_state() -> None:
    selection = cancelled_startup_selection("operator_cancelled_broker_selection")
    payload = selection.as_dict()

    assert selection.selected_broker == "NONE"
    assert selection.broker_mode == "paper"
    assert selection.broker_execution_armed is False
    assert payload["execution_allowed"] is False
    assert payload["live_order_permission"] is False
    assert payload["readiness_reason"] == "operator_cancelled_broker_selection"


def test_phase153c_paper_and_live_startup_persist_broker_state(tmp_path: Path) -> None:
    account = tmp_path / "artifacts" / "css_account_state_pcnrass.json"
    session = tmp_path / "artifacts" / "css_session_state_pcnrass.json"

    paper = build_startup_broker_selection()
    persist_broker_selection(account_state_path=account, session_state_path=session, selection=paper)
    paper_summary = broker_summary_from_artifacts(
        json.loads(account.read_text(encoding="utf-8")),
        json.loads(session.read_text(encoding="utf-8")),
    )
    assert paper_summary["selected_broker"] == "NONE"
    assert paper_summary["broker_mode"] == "paper"

    live_read_only = build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
    )
    persist_broker_selection(account_state_path=account, session_state_path=session, selection=live_read_only)
    live_summary = broker_summary_from_artifacts(
        json.loads(account.read_text(encoding="utf-8")),
        json.loads(session.read_text(encoding="utf-8")),
    )
    assert live_summary["selected_broker"] == "COINBASE"
    assert live_summary["broker_mode"] == "live"
    assert live_summary["broker_execution_status"] == "DISABLED"
    assert live_summary["execution_allowed"] is False


def test_phase153c_runtime_and_launcher_receive_selected_broker(tmp_path: Path, monkeypatch) -> None:
    artifacts = tmp_path / "artifacts"
    account = artifacts / "css_account_state_pcnrass.json"
    session = artifacts / "css_session_state_pcnrass.json"
    monkeypatch.setattr(launcher.LauncherConfig, "ARTIFACTS_DIR", str(artifacts))
    monkeypatch.setattr(launcher.LauncherConfig, "ACCOUNT_STATE_FILE", str(account))
    monkeypatch.setattr(launcher.LauncherConfig, "SESSION_STATE_FILE", str(session))

    selection = build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
    )
    persist_broker_selection(account_state_path=account, session_state_path=session, selection=selection)

    startup = launcher.get_broker_startup_summary()
    frontend = launcher.build_launcher_frontend_state()

    assert startup["selected_broker"] == "COINBASE"
    assert frontend["sections"]["broker"]["selected_broker"] == "COINBASE"
    assert frontend["sections"]["broker"]["broker_mode"] == "live"
    assert frontend["sections"]["broker"]["broker_execution_status"] == "DISABLED"
    assert frontend["sections"]["trade_summary"]["broker"] == "COINBASE"
    assert frontend["sections"]["trade_summary"]["execution_allowed"] is False
