"""Phase 189/192 — RC-004 readiness governance (no live unlock, no execution)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from backend.app.brokers.multi_broker_readiness.contracts import SCHEMA_VERSION, BrokerType

# RC-004 historically approved controlled paper baseline with live trading not authorized.
RC004_PAPER_BASELINE_SHA = "b0703f3"
RC004_LIVE_TRADING_AUTHORIZED = False
RC004_EXPLICIT_STATEMENT = "LIVE_TRADING_NOT_AUTHORIZED"

# Phase 192 committed governance package (relative to repository root).
RC004_POSTURE_DOC = Path("docs") / "governance" / "RC_004_OPERATIONAL_POSTURE.md"
RC004_POSTURE_MATRIX = Path("docs") / "governance" / "RC_004_POSTURE_MATRIX.json"


def rc004_signoff_artifact_present(repo_root: Path | None = None) -> bool:
    """True when the Phase 192 committed RC-004 posture package is present."""
    root = repo_root or Path(__file__).resolve().parents[4]
    return (root / RC004_POSTURE_DOC).is_file() and (root / RC004_POSTURE_MATRIX).is_file()


@dataclass(frozen=True)
class RC004Readiness:
    schema_id: str = "RC004_READINESS"
    schema_version: str = SCHEMA_VERSION
    broker_type: str = ""
    paper_baseline_acknowledged: bool = True
    paper_baseline_sha: str = RC004_PAPER_BASELINE_SHA
    live_trading_authorized: bool = False
    signoff_artifact_present: bool = False
    explicit_statement: str = RC004_EXPLICIT_STATEMENT
    status: str = "BLOCKED_LIVE_UNLOCK"
    remaining_blockers: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["live_trading_authorized"] = False
        payload["explicit_statement"] = RC004_EXPLICIT_STATEMENT
        payload["remaining_blockers"] = list(self.remaining_blockers)
        return payload

    def __post_init__(self) -> None:
        if self.live_trading_authorized:
            raise ValueError("RC-004 readiness must not authorize live trading")
        if self.explicit_statement != RC004_EXPLICIT_STATEMENT:
            raise ValueError("RC-004 must retain LIVE_TRADING_NOT_AUTHORIZED")


def evaluate_rc004_readiness(
    broker: BrokerType | str,
    *,
    signoff_artifact_present: bool | None = None,
    extra_blockers: Sequence[str] | None = None,
    repo_root: Path | None = None,
) -> RC004Readiness:
    broker_key = broker.value if isinstance(broker, BrokerType) else str(broker).upper()
    artifact_present = (
        bool(signoff_artifact_present)
        if signoff_artifact_present is not None
        else rc004_signoff_artifact_present(repo_root)
    )

    blockers = [
        "BLK-RC004-LIVE-UNLOCK",
        "LIVE_TRADING_NOT_AUTHORIZED",
    ]
    if not artifact_present:
        blockers.insert(0, "BLK-RC004-ARTIFACT")
        blockers.append("no_committed_RC004_doc")
    if broker_key == "IBKR":
        blockers.append("IBKR_ROADMAP_EXCLUDED")
    for item in extra_blockers or ():
        if item not in blockers:
            blockers.append(item)

    # Even with the posture package present, live remains unauthorized.
    if artifact_present:
        status = "PAPER_ONLY_NO_LIVE_UNLOCK"
    else:
        status = "BLOCKED_LIVE_UNLOCK"

    if not RC004_LIVE_TRADING_AUTHORIZED:
        # Hard invariant: never emit a live-ready status.
        if status not in {"PAPER_ONLY_NO_LIVE_UNLOCK", "BLOCKED_LIVE_UNLOCK"}:
            status = "BLOCKED_LIVE_UNLOCK"

    return RC004Readiness(
        broker_type=broker_key,
        paper_baseline_acknowledged=True,
        paper_baseline_sha=RC004_PAPER_BASELINE_SHA,
        live_trading_authorized=False,
        signoff_artifact_present=artifact_present,
        explicit_statement=RC004_EXPLICIT_STATEMENT,
        status=status,
        remaining_blockers=tuple(blockers),
        diagnostics={
            "execution_allowed": False,
            "execution_authority": False,
            "order_submission_allowed": False,
            "runtime_modifications_allowed": False,
            "freeze_sha_designated": False,
            "read_only_ttl_is_not_live_authority_ttl": True,
            "posture_doc": str(RC004_POSTURE_DOC).replace("\\", "/"),
            "posture_matrix": str(RC004_POSTURE_MATRIX).replace("\\", "/"),
        },
    )
