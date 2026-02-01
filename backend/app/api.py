from fastapi import APIRouter, Request
from .main import orchestrate

router = APIRouter()

@router.post("/orchestrate")
async def orchestrator_entry(request: Request):
    """
    API entry point.
    Delegates all orchestration to main.orchestrate
    """
    return await orchestrate(request)
