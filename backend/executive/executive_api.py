"""GET-only Executive Intelligence API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .executive_service import ExecutiveIntelligenceService


def create_executive_intelligence_router(
    *,
    state_provider: Callable[[], Mapping[str, Any] | None] | None = None,
    service: ExecutiveIntelligenceService | None = None,
) -> APIRouter:
    executive = service or ExecutiveIntelligenceService(state_provider=state_provider)
    router = APIRouter(prefix="/executive", tags=["executive-intelligence"])

    def response(producer: Callable[[], dict[str, Any]]) -> JSONResponse:
        try:
            payload = producer()
        except Exception:
            payload = {
                "status": "DEGRADED",
                "reason": "executive_evidence_unavailable",
                "safety": {
                    "read_only": True,
                    "execution_allowed": False,
                    "live_trading_blocked": True,
                    "broker_execution_armed": False,
                    "runtime_mutation_allowed": False,
                },
            }
        return JSONResponse(payload)

    @router.get("/summary")
    async def summary() -> JSONResponse:
        return response(executive.summary)

    @router.get("/kpis")
    async def kpis() -> JSONResponse:
        return response(executive.kpis)

    @router.get("/scorecard")
    async def scorecard() -> JSONResponse:
        return response(executive.scorecard)

    @router.get("/income")
    async def income() -> JSONResponse:
        return response(executive.income)

    @router.get("/balance-sheet")
    async def balance_sheet() -> JSONResponse:
        return response(executive.balance_sheet)

    @router.get("/cashflow")
    async def cashflow() -> JSONResponse:
        return response(executive.cashflow)

    @router.get("/run-rate")
    async def run_rate() -> JSONResponse:
        return response(executive.run_rate)

    @router.get("/risk")
    async def risk() -> JSONResponse:
        return response(executive.risk)

    @router.get("/commentary")
    async def commentary() -> JSONResponse:
        return response(executive.commentary_view)

    return router


__all__ = ["create_executive_intelligence_router"]
