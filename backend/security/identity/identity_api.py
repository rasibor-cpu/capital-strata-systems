"""Authenticated GET-only API for Enterprise Identity & Secrets metadata."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.security.security_api_auth import SecurityAPIAdminDependency
from backend.security.identity.enterprise_identity_service import EnterpriseIdentityService
from backend.security.identity.enterprise_secret_service import EnterpriseSecretService
from backend.security.identity.identity_certification import certify_identity_platform
from backend.security.identity.identity_models import EnterpriseIdentity, IdentityType
from backend.security.identity.identity_policy import SecretAccessRequest
from backend.security.identity.authority_certification import certify_secret_authority
from backend.security.identity.authority_redirector import EnterpriseAuthorityRedirector
from backend.security.identity.vault_health_score import calculate_vault_health_score


def create_identity_security_router(
    *,
    identities: EnterpriseIdentityService,
    secrets: EnterpriseSecretService,
    authority_redirector: EnterpriseAuthorityRedirector | None = None,
) -> Any:
    router = APIRouter(tags=["enterprise-identity-secrets"])
    require_admin = SecurityAPIAdminDependency("enterprise_identity_api")

    def authority_unavailable() -> JSONResponse:
        return JSONResponse(
            {
                "status": "UNAVAILABLE",
                "reason": "ENTERPRISE_AUTHORITY_REDIRECTOR_NOT_CONFIGURED",
                "execution_allowed": False,
            },
            status_code=503,
        )

    def request_identity(auth) -> EnterpriseIdentity:
        try:
            return identities.get(str(auth.user_id))
        except KeyError:
            return EnterpriseIdentity(
                identity_id=str(auth.user_id),
                display_name=str(auth.display_name or auth.user_id),
                identity_type=IdentityType.HUMAN,
                role=str(auth.role),
                owner=str(auth.user_id),
                environment="MISSION_CONTROL",
            )

    def access_request(auth, purpose: str) -> SecretAccessRequest:
        return SecretAccessRequest(
            identity=request_identity(auth),
            purpose=purpose,
            component="enterprise_identity_api",
            duration_seconds=60,
        )

    @router.get("/api/security/identity")
    def identity_inventory(auth=Depends(require_admin)):
        return {
            "identities": identities.inventory(),
            "request_identity": {"identity_id": auth.user_id, "role": auth.role},
            "execution_allowed": False,
        }

    @router.get("/api/security/secrets")
    def secret_inventory(auth=Depends(require_admin)):
        return {
            "secrets": secrets.inventory(
                request=access_request(auth, "READ_SECRET_INVENTORY")
            ),
            "plaintext_returned": False,
            "execution_allowed": False,
        }

    @router.get("/api/security/secrets/{secret_uuid}")
    def secret_detail(secret_uuid: str, auth=Depends(require_admin)):
        try:
            return secrets.retrieve(
                secret_uuid,
                request=access_request(auth, "READ_SECRET_METADATA"),
            )
        except KeyError:
            return JSONResponse(
                {"status": "NOT_FOUND", "execution_allowed": False},
                status_code=404,
            )

    @router.get("/api/security/rotation")
    def rotation(_auth=Depends(require_admin)):
        return secrets.rotation_status()

    @router.get("/api/security/certification")
    def certification(_auth=Depends(require_admin)):
        return certify_identity_platform(identities, secrets)

    @router.get("/api/security/risk")
    def risk(_auth=Depends(require_admin)):
        return secrets.risk_summary()

    @router.get("/api/security/authority")
    def authority(_auth=Depends(require_admin)):
        if authority_redirector is None:
            return authority_unavailable()
        return certify_secret_authority(authority_redirector)

    @router.get("/api/security/ownership")
    def ownership(_auth=Depends(require_admin)):
        if authority_redirector is None:
            return authority_unavailable()
        return {
            "ownership": authority_redirector.ownership_inventory(),
            "execution_allowed": False,
        }

    @router.get("/api/security/vault-health")
    def vault_health(_auth=Depends(require_admin)):
        if authority_redirector is None:
            return authority_unavailable()
        return calculate_vault_health_score(authority_redirector)

    @router.get("/api/security/migration")
    def migration(_auth=Depends(require_admin)):
        if authority_redirector is None:
            return authority_unavailable()
        return authority_redirector.migration_status()

    @router.get("/api/security/direct-access")
    def direct_access(_auth=Depends(require_admin)):
        if authority_redirector is None:
            return authority_unavailable()
        return {
            "violations": authority_redirector.direct_access_violations(),
            "execution_allowed": False,
        }

    return router


__all__ = ["create_identity_security_router"]
