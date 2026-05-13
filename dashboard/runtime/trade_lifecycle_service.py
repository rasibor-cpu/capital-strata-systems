from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from dashboard.runtime.replay_correlation import enrich_with_correlation
from dashboard.runtime.replay_event_envelope import build_replay_event_envelope
from dashboard.runtime.runtime_event_bus import (
    publish_shadow_runtime_event,
    runtime_event_from_replay_payload,
)


TRADE_LIFECYCLE_SERVICE_VERSION = "css.trade_lifecycle.execution_state.v1"
FORCED_EXIT_REASONS = {"STOP", "FAST_STOP"}
PROFIT_EXIT_REASONS = {"TAKE_PROFIT"}
DEFENSIVE_EXIT_REASONS = {"DEFENSIVE_REDUCTION"}


@dataclass(frozen=True)
class TradeLifecycleExitResult:
    status: str
    booked: bool
    position_id: str = ""
    symbol: str = ""
    asset_class: str = ""
    reason: str = ""
    classification: str = ""
    realized_pnl: float = 0.0
    last_trade: str | None = None
    audit_payload: dict[str, Any] = field(default_factory=dict)
    replay_payload: dict[str, Any] = field(default_factory=dict)
    replay_events: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload_version": TRADE_LIFECYCLE_SERVICE_VERSION,
            "status": self.status,
            "booked": self.booked,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "reason": self.reason,
            "classification": self.classification,
            "realized_pnl": self.realized_pnl,
            "last_trade": self.last_trade,
            "audit_payload": self.audit_payload,
            "replay_payload": self.replay_payload,
            "replay_events": list(self.replay_events),
        }


@dataclass(frozen=True)
class DefensiveReductionResult:
    reductions: int
    exits: tuple[TradeLifecycleExitResult, ...]

    @property
    def last_trade(self) -> str | None:
        for result in reversed(self.exits):
            if result.last_trade:
                return result.last_trade
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload_version": TRADE_LIFECYCLE_SERVICE_VERSION,
            "reductions": self.reductions,
            "exits": [result.as_dict() for result in self.exits],
            "last_trade": self.last_trade,
        }


