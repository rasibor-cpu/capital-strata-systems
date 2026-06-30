from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RuntimeArtifactFreshnessError(RuntimeError):
    """Fail-closed exception for runtime artifact freshness checks."""


class RuntimeArtifactFreshnessManager:
    """Inspect runtime artifacts and classify operational freshness."""

    CRITICAL = {"account_state", "session_state", "supervisor_state"}
    OPTIONAL = {
        "closed_trade_ledger",
        "portfolio_snapshot",
        "runtime_portfolio_state",
        "runtime_advisory_snapshot",
        "portfolio_decision",
        "validation_summary",
    }
    REFRESHABLE = {
        "account_state",
        "session_state",
        "supervisor_state",
        "portfolio_snapshot",
        "runtime_portfolio_state",
        "runtime_advisory_snapshot",
        "portfolio_decision",
        "validation_summary",
    }

    def __init__(
        self,
        *,
        artifacts_dir: str | Path,
        account_state_path: str | Path | None = None,
        session_state_path: str | Path | None = None,
        supervisor_state_path: str | Path | None = None,
        closed_trade_ledger_path: str | Path | None = None,
        stale_after_seconds: float = 300.0,
    ) -> None:
        root = Path(artifacts_dir)
        self.artifacts_dir = root
        self.paths = {
            "account_state": Path(account_state_path) if account_state_path else root / "css_account_state_pcnrass.json",
            "session_state": Path(session_state_path) if session_state_path else root / "css_session_state_pcnrass.json",
            "supervisor_state": Path(supervisor_state_path) if supervisor_state_path else root.parent / "runtime" / "supervisor" / "css_runtime_supervisor_state.json",
            "closed_trade_ledger": Path(closed_trade_ledger_path) if closed_trade_ledger_path else root.parent / "audit_logs" / "closed_trades.jsonl",
            "portfolio_snapshot": root / "portfolio_snapshot.json",
            "runtime_portfolio_state": root / "runtime_portfolio_state.json",
            "runtime_advisory_snapshot": root / "runtime_advisory_snapshot.json",
            "portfolio_decision": root / "portfolio_decision.json",
            "validation_summary": root / "validation_summary.json",
        }
        self.stale_after_seconds = float(stale_after_seconds)

    def evaluate(
        self,
        *,
        runtime_active: bool | None = None,
        refresh: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now_dt = now or datetime.now(timezone.utc)
        active = self._runtime_active() if runtime_active is None else bool(runtime_active)
        artifacts: dict[str, dict[str, Any]] = {}
        stale_artifacts: list[str] = []
        refreshed_artifacts: list[str] = []
        warnings: list[str] = []
        blockers: list[str] = []

        for name, path in self.paths.items():
            artifact = self._artifact_state(name, path, now_dt, active)
            artifacts[name] = artifact
            status = artifact["freshness"]
            if status == "MISSING":
                if name in self.CRITICAL:
                    blockers.append(f"missing_{name}")
                else:
                    warnings.append(f"missing_{name}")
            elif status == "STALE":
                stale_artifacts.append(name)
                warning = self._stale_warning(name)
                warnings.append(warning)
                if name in {"session_state", "supervisor_state"}:
                    blockers.append(warning)
            elif status == "NO_RECENT_TRADES":
                warnings.append("no_recent_closed_trades")

            if refresh and active and artifact["exists"] and name in self.REFRESHABLE:
                try:
                    os.utime(path, None)
                    refreshed_artifacts.append(name)
                except OSError:
                    warnings.append(f"refresh_failed_{name}")

        material_warnings = [item for item in warnings if item != "no_recent_closed_trades"]
        if blockers:
            status = "RED"
        elif stale_artifacts or any(item.startswith("missing_") for item in material_warnings) or material_warnings:
            status = "AMBER"
        else:
            status = "GREEN"

        return {
            "freshness_status": status,
            "runtime_active": active,
            "artifacts": artifacts,
            "stale_artifacts": sorted(set(stale_artifacts)),
            "refreshed_artifacts": sorted(set(refreshed_artifacts)),
            "warnings": sorted(set(warnings)),
            "blockers": sorted(set(blockers)),
            "advisory_only": True,
            "execution_allowed": False,
        }

    def _artifact_state(self, name: str, path: Path, now: datetime, runtime_active: bool) -> dict[str, Any]:
        exists = path.exists()
        age = max(0.0, now.timestamp() - path.stat().st_mtime) if exists else None
        stale = age is None or age > self.stale_after_seconds
        freshness = "FRESH"
        if not exists:
            freshness = "MISSING"
        elif name == "closed_trade_ledger" and stale and runtime_active:
            freshness = "NO_RECENT_TRADES"
            stale = False
        elif stale:
            freshness = "STALE"
        return {
            "path": str(path),
            "exists": exists,
            "critical": name in self.CRITICAL,
            "optional": name in self.OPTIONAL,
            "age_seconds": round(age, 6) if age is not None else None,
            "stale_after_seconds": self.stale_after_seconds,
            "freshness": freshness,
            "stale": stale,
        }

    def _runtime_active(self) -> bool:
        supervisor = self._read_json(self.paths["supervisor_state"])
        status = str(supervisor.get("status", "")).upper() if isinstance(supervisor, Mapping) else ""
        if status in {"RUNNING", "ONLINE", "HEALTHY", "GREEN"}:
            return True
        session = self._read_json(self.paths["session_state"])
        payload = session.get("session", session) if isinstance(session, Mapping) else {}
        mode = str(payload.get("engine_mode", payload.get("runtime_mode", ""))).upper() if isinstance(payload, Mapping) else ""
        return mode == "PAPER"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists() or path.suffix.lower() == ".jsonl":
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _stale_warning(name: str) -> str:
        return {
            "account_state": "stale_account_state",
            "session_state": "stale_session_state",
            "supervisor_state": "stale_supervisor_state",
            "portfolio_snapshot": "stale_portfolio_snapshot",
            "runtime_portfolio_state": "stale_runtime_portfolio_state",
            "runtime_advisory_snapshot": "stale_runtime_advisory_snapshot",
            "portfolio_decision": "stale_portfolio_decision",
            "validation_summary": "stale_validation_summary",
            "closed_trade_ledger": "stale_closed_trade_ledger",
        }.get(name, f"stale_{name}")
