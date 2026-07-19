"""Executive Intelligence Engine service — generate, validate, archive, retrieve."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.executive_intelligence.assembler import ExecutiveMorningBriefAssembler
from backend.executive_intelligence.archive import MorningBriefArchiveStore
from backend.executive_intelligence.constants import DEFAULT_ARCHIVE_RELATIVE, SAFETY_LOCKS
from backend.executive_intelligence.evidence import gather_evidence
from backend.executive_intelligence.orchestrator import ExecutiveBriefReadinessOrchestrator
from backend.executive_intelligence.readiness import ExecutiveBriefReadinessEvaluator
from backend.executive_intelligence.retrieval import MorningBriefRetrieval
from backend.executive_intelligence.sanitizer import sanitize_payload
from backend.executive_intelligence.validator import validate_brief_for_final


class ExecutiveIntelligenceEngine:
    """Canonical producer of the CSS Daily Executive Brief."""

    def __init__(
        self,
        *,
        repo_root: Path | str | None = None,
        archive_root: Path | str | None = None,
        freshness_policy: Mapping[str, Any] | None = None,
        freshness_policy_path: Path | str | None = None,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        if archive_root is None:
            archive_root = self.repo_root / DEFAULT_ARCHIVE_RELATIVE
        self.archive_root = Path(archive_root)
        self.assembler = ExecutiveMorningBriefAssembler()
        self.archive = MorningBriefArchiveStore(self.archive_root)
        self.retrieval = MorningBriefRetrieval(self.archive_root)
        self.freshness_policy = dict(freshness_policy) if freshness_policy else None
        self.freshness_policy_path = freshness_policy_path

    def readiness(self, *, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Evaluate Executive Brief evidence freshness without generating."""
        evaluator = ExecutiveBriefReadinessEvaluator(
            repo_root=self.repo_root,
            policy=self.freshness_policy,
            policy_path=self.freshness_policy_path,
        )
        return evaluator.evaluate(evidence=evidence)

    def generate(
        self,
        *,
        evidence: Mapping[str, Any] | None = None,
        report_date: str | None = None,
        persist: bool = True,
        created_reason: str = "scheduled_cutover",
        wait_for_readiness: bool | None = None,
        readiness: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Assemble, validate, and optionally persist the Daily Executive Brief.

        Production (disk evidence) waits for readiness by default. Explicit
        injected evidence (tests/controlled runs) skips the wait loop unless
        ``wait_for_readiness=True`` is forced. Fail-closed validation is unchanged.
        """
        if wait_for_readiness is None:
            wait_for_readiness = evidence is None
        if wait_for_readiness and readiness is None:
            orchestrator = ExecutiveBriefReadinessOrchestrator(
                repo_root=self.repo_root,
                archive_root=self.archive_root,
                policy=self.freshness_policy,
                policy_path=self.freshness_policy_path,
            )
            return orchestrator.run(
                evidence=evidence,
                report_date=report_date,
                wait=True,
                persist=persist,
                created_reason=created_reason,
                generate_fn=self._generate_once,
            )
        return self._generate_once(
            evidence=evidence,
            report_date=report_date,
            persist=persist,
            created_reason=created_reason,
            readiness=readiness,
        )

    def _generate_once(
        self,
        *,
        evidence: Mapping[str, Any] | None = None,
        report_date: str | None = None,
        persist: bool = True,
        created_reason: str = "scheduled_cutover",
        readiness: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Single-shot assemble → validate → archive (no readiness wait loop)."""
        bundle = gather_evidence(self.repo_root, injected=evidence)
        draft = self.assembler.assemble(bundle, report_date=report_date)
        trading = draft.get("panels", {}).get("trading_intelligence", {})
        if isinstance(trading, dict):
            headlines = []
            for opp in trading.get("ranked_opportunities") or []:
                if isinstance(opp, Mapping):
                    headlines.append(opp.get("title") or opp.get("symbol") or opp.get("id"))
            draft["panels"]["executive_decision"]["top_opportunities_headline"] = [
                h for h in headlines[:3] if h
            ]

        if readiness:
            draft["readiness_orchestration"] = dict(readiness)
            draft["readiness_audit"] = readiness.get("audit_phrase")

        draft = sanitize_payload(draft)
        validation = validate_brief_for_final(draft, evidence=bundle)
        draft["validation"] = validation
        draft["validation_status"] = validation.get("validation_status")

        if not persist:
            draft["report_status"] = "DRAFT" if validation.get("finalization_allowed") else "FAILED"
            return {
                "brief": draft,
                "validation": validation,
                "archive": None,
                "readiness": readiness,
                **SAFETY_LOCKS,
            }

        archived = self.archive.publish(
            draft,
            validation,
            created_by="executive_intelligence_engine",
            created_reason=created_reason,
            readiness=readiness,
        )
        return {
            "brief": archived.get("brief") or draft,
            "validation": validation,
            "archive": {
                "status": archived.get("status"),
                "version": archived.get("version"),
                "path": archived.get("path"),
                "report_id": archived.get("report_id"),
                "report_hash": archived.get("report_hash"),
                "blockers": archived.get("blockers"),
            },
            "readiness": readiness,
            **SAFETY_LOCKS,
        }
