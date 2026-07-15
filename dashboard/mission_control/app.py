from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI

from dashboard.mission_control.routes import StateProvider, create_mission_control_router


def create_app(state_provider: StateProvider | None = None) -> FastAPI:
    app = FastAPI(
        title="CSS Mission Control",
        version="0.1.0",
        description="Read-only enterprise Mission Control shell for Capital Strata Systems.",
    )
    app.include_router(create_mission_control_router(state_provider))

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "app": "CSS Mission Control",
            "host_registration": "standalone",
            "read_only": True,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }

    return app


__all__ = ["create_app"]
