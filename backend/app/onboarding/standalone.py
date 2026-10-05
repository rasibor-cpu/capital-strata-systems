"""Standalone development app for the Trader Passport (separate from the CSS runtime).

    uvicorn backend.app.onboarding.standalone:app --port 8790

Never use port 8765 (reserved for the governed CSS runtime). This app includes only the existing auth router and
the Passport router; it imports no broker, execution or engine modules.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from backend.app.auth.auth_router import router as auth_router

from .router import create_onboarding_router


def create_app(service=None) -> FastAPI:
    app = FastAPI(title="CSS Trader Passport (development)", version="1.0.0")
    app.include_router(auth_router)
    app.include_router(create_onboarding_router(service))

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse("/passport/app/index.html", status_code=303)

    return app


app = create_app()
