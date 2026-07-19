"""Executive Brief readiness orchestrator — wait/retry before generation."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from backend.executive_intelligence.constants import DEFAULT_ARCHIVE_RELATIVE, SAFETY_LOCKS
from backend.executive_intelligence.freshness_policy import load_freshness_policy
from backend.executive_intelligence.readiness import (
    ExecutiveBriefReadinessEvaluator,
    persist_readiness_session,
    readiness_audit_phrase,
)
from backend.executive_intelligence.utils import utc_now_iso


class ExecutiveBriefReadinessOrchestrator:
    """
    Sequence: evaluate → READY generate | WAITING retry | FAILED archive fail-closed.

    Does not fabricate evidence or bypass fail-closed validation.
    """

    def __init__(
        self,
        *,
        repo_root: Path | str | None = None,
        archive_root: Path | str | None = None,
        policy: Mapping[str, Any] | None = None,
        policy_path: Path | str | None = None,
        sleep_fn: Callable[[float], None] | None = None,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        if archive_root is None:
            archive_root = self.repo_root / DEFAULT_ARCHIVE_RELATIVE
        self.archive_root = Path(archive_root)
        self.policy = dict(policy) if policy else load_freshness_policy(policy_path=policy_path)
        self.evaluator = ExecutiveBriefReadinessEvaluator(
            repo_root=self.repo_root,
            policy=self.policy,
            policy_path=policy_path,
        )
        self._sleep = sleep_fn or time.sleep
        self._time = time_fn or time.monotonic

    def run(
        self,
        *,
        evidence: Mapping[str, Any] | None = None,
        report_date: str | None = None,
        wait: bool = True,
        generate_fn: Callable[..., dict[str, Any]] | None = None,
        persist: bool = True,
        created_reason: str = "scheduled_cutover",
    ) -> dict[str, Any]:
        """
        Wait until READY (or timeout → FAILED), then call generate_fn.

        ``generate_fn`` should be ExecutiveIntelligenceEngine.generate_once (no wait).
        """
        if generate_fn is None:
            raise ValueError("generate_fn_required")

        retry_interval = float(self.policy.get("retry_interval_seconds") or 60)
        max_wait = float(self.policy.get("max_wait_seconds") or 1800)
        started = self._time()
        attempts: list[dict[str, Any]] = []
        attempt = 0
        last: dict[str, Any] = {}

        while True:
            attempt += 1
            evaluation = self.evaluator.evaluate(evidence=evidence)
            elapsed = self._time() - started
            next_retry = None
            status = str(evaluation.get("status") or "FAILED")

            if status == "WAITING" and wait and elapsed + 0.001 < max_wait:
                next_retry = utc_now_iso()
                remaining = max(0.0, max_wait - elapsed)
                sleep_for = min(retry_interval, remaining)
            else:
                sleep_for = 0.0

            record = {
                "attempt": attempt,
                "status": status,
                "reason": evaluation.get("reason"),
                "gates": evaluation.get("gates"),
                "waiting_for": evaluation.get("waiting_for"),
                "elapsed_seconds": round(elapsed, 3),
                "next_retry_interval_seconds": sleep_for if sleep_for > 0 else None,
                "evaluated_at_utc": evaluation.get("evaluated_at_utc"),
            }
            attempts.append(record)
            last = evaluation

            session = {
                "report_date": report_date,
                "status": status,
                "attempt": attempt,
                "reason": evaluation.get("reason"),
                "waiting_for": evaluation.get("waiting_for"),
                "attempts": attempts,
                "policy": evaluation.get("policy"),
                "elapsed_seconds": round(elapsed, 3),
                "max_wait_seconds": max_wait,
                "retry_interval_seconds": retry_interval,
                **SAFETY_LOCKS,
            }
            persist_readiness_session(self.archive_root, session)

            if status == "READY":
                break
            if status == "FAILED":
                break
            if not wait:
                break
            if elapsed >= max_wait:
                # Timeout: treat as FAILED for orchestration (generation still fail-closed).
                last = {
                    **evaluation,
                    "status": "FAILED",
                    "reason": f"readiness_timeout_after_{int(elapsed)}s",
                    "timeout": True,
                }
                session["status"] = "FAILED"
                session["reason"] = last["reason"]
                persist_readiness_session(self.archive_root, session)
                break
            if sleep_for > 0:
                self._sleep(sleep_for)
            else:
                break

        waited = self._time() - started
        final_status = str(last.get("status") or "FAILED")
        audit = readiness_audit_phrase(
            attempts=attempt,
            waited_seconds=waited,
            status="READY" if final_status == "READY" else "FAILED",
        )

        readiness_meta = {
            "orchestration_status": final_status,
            "attempts": attempt,
            "retries": max(0, attempt - 1),
            "waited_seconds": round(waited, 3),
            "audit_phrase": audit,
            "waiting_for": last.get("waiting_for") or [],
            "gates": last.get("gates") or {},
            "reason": last.get("reason"),
            "history": attempts,
            "evaluated_at_utc": last.get("evaluated_at_utc"),
            **SAFETY_LOCKS,
        }

        if final_status != "READY":
            # Still run generation so fail-closed validation archives a FAILED brief.
            result = generate_fn(
                evidence=evidence,
                report_date=report_date,
                persist=persist,
                created_reason=created_reason,
                readiness=readiness_meta,
            )
            result = dict(result)
            result["ready"] = False
            result["status"] = "FAILED"
            result["readiness"] = readiness_meta
            result["evaluation"] = last
            return result

        result = generate_fn(
            evidence=evidence,
            report_date=report_date,
            persist=persist,
            created_reason=created_reason,
            readiness=readiness_meta,
        )
        result = dict(result)
        result["ready"] = True
        result["status"] = "OK"
        result["readiness"] = readiness_meta
        return result


__all__ = ["ExecutiveBriefReadinessOrchestrator"]