class TradeLifecycleExecutionStateService:
    def __init__(
        self,
        *,
        pnl_tracker: Any,
        capital_tracker: Any,
        pnl_dict_provider: Callable[[str], dict[str, float]],
        cluster_amplifier: Any,
        cluster_risk_governor: Any,
        locked_profit_ledger: Any,
        session_context_provider: Callable[[], Mapping[str, Any]] | None = None,
        mode_provider: Callable[[], str] | None = None,
        audit_recorder: Callable[[dict[str, Any]], None] | None = None,
        replay_recorder: Callable[[dict[str, Any]], None] | None = None,
        event_publisher: Callable[[dict[str, Any]], None] | None = None,
        strict_replay_persistence: bool = False,
        strict_event_publishing: bool = False,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self.pnl_tracker = pnl_tracker
        self.capital_tracker = capital_tracker
        self.pnl_dict_provider = pnl_dict_provider
        self.cluster_amplifier = cluster_amplifier
        self.cluster_risk_governor = cluster_risk_governor
        self.locked_profit_ledger = locked_profit_ledger
        self.session_context_provider = session_context_provider or (lambda: {})
        self.mode_provider = mode_provider or (lambda: "paper")
        self.audit_recorder = audit_recorder
        self.replay_recorder = replay_recorder
        self.event_publisher = event_publisher
        self.strict_replay_persistence = strict_replay_persistence
        self.strict_event_publishing = strict_event_publishing
        self.logger = logger

    def execute_exit(
        self,
        pos: dict[str, Any],
        *,
        observer_symbol: str,
        observer_price: float,
        reason: str,
        pnl_observer: Any,
    ) -> TradeLifecycleExitResult:
        try:
            if pos.get("forced_exit"):
                return self._result(pos, reason, "ALREADY_CLOSED", booked=False)

            result = self.book_position_exit(pos, reason)

            try:
                pnl_observer.close_position(observer_symbol, observer_price)
            except Exception as exc:
                self._log(f"[R17 WARN] Observer close failed: {str(exc)[:60]}")

            try:
                if pos.get("broker_tested", False):
                    self.capital_tracker.release_trade(pos["position_id"])
            except Exception as exc:
                self._log(f"[R17 WARN] Capital release failed: {str(exc)[:60]}")

            return result

        except Exception as exc:
            self._log(f"[R17 ERROR] Exit execution failure: {str(exc)[:80]}")
            return self._result(pos, reason, "EXIT_ERROR", booked=False)

    def book_position_exit(
        self,
        pos: dict[str, Any],
        reason: str,
    ) -> TradeLifecycleExitResult:
        if pos["forced_exit"]:
            return self._result(pos, reason, "ALREADY_CLOSED", booked=False)

        if pos.get("broker_order_ok"):
            last_trade = f"{pos['symbol']} BROKER_OPEN_MANUAL_REVIEW"
            return self._result(
                pos,
                reason,
                "BROKER_OPEN_MANUAL_REVIEW",
                booked=False,
                last_trade=last_trade,
            )

        realized = round(_safe_float(pos.get("floating")), 4)

        try:
            self.pnl_tracker.record_trade(
                instrument=pos["symbol"],
                realized_pnl=realized,
                unrealized_pnl=0.0,
            )
        except Exception as exc:
            self._log(f"[TRACKER ERROR] {exc}")

        pos["forced_exit"] = True
        pos["exit_reason"] = reason

        self.cluster_risk_governor.release_cluster_slot(pos["cluster_name"])

        if pos.get("broker_tested", False):
            self.capital_tracker.release_trade(pos["position_id"])

        target_pnl = self.pnl_dict_provider(pos["asset_class"])
        target_pnl[pos["symbol"]] = round(
            target_pnl.get(pos["symbol"], 0.0) + realized,
            4,
        )

        self.cluster_amplifier.record_cluster_win(pos["symbol"], realized)
        self._record_locked_profit(pos, reason, realized)
        self.locked_profit_ledger.record_recycled_slot()

        last_trade = f"{pos['symbol']} EXIT {reason} {realized:+.4f}"
        result = self._result(
            pos,
            reason,
            "EXIT_BOOKED",
            booked=True,
            realized_pnl=realized,
            last_trade=last_trade,
        )
        self._handoff_event(result)
        return result

    def apply_defensive_exposure_reduction(
        self,
        *,
        positions: Iterable[dict[str, Any]],
        is_session_locked: Callable[[], bool],
        limit: int,
    ) -> DefensiveReductionResult:
        if not is_session_locked():
            return DefensiveReductionResult(0, ())

        open_positions = [
            pos for pos in positions if not pos["forced_exit"]
        ]

        if not open_positions:
            return DefensiveReductionResult(0, ())

        open_positions.sort(
            key=lambda pos: (
                _safe_float(pos.get("floating")),
                -_safe_int(pos.get("age_cycles")),
            )
        )

        exits: list[TradeLifecycleExitResult] = []

        for pos in open_positions:
            if len(exits) >= limit:
                break

            if pos.get("broker_order_ok"):
                continue

            exits.append(self.book_position_exit(pos, "DEFENSIVE_REDUCTION"))

        return DefensiveReductionResult(len(exits), tuple(exits))

    def _record_locked_profit(
        self,
        pos: Mapping[str, Any],
        reason: str,
        realized: float,
    ) -> None:
        classification = classify_exit_reason(reason)
        if classification == "FORCED_EXIT":
            self.locked_profit_ledger.record_forced_exit(pos["position_id"], realized)
        elif classification == "PRIORITY_EXIT":
            self.locked_profit_ledger.record_priority_exit()
        elif classification == "DEFENSIVE_REDUCTION":
            self.locked_profit_ledger.record_defensive_reduction_exit()

    def _result(
        self,
        pos: Mapping[str, Any],
        reason: str,
        status: str,
        *,
        booked: bool,
        realized_pnl: float = 0.0,
        last_trade: str | None = None,
    ) -> TradeLifecycleExitResult:
        classification = classify_exit_reason(reason)
        audit_payload = build_trade_exit_audit_payload(
            pos,
            reason=reason,
            status=status,
            classification=classification,
            realized_pnl=realized_pnl,
            mode=self.mode_provider(),
            session_context=self.session_context_provider(),
        )
        audit_payload = enrich_with_correlation(audit_payload)
        replay_payload = {
            "payload_version": TRADE_LIFECYCLE_SERVICE_VERSION,
            "event_type": "trade_exit_replay_event",
            "correlation_id": audit_payload["correlation_id"],
            "lifecycle_id": audit_payload["lifecycle_id"],
            "position_id": audit_payload["position_id"],
            "symbol": audit_payload["symbol"],
            "asset_class": audit_payload["asset_class"],
            "cycle": audit_payload["cycle"],
            "status": status,
            "reason": reason,
            "classification": classification,
            "realized_pnl": realized_pnl,
            "mode": audit_payload["mode"],
            "timestamp_utc": audit_payload["timestamp_utc"],
        }
        replay_events = build_trade_exit_replay_events(
            pos,
            audit_payload=audit_payload,
            replay_payload=replay_payload,
            booked=booked,
        )
        return TradeLifecycleExitResult(
            status=status,
            booked=booked,
            position_id=audit_payload["position_id"],
            symbol=audit_payload["symbol"],
            asset_class=audit_payload["asset_class"],
            reason=reason,
            classification=classification,
            realized_pnl=realized_pnl,
            last_trade=last_trade,
            audit_payload=audit_payload,
            replay_payload=replay_payload,
            replay_events=replay_events,
        )

    def _handoff_event(self, result: TradeLifecycleExitResult) -> None:
        if self.audit_recorder is not None:
            try:
                self.audit_recorder(result.audit_payload)
            except Exception as exc:
                self._log(f"[R17 WARN] Audit handoff failed: {str(exc)[:60]}")

        if self.replay_recorder is not None:
            for replay_event in result.replay_events:
                try:
                    self.replay_recorder(replay_event)
                except Exception as exc:
                    self._log(f"[R17 WARN] Replay handoff failed: {str(exc)[:60]}")
                    if self.strict_replay_persistence:
                        raise

        if self.event_publisher is not None:
            for replay_event in result.replay_events:
                publish_shadow_runtime_event(
                    self.event_publisher,
                    runtime_event_from_replay_payload(
                        replay_event,
                        source_module="dashboard.runtime.trade_lifecycle_service",
                    ),
                    strict=self.strict_event_publishing,
                    logger=self.logger,
                )

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger(message)


def classify_exit_reason(reason: str) -> str:
    normalized = str(reason).strip().upper()
    if normalized in FORCED_EXIT_REASONS:
        return "FORCED_EXIT"
    if normalized in PROFIT_EXIT_REASONS:
        return "PRIORITY_EXIT"
    if normalized in DEFENSIVE_EXIT_REASONS:
        return "DEFENSIVE_REDUCTION"
    return "STANDARD_EXIT"


def build_trade_exit_audit_payload(
    pos: Mapping[str, Any],
    *,
    reason: str,
    status: str,
    classification: str,
    realized_pnl: float,
    mode: str,
    session_context: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "payload_version": TRADE_LIFECYCLE_SERVICE_VERSION,
        "event_type": "position_exit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "position_id": str(pos.get("position_id", "")),
        "symbol": str(pos.get("symbol", "")),
        "asset_class": str(pos.get("asset_class", "")),
        "status": status,
        "reason": str(reason),
        "classification": classification,
        "realized_pnl": round(_safe_float(realized_pnl), 4),
        "mode": _safe_mode(mode),
        "cycle": str(
            pos.get("cycle")
            or pos.get("cycle_number")
            or session_context.get("cycle")
            or session_context.get("cycle_number")
            or ""
        ),
        "broker_tested": bool(pos.get("broker_tested", False)),
        "broker_order_ok": bool(pos.get("broker_order_ok", False)),
        "cluster_name": str(pos.get("cluster_name") or ""),
        "session_user_id": str(
            pos.get("session_user_id")
            or session_context.get("user_id")
            or ""
        ),
        "session_role": str(
            pos.get("session_role")
            or session_context.get("role")
            or ""
        ),
        "session_id": str(
            pos.get("session_id")
            or session_context.get("session_id")
            or ""
        ),
    }


def build_trade_exit_replay_events(
    pos: Mapping[str, Any],
    *,
    audit_payload: Mapping[str, Any],
    replay_payload: Mapping[str, Any],
    booked: bool,
) -> tuple[dict[str, Any], ...]:
    if not booked:
        return (dict(replay_payload),)

    common = {
        "payload_version": TRADE_LIFECYCLE_SERVICE_VERSION,
        "correlation_id": audit_payload["correlation_id"],
        "lifecycle_id": audit_payload["lifecycle_id"],
        "position_id": audit_payload["position_id"],
        "symbol": audit_payload["symbol"],
        "asset_class": audit_payload["asset_class"],
        "mode": audit_payload["mode"],
        "cycle": audit_payload["cycle"],
        "session_id": audit_payload["session_id"],
        "session_user_id": audit_payload["session_user_id"],
        "timestamp_utc": audit_payload["timestamp_utc"],
        "reason": audit_payload["reason"],
        "classification": audit_payload["classification"],
        "status": audit_payload["status"],
    }
    realized_pnl = round(_safe_float(audit_payload.get("realized_pnl")), 4)
    events = [
        {
            **common,
            "event_type": "position_exit_booked",
            "realized_pnl": realized_pnl,
        },
        {
            **common,
            "event_type": "realized_pnl_handoff",
            "realized_pnl": realized_pnl,
        },
    ]

    if bool(audit_payload.get("broker_tested", False)):
        events.append(
            {
                **common,
                "event_type": "capital_released",
                "capital_position_id": audit_payload["position_id"],
            }
        )

    events.append(
        {
            **common,
            "event_type": "locked_profit_updated",
            "realized_pnl": realized_pnl,
        }
    )
    events.append(
        {
            **common,
            "event_type": "lifecycle_audit_payload_created",
            "audit_payload": dict(audit_payload),
        }
    )

    if str(audit_payload.get("classification")) == "DEFENSIVE_REDUCTION":
        events.append(
            {
                **common,
                "event_type": "defensive_reduction_applied",
                "age_cycles": _safe_int(pos.get("age_cycles")),
                "floating": _safe_float(pos.get("floating")),
            }
        )

    return tuple(
        build_replay_event_envelope(
            event,
            subsystem="trade_lifecycle",
            source_module="dashboard.runtime.trade_lifecycle_service",
            correlation_id=str(audit_payload["correlation_id"]),
            lifecycle_id=str(audit_payload["lifecycle_id"]),
        )
        for event in events
    )


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _safe_mode(value: str) -> str:
    return "live" if str(value).strip().lower() == "live" else "paper"
