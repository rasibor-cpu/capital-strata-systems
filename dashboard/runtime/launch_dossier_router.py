from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Header, Query

from backend.app.persistence.services.launch_dossier_export_service import (
    LaunchDossierExportService,
)
from dashboard.runtime.commercial_governance_router import token_store_session_resolver
from engine.commercial.commercial_authorization import (
    BearerSessionResolver,
    CommercialAuthorizer,
    actor_from_bearer,
)


def create_launch_dossier_router(
    *,
    session_resolver: BearerSessionResolver = token_store_session_resolver,
    authorizer: Optional[CommercialAuthorizer] = None,
) -> APIRouter:
    """Requires a bearer session with commercial view rights.

    Previously unauthenticated: exported full launch-dossier content for any
    guessed dossier_id.
    """
    router = APIRouter()
    authorizer_ = authorizer or CommercialAuthorizer()

    @router.get("/api/v1/launch-dossier/export")
    def read_launch_dossier(
        dossier_id: str = Query(...),
        authorization: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        actor_from_bearer(
            authorization, "commercial_view_obligations",
            session_resolver=session_resolver, authorizer=authorizer_,
        )
        return LaunchDossierExportService().export(dossier_id=dossier_id)

    return router
