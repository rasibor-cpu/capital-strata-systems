from __future__ import annotations

from pathlib import Path

from backend.runtime.canonical_broker_state_registry import classify_coinbase_environment
from backend.runtime.live_environment_loader import (
    load_css_runtime_environment,
    paper_only_coinbase_test_order_usd,
    sanitize_live_environment,
)


def test_phase166d_unknown_or_live_startup_does_not_load_practice_env(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("COINBASE_CDP_KEY_NAME=present\n", encoding="utf-8")
    (tmp_path / ".env.practice").write_text("COINBASE_TEST_ORDER_USD=1.00\n", encoding="utf-8")
    env: dict[str, str] = {}

    trace = load_css_runtime_environment(tmp_path, mode="live", env=env)

    assert trace["env_loaded"] is True
    assert trace["practice_env_loaded"] is False
    assert "COINBASE_TEST_ORDER_USD" not in env
    assert trace["paper_only_keys_present_after_load"] == []
    evidence = classify_coinbase_environment(env, mode="live")
    assert evidence["status"] == "PASS"
    assert evidence["contamination_keys"] == []


def test_phase166d_live_startup_removes_inherited_process_contamination(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("COINBASE_CDP_KEY_NAME=present\n", encoding="utf-8")
    (tmp_path / ".env.practice").write_text("COINBASE_TEST_ORDER_USD=1.00\n", encoding="utf-8")
    env = {"COINBASE_TEST_ORDER_USD": "1.00"}

    trace = load_css_runtime_environment(tmp_path, mode="live", env=env)

    assert trace["removed_live_blocked_keys"] == ["COINBASE_TEST_ORDER_USD"]
    assert "COINBASE_TEST_ORDER_USD" not in env
    assert classify_coinbase_environment(env, mode="live")["status"] == "PASS"


def test_phase166d_paper_mode_keeps_paper_only_test_notional(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("COINBASE_CDP_KEY_NAME=present\n", encoding="utf-8")
    (tmp_path / ".env.practice").write_text("COINBASE_TEST_ORDER_USD=2.50\n", encoding="utf-8")
    env: dict[str, str] = {}

    trace = load_css_runtime_environment(tmp_path, mode="paper", env=env)

    assert trace["practice_env_loaded"] is True
    assert env.get("COINBASE_TEST_ORDER_USD") == "2.50"
    assert paper_only_coinbase_test_order_usd(mode="paper", env=env) == 2.5


def test_phase166d_sanitizer_is_targeted_and_advisory_only() -> None:
    env = {
        "COINBASE_TEST_ORDER_USD": "1.00",
        "COINBASE_CDP_KEY_NAME": "present",
        "OANDA_ENV": "live",
    }

    removed = sanitize_live_environment(env)

    assert removed == ["COINBASE_TEST_ORDER_USD"]
    assert "COINBASE_TEST_ORDER_USD" not in env
    assert env["COINBASE_CDP_KEY_NAME"] == "present"
    assert env["OANDA_ENV"] == "live"


def test_phase166d_startup_wrappers_do_not_unconditionally_load_practice_env() -> None:
    for path in (
        Path("scripts/css_live_dashboard.py"),
        Path("launcher/css_runtime_launcher.py"),
        Path("launcher/css_mobile_launcher.py"),
    ):
        source = path.read_text(encoding="utf-8")
        assert 'load_dotenv(PROJECT_ROOT / ".env.practice", override=False)' not in source
        assert 'load_dotenv(os.path.join(REPO_ROOT, ".env.practice"), override=False)' not in source
        assert 'load_dotenv(os.path.join(PROJECT_ROOT, ".env.practice"), override=False)' not in source
        assert "load_css_runtime_environment" in source
