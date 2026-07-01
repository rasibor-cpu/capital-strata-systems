from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Mapping


class PortfolioDecisionOrchestratorError(RuntimeError):
    """Fail-closed exception for portfolio decision orchestration."""


class PortfolioDecisionOrchestrator:
    """Canonical advisory package builder for portfolio-level decisions."""

    REQUIRED_INPUTS = {
        "portfolio_intelligence",
        "capital_rotation",
        "adaptive_portfolio",
        "strategy_attribution",
        "regime_allocation",
        "risk_committee",
        "quantitative_metrics",
        "market_regime_intelligence",
        "policy_profile",
        "recommendation_tracker",
    }

    def orchestrate(self, inputs: Mapping[str, Any] | None, timestamp: str | None = None) -> dict[str, Any]:
        if not isinstance(inputs, Mapping):
            return self._fail_closed(["inputs_unavailable"], timestamp=timestamp)

        missing = []
        for key in sorted(self.REQUIRED_INPUTS):
            payload = inputs.get(key)
            if not isinstance(payload, Mapping):
                missing.append(key)
            elif str(payload.get("status", "OK")).upper() == "DATA UNAVAILABLE":
                missing.append(key)

        adaptive = inputs.get("adaptive_portfolio", {}) if isinstance(inputs.get("adaptive_portfolio"), Mapping) else {}
        committee = inputs.get("risk_committee", {}) if isinstance(inputs.get("risk_committee"), Mapping) else {}
        policy = inputs.get("policy_profile", {}) if isinstance(inputs.get("policy_profile"), Mapping) else {}
        market_regime = inputs.get("market_regime_intelligence", {}) if isinstance(inputs.get("market_regime_intelligence"), Mapping) else {}
        quantitative = inputs.get("quantitative_metrics", {}) if isinstance(inputs.get("quantitative_metrics"), Mapping) else {}
        multi_factor = inputs.get("multi_factor_signal", {}) if isinstance(inputs.get("multi_factor_signal"), Mapping) else {}

        if missing:
            return self._fail_closed(missing, timestamp=timestamp, inputs=inputs)

        committee_status = str(committee.get("committee_status", "")).upper()
        adaptive_status = str(adaptive.get("risk_committee_status", "")).upper()
        recommendation = str(adaptive.get("adaptive_recommendation", "MAINTAIN")).upper()
        confidence = self._bounded(adaptive.get("confidence", committee.get("confidence", 50)), 0, 100)
        if committee_status == "RED" or adaptive_status == "RED":
            overall_status = "RED"
            recommendation = "PAUSE_NEW_TRADES"
            confidence = min(confidence, 30)
        elif committee_status == "AMBER" or adaptive_status == "AMBER":
            overall_status = "AMBER"
            confidence = min(confidence, 70)
        else:
            overall_status = "GREEN"

        explanation = [
            f"Adaptive recommendation is {recommendation}.",
            f"Risk committee status is {committee_status or 'UNKNOWN'}.",
            f"Policy profile is {policy.get('active_profile', 'UNKNOWN')}.",
            f"Market regime is {market_regime.get('detected_regime', 'UNKNOWN')}.",
        ]
        if multi_factor:
            explanation.append(
                "Multi-factor market intelligence is "
                f"{multi_factor.get('multi_factor_signal', 'DATA_UNAVAILABLE')} "
                f"with score {multi_factor.get('multi_factor_score', 'DATA UNAVAILABLE')}."
            )
        conflicts = inputs.get("conflicting_signals", [])
        conflicts = conflicts if isinstance(conflicts, list) else []

        package_timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        package = {
            "decision_id": self._decision_id(package_timestamp, inputs),
            "timestamp": package_timestamp,
            "overall_status": overall_status,
            "portfolio_recommendation": recommendation,
            "confidence": int(confidence),
            "policy_profile": policy.get("active_profile"),
            "market_regime": market_regime.get("detected_regime"),
            "portfolio_health": inputs.get("portfolio_intelligence", {}),
            "capital_rotation": inputs.get("capital_rotation", {}),
            "risk_committee": committee,
            "quantitative_summary": self._quantitative_summary(quantitative),
            "multi_factor_signal": multi_factor,
            "explanation": explanation,
            "conflicting_signals": sorted(set(str(item) for item in conflicts)),
            "missing_inputs": [],
            "advisory_only": True,
            "execution_allowed": False,
        }
        return package

    def _fail_closed(
        self,
        missing_inputs: list[str],
        timestamp: str | None = None,
        inputs: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        package_timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        package = {
            "decision_id": self._decision_id(package_timestamp, inputs or {"missing": missing_inputs}),
            "timestamp": package_timestamp,
            "overall_status": "RED",
            "portfolio_recommendation": "PAUSE_NEW_TRADES",
            "confidence": 25,
            "policy_profile": None,
            "market_regime": None,
            "portfolio_health": {},
            "capital_rotation": {},
            "risk_committee": {},
            "quantitative_summary": {},
            "explanation": ["Advisory package is incomplete; fail closed to PAUSE_NEW_TRADES."],
            "conflicting_signals": [],
            "missing_inputs": sorted(set(missing_inputs)),
            "advisory_only": True,
            "execution_allowed": False,
        }
        return package

    @staticmethod
    def _quantitative_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
        metrics = payload.get("metrics", {}) if isinstance(payload, Mapping) else {}
        metrics = metrics if isinstance(metrics, Mapping) else {}
        return {
            "rolling_sharpe": metrics.get("rolling_sharpe"),
            "rolling_sortino": metrics.get("rolling_sortino"),
            "max_drawdown": metrics.get("max_drawdown"),
            "volatility": metrics.get("volatility"),
            "sample_size": payload.get("sample_size") if isinstance(payload, Mapping) else None,
        }

    @staticmethod
    def _decision_id(timestamp: str, inputs: Mapping[str, Any]) -> str:
        payload = json.dumps({"timestamp": timestamp, "inputs": inputs}, sort_keys=True, default=str)
        return "pdecision-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _bounded(value: Any, low: int, high: int) -> int:
        try:
            numeric = int(round(float(value)))
        except (TypeError, ValueError):
            numeric = low
        return max(low, min(high, numeric))


class DecisionPackageStore:
    """Safe JSON persistence for advisory decision packages."""

    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        self.path = os.path.join(storage_dir, "portfolio_decision_packages.json")

    def append(self, package: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(package, Mapping):
            return {"status": "DATA UNAVAILABLE", "reason": "decision_package_malformed", "advisory_only": True}
        rows = self._read_rows()
        record = dict(package)
        rows.append(record)
        self._write_rows(rows)
        return {"status": "OK", "record": record, "count": len(rows), "advisory_only": True}

    def list_recent(self, limit: int = 10) -> dict[str, Any]:
        rows = self._read_rows()
        return {"status": "OK", "decisions": rows[-max(1, int(limit or 10)):], "count": len(rows), "advisory_only": True}

    def lookup(self, decision_id: str) -> dict[str, Any]:
        for row in self._read_rows():
            if str(row.get("decision_id")) == str(decision_id):
                return {"status": "OK", "decision": row, "advisory_only": True}
        return {"status": "DATA UNAVAILABLE", "reason": "decision_not_found", "advisory_only": True}

    def summary(self) -> dict[str, Any]:
        rows = self._read_rows()
        counts: dict[str, int] = {}
        for row in rows:
            status = str(row.get("overall_status", "UNKNOWN")).upper()
            counts[status] = counts.get(status, 0) + 1
        return {
            "status": "OK",
            "total_decisions": len(rows),
            "status_counts": {key: counts[key] for key in sorted(counts.keys())},
            "advisory_only": True,
        }

    def _read_rows(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, list):
                return []
            return [row for row in payload if isinstance(row, dict)]
        except Exception:
            return []

    def _write_rows(self, rows: list[dict[str, Any]]) -> None:
        os.makedirs(self.storage_dir, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=2, sort_keys=True)
