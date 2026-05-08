from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from dashboard.runtime.dashboard_state import DashboardState


@dataclass(frozen=True)
class DiagnosticsRenderContract:
    """
    PCNRASS-safe immutable render contract for runtime diagnostics display.
    """

    messages: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    hydration_gaps: tuple[str, ...] = ()
    builder_failures: tuple[str, ...] = ()
    governance_alerts: tuple[str, ...] = ()

    @classmethod
    def from_dashboard_state(
        cls,
        state: DashboardState,
    ) -> "DiagnosticsRenderContract":
        last_scan_results = state.last_scan_results or {}
        diagnostics_summary = cls._mapping(
            last_scan_results.get("diagnostics_summary", {})
        )

        messages = cls._items(state.dashboard_messages)
        messages += cls._items(diagnostics_summary.get("messages", ()))

        warnings = cls._items(diagnostics_summary.get("warnings", ()))
        warnings += cls._runtime_warnings(state)

        hydration_gaps = cls._items(
            diagnostics_summary.get("hydration_gaps", ())
        )
        hydration_gaps += cls._hydration_gaps(state)

        builder_failures = cls._items(
            last_scan_results.get("builder_failures", ())
        )
        builder_failures += cls._items(
            diagnostics_summary.get("builder_failures", ())
        )

        governance_alerts = cls._items(
            diagnostics_summary.get("governance_alerts", ())
        )
        governance_alerts += cls._governance_alerts(state)

        return cls(
            messages=cls._unique(messages),
            warnings=cls._unique(warnings),
            hydration_gaps=cls._unique(hydration_gaps),
            builder_failures=cls._unique(builder_failures),
            governance_alerts=cls._unique(governance_alerts),
        )

    def has_items(self) -> bool:
        return any(
            (
                self.messages,
                self.warnings,
                self.hydration_gaps,
                self.builder_failures,
                self.governance_alerts,
            )
        )

    @classmethod
    def _runtime_warnings(cls, state: DashboardState) -> tuple[str, ...]:
        warnings: list[str] = []

        if state.broker_state.selected_broker == "NONE":
            warnings.append("No broker selected")

        if state.resolved_mode() != cls._normalize_mode(state.live_or_paper):
            warnings.append(
                "Session mode and broker mode disagree; resolved mode is paper"
            )

        return tuple(warnings)

    @staticmethod
    def _hydration_gaps(state: DashboardState) -> tuple[str, ...]:
        gaps: list[str] = []
        last_scan_results = state.last_scan_results or {}

        for key in (
            "account_summary",
            "pnl_summary",
            "risk_summary",
            "execution_summary",
        ):
            if not last_scan_results.get(key):
                gaps.append(f"Missing {key}")

        if not state.session_id:
            gaps.append("Missing session_id")

        if not state.user_id:
            gaps.append("Missing user_id")

        return tuple(gaps)

    @staticmethod
    def _governance_alerts(state: DashboardState) -> tuple[str, ...]:
        governance = state.governance_state
        alerts: list[str] = []

        if not governance.governance_enabled:
            alerts.append("Governance disabled")

        if governance.session_locked:
            alerts.append("Session locked")

        if governance.defensive_mode_active:
            alerts.append("Defensive mode active")

        if not governance.unified_trade_gate_active:
            alerts.append("Unified trade gate inactive")

        return tuple(alerts)

    @staticmethod
    def _normalize_mode(value: Any) -> str:
        return "live" if str(value or "").strip().lower() == "live" else "paper"

    @staticmethod
    def _mapping(value: Any) -> dict:
        return dict(value) if isinstance(value, dict) else {}

    @classmethod
    def _items(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()

        if isinstance(value, str):
            return cls._clean_items((value,))

        if isinstance(value, Iterable):
            return cls._clean_items(value)

        return cls._clean_items((value,))

    @staticmethod
    def _clean_items(values: Iterable[Any]) -> tuple[str, ...]:
        return tuple(
            item
            for item in (str(value).strip() for value in values)
            if item
        )

    @staticmethod
    def _unique(values: Iterable[str]) -> tuple[str, ...]:
        unique_values: list[str] = []
        seen: set[str] = set()

        for value in values:
            if value in seen:
                continue

            seen.add(value)
            unique_values.append(value)

        return tuple(unique_values)
