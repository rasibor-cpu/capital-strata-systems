"""Executive Brief readiness evaluation — WAIT before fail-closed generation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from backend.executive_intelligence.constants import SAFETY_LOCKS
from backend.executive_intelligence.evidence import gather_evidence
from backend.executive_intelligence.freshness_policy import GATE_IDS, gate_config, load_freshness_policy
from backend.executive_intelligence.utils import as_mapping, normalize_freshness, utc_now_iso


GateStatus = str  # READY | STALE | UNAVAILABLE | ERROR
OverallStatus = str  # READY | WAITING | FAILED


class ExecutiveBriefReadinessEvaluator:
    """Evaluate whether required DEB evidence is fresh enough to generate."""

    def __init__(
        self,
        *,
        repo_root: Path | str | None = None,
        policy: Mapping[str, Any] | None = None,
        policy_path: Path | str | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        self.policy = dict(policy) if policy else load_freshness_policy(policy_path=policy_path)
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    def evaluate(self, *, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        bundle = gather_evidence(self.repo_root, injected=evidence)
        now = self._now_fn()
        gates: dict[str, Any] = {}
        for gate_id in GATE_IDS:
            gates[gate_id] = self._evaluate_gate(gate_id, bundle, now=now)

        overall, reason = self._overall(gates)
        waiting_for = [
            self._waiting_label(gid)
            for gid, g in gates.items()
            if g.get("status") in {"STALE", "UNAVAILABLE", "ERROR"} and gate_config(self.policy, gid).get("required", True)
        ]
        return {
            "schema_version": "css.executive_brief_readiness.v1",
            "status": overall,
            "reason": reason,
            "evaluated_at_utc": utc_now_iso(),
            "gates": gates,
            "waiting_for": waiting_for,
            "waiting_labels": waiting_for,
            "policy": {
                "retry_interval_seconds": int(self.policy.get("retry_interval_seconds") or 60),
                "max_wait_seconds": int(self.policy.get("max_wait_seconds") or 1800),
                "advisory_only": bool(self.policy.get("advisory_only", SAFETY_LOCKS.get("advisory_only"))),
            },
            **SAFETY_LOCKS,
        }

    def _evaluate_gate(self, gate_id: str, evidence: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
        cfg = gate_config(self.policy, gate_id)
        max_age = float(cfg.get("max_age_seconds") or 0)
        advisory = bool(self.policy.get("advisory_only", SAFETY_LOCKS.get("advisory_only")))
        try:
            if gate_id == "runtime_snapshot":
                return self._gate_runtime(evidence, max_age=max_age, cfg=cfg, advisory=advisory, now=now)
            if gate_id == "system_heartbeat":
                return self._gate_heartbeat(evidence, max_age=max_age, cfg=cfg, advisory=advisory, now=now)
            if gate_id == "broker_snapshot":
                return self._gate_broker(evidence, max_age=max_age, cfg=cfg, advisory=advisory, now=now)
            if gate_id == "portfolio_snapshot":
                return self._gate_portfolio(evidence, max_age=max_age, cfg=cfg, advisory=advisory, now=now)
            if gate_id == "market_snapshot":
                return self._gate_market(evidence, max_age=max_age, cfg=cfg, advisory=advisory, now=now)
            if gate_id == "executive_kpi_snapshot":
                return self._gate_kpi(evidence, max_age=max_age, cfg=cfg, advisory=advisory, now=now)
            if gate_id == "risk_snapshot":
                return self._gate_mapping(
                    evidence.get("risk"),
                    max_age=max_age,
                    cfg=cfg,
                    advisory=advisory,
                    now=now,
                    paths=(
                        self.repo_root / "artifacts" / "risk_snapshot.json",
                        self.repo_root / "artifacts" / "runtime_risk_state.json",
                    ),
                    label="risk",
                )
            if gate_id == "learning_snapshot":
                return self._gate_mapping(
                    evidence.get("learning"),
                    max_age=max_age,
                    cfg=cfg,
                    advisory=advisory,
                    now=now,
                    paths=(
                        self.repo_root / "artifacts" / "learning_snapshot.json",
                        self.repo_root / "artifacts" / "learning_state.json",
                    ),
                    label="learning",
                )
            return self._result("ERROR", freshness="UNAVAILABLE", reason=f"unknown_gate:{gate_id}", age=None)
        except Exception as exc:
            return self._result("ERROR", freshness="UNAVAILABLE", reason=f"gate_error:{exc}", age=None)

    def _gate_runtime(
        self, evidence: Mapping[str, Any], *, max_age: float, cfg: dict[str, Any], advisory: bool, now: datetime
    ) -> dict[str, Any]:
        runtime = as_mapping(evidence.get("runtime_health"))
        if not runtime:
            return self._absent("runtime", cfg=cfg, advisory=advisory)
        age = self._as_float(runtime.get("heartbeat_age_seconds"))
        freshness = normalize_freshness(runtime.get("freshness"))
        if age is None:
            age = self._age_from_paths(
                now,
                self.repo_root / "runtime" / "supervisor" / "css_runtime_supervisor_state.json",
            )
        return self._from_age_and_freshness(
            age, freshness, max_age=max_age, cfg=cfg, advisory=advisory, label="runtime"
        )

    def _gate_heartbeat(
        self, evidence: Mapping[str, Any], *, max_age: float, cfg: dict[str, Any], advisory: bool, now: datetime | None = None
    ) -> dict[str, Any]:
        runtime = as_mapping(evidence.get("runtime_health"))
        if not runtime:
            return self._absent("heartbeat", cfg=cfg, advisory=advisory)
        age = self._as_float(runtime.get("heartbeat_age_seconds"))
        if age is None:
            age = self._age_from_paths(
                now or self._now_fn(),
                self.repo_root / "runtime" / "supervisor" / "css_runtime_supervisor_state.json",
            )
        if age is None:
            return self._result("UNAVAILABLE", freshness="UNAVAILABLE", reason="heartbeat_age_unknown", age=None)
        if age <= max_age:
            return self._result("READY", freshness="FRESH" if age <= max_age / 2 else "AGING", reason="heartbeat_ok", age=age)
        return self._result("STALE", freshness="STALE", reason="heartbeat_stale", age=age)

    def _gate_broker(
        self, evidence: Mapping[str, Any], *, max_age: float, cfg: dict[str, Any], advisory: bool, now: datetime
    ) -> dict[str, Any]:
        broker = as_mapping(evidence.get("broker_health"))
        # Broker unavailable must never become READY (even in advisory mode).
        if not broker:
            return self._result(
                "UNAVAILABLE",
                freshness="UNAVAILABLE",
                reason="broker_unavailable",
                age=None,
            )
        freshness = normalize_freshness(broker.get("freshness"))
        age = self._age_from_paths(
            now,
            self.repo_root / "artifacts" / "css_account_state_pcnrass.json",
            self.repo_root / "artifacts" / "css_session_state_pcnrass.json",
        )
        if freshness in {"STALE", "UNAVAILABLE"}:
            status = "UNAVAILABLE" if freshness == "UNAVAILABLE" else "STALE"
            return self._result(status, freshness=freshness, reason="broker_stale_or_unavailable", age=age)
        if age is not None and age > max_age:
            return self._result("STALE", freshness="STALE", reason="broker_age_exceeded", age=age)
        return self._result("READY", freshness=freshness or "FRESH", reason="broker_ok", age=age)

    def _gate_portfolio(
        self, evidence: Mapping[str, Any], *, max_age: float, cfg: dict[str, Any], advisory: bool, now: datetime
    ) -> dict[str, Any]:
        portfolio = as_mapping(evidence.get("portfolio"))
        if not portfolio:
            return self._absent("portfolio", cfg=cfg, advisory=advisory)
        freshness = normalize_freshness(portfolio.get("freshness"))
        age = self._age_from_paths(
            now,
            self.repo_root / "artifacts" / "runtime_portfolio_state.json",
            self.repo_root / "artifacts" / "portfolio_snapshot.json",
        )
        return self._from_age_and_freshness(
            age, freshness, max_age=max_age, cfg=cfg, advisory=advisory, label="portfolio"
        )

    def _gate_market(
        self, evidence: Mapping[str, Any], *, max_age: float, cfg: dict[str, Any], advisory: bool, now: datetime
    ) -> dict[str, Any]:
        market = as_mapping(evidence.get("market"))
        if not market:
            return self._absent("market", cfg=cfg, advisory=advisory)
        freshness = normalize_freshness(market.get("freshness"))
        if str(market.get("market_data_status") or "").upper() == "UNAVAILABLE":
            return self._result("UNAVAILABLE", freshness="UNAVAILABLE", reason="market_panel_unavailable", age=None)
        age = None
        generated = market.get("generated_at_utc") or as_mapping(market.get("overnight_full")).get("generated_at_utc")
        if generated:
            age = self._age_from_iso(generated, now=now)
        if age is None:
            age = self._age_from_paths(
                now,
                self.repo_root / "artifacts" / "overnight_market_intelligence.json",
                self.repo_root / "artifacts" / "runtime_advisory_snapshot.json",
            )
        return self._from_age_and_freshness(
            age, freshness, max_age=max_age, cfg=cfg, advisory=advisory, label="market"
        )

    def _gate_kpi(
        self, evidence: Mapping[str, Any], *, max_age: float, cfg: dict[str, Any], advisory: bool, now: datetime
    ) -> dict[str, Any]:
        committee = as_mapping(evidence.get("committee"))
        portfolio = as_mapping(evidence.get("portfolio"))
        if not committee and not portfolio:
            return self._absent("executive_kpi", cfg=cfg, advisory=advisory)
        age = self._age_from_paths(
            now,
            self.repo_root / "artifacts" / "portfolio_decision.json",
            self.repo_root / "artifacts" / "runtime_portfolio_state.json",
        )
        freshness = normalize_freshness(
            committee.get("freshness") or portfolio.get("freshness") or ("FRESH" if age is not None and age <= max_age else "AGING")
        )
        return self._from_age_and_freshness(
            age, freshness, max_age=max_age, cfg=cfg, advisory=advisory, label="executive_kpi"
        )

    def _gate_mapping(
        self,
        payload: Any,
        *,
        max_age: float,
        cfg: dict[str, Any],
        advisory: bool,
        now: datetime,
        paths: tuple[Path, ...],
        label: str,
    ) -> dict[str, Any]:
        data = as_mapping(payload)
        path_age = self._age_from_paths(now, *paths)
        if not data and path_age is None:
            return self._absent(label, cfg=cfg, advisory=advisory)
        if not data and path_age is not None:
            # File exists but evidence loader returned empty — still use mtime.
            data = {"freshness": "AGING"}
        freshness = normalize_freshness(data.get("freshness", "AGING"))
        return self._from_age_and_freshness(
            path_age, freshness, max_age=max_age, cfg=cfg, advisory=advisory, label=label
        )

    def _from_age_and_freshness(
        self,
        age: float | None,
        freshness: str,
        *,
        max_age: float,
        cfg: dict[str, Any],
        advisory: bool,
        label: str,
    ) -> dict[str, Any]:
        freshness = normalize_freshness(freshness)
        if freshness == "UNAVAILABLE":
            return self._result("UNAVAILABLE", freshness=freshness, reason=f"{label}_unavailable", age=age)
        if freshness == "STALE" or (age is not None and age > max_age):
            return self._result("STALE", freshness="STALE", reason=f"{label}_stale", age=age)
        return self._result("READY", freshness=freshness or "FRESH", reason=f"{label}_ok", age=age)

    def _absent(self, label: str, *, cfg: dict[str, Any], advisory: bool) -> dict[str, Any]:
        if advisory and cfg.get("allow_absent_when_advisory"):
            return self._result(
                "READY",
                freshness="UNAVAILABLE",
                reason=f"{label}_absent_advisory_permitted",
                age=None,
            )
        return self._result("UNAVAILABLE", freshness="UNAVAILABLE", reason=f"{label}_unavailable", age=None)

    def _overall(self, gates: Mapping[str, Any]) -> tuple[str, str]:
        blocking: list[str] = []
        errors: list[str] = []
        for gate_id, gate in gates.items():
            cfg = gate_config(self.policy, gate_id)
            if not cfg.get("required", True):
                continue
            status = str(gate.get("status") or "UNAVAILABLE")
            if status == "READY":
                continue
            if status == "ERROR":
                errors.append(gate_id)
            else:
                blocking.append(gate_id)
            # Hard rule: broker unavailable never READY (already enforced per-gate).
            if gate_id == "broker_snapshot" and status in {"UNAVAILABLE", "STALE", "ERROR"}:
                blocking.append("broker_not_ready")
        if errors and not blocking:
            return "FAILED", "gate_error:" + ",".join(sorted(set(errors)))
        if blocking:
            return "WAITING", "waiting_for:" + ",".join(sorted(set(blocking)))
        return "READY", "all_required_gates_ready"

    @staticmethod
    def _waiting_label(gate_id: str) -> str:
        labels = {
            "runtime_snapshot": "Waiting for Runtime",
            "executive_kpi_snapshot": "Waiting for Executive KPI",
            "portfolio_snapshot": "Waiting for Portfolio",
            "risk_snapshot": "Waiting for Risk",
            "market_snapshot": "Waiting for Market",
            "learning_snapshot": "Waiting for Learning",
            "broker_snapshot": "Waiting for Broker",
            "system_heartbeat": "Waiting for Heartbeat",
        }
        return labels.get(gate_id, f"Waiting for {gate_id}")

    @staticmethod
    def _result(status: str, *, freshness: str, reason: str, age: float | None) -> dict[str, Any]:
        return {
            "status": status,
            "freshness": normalize_freshness(freshness),
            "reason": reason,
            "age_seconds": age,
            "timestamp": utc_now_iso(),
        }

    @staticmethod
    def _as_float(value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _age_from_paths(self, now: datetime, *paths: Path) -> float | None:
        ages: list[float] = []
        for path in paths:
            try:
                if path.is_file():
                    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                    ages.append(max(0.0, (now - mtime).total_seconds()))
            except OSError:
                continue
        return min(ages) if ages else None

    def _age_from_iso(self, value: Any, *, now: datetime) -> float | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(0.0, (now - parsed.astimezone(timezone.utc)).total_seconds())
        except ValueError:
            return None


def format_wait_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    if minutes <= 0:
        return f"{secs}s"
    return f"{minutes}m {secs}s"


def readiness_audit_phrase(*, attempts: int, waited_seconds: float, status: str) -> str:
    if status == "READY" and attempts <= 1 and waited_seconds < 1:
        return "Generated immediately"
    if status == "READY":
        return f"Readiness achieved after: {max(0, attempts - 1)} retries · Generated after waiting: {format_wait_duration(waited_seconds)}"
    return f"Readiness not achieved after: {attempts} attempts · waited {format_wait_duration(waited_seconds)}"


def persist_readiness_session(archive_root: Path, session: Mapping[str, Any]) -> Path:
    """Persist orchestrator retry history under morning_briefings/readiness/."""
    root = Path(archive_root)
    dest_dir = root / "readiness"
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "latest_session.json"
    payload = dict(session)
    payload["updated_at_utc"] = utc_now_iso()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)
    history = dest_dir / "sessions.jsonl"
    with history.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": utc_now_iso(), **{k: payload.get(k) for k in ("status", "attempt", "report_date", "reason")}}, default=str) + "\n")
    return path


__all__ = [
    "ExecutiveBriefReadinessEvaluator",
    "format_wait_duration",
    "persist_readiness_session",
    "readiness_audit_phrase",
]
