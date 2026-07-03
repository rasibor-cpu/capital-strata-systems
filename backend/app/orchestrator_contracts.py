"""
Orchestration Contracts (Phase 12.4)

Single source of truth for UI ↔ backend orchestration contracts.

Hard constraints:
- prompt-only (no execution implied by these contracts)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import datetime


def _utc_now_compat() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


@dataclass
class ScreenRequest:
    screen_id: str
    action: str
    payload: Dict[str, Any]
    user_id: Optional[str] = None
    timestamp: datetime.datetime = field(default_factory=_utc_now_compat)


@dataclass
class ScreenResponse:
    screen_id: str
    status: str
    message: str
    data: Dict[str, Any]
