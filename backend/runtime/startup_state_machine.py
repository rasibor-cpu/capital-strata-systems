from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from backend.runtime.broker_startup_selection import (
    normalize_broker,
    normalize_broker_mode,
    startup_broker_from_choice,
    startup_broker_mode_from_choice,
)
from backend.runtime.live_operator_wizard import (
    broker_validation_display,
    paper_live_environment_conflict,
    require_exact_confirmation,
)
from backend.runtime.startup_summary import build_live_startup_summary, format_live_startup_summary


STARTUP_STATE_SEQUENCE = (
    "LOGIN",
    "GLOBAL_MODE",
    "GLOBAL_MODE_CONFIRMATION",
    "BROKER_SELECTION",
    "BROKER_MODE",
    "BROKER_MODE_CONFIRMATION",
    "BROKER_EXECUTION",
    "ENGINE_MODE",
    "CYCLE_MODE",
    "STARTUP_SUMMARY",
    "FINAL_CONFIRMATION",
    "START_RUNTIME",
)

QUIT_COMMANDS = {"Q", "QUIT", "EXIT"}


@dataclass(frozen=True)
class StartupMachineConfig:
    timeout_seconds: int = 120
    ibkr_supported: bool = False
    audit_path: str | Path | None = None
    test_mode_auto_confirm: bool = False


@dataclass(frozen=True)
class StartupRuntimeState:
    state: str = "LOGIN"
    global_mode: str = ""
    selected_broker: str = ""
    broker_mode: str = ""
    broker_execution_armed: bool = False
    engine_mode: str = ""
    cycle_mode: str = ""
    cycle_interval_seconds: int = 0
    execution_scope: str = "PAPER_OR_NOT_SELECTED"
    can_live_execute: bool = False
    broker_connected: bool = False
    broker_authenticated: bool = False
    broker_health: str = "NOT_TESTED"
    readiness_status: str = "NOT_TESTED"
    last_input: str = ""
    last_error: str = ""
    cancelled: bool = False
    timed_out: bool = False
    restart_requested: bool = False
    runtime_start_allowed: bool = False
    history: tuple[str, ...] = field(default_factory=lambda: ("LOGIN",))

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["broker_execution_status"] = "ARMED" if self.broker_execution_armed else "DISABLED"
        payload["live_order_permission"] = False
        payload["execution_allowed"] = False
        payload["advisory_only"] = True
        return payload


@dataclass(frozen=True)
class StartupMachineResult:
    state: StartupRuntimeState
    summary: dict[str, Any]
    audit_events: tuple[dict[str, Any], ...]

    @property
    def runtime_start_allowed(self) -> bool:
        return bool(self.state.runtime_start_allowed)

    @property
    def cancelled(self) -> bool:
        return bool(self.state.cancelled)

    @property
    def timed_out(self) -> bool:
        return bool(self.state.timed_out)


