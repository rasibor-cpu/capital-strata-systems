# backend/app/brokers/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Dict, Any


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str  # "buy" | "sell"
    units: int
    order_type: str = "market"  # keep simple for paper
    client_tag: Optional[str] = None


@dataclass(frozen=True)
class OrderResult:
    ok: bool
    broker: str
    symbol: str
    side: str
    units: int
    order_id: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BrokerAdapter(Protocol):
    name: str

    def is_configured(self) -> bool:
        ...

    def place_order(self, req: OrderRequest) -> OrderResult:
        ...
