"""CSS Trader Passport API (Issue #102).

Every endpoint except /passport/schema requires a valid CSS bearer session from the existing auth token store
(backend.app.auth.token_store). Fail closed: no session, no data. Nothing here can change runtime mode, broker
settings, execution authority or any governance gate.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.auth.token_store import token_store

from .engine import OnboardingError
from .schema import public_schema
from .service import OnboardingService

log = logging.getLogger("css.onboarding.router")
UI_DIR = Path(__file__).resolve().parents[3] / "frontend" / "trader_passport"


class StageAnswers(BaseModel):
    stage_id: str = Field(min_length=1, max_length=64)
    answers: Dict[str, Any] = Field(default_factory=dict)


class ProfileUpdate(BaseModel):
    answers: Dict[str, Any]


def _user(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or len(authorization.split()) != 2 or authorization.split()[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in to CSS to continue.")
    info = token_store.validate(authorization.split()[1])
    if info is None:
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.")
    return info.username


def _errors(e: OnboardingError) -> HTTPException:
    return HTTPException(status_code=422, detail={"errors": e.errors})


def create_onboarding_router(service: Optional[OnboardingService] = None) -> APIRouter:
    svc = service or OnboardingService()
    r = APIRouter(prefix="/passport", tags=["trader-passport"])

    @r.get("/schema")
    def schema() -> dict:
        return public_schema()

    @r.get("/session")
    def session(user: str = Depends(_user)) -> dict:
        return svc.view(user)

    @r.post("/answer")
    def answer(body: StageAnswers, user: str = Depends(_user)) -> dict:
        try:
            return svc.submit(user, body.stage_id, body.answers)
        except OnboardingError as e:
            raise _errors(e)

    @r.post("/back")
    def back(user: str = Depends(_user)) -> dict:
        return svc.back(user)

    @r.post("/complete")
    def complete(user: str = Depends(_user)) -> dict:
        try:
            return svc.complete(user)
        except OnboardingError as e:
            raise _errors(e)

    @r.post("/profile")
    def update_profile(body: ProfileUpdate, user: str = Depends(_user)) -> dict:
        try:
            return svc.update_profile(user, body.answers)
        except OnboardingError as e:
            raise _errors(e)

    @r.get("/profile/history")
    def history(user: str = Depends(_user)) -> list:
        return svc.history(user)

    @r.get("/performance")
    def performance(user: str = Depends(_user)) -> dict:
        if os.getenv("CSS_PASSPORT_DEMO", "").lower() in ("1", "true", "yes"):
            from backend.app.trade_origin.demo import demo_lifecycle
            from backend.app.trade_origin.performance import segregate
            lc, marks = demo_lifecycle()
            report = segregate(lc, marks)
            report["data_source"] = "SAMPLE"
            report["sample_notice"] = "Sample data for illustration only. These are not real trades or results."
            return report
        raise HTTPException(status_code=503, detail={
            "status": "not_connected",
            "message": "Separated results appear here once your trades are recorded with their origin."})

    @r.get("/app/{path:path}", include_in_schema=False)
    def ui(path: str = "") -> FileResponse:
        target = (UI_DIR / (path or "index.html")).resolve()
        if UI_DIR.resolve() not in target.parents and target != UI_DIR.resolve() / "index.html":
            raise HTTPException(status_code=404)
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            raise HTTPException(status_code=404)
        return FileResponse(target)

    return r
