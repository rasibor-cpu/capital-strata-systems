"""HTTP API for trading profiles (mounted on the mobile app).

Every endpoint needs an authenticated user. The user identity always comes from the
server-side session, never from the request body, so a user can only change their
own profile and mandates. No endpoint can place an order or enable live trading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from backend.trading_profiles.mandates import MandateError
from backend.trading_profiles.preferences import PreferencesError
from backend.trading_profiles.service import TradingProfileService

UserResolver = Callable[[Request], Mapping[str, Any] | None]
PREFIX = "/api/v1/trading-profiles"


def _error(status: int, reason: str) -> JSONResponse:
    return JSONResponse({"ok": False, "reason": reason}, status_code=status)


def create_trading_profiles_router(
    *,
    user_resolver: UserResolver,
    service_factory: Callable[[], TradingProfileService],
) -> APIRouter:
    router = APIRouter(tags=["trading-profiles"])

    def _identity(request: Request) -> tuple[str, str] | None:
        try:
            ident = user_resolver(request) or {}
        except Exception:
            return None
        user_id, session_id = str(ident.get("user_id") or ""), str(ident.get("session_id") or "")
        return (user_id, session_id) if user_id and session_id else None

    def _guard(request: Request, action: Callable[[TradingProfileService, str, str], Any]) -> Any:
        ident = _identity(request)
        if ident is None:
            return _error(401, "authentication_required")
        try:
            result = action(service_factory(), *ident)
        except (PreferencesError, MandateError, ValueError) as exc:
            reason = str(exc)
            status = 503 if "signing_key" in reason else 400
            return _error(status, reason)
        return {"ok": True, **(result if isinstance(result, dict) else {"result": result})}

    @router.get(PREFIX + "/catalog")
    def catalog(request: Request) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.catalog())

    @router.get(PREFIX + "/me")
    def me(request: Request) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.startup_state(uid, session_id=sid))

    @router.post(PREFIX + "/mode")
    def select_mode(request: Request, payload: dict = Body(...)) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.preferences.select_operating_mode(uid, payload.get("mode")).to_record())

    @router.post(PREFIX + "/personality")
    def select_personality(request: Request, payload: dict = Body(...)) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.preferences.select_risk_personality(uid, payload.get("personality")).to_record())

    @router.post(PREFIX + "/disclosure/acknowledge")
    def acknowledge(request: Request, payload: dict = Body(...)) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.preferences.acknowledge_disclosure(uid, str(payload.get("version") or "")).to_record())

    @router.post(PREFIX + "/mandates")
    def authorize(request: Request, payload: dict = Body(...)) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.authorize_trader(
            uid, trader_id=str(payload.get("trader_id") or ""), asset_classes=list(payload.get("asset_classes") or []),
            max_allocation=float(payload.get("max_allocation") or 0), currency=str(payload.get("currency") or "CAD"),
            valid_days=float(payload.get("valid_days") or 0),
            reauthorization_policy=str(payload.get("reauthorization_policy") or "EACH_SIGN_ON"),
            reauthorization_interval_hours=float(payload.get("reauthorization_interval_hours") or 0), session_id=sid))

    @router.post(PREFIX + "/mandates/{mandate_id}/reauthorize")
    def reauthorize(request: Request, mandate_id: str) -> Any:
        return _guard(request, lambda svc, uid, sid: {"expires_at_utc": svc.mandates.reauthorize(
            mandate_id, follower_user_id=uid, session_id=sid, now=datetime.now(timezone.utc)).expires_at_utc})

    @router.post(PREFIX + "/mandates/{mandate_id}/revoke")
    def revoke(request: Request, mandate_id: str, payload: dict = Body(default={})) -> Any:
        return _guard(request, lambda svc, uid, sid: {"revoked_at_utc": svc.mandates.revoke(
            mandate_id, follower_user_id=uid, reason=str(payload.get("reason") or "user_revoked"),
            now=datetime.now(timezone.utc)).revoked_at_utc})

    @router.get(PREFIX + "/statement")
    def statement(request: Request) -> Any:
        return _guard(request, lambda svc, uid, sid: svc.statement(uid))

    return router
