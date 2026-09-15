from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from backend.app.persistence.services.launch_dossier_export_service import (
    LaunchDossierExportService,
)


def create_launch_dossier_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/launch-dossier/export")
    def read_launch_dossier(
        dossier_id: str = Query(...),
    ) -> dict[str, Any]:
        return LaunchDossierExportService().export(dossier_id=dossier_id)

    return router
