from __future__ import annotations

import inspect
import os
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.runtime_contract import DashboardRuntimeCoordinator
from dashboard.summaries.summary_contract import DashboardSummaryPayload


class MinimalRuntimeCoordinator(DashboardRuntimeCoordinator):
    def __init__(self) -> None:
        self.refreshes: list[str] = []

    def build_dashboard_state(self) -> DashboardState:
        return DashboardState(session_id="test-session", engine_mode="SAFE")

    def build_dashboard_summary(
        self,
        state: DashboardState,
    ) -> DashboardSummaryPayload:
        return DashboardSummaryPayload(
            metadata={
                "session_id": state.session_id,
                "engine_mode": state.engine_mode,
            }
        )

    def refresh_cycle(self) -> None:
        self.refreshes.append("refresh")


def test_runtime_contract_imports_and_declares_abstract_interface() -> None:
    assert inspect.isclass(DashboardRuntimeCoordinator)
    assert inspect.isabstract(DashboardRuntimeCoordinator)
    assert DashboardRuntimeCoordinator.__abstractmethods__ == {
        "build_dashboard_state",
        "build_dashboard_summary",
        "refresh_cycle",
    }

    with pytest.raises(TypeError):
        DashboardRuntimeCoordinator()


def test_runtime_contract_method_signatures_are_stable() -> None:
    state_signature = inspect.signature(DashboardRuntimeCoordinator.build_dashboard_state)
    summary_signature = inspect.signature(
        DashboardRuntimeCoordinator.build_dashboard_summary
    )
    refresh_signature = inspect.signature(DashboardRuntimeCoordinator.refresh_cycle)

    assert list(state_signature.parameters) == ["self"]
    assert state_signature.return_annotation == "DashboardState"

    assert list(summary_signature.parameters) == ["self", "state"]
    assert summary_signature.parameters["state"].annotation == "DashboardState"
    assert summary_signature.return_annotation == "DashboardSummaryPayload"

    assert list(refresh_signature.parameters) == ["self"]
    assert refresh_signature.return_annotation == "None"


def test_minimal_runtime_coordinator_is_deterministic_and_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_side_effect(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("runtime contract exercise attempted an external side effect")

    with monkeypatch.context() as side_effect_guard:
        side_effect_guard.setattr(os, "getenv", fail_side_effect)
        side_effect_guard.setattr(os, "putenv", fail_side_effect)
        side_effect_guard.setattr(os, "system", fail_side_effect)
        side_effect_guard.setattr(socket, "socket", fail_side_effect)
        side_effect_guard.setattr(socket, "create_connection", fail_side_effect)
        side_effect_guard.setattr(subprocess, "run", fail_side_effect)
        side_effect_guard.setattr(subprocess, "Popen", fail_side_effect)
        side_effect_guard.setattr(Path, "open", fail_side_effect)
        side_effect_guard.setattr(Path, "read_text", fail_side_effect)
        side_effect_guard.setattr(Path, "write_text", fail_side_effect)

        coordinator = MinimalRuntimeCoordinator()

        first_state = coordinator.build_dashboard_state()
        first_summary = coordinator.build_dashboard_summary(first_state)
        coordinator.refresh_cycle()

        second_state = coordinator.build_dashboard_state()
        second_summary = coordinator.build_dashboard_summary(second_state)
        coordinator.refresh_cycle()

    assert first_state == second_state
    assert first_summary == second_summary
    assert first_summary.metadata == {
        "session_id": "test-session",
        "engine_mode": "SAFE",
    }
    assert coordinator.refreshes == ["refresh", "refresh"]
