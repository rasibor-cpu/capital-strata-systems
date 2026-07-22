from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.runtime.environment_bootstrap import (
    CANONICAL_REPOSITORY_ROOT,
    _reset_environment_bootstrap_for_tests,
    bootstrap_broker_environment,
    resolve_repository_root,
)
from backend.runtime.live_environment_loader import load_css_runtime_environment
from launcher.css_service_manager import CSSServiceManager


FAKE_ENV = """\
COINBASE_CDP_KEY_NAME=fake-key-name
COINBASE_CDP_PRIVATE_KEY_PATH=fake-private.pem
OANDA_API_KEY=fake-oanda-token
OANDA_ACCOUNT_ID=fake-oanda-account
COINBASE_ENABLE_LIVE_ORDERS=false
OANDA_ENABLE_LIVE_TRADING=false
"""


@pytest.fixture(autouse=True)
def _reset_bootstrap_cache() -> None:
    _reset_environment_bootstrap_for_tests()
    yield
    _reset_environment_bootstrap_for_tests()


def _write_env(root: Path, content: str = FAKE_ENV) -> Path:
    path = root / ".env"
    path.write_text(content, encoding="utf-8")
    return path


def test_canonical_repository_root_is_cwd_independent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve_repository_root() == CANONICAL_REPOSITORY_ROOT
    assert resolve_repository_root(tmp_path) == tmp_path.resolve()


def test_bootstrap_is_idempotent(tmp_path: Path) -> None:
    _write_env(tmp_path)
    env: dict[str, str] = {}
    first = bootstrap_broker_environment(tmp_path, env=env)
    snapshot = dict(env)
    second = bootstrap_broker_environment(tmp_path, env=env)
    assert first == second
    assert env == snapshot
    assert first.idempotent is True


def test_diagnostics_never_contain_secret_values(tmp_path: Path) -> None:
    secret = "fake-do-not-disclose-value"
    _write_env(
        tmp_path,
        FAKE_ENV + f"COINBASE_API_SECRET={secret}\n",
    )
    diagnostics = bootstrap_broker_environment(tmp_path, env={}).as_dict()
    serialized = json.dumps(diagnostics, sort_keys=True)
    assert secret not in serialized
    assert diagnostics["secrets_redacted"] is True


def test_explicit_process_environment_takes_precedence(tmp_path: Path) -> None:
    _write_env(tmp_path, "OANDA_API_KEY=file-fake-token\n")
    env = {"OANDA_API_KEY": "explicit-fake-token"}
    diagnostics = bootstrap_broker_environment(tmp_path, env=env)
    assert env["OANDA_API_KEY"] == "explicit-fake-token"
    assert diagnostics.skipped_existing_key_count == 1


def test_missing_env_fails_safely(tmp_path: Path) -> None:
    env: dict[str, str] = {}
    diagnostics = bootstrap_broker_environment(tmp_path, env=env)
    assert diagnostics.status == "MISSING"
    assert diagnostics.env_file_exists is False
    assert env == {}
    assert diagnostics.execution_allowed is False
    assert diagnostics.live_trading_blocked is True


def test_runtime_sees_coinbase_and_oanda_presence_after_bootstrap(
    tmp_path: Path,
) -> None:
    _write_env(tmp_path)
    env: dict[str, str] = {}
    trace = load_css_runtime_environment(tmp_path, env=env)
    bootstrap = trace["environment_bootstrap"]
    assert bootstrap["coinbase_configuration_present"] is True
    assert bootstrap["oanda_configuration_present"] is True
    assert env["COINBASE_CDP_KEY_NAME"]
    assert env["OANDA_API_KEY"]
    assert trace["execution_allowed"] is False
    assert trace["live_trading_blocked"] is True


def test_private_key_reference_is_checked_without_reading_contents(
    tmp_path: Path,
) -> None:
    private_key = tmp_path / "fake-private.pem"
    private_key.write_text("fake-private-key-content", encoding="utf-8")
    _write_env(tmp_path)
    diagnostics = bootstrap_broker_environment(tmp_path, env={})
    reference = next(
        item
        for item in diagnostics.path_references
        if item.variable == "COINBASE_CDP_PRIVATE_KEY_PATH"
    )
    assert reference.reference_present is True
    assert reference.target_exists is True
    assert reference.target_is_file is True
    assert reference.target_readable is True
    assert "fake-private-key-content" not in json.dumps(diagnostics.as_dict())


