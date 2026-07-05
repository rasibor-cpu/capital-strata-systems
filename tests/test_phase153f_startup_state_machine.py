from __future__ import annotations

import json
from pathlib import Path

from backend.runtime.startup_state_machine import (
    STARTUP_STATE_SEQUENCE,
    OperatorStartupStateMachine,
    StartupMachineConfig,
    run_startup_state_machine,
)


class InputTape:
    def __init__(self, values: list[str]):
        self.values = list(values)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.values:
            raise AssertionError(f"No input left for prompt: {prompt}")
        return self.values.pop(0)


def _run(inputs: list[str], **kwargs):
    tape = InputTape(inputs)
    output: list[str] = []
    flushes: list[str] = []
    result = run_startup_state_machine(
        input_func=tape,
        output_func=output.append,
        flush_func=lambda: flushes.append("flush"),
        role_profile={
            "can_arm_broker": True,
            "allowed_engine_modes": ["SAFE", "CONSERVATIVE", "BALANCED"],
        },
        pilot_status={
            "pilot_state": "DISARMED",
            "currency": "CAD",
            "canonical_live_pilot_limit_cad": "20.00",
        },
        **kwargs,
    )
    return result, tape, output, flushes


def test_phase153f_live_startup_uses_required_state_sequence() -> None:
    result, _tape, _output, flushes = _run(["2", "LIVE", "2", "2", "LIVE", "1", "1", "1", "Y"])

    assert result.runtime_start_allowed is True
    assert result.state.global_mode == "live"
    assert result.state.selected_broker == "COINBASE"
    assert result.state.broker_mode == "live"
    assert result.state.broker_execution_armed is False
    assert result.state.execution_scope == "LIVE READ-ONLY VALIDATION"
    assert tuple(dict.fromkeys(result.state.history)) == STARTUP_STATE_SEQUENCE
    assert len(flushes) >= 3


def test_phase153f_paper_startup_remains_order_blocked() -> None:
    result, _tape, _output, _flushes = _run(["1", "1", "1", "1", "1", "Y"])

    assert result.runtime_start_allowed is True
    assert result.state.global_mode == "paper"
    assert result.state.selected_broker == "NONE"
    assert result.state.broker_mode == "paper"
    assert result.state.broker_execution_armed is False
    assert result.state.can_live_execute is False
    assert result.summary["broker_execution_status"] == "DISABLED"


def test_phase153f_invalid_live_confirmation_retries_and_displays_received_value() -> None:
    result, _tape, output, _flushes = _run(["2", "2", "LIVE", "1", "1", "1", "1", "Y"])
    text = "\n".join(output)

    assert result.runtime_start_allowed is True
    assert result.state.global_mode == "live"
    assert "INVALID CONFIRMATION" in text
    assert "Expected: LIVE" in text
    assert "Received: 2" in text
    assert "Received:\n" not in text


def test_phase153f_buffered_newline_is_ignored_before_confirmation() -> None:
    result, _tape, output, flushes = _run(["2", "", "LIVE", "1", "1", "1", "1", "Y"])
    text = "\n".join(output)

    assert result.state.global_mode == "live"
    assert "Ignored buffered ENTER" in text
    assert flushes
    assert any(event["event_type"] == "BUFFERED_ENTER_IGNORED" for event in result.audit_events)


def test_phase153f_broker_confirmation_retries_without_paper_fallback() -> None:
    result, _tape, output, _flushes = _run(["2", "LIVE", "2", "2", "2", "LIVE", "1", "1", "1", "Y"])
    text = "\n".join(output)

    assert result.state.broker_mode == "live"
    assert result.state.execution_scope == "LIVE READ-ONLY VALIDATION"
    assert "Expected: LIVE" in text
    assert "Received: 2" in text


def test_phase153f_live_broker_execution_requires_arm_live_phrase() -> None:
    result, _tape, output, _flushes = _run(["2", "LIVE", "2", "2", "LIVE", "2", "ARM LIVE", "1", "1", "Y"])
    text = "\n".join(output)

    assert result.state.operator_requested_live is True
    assert result.state.broker_execution_armed is False
    assert result.state.execution_authority is False
    assert result.state.can_live_execute is False
    assert "Expected: ARM LIVE" in text
    assert "Received: 2" in text


