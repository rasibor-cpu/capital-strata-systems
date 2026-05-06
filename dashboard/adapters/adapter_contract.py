from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from dashboard.runtime.dashboard_state import DashboardState
from dashboard.summaries.summary_contract import DashboardSummaryPayload


class DashboardAdapter(ABC):
    """
    Canonical adapter contract for translating backend/module outputs
    into dashboard-safe state and summary payloads.

    Adapter rules:
    - normalize module outputs
    - protect dashboard from raw internal structures
    - never execute trades
    - never override governance decisions
    - never mutate accounting truth
    """

    @abstractmethod
    def to_dashboard_state(
        self,
        module_output: Dict[str, Any],
        current_state: DashboardState,
    ) -> DashboardState:
        pass

    @abstractmethod
    def to_dashboard_summary(
        self,
        state: DashboardState,
    ) -> DashboardSummaryPayload:
        pass