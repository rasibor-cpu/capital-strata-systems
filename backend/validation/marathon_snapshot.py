from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class MarathonCyclePlan:
    timestamp: str
    paper_balance: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    open_positions: int
    alerts: int
    recoveries: int
    heartbeat_status: str
    runtime_healthy: bool = True
    paper_mode_enabled: bool = True
    recovery_exhausted: bool = False
    critical_alert_threshold_exceeded: bool = False
    heartbeat_lost_seconds: float = 0.0
    portfolio_exposure: float = 0.0
    cycle_duration_seconds: float = 0.0
    replay_history: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "MarathonCyclePlan":
        if not isinstance(payload, Mapping):
            raise TypeError("cycle plan must be a mapping")

        required = {
            "timestamp",
            "paper_balance",
            "equity",
            "realized_pnl",
            "unrealized_pnl",
            "open_positions",
            "alerts",
            "recoveries",
            "heartbeat_status",
        }
        missing = [field for field in required if field not in payload]
        if missing:
            raise ValueError(f"cycle plan missing required fields: {', '.join(missing)}")

        replay_history = payload.get("replay_history", ())
        if replay_history is None:
            replay_history = ()
        if not isinstance(replay_history, tuple):
            replay_history = tuple(replay_history)

        return MarathonCyclePlan(
            timestamp=str(payload["timestamp"]).strip(),
            paper_balance=float(payload["paper_balance"]),
            equity=float(payload["equity"]),
            realized_pnl=float(payload["realized_pnl"]),
            unrealized_pnl=float(payload["unrealized_pnl"]),
            open_positions=int(payload["open_positions"]),
            alerts=int(payload["alerts"]),
            recoveries=int(payload["recoveries"]),
            heartbeat_status=str(payload["heartbeat_status"]).strip().upper() or "UNKNOWN",
            runtime_healthy=bool(payload.get("runtime_healthy", True)),
            paper_mode_enabled=bool(payload.get("paper_mode_enabled", True)),
            recovery_exhausted=bool(payload.get("recovery_exhausted", False)),
            critical_alert_threshold_exceeded=bool(payload.get("critical_alert_threshold_exceeded", False)),
            heartbeat_lost_seconds=float(payload.get("heartbeat_lost_seconds", 0.0)),
            portfolio_exposure=float(payload.get("portfolio_exposure", 0.0)),
            cycle_duration_seconds=float(payload.get("cycle_duration_seconds", 0.0)),
            replay_history=tuple(replay_history),
        )


@dataclass(frozen=True)
class MarathonSnapshot:
    timestamp: str
    uptime_seconds: float
    cycle_number: int
    paper_balance: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    approved_trades: int
    blocked_trades: int
    open_positions: int
    alerts: int
    recoveries: int
    heartbeat_status: str
    decision: str = "UNKNOWN"
    selected_strategy: str = ""
    market_regime: str = "UNKNOWN"
    confidence: float = 0.0
    signal_strength: float = 0.0
    allocation: float = 0.0
    position_size: float = 0.0
    expected_reward: float = 0.0
    expected_risk: float = 0.0
    execution_status: str = "UNKNOWN"
    learning_version: str = ""
    portfolio_exposure: float = 0.0
    cycle_duration_seconds: float = 0.0
    drawdown: float = 0.0
    canonical_decision: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
