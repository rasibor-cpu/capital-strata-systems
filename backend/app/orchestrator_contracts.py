"""
Orchestration Contracts (Phase 12.4)

Single source of truth for UI ↔ backend orchestration contracts.

Hard constraints:
- prompt-only (no execution implied by these contracts)
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import datetime


@dataclass
class ScreenRequest:
    screen_id: str
    action: str
    payload: Dict[str, Any]
    user_id: Optional[str] = None
    timestamp: datetime.datetime = datetime.datetime.utcnow()


@dataclass
class ScreenResponse:
    screen_id: str
    status: str
    message: str
    data: Dict[str, Any]
