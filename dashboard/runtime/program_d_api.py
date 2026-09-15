from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from backend.operations import (
    AtlasKnowledgeEntry,
    ExecutiveCommandInput,
    build_executive_command_snapshot,
    build_program_d_projection,
    build_project_atlas_index,
)


def build_program_d_api_payload() -> dict[str, Any]:
    """Return an empty-safe, read-only enterprise-operations projection.

    Runtime integrations may replace normalized upstream status values later;
    this endpoint does not reach brokers or mutate operational state.
    """

    snapshot = build_executive_command_snapshot(
        ExecutiveCommandInput(
            observed_at_utc=datetime.now(timezone.utc),
            runtime_health="UNKNOWN",
            broker_health="UNKNOWN",
            data_freshness="UNKNOWN",
            governance_status="PASS",
            security_status="PASS",
            reconciliation_status="UNKNOWN",
            backup_status="UNKNOWN",
            recovery_status="UNKNOWN",
            capacity_status="UNKNOWN",
        )
    )

    atlas = build_project_atlas_index(
        [
            AtlasKnowledgeEntry("OPS-001", "Startup Runbook", "OPERATIONS", "docs/operations/CSS_STARTUP_RUNBOOK.md"),
            AtlasKnowledgeEntry("OPS-002", "Emergency Shutdown Runbook", "OPERATIONS", "docs/operations/CSS_EMERGENCY_SHUTDOWN_RUNBOOK.md"),
            AtlasKnowledgeEntry("SEC-001", "Security Architecture", "SECURITY", "docs/security/CSS_SECURITY_ARCHITECTURE.md"),
            AtlasKnowledgeEntry("GOV-001", "Governance Authority Register", "GOVERNANCE", "docs/governance/PHASE_106C_GOVERNANCE_AUTHORITY_REGISTER.md"),
            AtlasKnowledgeEntry("CERT-001", "Certification Package Index", "CERTIFICATION", "certification/CERTIFICATION_PACKAGE_INDEX.md"),
        ]
    )
    return build_program_d_projection(snapshot, project_atlas=atlas)


def create_program_d_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/program-d/executive-command")
    def read_program_d_executive_command() -> dict[str, Any]:
        return build_program_d_api_payload()

    return router


__all__ = ["build_program_d_api_payload", "create_program_d_router"]
