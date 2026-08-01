"""Phase 189 — RC-004 readiness governance (no live unlock, no execution)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from backend.app.brokers.multi_broker_readiness.contracts import SCHEMA_VERSION, BrokerType

# RC-004 historically approved controlled paper baseline with live trading not authorized.
RC004_PAPER_BASELINE_SHA = "b0703f3"
RC004_LIVE_TRADING_AUTHORIZED = False


@dataclass(frozen=True)
class RC004Readiness:
    schema_id: str = "RC004_READINESS"
    schema_version: str = SCHEMA_VERSION
    broker_type: str = ""
    paper_baseline_acknowledged: bool = True
    paper_baseline_sha: str = RC004_PAPER_BASELINE_SHA
    live_trading_authorized: bool = False
    signoff_artifact_present: bool = False
    status: str = "BLOCKED_LIVE_UNLOCK"
    remaining_blockers: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["live_trading_authorized"] = False
        payload["remaining_blockers"] = list(self.remaining_blockers)
        return payload

    def __post_init__(self) -> None:
        if self.live_trading_authorized:
            raise ValueError("RC-004 readiness must not authorize live trading in Phase 189")


def evaluate_rc004_readiness(
    broker: BrokerType | str,
    *,
    signoff_artifact_present: bool = False,
    extra_blockers: Sequence[str] | None = None,
) -> RC004Readiness:
    broker_key = broker.value if isinstance(broker, BrokerType) else str(broker).upper()
    blockers = [
        "BLK-RC004-SIGNOFF",
        "LIVE_TRADING_NOT_AUTHORIZED",
        "no_committed_RC004_live_unlock_artifact",
    ]
    if broker_key == "IBKR":
        blockers.append("IBKR_ROADMAP_EXCLUDED")
    for item in extra_blockers or ():
        if item not in blockers:
            blockers.append(item)

    status = "READY_FOR_PAPER_GOVERNANCE" if signoff_artifact_present else "BLOCKED_LIVE_UNLOCK"
    # Even with paper governance ready, live remains unauthorized.
    if not RC004_LIVE_TRADING_AUTHORIZED:
        status = "BLOCKED_LIVE_UNLOCK" if not signoff_artifact_present else "PAPER_ONLY_NO_LIVE_UNLOCK"

    return RC004Readiness(
        broker_type=broker_key,
        paper_baseline_acknowledged=True,
        paper_baseline_sha=RC004_PAPER_BASELINE_SHA,
        live_trading_authorized=False,
        signoff_artifact_present=signoff_artifact_present,
        status=status,
        remaining_blockers=tuple(blockers),
        diagnostics={
            "execution_allowed": False,
            "order_submission_allowed": False,
            "runtime_modifications_allowed": False,
        },
    )
