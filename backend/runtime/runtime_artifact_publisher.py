from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.portfolio.runtime_portfolio_state_builder import RuntimePortfolioStateBuilder


class RuntimeArtifactPublisherError(RuntimeError):
    """Fail-closed exception for canonical runtime artifact publishing."""


class RuntimeArtifactPublisher:
    """Publish advisory-only canonical runtime artifacts for paper validation."""

    SCHEMA_VERSION = "136A.1"

    def __init__(
        self,
        *,
        artifacts_dir: str | Path,
        account_state_path: str | Path | None = None,
        session_state_path: str | Path | None = None,
        closed_trade_ledger_path: str | Path | None = None,
        supervisor_state_path: str | Path | None = None,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir)
        self.account_state_path = Path(account_state_path) if account_state_path else self.artifacts_dir / "css_account_state_pcnrass.json"
        self.session_state_path = Path(session_state_path) if session_state_path else self.artifacts_dir / "css_session_state_pcnrass.json"
        self.closed_trade_ledger_path = Path(closed_trade_ledger_path) if closed_trade_ledger_path else None
        self.supervisor_state_path = Path(supervisor_state_path) if supervisor_state_path else None

    def publish(
        self,
        *,
        runtime_cycle: int | None = None,
        runtime_portfolio_state: Mapping[str, Any] | None = None,
        runtime_advisory_snapshot: Mapping[str, Any] | None = None,
        portfolio_decision: Mapping[str, Any] | None = None,
        portfolio_snapshot: Mapping[str, Any] | None = None,
        validation_summary: Mapping[str, Any] | None = None,
        advisory_snapshot_builder: Callable[[], Mapping[str, Any]] | None = None,
        portfolio_decision_builder: Callable[[], Mapping[str, Any]] | None = None,
        validation_summary_builder: Callable[[], Mapping[str, Any]] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        cycle = int(runtime_cycle or self._runtime_cycle())
        warnings: list[str] = []
        published: dict[str, str] = {}

        state = dict(runtime_portfolio_state) if isinstance(runtime_portfolio_state, Mapping) else self._build_portfolio_state(warnings)
        decision = self._payload_or_builder(portfolio_decision, portfolio_decision_builder, warnings, "portfolio_decision")
        advisory = self._payload_or_builder(runtime_advisory_snapshot, advisory_snapshot_builder, warnings, "runtime_advisory_snapshot")
        summary = self._payload_or_builder(validation_summary, validation_summary_builder, warnings, "validation_summary")
        snapshot = dict(portfolio_snapshot) if isinstance(portfolio_snapshot, Mapping) else self._portfolio_snapshot(state)
        account = self._account_artifact(state)

        artifacts = {
            "css_account_state_pcnrass.json": account,
            "runtime_portfolio_state.json": state,
            "runtime_advisory_snapshot.json": advisory,
            "portfolio_snapshot.json": snapshot,
            "portfolio_decision.json": decision,
            "validation_summary.json": summary,
        }

        for filename, payload in artifacts.items():
            canonical = self._canonical(payload, runtime_cycle=cycle, timestamp=ts, source_module="RuntimeArtifactPublisher")
            try:
                self.artifacts_dir.mkdir(parents=True, exist_ok=True)
                path = self.artifacts_dir / filename
                path.write_text(json.dumps(canonical, indent=2, sort_keys=True, default=str), encoding="utf-8")
                published[filename] = str(path)
            except Exception as exc:
                warnings.append(f"write_failed_{filename}:{exc}")

        status = "OK" if len(published) == len(artifacts) else "AMBER"
        if not published:
            status = "DATA UNAVAILABLE"
        return {
            "status": status,
            "published_artifacts": published,
            "warnings": sorted(set(warnings)),
            "runtime_cycle": cycle,
            "timestamp": ts,
            "schema_version": self.SCHEMA_VERSION,
            "advisory_only": True,
            "execution_allowed": False,
        }

    def _build_portfolio_state(self, warnings: list[str]) -> dict[str, Any]:
        try:
            return RuntimePortfolioStateBuilder(
                artifacts_dir=self.artifacts_dir,
                account_state_path=self.account_state_path,
                session_state_path=self.session_state_path,
                closed_trade_ledger_path=self.closed_trade_ledger_path,
                supervisor_state_path=self.supervisor_state_path,
            ).build()
        except Exception as exc:
            warnings.append(f"runtime_portfolio_state_unavailable:{exc}")
            return self._unavailable("runtime_portfolio_state_unavailable")

    def _payload_or_builder(
        self,
        payload: Mapping[str, Any] | None,
        builder: Callable[[], Mapping[str, Any]] | None,
        warnings: list[str],
        name: str,
    ) -> dict[str, Any]:
        if isinstance(payload, Mapping):
            return dict(payload)
        if builder is not None:
            try:
                built = builder()
                if isinstance(built, Mapping):
                    return dict(built)
                warnings.append(f"{name}_builder_returned_non_mapping")
            except Exception as exc:
                warnings.append(f"{name}_builder_failed:{exc}")
        return self._unavailable(f"{name}_unavailable")

    def _runtime_cycle(self) -> int:
        for path in (self.session_state_path, self.artifacts_dir / "css_session_recovery.json"):
            payload = self._read_json(path)
            session = payload.get("session", payload) if isinstance(payload, Mapping) else {}
            if not isinstance(session, Mapping):
                continue
            for key in ("cycle_number", "runtime_cycle", "current_cycle"):
                value = session.get(key)
                try:
                    return int(value)
                except (TypeError, ValueError):
                    continue
        return 0

    def _account_artifact(self, runtime_state: Mapping[str, Any]) -> dict[str, Any]:
        account = self._read_json(self.account_state_path)
        if account:
            return account
        summary = runtime_state.get("account", {}) if isinstance(runtime_state, Mapping) else {}
        return dict(summary) if isinstance(summary, Mapping) else self._unavailable("account_state_unavailable")

    @staticmethod
    def _portfolio_snapshot(runtime_state: Mapping[str, Any]) -> dict[str, Any]:
        account = runtime_state.get("account", {}) if isinstance(runtime_state, Mapping) else {}
        return {
            "status": runtime_state.get("status", "DATA UNAVAILABLE") if isinstance(runtime_state, Mapping) else "DATA UNAVAILABLE",
            "portfolio_state": runtime_state.get("portfolio_state", "UNKNOWN") if isinstance(runtime_state, Mapping) else "UNKNOWN",
            "account_snapshot": dict(account) if isinstance(account, Mapping) else {},
            "asset_allocations": runtime_state.get("asset_allocations", {}) if isinstance(runtime_state, Mapping) else {},
            "open_positions": runtime_state.get("positions", []) if isinstance(runtime_state, Mapping) else [],
            "closed_trade_count": len(runtime_state.get("trades", [])) if isinstance(runtime_state.get("trades", []), list) else 0,
        }

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _canonical(
        cls,
        payload: Mapping[str, Any],
        *,
        runtime_cycle: int,
        timestamp: str,
        source_module: str,
    ) -> dict[str, Any]:
        result = dict(payload)
        result.update(
            {
                "timestamp": result.get("timestamp") or timestamp,
                "runtime_cycle": runtime_cycle,
                "schema_version": cls.SCHEMA_VERSION,
                "source_module": source_module,
                "advisory_only": True,
                "execution_allowed": False,
            }
        )
        return result

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "reason": reason,
            "advisory_only": True,
            "execution_allowed": False,
        }
