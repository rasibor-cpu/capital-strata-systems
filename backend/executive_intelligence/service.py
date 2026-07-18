"""Executive Intelligence Engine service — generate, validate, archive, retrieve."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.executive_intelligence.assembler import ExecutiveMorningBriefAssembler
from backend.executive_intelligence.archive import MorningBriefArchiveStore
from backend.executive_intelligence.constants import DEFAULT_ARCHIVE_RELATIVE, SAFETY_LOCKS
from backend.executive_intelligence.evidence import gather_evidence
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
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        if archive_root is None:
            archive_root = self.repo_root / DEFAULT_ARCHIVE_RELATIVE
        self.archive_root = Path(archive_root)
        self.assembler = ExecutiveMorningBriefAssembler()
        self.archive = MorningBriefArchiveStore(self.archive_root)
        self.retrieval = MorningBriefRetrieval(self.archive_root)

    def generate(
        self,
        *,
        evidence: Mapping[str, Any] | None = None,
        report_date: str | None = None,
        persist: bool = True,
        created_reason: str = "scheduled_cutover",
    ) -> dict[str, Any]:
        """
        Assemble, validate, and optionally persist the Daily Executive Brief.

        Returns a result envelope with brief, validation, and archive metadata.
        Never grants execution authority.
        """
        bundle = gather_evidence(self.repo_root, injected=evidence)
        # Enrich executive decision opportunity headlines after trading panel built inside assembler
        draft = self.assembler.assemble(bundle, report_date=report_date)
        trading = draft.get("panels", {}).get("trading_intelligence", {})
        if isinstance(trading, dict):
            headlines = []
            for opp in trading.get("ranked_opportunities") or []:
                if isinstance(opp, Mapping):
                    headlines.append(opp.get("title") or opp.get("symbol") or opp.get("id"))
            draft["panels"]["executive_decision"]["top_opportunities_headline"] = [h for h in headlines[:3] if h]

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
                **SAFETY_LOCKS,
            }

        archived = self.archive.publish(
            draft,
            validation,
            created_by="executive_intelligence_engine",
            created_reason=created_reason,
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
            **SAFETY_LOCKS,
        }
