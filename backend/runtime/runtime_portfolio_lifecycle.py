from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.portfolio.open_position_registry import OpenPositionRegistry
from backend.portfolio.runtime_exposure_builder import RuntimeExposureBuilder
from backend.portfolio.runtime_portfolio_state_builder import RuntimePortfolioStateBuilder


class RuntimePortfolioLifecycleError(RuntimeError):
    """Fail-closed exception for runtime portfolio lifecycle refresh."""


class RuntimePortfolioLifecycle:
    """Maintain canonical advisory runtime portfolio lifecycle snapshots."""

    def __init__(self, artifacts_dir: str | Path, *, stale_after_seconds: float = 300.0) -> None:
        self.artifacts_dir = Path(artifacts_dir)
        self.stale_after_seconds = float(stale_after_seconds)
        self.registry = OpenPositionRegistry(self.artifacts_dir)

    def refresh(
        self,
        *,
        runtime_state: Mapping[str, Any] | None = None,
        advisory_snapshot: Mapping[str, Any] | None = None,
        portfolio_decision: Mapping[str, Any] | None = None,
        validation_summary: Mapping[str, Any] | None = None,
        timestamp: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        state = dict(runtime_state) if isinstance(runtime_state, Mapping) else RuntimePortfolioStateBuilder(
            artifacts_dir=self.artifacts_dir,
            stale_after_seconds=self.stale_after_seconds,
        ).build()
        positions = state.get("positions", []) if isinstance(state.get("positions", []), list) else []
        exposure = RuntimeExposureBuilder().build(positions)
        registry_summary = self.registry.sync_positions(positions, timestamp=ts, persist=persist)

        lifecycle_state = self._lifecycle_state(state, exposure)
        account = state.get("account", {}) if isinstance(state.get("account"), Mapping) else {}
        snapshot = {
            "status": "OK" if lifecycle_state != "BROKEN_PIPELINE" else "DATA UNAVAILABLE",
            "lifecycle_status": "CONNECTED" if lifecycle_state != "BROKEN_PIPELINE" else "BROKEN",
            "portfolio_state": lifecycle_state,
            "timestamp": ts,
            "account_snapshot": account,
            "open_positions": registry_summary.get("open_positions", []),
            "open_position_count": registry_summary.get("open_count", 0),
            "unrealized_pnl": account.get("open_pnl", 0.0),
            "realized_pnl": account.get("realized_pnl", 0.0),
            "exposure": exposure,
            "allocations": state.get("asset_allocations", {}),
            "strategy_performance": state.get("strategy_metrics", {}),
            "regime_inputs": state.get("market_data", {}),
            "runtime_state_status": state.get("status", "DATA UNAVAILABLE"),
            "artifact_freshness": state.get("staleness", {}),
            "advisory_snapshot_status": self._payload_status(advisory_snapshot, "snapshot_status"),
            "portfolio_decision_status": self._payload_status(portfolio_decision, "overall_status"),
            "validation_status": self._payload_status(validation_summary, "final_validation_status", "readiness_status"),
            "reasons": self._reasons(state, exposure, lifecycle_state),
            "advisory_only": True,
            "execution_allowed": False,
        }
        if persist:
            self._publish(snapshot, state, advisory_snapshot, portfolio_decision, validation_summary)
        return snapshot

    def _publish(
        self,
        lifecycle: Mapping[str, Any],
        runtime_state: Mapping[str, Any],
        advisory_snapshot: Mapping[str, Any] | None,
        portfolio_decision: Mapping[str, Any] | None,
        validation_summary: Mapping[str, Any] | None,
    ) -> None:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        portfolio_dir = self.artifacts_dir / "portfolio"
        portfolio_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(portfolio_dir / "runtime_portfolio_lifecycle.json", lifecycle)
        self._write_json(self.artifacts_dir / "runtime_portfolio_state.json", runtime_state)
        self._write_json(self.artifacts_dir / "portfolio_snapshot.json", lifecycle)
        if isinstance(advisory_snapshot, Mapping):
            self._write_json(self.artifacts_dir / "runtime_advisory_snapshot.json", advisory_snapshot)
        if isinstance(portfolio_decision, Mapping):
            self._write_json(self.artifacts_dir / "portfolio_decision.json", portfolio_decision)
        if isinstance(validation_summary, Mapping):
            self._write_json(self.artifacts_dir / "validation_summary.json", validation_summary)

    @staticmethod
    def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
        path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")

    @staticmethod
    def _lifecycle_state(state: Mapping[str, Any], exposure: Mapping[str, Any]) -> str:
        if str(state.get("status", "")).upper() == "DATA UNAVAILABLE":
            reasons = {str(item) for item in state.get("reasons", [])}
            if reasons and reasons <= {"no_current_exposure", "trade_history_unavailable"}:
                return "NO_PORTFOLIO"
            return "BROKEN_PIPELINE"
        exposure_state = str(exposure.get("portfolio_state", "")).upper()
        if exposure_state == "NO_PORTFOLIO":
            return "NO_PORTFOLIO"
        if exposure_state == "ACTIVE_PORTFOLIO":
            return "ACTIVE_PORTFOLIO"
        return "PARTIAL_PORTFOLIO"

    @staticmethod
    def _payload_status(payload: Mapping[str, Any] | None, *keys: str) -> str:
        if not isinstance(payload, Mapping):
            return "DATA UNAVAILABLE"
        for key in keys:
            value = payload.get(key)
            if value:
                return str(value).upper()
        return str(payload.get("status", "DATA UNAVAILABLE")).upper()

    @staticmethod
    def _reasons(state: Mapping[str, Any], exposure: Mapping[str, Any], lifecycle_state: str) -> list[str]:
        reasons = [str(item) for item in state.get("reasons", []) if str(item).strip()]
        reasons.extend(str(item) for item in exposure.get("reasons", []) if str(item).strip())
        if lifecycle_state == "NO_PORTFOLIO":
            reasons.append("No current exposure.")
        if lifecycle_state == "BROKEN_PIPELINE":
            reasons.append("runtime_portfolio_pipeline_broken")
        return sorted(set(reasons))