def test_configuration_changes_from_incomplete_to_present(tmp_path: Path) -> None:
    env: dict[str, str] = {}
    before = bootstrap_broker_environment(tmp_path, env=env)
    assert before.coinbase_configuration_present is False
    assert before.oanda_configuration_present is False

    _reset_environment_bootstrap_for_tests()
    _write_env(tmp_path)
    after = bootstrap_broker_environment(tmp_path, env=env)
    assert after.coinbase_configuration_present is True
    assert after.oanda_configuration_present is True


def test_truthy_file_live_flags_are_blocked_and_execution_remains_disabled(
    tmp_path: Path,
) -> None:
    _write_env(
        tmp_path,
        FAKE_ENV
        + "ALLOW_LIVE_TRADING=true\n"
        + "COINBASE_ENABLE_LIVE_TRADING=1\n",
    )
    env: dict[str, str] = {}
    diagnostics = bootstrap_broker_environment(tmp_path, env=env)
    assert env["ALLOW_LIVE_TRADING"] == "false"
    assert env["COINBASE_ENABLE_LIVE_TRADING"] == "false"
    assert diagnostics.blocked_live_enable_keys == (
        "ALLOW_LIVE_TRADING",
        "COINBASE_ENABLE_LIVE_TRADING",
    )
    assert diagnostics.execution_allowed is False
    assert diagnostics.live_trading_blocked is True
    assert diagnostics.broker_execution_armed is False


def test_explicit_truthy_live_flag_is_the_only_precedence_exception(
    tmp_path: Path,
) -> None:
    _write_env(tmp_path)
    env = {"ALLOW_LIVE_TRADING": "true", "UNRELATED_SETTING": "explicit"}
    diagnostics = bootstrap_broker_environment(tmp_path, env=env)
    assert env["ALLOW_LIVE_TRADING"] == "false"
    assert env["UNRELATED_SETTING"] == "explicit"
    assert diagnostics.blocked_explicit_live_enable_keys == (
        "ALLOW_LIVE_TRADING",
    )
    assert diagnostics.explicit_live_enable_keys == ()
    assert diagnostics.execution_allowed is False


def test_duplicate_keys_are_reported_and_last_occurrence_wins(tmp_path: Path) -> None:
    _write_env(
        tmp_path,
        "OANDA_API_KEY=fake-first\nOANDA_API_KEY=fake-second\n",
    )
    env: dict[str, str] = {}
    diagnostics = bootstrap_broker_environment(tmp_path, env=env)
    assert env["OANDA_API_KEY"] == "fake-second"
    assert diagnostics.duplicate_keys == (("OANDA_API_KEY", 2),)


def test_launcher_mobile_and_runtime_start_before_broker_consumers() -> None:
    root = Path(__file__).resolve().parents[1]
    runtime_launcher = (root / "launcher/css_runtime_launcher.py").read_text(
        encoding="utf-8"
    )
    mobile_launcher = (root / "launcher/css_mobile_launcher.py").read_text(
        encoding="utf-8"
    )
    mobile_app = (root / "dashboard/mobile/mobile_app.py").read_text(
        encoding="utf-8"
    )
    runtime_script = (root / "scripts/css_live_dashboard.py").read_text(
        encoding="utf-8"
    )

    assert runtime_launcher.index("load_css_runtime_environment(REPO_ROOT)") < (
        runtime_launcher.index("CSSRuntimeSupervisor")
    )
    assert mobile_launcher.index(
        "load_css_runtime_environment(PROJECT_ROOT)"
    ) < mobile_launcher.index("backend.brokers.account_balance_contract")
    assert mobile_app.index("bootstrap_broker_environment(") < mobile_app.index(
        "backend.brokers.account_balance_contract"
    )
    assert runtime_script.index(
        "CSS_ENVIRONMENT_LOAD_TRACE = load_css_runtime_environment(PROJECT_ROOT)"
    ) < runtime_script.index("backend.runtime.broker_startup_selection")


def test_child_process_environment_inherits_initialized_parent(tmp_path: Path) -> None:
    _write_env(tmp_path)
    parent_env: dict[str, str] = {}
    bootstrap_broker_environment(tmp_path, env=parent_env)
    child_env = dict(parent_env)
    manager = CSSServiceManager(
        "test",
        ["python", "-c", "pass"],
        str(tmp_path),
        child_env,
    )
    assert manager.env["COINBASE_CDP_KEY_NAME"] == "fake-key-name"
    assert manager.env["OANDA_API_KEY"] == "fake-oanda-token"
    assert "COINBASE_ENABLE_LIVE_TRADING" not in manager.env