def test_phase153f_broker_none_cannot_arm_execution() -> None:
    result, _tape, output, _flushes = _run(["1", "1", "2", "1", "1", "1", "Y"])
    text = "\n".join(output)

    assert result.state.selected_broker == "NONE"
    assert result.state.broker_execution_armed is False
    assert "Broker execution cannot be armed because no broker is selected." in text


def test_phase153f_paper_mode_blocks_live_broker_environment() -> None:
    result, _tape, output, _flushes = _run(
        ["1", "3", "1", "2", "LIVE", "1", "1", "1", "Y"],
        env={"OANDA_ENV": "live"},
    )
    text = "\n".join(output)

    assert "Paper mode cannot use LIVE broker credentials/environment." in text
    assert result.state.selected_broker == "OANDA"
    assert result.state.broker_mode == "live"


def test_phase153f_startup_summary_and_final_confirmation_gate_runtime() -> None:
    result, _tape, output, _flushes = _run(["1", "1", "1", "1", "1", "Y"])
    text = "\n".join(output)

    assert result.runtime_start_allowed is True
    assert "========== LIVE STARTUP SUMMARY ==========" in text
    assert "Broker Mode: paper" in text
    assert "Capital Governor: PHASE_152A_CAD20_GUARD_ONLY" in text
    assert "Can Live Execute: NO" in text


def test_phase153f_cancel_command_exits_from_any_screen() -> None:
    result, _tape, output, _flushes = _run(["Q"])

    assert result.cancelled is True
    assert result.runtime_start_allowed is False
    assert "Startup cancelled." in "\n".join(output)


def test_phase153f_timeout_returns_to_login() -> None:
    ticks = iter([0.0, 121.0])
    output: list[str] = []
    result = run_startup_state_machine(
        input_func=lambda prompt: "1",
        output_func=output.append,
        clock=lambda: next(ticks),
        config=StartupMachineConfig(timeout_seconds=120),
    )

    assert result.timed_out is True
    assert result.state.state == "LOGIN"
    assert "Startup cancelled.\nReturning to Login." in output


def test_phase153f_restart_runs_wizard_again_before_runtime() -> None:
    result, _tape, _output, _flushes = _run(["1", "1", "1", "1", "1", "N", "1", "1", "1", "1", "1", "Y"])

    assert result.runtime_start_allowed is True
    assert result.state.restart_requested is True
    assert result.state.history.count("GLOBAL_MODE") >= 2


def test_phase153f_jsonl_audit_events_are_structured(tmp_path: Path) -> None:
    audit_path = tmp_path / "startup_audit.jsonl"
    result, _tape, _output, _flushes = _run(
        ["1", "1", "1", "1", "1", "Y"],
        config=StartupMachineConfig(audit_path=audit_path),
    )

    assert result.audit_events
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert lines
    event = json.loads(lines[0])
    assert {"timestamp", "event_type", "state", "details", "advisory_only", "execution_allowed"} <= set(event)
    assert event["execution_allowed"] is False


def test_phase153f_no_silent_paper_fallback_after_invalid_live_confirmation() -> None:
    result, _tape, _output, _flushes = _run(["2", "bad", "LIVE", "2", "2", "bad", "LIVE", "1", "1", "1", "Y"])

    assert result.state.global_mode == "live"
    assert result.state.broker_mode == "live"
    assert result.state.execution_scope == "LIVE READ-ONLY VALIDATION"


def test_phase153f_each_prompt_belongs_to_current_state() -> None:
    _result, tape, _output, _flushes = _run(["2", "LIVE", "2", "2", "LIVE", "1", "1", "1", "Y"])
    joined = "\n".join(tape.prompts)

    assert "GLOBAL MODE" in joined
    assert "Type LIVE to confirm GLOBAL LIVE mode" in joined
    assert "BROKER SELECTION" in joined
    assert "BROKER MODE FOR COINBASE" in joined
    assert "Type LIVE to confirm COINBASE LIVE read-only validation" in joined
    assert "BROKER EXECUTION" in joined
    assert "ENGINE MODE" in joined
    assert "CYCLE MODE" in joined
    assert "Y = Start Runtime" in joined
