from __future__ import annotations

import builtins
import inspect
import json
import os
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from dashboard.runtime import css_mobile_controls
from dashboard.runtime.css_mobile_controls import (
    MOBILE_CONTROLS_SCHEMA_VERSION,
    MobileControlPersistenceError,
    MobileControlRevisionError,
    evaluate_kill_switch_state,
    load_mobile_controls,
    save_mobile_controls,
)

GENERATED_AT = "2026-07-29T00:00:00+00:00"


def _state(**overrides: Any) -> dict[str, Any]:
    payload = {
        "schema_version": MOBILE_CONTROLS_SCHEMA_VERSION,
        "control_revision": 1,
        "updated_utc": GENERATED_AT,
        "requested_orders_enabled": False,
        "requested_pause": True,
        "operator_acknowledged": False,
        "requested_runtime_mode": "PAPER",
        "display_mode": "DEFAULT",
        "engine_mode": "SAFE",
    }
    payload.update(overrides)
    return payload


def test_import_succeeds_with_no_side_effects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "import_controls.json"
    monkeypatch.setattr(css_mobile_controls, "MOBILE_CONTROL_FILE", target)

    assert css_mobile_controls.MOBILE_CONTROL_FILE == target
    assert not target.exists()


@pytest.mark.parametrize(
    "writer",
    [
        lambda path: None,
        lambda path: path.write_text("", encoding="utf-8"),
        lambda path: path.write_text("{not json", encoding="utf-8"),
        lambda path: path.write_text("[]", encoding="utf-8"),
        lambda path: path.write_text(json.dumps({"control_revision": 4}), encoding="utf-8"),
        lambda path: path.write_text(
            json.dumps({"schema_version": "css.mobile_controls.v999"}),
            encoding="utf-8",
        ),
    ],
)
def test_missing_empty_invalid_or_incompatible_state_returns_safe_defaults(
    tmp_path: Path,
    writer: Any,
) -> None:
    path = tmp_path / "controls.json"
    writer(path)

    payload = load_mobile_controls(path, generated_at_utc=GENERATED_AT)

    assert payload["control_revision"] == 0
    assert payload["requested_orders_enabled"] is False
    assert payload["orders_enabled"] is False
    assert payload["requested_runtime_mode"] == ""
    assert payload["runtime_mode"] == "DISABLED"
    assert payload["effective_order_permission"] is False
    assert payload["live_capital_active"] is False
    assert payload["broker_ready"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["certification_status"] == "NOT_AUTHORITY"


def test_missing_order_flag_defaults_false_and_text_true_is_not_trusted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "controls.json"
    path.write_text(
        json.dumps(_state(orders_enabled=True, requested_orders_enabled="true")),
        encoding="utf-8",
    )

    payload = load_mobile_controls(path, generated_at_utc=GENERATED_AT)

    assert payload["requested_orders_enabled"] is False
    assert payload["orders_enabled"] is False
    assert payload["effective_order_permission"] is False


def test_live_text_and_mobile_intent_never_create_authority(tmp_path: Path) -> None:
    path = tmp_path / "controls.json"
    saved = save_mobile_controls(
        {
            "requested_orders_enabled": True,
            "requested_runtime_mode": "LIVE",
            "runtime_mode": "LIVE",
            "live_capital_active": True,
            "broker_ready": True,
            "broker_execution_armed": True,
            "certification_status": "CERTIFIED",
        },
        state_path=path,
        generated_at_utc=GENERATED_AT,
    )

    assert saved["requested_orders_enabled"] is True
    assert saved["requested_runtime_mode"] == ""
    assert saved["runtime_mode"] == "DISABLED"
    assert saved["orders_enabled"] is False
    assert saved["live_capital_active"] is False
    assert saved["broker_ready"] is False
    assert saved["broker_execution_armed"] is False
    assert saved["certification_status"] == "NOT_AUTHORITY"


def test_valid_safe_state_write_and_read_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "controls.json"

    saved = save_mobile_controls(
        {
            "requested_orders_enabled": False,
            "requested_pause": True,
            "operator_acknowledged": True,
            "requested_runtime_mode": "LIVE_READ_ONLY",
            "display_mode": "DETAILED",
            "engine_mode": "BALANCED",
            "notes": "review only",
        },
        state_path=path,
        expected_revision=0,
        generated_at_utc=GENERATED_AT,
    )
    loaded = load_mobile_controls(path, generated_at_utc=GENERATED_AT)

    assert saved == loaded
    assert loaded["control_revision"] == 1
    assert loaded["updated_utc"] == GENERATED_AT
    assert loaded["requested_runtime_mode"] == "LIVE_READ_ONLY"
    assert loaded["display_mode"] == "DETAILED"
    assert loaded["engine_mode"] == "BALANCED"
    assert loaded["operator_acknowledged"] is True


def test_atomic_replace_failure_preserves_prior_valid_file_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "controls.json"
    original = save_mobile_controls(
        {"requested_pause": True},
        state_path=path,
        generated_at_utc=GENERATED_AT,
    )
    original_text = path.read_text(encoding="utf-8")

    def fail_replace(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(css_mobile_controls.os, "replace", fail_replace)
    with pytest.raises(MobileControlPersistenceError):
        save_mobile_controls(
            {"requested_pause": False},
            state_path=path,
            generated_at_utc=GENERATED_AT,
        )

    assert json.loads(path.read_text(encoding="utf-8")) == original
    assert path.read_text(encoding="utf-8") == original_text
    assert list(tmp_path.glob(f".{path.name}.*.tmp")) == []


def test_failed_temporary_write_preserves_prior_valid_file_and_revision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "controls.json"
    original = save_mobile_controls(
        {"requested_pause": True},
        state_path=path,
        generated_at_utc=GENERATED_AT,
    )

    def fail_dump(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("dump failed")

    monkeypatch.setattr(css_mobile_controls.json, "dump", fail_dump)
    with pytest.raises(MobileControlPersistenceError):
        save_mobile_controls(
            {"requested_pause": False},
            state_path=path,
            generated_at_utc=GENERATED_AT,
        )

    loaded = load_mobile_controls(path, generated_at_utc=GENERATED_AT)
    assert loaded == original
    assert loaded["control_revision"] == 1
    assert list(tmp_path.glob(f".{path.name}.*.tmp")) == []


def test_json_output_is_deterministic_with_fixed_timestamp(tmp_path: Path) -> None:
    one = tmp_path / "one.json"
    two = tmp_path / "two.json"
    controls = {
        "engine_mode": "SAFE",
        "display_mode": "COMPACT",
        "operator_acknowledged": True,
    }

    save_mobile_controls(controls, state_path=one, generated_at_utc=GENERATED_AT)
    save_mobile_controls(controls, state_path=two, generated_at_utc=GENERATED_AT)

    assert one.read_text(encoding="utf-8") == two.read_text(encoding="utf-8")


def test_revision_increases_monotonically_and_stale_revision_is_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "controls.json"
    first = save_mobile_controls({"display_mode": "COMPACT"}, state_path=path)
    second = save_mobile_controls(
        {"display_mode": "DETAILED"},
        state_path=path,
        expected_revision=first["control_revision"],
    )

    assert first["control_revision"] == 1
    assert second["control_revision"] == 2
    with pytest.raises(MobileControlRevisionError):
        save_mobile_controls(
            {"display_mode": "DEFAULT"},
            state_path=path,
            expected_revision=first["control_revision"],
        )
    assert load_mobile_controls(path)["control_revision"] == 2


def test_concurrent_writes_do_not_corrupt_file_or_duplicate_revisions(tmp_path: Path) -> None:
    path = tmp_path / "controls.json"

    def write(index: int) -> int:
        payload = save_mobile_controls(
            {"notes": f"writer-{index}", "display_mode": "COMPACT"},
            state_path=path,
        )
        return int(payload["control_revision"])

    with ThreadPoolExecutor(max_workers=8) as pool:
        revisions = list(pool.map(write, range(20)))

    loaded = load_mobile_controls(path)
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == (
        MOBILE_CONTROLS_SCHEMA_VERSION
    )
    assert sorted(revisions) == list(range(1, 21))
    assert loaded["control_revision"] == 20


def test_concurrent_reads_never_observe_partial_json(tmp_path: Path) -> None:
    path = tmp_path / "controls.json"
    save_mobile_controls({"notes": "seed"}, state_path=path)

    def write(index: int) -> None:
        save_mobile_controls({"notes": f"writer-{index}"}, state_path=path)

    def read(_: int) -> str:
        return str(load_mobile_controls(path)["schema_version"])

    with ThreadPoolExecutor(max_workers=8) as pool:
        write_results = [pool.submit(write, index) for index in range(10)]
        read_results = [pool.submit(read, index) for index in range(50)]
        for result in write_results:
            result.result()
        schemas = [result.result() for result in read_results]

    assert set(schemas) == {MOBILE_CONTROLS_SCHEMA_VERSION}


def test_unexpected_and_sensitive_fields_do_not_weaken_or_persist_controls(
    tmp_path: Path,
) -> None:
    path = tmp_path / "controls.json"
    saved = save_mobile_controls(
        {
            "unexpected": {"orders_enabled": True},
            "api_key": "SECRET",
            "nested": {"token": "SECRET"},
            "notes": "secret token should be omitted",
            "orders_enabled": True,
        },
        state_path=path,
        generated_at_utc=GENERATED_AT,
    )
    text = path.read_text(encoding="utf-8")

    assert "SECRET" not in text
    assert "api_key" not in text
    assert "token" not in text
    assert saved["notes"] == ""
    assert saved["orders_enabled"] is False
    assert saved["source_metadata"]["sensitive_fields_omitted"] is True


def test_no_absolute_state_path_leaks_into_returned_payload(tmp_path: Path) -> None:
    path = tmp_path / "controls.json"
    payload = save_mobile_controls({"display_mode": "COMPACT"}, state_path=path)

    assert str(path) not in json.dumps(payload, sort_keys=True)


def test_kill_switch_state_is_display_only_and_fail_closed() -> None:
    controls = load_mobile_controls(
        Path("missing.json"),
        generated_at_utc=GENERATED_AT,
    )
    missing = evaluate_kill_switch_state(
        controls,
        generated_at_utc=GENERATED_AT,
    )
    supplied = evaluate_kill_switch_state(
        controls,
        canonical_kill_switch={"blocked": False, "reason": "canonical_clear"},
        generated_at_utc=GENERATED_AT,
    )

    assert missing["blocked"] is True
    assert missing["reason"] == "canonical_kill_switch_not_supplied"
    assert supplied["blocked"] is False
    assert supplied["source"] == "canonical_authority_display"
    assert supplied["authority"]["kill_switch_authority"] is False


def test_no_environment_network_broker_order_subprocess_or_authority_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_side_effect(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("mobile controls attempted a prohibited side effect")

    with monkeypatch.context() as guard:
        guard.setattr(os, "getenv", fail_side_effect)
        guard.setattr(os, "putenv", fail_side_effect)
        guard.setattr(os, "system", fail_side_effect)
        guard.setattr(socket, "socket", fail_side_effect)
        guard.setattr(socket, "create_connection", fail_side_effect)
        guard.setattr(subprocess, "run", fail_side_effect)
        guard.setattr(subprocess, "Popen", fail_side_effect)
        guard.setattr(builtins, "open", fail_side_effect)

        payload = load_mobile_controls(
            tmp_path / "missing.json",
            generated_at_utc=GENERATED_AT,
        )
        kill_state = evaluate_kill_switch_state(
            payload,
            generated_at_utc=GENERATED_AT,
        )

    assert payload["source_metadata"]["no_environment_reads"] is True
    assert kill_state["authority"]["runtime_authority"] is False
    assert kill_state["authority"]["order_authority"] is False


def test_source_has_no_prohibited_imports_or_authority_calls() -> None:
    source = inspect.getsource(css_mobile_controls)

    assert "dashboard.runtime.web_kill_switch_governance" not in source
    assert "evaluate_live_order_kill_switch" not in source
    assert "resolve_runtime_mode" not in source
    assert "build_platform_status" not in source
    assert "submit_order" not in source
    assert "cancel_order" not in source
    assert "oanda_adapter" not in source