class OperatorStartupStateMachine:
    def __init__(
        self,
        *,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
        flush_func: Callable[[], None] | None = None,
        clock: Callable[[], float] | None = None,
        config: StartupMachineConfig | None = None,
        role_profile: Mapping[str, Any] | None = None,
        env: Mapping[str, Any] | None = None,
        broker_status: Mapping[str, Any] | None = None,
        pilot_status: Mapping[str, Any] | None = None,
        allowed_engine_modes: Iterable[str] | None = None,
    ) -> None:
        self.input_func = input_func
        self.output_func = output_func
        self.flush_func = flush_func or (lambda: None)
        self.clock = clock or time.monotonic
        self.config = config or StartupMachineConfig()
        self.role_profile = role_profile if isinstance(role_profile, Mapping) else {}
        self.env = env if isinstance(env, Mapping) else {}
        self.broker_status = broker_status if isinstance(broker_status, Mapping) else {}
        self.pilot_status = pilot_status if isinstance(pilot_status, Mapping) else {}
        self.allowed_engine_modes = tuple(allowed_engine_modes or self.role_profile.get("allowed_engine_modes", ()) or ("SAFE", "CONSERVATIVE", "BALANCED"))
        self.audit_events: list[dict[str, Any]] = []
        self.started_at = self.clock()

    def run(self) -> StartupMachineResult:
        state = StartupRuntimeState()
        self._audit("STATE_ENTER", state, next_state="LOGIN")
        state = self._advance(state, "GLOBAL_MODE", "login_authenticated")

        while state.state != "START_RUNTIME":
            timeout_state = self._timeout_if_needed(state)
            if timeout_state is not None:
                return self._result(timeout_state)
            handler = getattr(self, f"_handle_{state.state.lower()}")
            state = handler(state)
            if state.cancelled or state.timed_out:
                return self._result(state)

        return self._result(state)

    def _handle_global_mode(self, state: StartupRuntimeState) -> StartupRuntimeState:
        value = self._prompt(state, "GLOBAL MODE\n1. PAPER / PRACTICE\n2. LIVE\nEnter choice (1-2): ")
        if self._is_quit(value):
            return self._cancel(state, "operator_exit")
        if value not in {"1", "2"}:
            return self._invalid(state, "1 or 2", value)
        if value == "1":
            return self._advance(replace(state, global_mode="paper", last_input=value), "BROKER_SELECTION", "global_paper_selected")
        return self._advance(replace(state, last_input=value), "GLOBAL_MODE_CONFIRMATION", "global_live_selected")

    def _handle_global_mode_confirmation(self, state: StartupRuntimeState) -> StartupRuntimeState:
        value = self._prompt(state, "Type LIVE to confirm GLOBAL LIVE mode: ", confirmation=True)
        if self._is_quit(value):
            return self._cancel(state, "operator_exit")
        if not value:
            self.output_func("Ignored buffered ENTER. Please enter LIVE.")
            self._audit("BUFFERED_ENTER_IGNORED", state, received="<ENTER>")
            return state
        confirmation = require_exact_confirmation("LIVE", value)
        if not confirmation["accepted"]:
            self.output_func(str(confirmation["message"]))
            self._audit("INVALID_CONFIRMATION", state, received=value, expected="LIVE")
            return replace(state, last_input=value, last_error=str(confirmation["message"]))
        return self._advance(replace(state, global_mode="live", last_input=value, last_error=""), "BROKER_SELECTION", "global_live_confirmed")

    def _handle_broker_selection(self, state: StartupRuntimeState) -> StartupRuntimeState:
        value = self._prompt(state, "BROKER SELECTION\n1. NONE / PAPER ONLY\n2. COINBASE\n3. OANDA\n4. IBKR (if supported)\nEnter broker choice (1-4): ")
        if self._is_quit(value):
            return self._cancel(state, "operator_exit")
        if value not in {"1", "2", "3", "4"}:
            return self._invalid(state, "1, 2, 3, or 4", value)
        if value == "4" and not self.config.ibkr_supported:
            message = "IBKR is not enabled in this runtime. Please choose another broker."
            self.output_func(message)
            self._audit("INVALID_BROKER", state, received=value, reason=message)
            return replace(state, last_input=value, last_error=message)
        broker = startup_broker_from_choice(value, ibkr_supported=self.config.ibkr_supported)
        next_state = "BROKER_EXECUTION" if broker == "NONE" else "BROKER_MODE"
        broker_mode = "paper" if broker == "NONE" else ""
        scope = "PAPER_OR_NOT_SELECTED" if broker == "NONE" else "BROKER_SELECTED_PENDING_MODE"
        return self._advance(
            replace(state, selected_broker=broker, broker_mode=broker_mode, execution_scope=scope, last_input=value, last_error=""),
            next_state,
            "broker_selected",
        )

    def _handle_broker_mode(self, state: StartupRuntimeState) -> StartupRuntimeState:
        default_choice = "2" if state.global_mode == "live" else "1"
        value = self._prompt(state, f"BROKER MODE FOR {state.selected_broker}\n1. PAPER / PRACTICE / AUTH TEST\n2. LIVE / READ-ONLY VALIDATION\nEnter broker mode (1-2) [default={default_choice}]: ")
        if self._is_quit(value):
            return self._cancel(state, "operator_exit")
        if value == "":
            value = default_choice
        if value not in {"1", "2"}:
            return self._invalid(state, "1 or 2", value)
        mode = startup_broker_mode_from_choice(value, selected_broker=state.selected_broker, global_mode=state.global_mode)
        conflict = paper_live_environment_conflict(state.selected_broker, mode, env=self.env)
        if conflict.get("blocking"):
            self.output_func(str(conflict["message"]))
            self._audit("PAPER_LIVE_ENV_CONFLICT", state, received=value, live_environment_keys=conflict.get("live_environment_keys", []))
            return replace(state, last_input=value, last_error=str(conflict["message"]))
        if mode == "live":
            return self._advance(replace(state, broker_mode=mode, last_input=value, last_error=""), "BROKER_MODE_CONFIRMATION", "broker_live_selected")
        return self._advance(
            replace(state, broker_mode="paper", execution_scope="READ_ONLY_PAPER", last_input=value, last_error=""),
            "BROKER_EXECUTION",
            "broker_paper_selected",
        )

    def _handle_broker_mode_confirmation(self, state: StartupRuntimeState) -> StartupRuntimeState:
        value = self._prompt(state, f"Type LIVE to confirm {state.selected_broker} LIVE read-only validation: ", confirmation=True)
        if self._is_quit(value):
            return self._cancel(state, "operator_exit")
        if not value:
            self.output_func("Ignored buffered ENTER. Please enter LIVE.")
            self._audit("BUFFERED_ENTER_IGNORED", state, received="<ENTER>")
            return state
        confirmation = require_exact_confirmation("LIVE", value)
        if not confirmation["accepted"]:
            self.output_func(str(confirmation["message"]))
            self._audit("INVALID_CONFIRMATION", state, received=value, expected="LIVE")
            return replace(state, last_input=value, last_error=str(confirmation["message"]))
        return self._advance(
            replace(state, broker_mode="live", execution_scope="LIVE READ-ONLY VALIDATION", last_input=value, last_error=""),
            "BROKER_EXECUTION",
            "broker_live_confirmed",
        )

    def _handle_broker_execution(self, state: StartupRuntimeState) -> StartupRuntimeState:
        live_mode = normalize_broker_mode(state.broker_mode, selected_broker=state.selected_broker) == "live"
        arm_text = "2. ARMED / BROKER EXECUTION ALLOWED" if not live_mode else "Type ARM LIVE to arm live broker execution"
        value = self._prompt(
            state,
            f"BROKER EXECUTION\n1. DISABLED / READ-ONLY VALIDATION\n{arm_text}\nEnter broker execution choice: ",
            confirmation=live_mode,
        )
        if self._is_quit(value):
            return self._cancel(state, "operator_exit")
        if value == "1":
            return self._advance(replace(state, broker_execution_armed=False, can_live_execute=False, last_input=value, last_error=""), "ENGINE_MODE", "broker_execution_disabled")
        if live_mode and value != "ARM LIVE":
            confirmation = require_exact_confirmation("ARM LIVE", value)
            self.output_func(str(confirmation["message"]))
            self._audit("INVALID_CONFIRMATION", state, received=value if value else "<ENTER>", expected="ARM LIVE")
            return replace(state, broker_execution_armed=False, can_live_execute=False, last_input=value if value else "<ENTER>", last_error=str(confirmation["message"]))
        if not live_mode and value != "2":
            return self._invalid(state, "1 or 2", value)
        if normalize_broker(state.selected_broker) == "NONE":
            message = "Broker execution cannot be armed because no broker is selected."
            self.output_func(message)
            self._audit("BROKER_ARM_BLOCKED", state, received=value, reason=message)
            return replace(state, broker_execution_armed=False, can_live_execute=False, last_input=value, last_error=message)
        if not bool(self.role_profile.get("can_arm_broker", False)):
            message = "Broker execution arming denied by RBAC."
            self.output_func(message)
            self._audit("BROKER_ARM_BLOCKED", state, received=value, reason=message)
            return self._advance(replace(state, broker_execution_armed=False, can_live_execute=False, last_input=value, last_error=message), "ENGINE_MODE", "broker_arm_rbac_denied")
        return self._advance(
            replace(state, broker_execution_armed=True, can_live_execute=live_mode, last_input=value, last_error=""),
            "ENGINE_MODE",
            "broker_execution_armed",
        )

    def _handle_engine_mode(self, state: StartupRuntimeState) -> StartupRuntimeState:
        options = {str(index): mode for index, mode in enumerate(self.allowed_engine_modes, start=1)}
        prompt_lines = ["ENGINE MODE"] + [f"{key}. {value}" for key, value in options.items()]
        value = self._prompt(state, "\n".join(prompt_lines) + "\nEnter engine mode choice: ")
        if self._is_quit(value):
            return self._cancel(state, "operator_exit")
        if value not in options:
            return self._invalid(state, ", ".join(options), value)
        return self._advance(replace(state, engine_mode=str(options[value]).upper(), last_input=value, last_error=""), "CYCLE_MODE", "engine_mode_selected")

    def _handle_cycle_mode(self, state: StartupRuntimeState) -> StartupRuntimeState:
        value = self._prompt(state, "CYCLE MODE\n1. MANUAL\n2. CONTINUOUS\nEnter cycle mode choice (1-2): ")
        if self._is_quit(value):
            return self._cancel(state, "operator_exit")
        if value not in {"1", "2"}:
            return self._invalid(state, "1 or 2", value)
        if value == "1":
            return self._advance(replace(state, cycle_mode="manual", cycle_interval_seconds=0, last_input=value, last_error=""), "STARTUP_SUMMARY", "cycle_manual_selected")
        return self._advance(replace(state, cycle_mode="continuous", cycle_interval_seconds=60, last_input=value, last_error=""), "STARTUP_SUMMARY", "cycle_continuous_selected")

    def _handle_startup_summary(self, state: StartupRuntimeState) -> StartupRuntimeState:
        summary = self._summary(state)
        for line in format_live_startup_summary(summary):
            self.output_func(line)
        self._audit("STARTUP_SUMMARY_DISPLAYED", state, summary=summary)
        return self._advance(state, "FINAL_CONFIRMATION", "startup_summary_displayed")

    def _handle_final_confirmation(self, state: StartupRuntimeState) -> StartupRuntimeState:
        if self.config.test_mode_auto_confirm:
            return self._advance(replace(state, runtime_start_allowed=True, last_input="Y"), "START_RUNTIME", "test_mode_auto_confirmed")
        value = self._prompt(state, "Y = Start Runtime | N = Restart Startup Wizard | Q = Exit: ", confirmation=True)
        if self._is_quit(value):
            return self._cancel(state, "operator_exit")
        if not value:
            self.output_func("Ignored buffered ENTER. Please enter Y, N, or Q.")
            self._audit("BUFFERED_ENTER_IGNORED", state, received="<ENTER>")
            return state
        if value.upper() == "Y":
            return self._advance(replace(state, runtime_start_allowed=True, last_input=value, last_error=""), "START_RUNTIME", "final_confirmation_yes")
        if value.upper() == "N":
            restarted = StartupRuntimeState(state="GLOBAL_MODE", history=state.history + ("GLOBAL_MODE",), restart_requested=True)
            self._audit("STARTUP_RESTART_REQUESTED", state, next_state="GLOBAL_MODE", received=value)
            return restarted
        return self._invalid(state, "Y, N, or Q", value)

    def _prompt(self, state: StartupRuntimeState, prompt: str, *, confirmation: bool = False) -> str:
        if confirmation:
            self.flush_func()
            self._audit("STDIN_FLUSHED", state)
        value = self.input_func(prompt)
        text = str(value or "").strip()
        self._audit("INPUT_RECEIVED", state, received=text if text else "<ENTER>")
        return text

    def _advance(self, state: StartupRuntimeState, next_state: str, reason: str) -> StartupRuntimeState:
        if next_state not in STARTUP_STATE_SEQUENCE:
            raise ValueError(f"Unknown startup state: {next_state}")
        new_state = replace(state, state=next_state, history=state.history + (next_state,), last_error="")
        self._audit("STATE_TRANSITION", state, next_state=next_state, reason=reason)
        return new_state

    def _invalid(self, state: StartupRuntimeState, expected: str, received: Any) -> StartupRuntimeState:
        received_text = str(received if received != "" else "<ENTER>")
        message = f"INVALID INPUT\nExpected: {expected}\nReceived: {received_text}\nPlease try again."
        self.output_func(message)
        self._audit("INVALID_INPUT", state, expected=expected, received=received_text)
        return replace(state, last_error=message, last_input=received_text)

    def _cancel(self, state: StartupRuntimeState, reason: str) -> StartupRuntimeState:
        self.output_func("Startup cancelled.")
        self._audit("STARTUP_CANCELLED", state, reason=reason)
        return replace(state, cancelled=True, runtime_start_allowed=False, last_error=reason)

    def _timeout_if_needed(self, state: StartupRuntimeState) -> StartupRuntimeState | None:
        if int(self.config.timeout_seconds) <= 0:
            return None
        if self.clock() - self.started_at <= int(self.config.timeout_seconds):
            return None
        self.output_func("Startup cancelled.\nReturning to Login.")
        self._audit("STARTUP_TIMEOUT", state, next_state="LOGIN")
        return replace(state, state="LOGIN", timed_out=True, runtime_start_allowed=False, history=state.history + ("LOGIN",), last_error="startup_timeout")

    def _summary(self, state: StartupRuntimeState) -> dict[str, Any]:
        status = broker_validation_display(
            selected_broker=state.selected_broker or "NONE",
            broker_mode=state.broker_mode or "paper",
            readiness={
                **dict(self.broker_status),
                "broker_execution_armed": state.broker_execution_armed,
            },
            env=self.env,
        )
        broker_status = {
            **status,
            **dict(self.broker_status),
            "broker_health": self.broker_status.get("broker_health", status.get("connection_status", "NOT_TESTED")),
        }
        summary = build_live_startup_summary(
            {
                **state.as_dict(),
                "selected_broker": state.selected_broker or "NONE",
                "broker_mode": state.broker_mode or "paper",
            },
            broker_status=broker_status,
            pilot_status=self.pilot_status,
        )
        return summary | {
            "global_mode": str(state.global_mode or "paper"),
            "selected_broker": str(state.selected_broker or "NONE"),
            "broker_mode": str(state.broker_mode or "paper"),
            "broker_connection_status": str(broker_status.get("connection_status", broker_status.get("broker_health", "NOT_TESTED"))),
            "broker_auth_status": str(broker_status.get("auth_status", "NOT_TESTED")),
            "broker_connected": bool(self.broker_status.get("broker_connected", False)),
            "broker_authenticated": bool(self.broker_status.get("broker_authenticated", False)),
            "broker_health": str(self.broker_status.get("broker_health", "NOT_TESTED")),
            "readiness_status": str(self.broker_status.get("broker_readiness_status", self.broker_status.get("readiness_status", "NOT_TESTED"))),
        }

    def _result(self, state: StartupRuntimeState) -> StartupMachineResult:
        return StartupMachineResult(
            state=state,
            summary=self._summary(state),
            audit_events=tuple(self.audit_events),
        )

    def _audit(self, event_type: str, state: StartupRuntimeState, **details: Any) -> None:
        event = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event_type": event_type,
            "state": state.state,
            "details": details,
            "advisory_only": True,
            "execution_allowed": False,
        }
        self.audit_events.append(event)
        if self.config.audit_path:
            path = Path(self.config.audit_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")

    @staticmethod
    def _is_quit(value: str) -> bool:
        return str(value or "").strip().upper() in QUIT_COMMANDS


def default_stdin_flush() -> None:
    try:
        import msvcrt

        while msvcrt.kbhit():
            msvcrt.getwch()
    except Exception:
        return


def run_startup_state_machine(**kwargs: Any) -> StartupMachineResult:
    return OperatorStartupStateMachine(**kwargs).run()


__all__ = [
    "OperatorStartupStateMachine",
    "QUIT_COMMANDS",
    "STARTUP_STATE_SEQUENCE",
    "StartupMachineConfig",
    "StartupMachineResult",
    "StartupRuntimeState",
    "default_stdin_flush",
    "run_startup_state_machine",
]
