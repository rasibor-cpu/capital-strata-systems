"""Authenticated GET-only Enterprise OAuth API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.security.security_api_auth import SecurityAPIAdminDependency
from backend.security.oauth.oauth_certification import (
    certify_oauth_manager,
    oauth_governance_payload,
)
from backend.security.oauth.oauth_manager import EnterpriseOAuthManager
from backend.security.oauth.oauth_reporting import build_oauth_report


def create_oauth_security_router(*, manager: EnterpriseOAuthManager) -> Any:
    router = APIRouter(tags=["enterprise-oauth"])
    require_admin = SecurityAPIAdminDependency("enterprise_oauth_api")

    @router.get("/api/security/oauth")
    def oauth_summary(_auth=Depends(require_admin)):
        return oauth_governance_payload(manager)

    @router.get("/api/security/oauth/providers")
    def provider_inventory(_auth=Depends(require_admin)):
        return {
            "providers": manager.registry.inventory(),
            "registration_only": True,
            "execution_allowed": False,
        }

    @router.get("/api/security/oauth/certification")
    def certification(_auth=Depends(require_admin)):
        return certify_oauth_manager(manager)

    @router.get("/api/security/oauth/report")
    def report(
        report_type: str = "oauth_certification",
        _auth=Depends(require_admin),
    ):
        try:
            return build_oauth_report(report_type, manager=manager)
        except KeyError:
            return JSONResponse(
                {"status": "NOT_FOUND", "execution_allowed": False},
                status_code=404,
            )

    @router.get("/api/security/oauth/risk")
    def risk(_auth=Depends(require_admin)):
        return manager.risk_summary()

    @router.get("/api/security/oauth/{provider}")
    def provider_detail(provider: str, _auth=Depends(require_admin)):
        try:
            return {
                "provider": manager.registry.get(provider).as_dict(),
                "registrations": manager.get_provider(provider),
                "execution_allowed": False,
            }
        except (KeyError, ValueError):
            return JSONResponse(
                {"status": "NOT_FOUND", "execution_allowed": False},
                status_code=404,
            )

    return router


__all__ = ["create_oauth_security_router"]
