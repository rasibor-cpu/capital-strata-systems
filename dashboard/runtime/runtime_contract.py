from __future__ import annotations

from abc import ABC, abstractmethod

from dashboard.runtime.dashboard_state import DashboardState
from dashboard.summaries.summary_contract import DashboardSummaryPayload


class DashboardRuntimeCoordinator(ABC):
    """
    Canonical dashboard runtime coordination contract.

    PURPOSE
    -------
    Coordinate dashboard refresh/update cycles without
    owning trading, governance, accounting, or execution logic.

    The runtime coordinator may:
    - request payload refreshes
    - coordinate render cycles
    - trigger summary updates
    - orchestrate dashboard refresh timing

    The runtime coordinator must NOT:
    - execute trades
    - calculate market intelligence
    - override governance
    - mutate accounting truth
    """

    @abstractmethod
    def build_dashboard_state(self) -> DashboardState:
        """
        Build structured dashboard runtime state.
        """
        pass

    @abstractmethod
    def build_dashboard_summary(
        self,
        state: DashboardState,
    ) -> DashboardSummaryPayload:
        """
        Build aggregated dashboard summaries.
        """
        pass

    @abstractmethod
    def refresh_cycle(self) -> None:
        """
        Execute one dashboard refresh cycle.
        """
        pass