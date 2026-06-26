from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .futures_contract import CanonicalFuturesContract
from .option_contract import CanonicalOptionContract


@dataclass(frozen=True)
class DerivativesMarketSnapshot:
    options: list[CanonicalOptionContract]
    futures: list[CanonicalFuturesContract]
    timestamp: datetime

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            object.__setattr__(self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "options": [contract.to_dict() for contract in self.options],
            "futures": [contract.to_dict() for contract in self.futures],
            "timestamp": self.timestamp.isoformat(),
        }


def serialize_derivatives(
    options: list[CanonicalOptionContract],
    futures: list[CanonicalFuturesContract],
) -> dict[str, Any]:
    snapshot = DerivativesMarketSnapshot(
        options=list(options),
        futures=list(futures),
        timestamp=datetime.now(timezone.utc),
    )
    return snapshot.to_dict()
