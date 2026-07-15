from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.brokers import credential_loader
from backend.runtime.broker_environment_profiles import (
    BrokerEnvironmentProfile,
    build_broker_environment,
    legacy_variable_migration_register,
    select_broker_environment_profile,
)
from backend.runtime.canonical_broker_state_builder import build_canonical_broker_runtime_state
from backend.runtime.live_environment_loader import load_css_runtime_environment
from dashboard.mission_control.state_adapter import build_broker_registry
from dashboard.runtime.frontend_contract import build_frontend_payload


def _write(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_br001_paper_profile_isolates_live_credentials_and_keeps_paper_test_notional(tmp_path: Path) -> None:
    _write(tmp_path / ".env.shared", "CSS_SHARED_SETTING=1")
    _write(
        tmp_path / ".env.paper",
        """
        COINBASE_TEST_ORDER_USD=2.50
        COINBASE_CDP_KEY_NAME=live-key
        COINBASE_ENABLE_LIVE_ORDERS=true
        """,
    )
    env: dict[str, str] = {}

    profile = build_broker_environment(tmp_path, explicit_profile="PAPER", env=env)

    assert profile.profile is BrokerEnvironmentProfile.PAPER
    assert profile.validation_status == "FAIL"
    assert "live_credential_in_paper_profile" in profile.failure_reasons
    assert "COINBASE_CDP_KEY_NAME" not in env
    assert "COINBASE_ENABLE_LIVE_ORDERS" not in env
    assert env["COINBASE_TEST_ORDER_USD"] == "2.50"
    assert profile.execution_allowed is False
    assert profile.live_trading_blocked is True
    assert profile.broker_execution_armed is False


def test_br001_live_read_only_profile_rejects_practice_and_execution_variables(tmp_path: Path) -> None:
    _write(tmp_path / ".env.shared", "CSS_SHARED_SETTING=1")
    _write(
        tmp_path / ".env.live_read_only",
        """
        COINBASE_CDP_KEY_NAME=key-name
        COINBASE_CDP_PRIVATE_KEY=private-key-material
        COINBASE_API_PERMISSIONS=view,accounts,products
        COINBASE_TEST_ORDER_USD=1.00
        COINBASE_ENABLE_LIVE_ORDERS=true
        """,
    )
    env: dict[str, str] = {}

    profile = build_broker_environment(tmp_path, explicit_profile="LIVE_READ_ONLY", env=env)

    assert profile.profile is BrokerEnvironmentProfile.LIVE_READ_ONLY
    assert profile.validation_status == "FAIL"
    assert "COINBASE_TEST_ORDER_USD" in profile.contamination_keys
    assert "unsafe_execution_flags" in profile.failure_reasons
    assert "execution_authorization_in_read_only_profile" in profile.failure_reasons
    assert "COINBASE_TEST_ORDER_USD" not in env
    assert profile.permissions_classification == "READ_ONLY"
    assert profile.read_only_allowed is True
    assert profile.execution_authorized is False


def test_br001_live_execution_profile_is_modeled_but_remains_blocked(tmp_path: Path) -> None:
    _write(
        tmp_path / ".env.live_execution",
        """
        COINBASE_CDP_KEY_NAME=key-name
        COINBASE_CDP_PRIVATE_KEY=private-key-material
        COINBASE_API_PERMISSIONS=view,trade
        """,
    )

    profile = build_broker_environment(tmp_path, explicit_profile="LIVE_EXECUTION", env={})

    assert profile.profile is BrokerEnvironmentProfile.LIVE_EXECUTION
    assert profile.execution_requested is True
    assert profile.execution_authorized is False
    assert profile.execution_allowed is False
    assert profile.live_trading_blocked is True
    assert profile.broker_execution_armed is False
    assert "live_execution_profile_modeled_but_execution_blocked" in profile.warnings


def test_br001_engine_mode_does_not_select_broker_profile(tmp_path: Path) -> None:
    _write(tmp_path / ".env.shared", "COINBASE_KEY_NAME=paper-key")
    env = {"ENGINE_MODE": "SAFE"}

    selected = select_broker_environment_profile(env=env)
    profile = build_broker_environment(tmp_path, env=env)

    assert selected is None
    assert profile.profile is None
    assert profile.validation_status == "FAIL"
    assert "no_explicit_broker_environment_profile" in profile.failure_reasons


def test_br001_unknown_and_multiple_profiles_fail_closed(tmp_path: Path) -> None:
    unknown = build_broker_environment(tmp_path, explicit_profile="BANANA", env={})
    multiple = build_broker_environment(
        tmp_path,
        explicit_profile="PAPER",
        cli_profile="LIVE_READ_ONLY",
        env={},
    )

    assert unknown.validation_status == "FAIL"
    assert "unknown_broker_environment_profile" in unknown.failure_reasons
    assert multiple.validation_status == "FAIL"
    assert "multiple_broker_environment_profiles_selected" in multiple.failure_reasons
    assert multiple.execution_allowed is False


def test_br001_inherited_environment_is_cleaned_before_profile_load(tmp_path: Path) -> None:
    _write(tmp_path / ".env.live_read_only", "COINBASE_KEY_NAME=profile-key\nCOINBASE_PRIVATE_KEY=profile-private")
    env = {
        "COINBASE_TEST_ORDER_USD": "1.00",
        "COINBASE_KEY_NAME": "inherited-key",
        "OANDA_PRACTICE_ACCOUNT_ID": "practice-account",
    }

    profile = build_broker_environment(tmp_path, explicit_profile="LIVE_READ_ONLY", env=env)

    assert "COINBASE_KEY_NAME" in profile.removed_inherited_variables
    assert "COINBASE_TEST_ORDER_USD" in profile.removed_inherited_variables
    assert "OANDA_PRACTICE_ACCOUNT_ID" in profile.removed_inherited_variables
    assert env["COINBASE_KEY_NAME"] == "profile-key"
    assert "COINBASE_TEST_ORDER_USD" not in env
    assert "OANDA_PRACTICE_ACCOUNT_ID" not in env


def test_br001_env_practice_cannot_enter_live_profiles(tmp_path: Path) -> None:
    _write(tmp_path / ".env", "COINBASE_KEY_NAME=legacy-key\nCOINBASE_PRIVATE_KEY=legacy-private")
    _write(tmp_path / ".env.practice", "COINBASE_TEST_ORDER_USD=1.00")
    env: dict[str, str] = {}

    trace = load_css_runtime_environment(tmp_path, mode="live", env=env)

    assert trace["profile"] == "LIVE_READ_ONLY"
    assert trace["practice_env_loaded"] is False
    assert "COINBASE_TEST_ORDER_USD" not in env
    assert trace["validation_status"] == "PASS"


def test_br001_coinbase_test_order_usd_is_paper_only(tmp_path: Path) -> None:
    _write(tmp_path / ".env.paper", "COINBASE_TEST_ORDER_USD=3.00")
    paper_env: dict[str, str] = {}
    live_env: dict[str, str] = {}

    paper = load_css_runtime_environment(tmp_path, mode="paper", env=paper_env)
    live = load_css_runtime_environment(tmp_path, mode="live", env=live_env)

    assert paper["profile"] == "PAPER"
    assert paper_env["COINBASE_TEST_ORDER_USD"] == "3.00"
    assert live["profile"] == "LIVE_READ_ONLY"
    assert "COINBASE_TEST_ORDER_USD" not in live_env


def test_br001_canonical_credential_object_is_redacted_and_stable(tmp_path: Path) -> None:
    _write(tmp_path / ".env.live_read_only", "COINBASE_KEY_NAME=key\nCOINBASE_PRIVATE_KEY=PRIVATE_VALUE_123")

    first = build_broker_environment(tmp_path, explicit_profile="LIVE_READ_ONLY", env={})
    second = build_broker_environment(tmp_path, explicit_profile="LIVE_READ_ONLY", env={})
    diagnostics = first.redacted_diagnostics()

    assert first.profile_fingerprint == second.profile_fingerprint
    assert diagnostics["credential_values_redacted"] is True
    assert diagnostics["private_key_redacted"] is True
    assert "PRIVATE_VALUE_123" not in str(diagnostics)
    assert first.credentials_for_broker()["COINBASE_PRIVATE_KEY"] == "PRIVATE_VALUE_123"


def test_br001_credential_loader_uses_canonical_profile_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path / ".env.live_read_only", "COINBASE_KEY_NAME=key\nCOINBASE_PRIVATE_KEY=not-a-pem")
    monkeypatch.setattr(credential_loader, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("CSS_BROKER_ENVIRONMENT_PROFILE", "LIVE_READ_ONLY")

    credentials = credential_loader.load_credentials("coinbase", mode="live", base_dir=str(tmp_path))

    assert credentials is not None
    assert credentials["COINBASE_KEY_NAME"] == "key"
    assert credentials["COINBASE_ENABLE_LIVE_ORDERS"] == "false"
    assert credentials["canonical_broker_environment"]["profile"] == "LIVE_READ_ONLY"
    assert credentials["canonical_broker_environment"]["execution_allowed"] is False


def test_br001_canonical_broker_state_and_frontend_expose_profile_metadata() -> None:
    canonical = build_canonical_broker_runtime_state(
        broker="coinbase",
        mode="live",
        runtime_payload={
            "broker_authenticated": False,
            "canonical_broker_environment": {
                "profile": "LIVE_READ_ONLY",
                "environment": "live_read_only",
                "permissions_classification": "READ_ONLY",
                "profile_fingerprint": "abc123",
                "status": "PASS",
                "contamination_keys": [],
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
            },
        },
        env={},
    )
    payload = build_frontend_payload({"broker_summary": {"canonical_broker_runtime_state": canonical.to_dict()}})
    broker = payload["sections"]["broker"]

    assert broker["broker_environment_profile"]["profile"] == "LIVE_READ_ONLY"
    assert broker["broker_environment_profile"]["permissions_classification"] == "READ_ONLY"
    assert broker["broker_environment_profile"]["profile_fingerprint"] == "abc123"
    assert broker["broker_environment_profile"]["execution_allowed"] is False


def test_br001_mission_control_metadata_is_redacted_and_read_only() -> None:
    registry = build_broker_registry(
        {
            "selected_broker": "COINBASE",
            "broker_mode": "live",
            "broker_environment_profile": {
                "profile": "LIVE_READ_ONLY",
                "environment": "live_read_only",
                "permissions_classification": "READ_ONLY",
                "profile_fingerprint": "fingerprint",
                "status": "PASS",
                "contamination_keys": [],
            },
        }
    )

    coinbase = next(item for item in registry if item["broker"] == "COINBASE")
    assert coinbase["profile"]["profile"] == "LIVE_READ_ONLY"
    assert coinbase["profile"]["credential_values_redacted"] is True
    assert coinbase["profile"]["execution_allowed"] is False
    assert coinbase["profile"]["live_trading_blocked"] is True
    assert coinbase["profile"]["broker_execution_armed"] is False


def test_br001_legacy_migration_register_classifies_coinbase_test_order_usd() -> None:
    rows = legacy_variable_migration_register()
    row = next(item for item in rows if item["variable"] == "COINBASE_TEST_ORDER_USD")

    assert row["profile"] == "PAPER"
    assert row["migration_target"] == ".env.paper"
    assert row["safe_to_remove_from_live"] is True
