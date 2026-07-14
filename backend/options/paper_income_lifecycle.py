from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from backend.options.collateral_manager import CollateralManager
from backend.options.expiration_engine import ExpirationEngine
from backend.options.options_income_strategy_domain import CASH_SECURED_PUT, COVERED_CALL
from backend.options.paper_position_repository import (
    SAFE_FLAGS,
    PaperIncomeEvent,
    PaperIncomePosition,
    PaperPositionRepository,
)
from backend.options.position_state_machine import (
    ACTIVE,
    APPROVED,
    ASSIGNED,
    CLOSED_EARLY,
    COMPLETED,
    DISCOVERED,
    EXERCISED,
    EXPIRING,
    EXPIRED_WORTHLESS,
    PAPER_OPEN,
    PositionStateMachine,
)
from backend.options.premium_accounting import PremiumAccounting


SUPPORTED_STRATEGIES = {COVERED_CALL, CASH_SECURED_PUT}


class PaperIncomeLifecycleError(ValueError):
    """Raised when paper income lifecycle processing must fail closed."""


class PaperIncomeLifecycleEngine:
    """Paper-only lifecycle engine for accepted OI-003 income candidates."""

    def __init__(
        self,
        *,
        repository: PaperPositionRepository | None = None,
        collateral_manager: CollateralManager | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.repository = repository or PaperPositionRepository()
        self.collateral = collateral_manager or CollateralManager()
        self.premium = PremiumAccounting()
        self.expiration = ExpirationEngine()
        self.state_machine = PositionStateMachine()
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())

    def create_position(self, candidate: Any, *, entry_date: str) -> PaperIncomePosition:
        payload = _candidate_payload(candidate)
        strategy = _strategy(payload)
        summary = _strategy_summary(payload)
        identity = dict(payload.get("option_contract_identity") or {})
        option_symbol = str(identity.get("option_symbol") or "").strip()
        if not option_symbol:
            raise PaperIncomeLifecycleError("Missing option symbol")

        contracts = _contracts(strategy, summary)
        quantity = _quantity(strategy, payload, summary)
        premium_received = _float(payload.get("total_premium"), "total_premium")
        collateral_required = _float(payload.get("collateral_required"), "collateral_required")
        if premium_received < 0.0 or collateral_required < 0.0:
            raise PaperIncomeLifecycleError("Premium and collateral must be non-negative")

        now = self.clock()
        position_id = _position_id(strategy, option_symbol, entry_date)
        position = PaperIncomePosition(
            position_id=position_id,
            strategy_id=strategy,
            underlying=str(payload.get("underlying_symbol") or "").strip().upper(),
            option_symbol=option_symbol,
            strategy_type=strategy,
            quantity=quantity,
            contracts=contracts,
            entry_date=_required_text(entry_date, "entry_date"),
            expiry=_required_text(payload.get("expiry"), "expiry"),
            strike=_positive(payload.get("strike"), "strike"),
            premium_received=round(premium_received, 6),
            premium_realized=0.0,
            premium_remaining=round(premium_received, 6),
            collateral_reserved=0.0,
            collateral_released=0.0,
            current_state=DISCOVERED,
            assignment_status="NONE",
            lifecycle_events=[
                PaperIncomeEvent(
                    event_id="0001",
                    event_type="Created",
                    timestamp=now,
                    state=DISCOVERED,
                    details={"source": "OI-003_ACCEPTED_CANDIDATE", "strategy_summary": strategy},
                ).to_dict()
            ],
            advisory_flags=dict(SAFE_FLAGS),
            timestamps={"created_at": now, "updated_at": now},
        )
        return self.repository.add(position)

    def approve_position(self, position_id: str) -> PaperIncomePosition:
        return self._transition(position_id, APPROVED, "Approved")

    def open_position(self, position_id: str) -> PaperIncomePosition:
        position = self.repository.get(position_id)
        if position.current_state != APPROVED:
            raise PaperIncomeLifecycleError("Position must be APPROVED before PAPER_OPEN")
        transition = self.state_machine.transition(position.current_state, PAPER_OPEN)
        collateral = self._reserve_collateral(position)
        accounting = self.premium.open_snapshot(
            premium_received=position.premium_received,
            collateral_reserved=collateral.amount_reserved,
            dte=_dte(position.entry_date, position.expiry),
        )
        events = list(position.lifecycle_events)
        events.extend(
            [
                self._event("Opened", PAPER_OPEN, {"transition": transition.event_type}),
                self._event("Premium Received", PAPER_OPEN, accounting.to_dict()),
                self._event("Collateral Reserved", PAPER_OPEN, collateral.to_dict()),
            ]
        )
        return self._save(
            replace(
                position,
                current_state=PAPER_OPEN,
                premium_realized=accounting.premium_realized,
                premium_remaining=accounting.premium_remaining,
                collateral_reserved=collateral.amount_reserved,
                lifecycle_events=events,
            )
        )

    def activate_position(self, position_id: str) -> PaperIncomePosition:
        return self._transition(position_id, ACTIVE, "Activated")

    def mark_expiring(self, position_id: str) -> PaperIncomePosition:
        return self._transition(position_id, EXPIRING, "Expiration Processing Started")

    def process_expiration(
        self,
        position_id: str,
        *,
        underlying_price: float,
        as_of: str,
        force_exercised: bool = False,
    ) -> PaperIncomePosition:
        position = self.repository.get(position_id)
        if position.current_state == COMPLETED:
            raise PaperIncomeLifecycleError("Completed positions cannot be processed again")
        if position.current_state == ACTIVE:
            position = self.mark_expiring(position_id)
        if position.current_state != EXPIRING:
            raise PaperIncomeLifecycleError("Position must be ACTIVE or EXPIRING for expiration processing")

        result = self.expiration.process(
            position,
            underlying_price=underlying_price,
            as_of=as_of,
            force_exercised=force_exercised,
        )
        return self._finalize(position, result.outcome, result.assignment_status, result.to_dict())

    def close_early(self, position_id: str, *, buyback_cost: float, as_of: str) -> PaperIncomePosition:
        position = self.repository.get(position_id)
        if position.current_state == COMPLETED:
            raise PaperIncomeLifecycleError("Completed positions cannot be processed again")
        if position.current_state == ACTIVE:
            self.state_machine.transition(ACTIVE, EXPIRING)
            position = self._transition(position_id, EXPIRING, "Early Close Processing Started")
        if position.current_state != EXPIRING:
            raise PaperIncomeLifecycleError("Position must be ACTIVE or EXPIRING before early close")
        self.expiration.process(position, underlying_price=position.strike, as_of=as_of, close_early=True)
        accounting = self.premium.close_early(
            premium_received=position.premium_received,
            buyback_cost=buyback_cost,
            collateral_reserved=position.collateral_reserved,
            dte=_dte(position.entry_date, position.expiry),
        )
        return self._finalize(
            position,
            CLOSED_EARLY,
            "CLOSED_EARLY",
            {"buyback_cost": float(buyback_cost), "premium_accounting": accounting.to_dict()},
            accounting=accounting,
        )

    def _transition(self, position_id: str, next_state: str, event_type: str) -> PaperIncomePosition:
        position = self.repository.get(position_id)
        transition = self.state_machine.transition(position.current_state, next_state)
        events = list(position.lifecycle_events)
        events.append(self._event(event_type, next_state, {"transition": transition.event_type}))
        return self._save(replace(position, current_state=next_state, lifecycle_events=events))

    def _finalize(
        self,
        position: PaperIncomePosition,
        outcome_state: str,
        assignment_status: str,
        details: dict[str, Any],
        *,
        accounting: Any | None = None,
    ) -> PaperIncomePosition:
        if outcome_state not in {EXPIRED_WORTHLESS, ASSIGNED, EXERCISED, CLOSED_EARLY}:
            raise PaperIncomeLifecycleError(f"Unsupported final outcome: {outcome_state}")
        self.state_machine.transition(position.current_state, outcome_state)
        release = self.collateral.release(position_id=position.position_id)
        accounting = accounting or self.premium.realize_all(
            premium_received=position.premium_received,
            collateral_reserved=position.collateral_reserved,
            dte=_dte(position.entry_date, position.expiry),
        )
        events = list(position.lifecycle_events)
        events.append(self._event("Expiration Processed", outcome_state, details))
        events.append(self._event(_event_name_for_outcome(outcome_state), outcome_state, {"assignment_status": assignment_status}))
        events.append(self._event("Collateral Released", outcome_state, release.to_dict()))
        terminal = self._save(
            replace(
                position,
                current_state=outcome_state,
                assignment_status=assignment_status,
                premium_realized=accounting.premium_realized,
                premium_remaining=accounting.premium_remaining,
                collateral_released=release.amount_released,
                lifecycle_events=events,
            )
        )
        self.state_machine.transition(outcome_state, COMPLETED)
        completed_events = list(terminal.lifecycle_events)
        completed_events.append(self._event("Completed", COMPLETED, {"previous_state": outcome_state}))
        return self._save(replace(terminal, current_state=COMPLETED, lifecycle_events=completed_events))

    def _reserve_collateral(self, position: PaperIncomePosition):
        if position.strategy_type == COVERED_CALL:
            return self.collateral.reserve_shares(position_id=position.position_id, shares=position.quantity)
        if position.strategy_type == CASH_SECURED_PUT:
            return self.collateral.reserve_cash(position_id=position.position_id, cash=_cash_collateral(position))
        raise PaperIncomeLifecycleError(f"Unsupported strategy: {position.strategy_type}")

    def _event(self, event_type: str, state: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        return PaperIncomeEvent(
            event_id=f"{datetime.now(timezone.utc).timestamp():.6f}",
            event_type=event_type,
            timestamp=self.clock(),
            state=state,
            details=dict(details or {}),
        ).to_dict()

    def _save(self, position: PaperIncomePosition) -> PaperIncomePosition:
        now = self.clock()
        timestamps = dict(position.timestamps)
        timestamps["updated_at"] = now
        return self.repository.update(replace(position, timestamps=timestamps, advisory_flags=dict(SAFE_FLAGS)))


def _candidate_payload(candidate: Any) -> dict[str, Any]:
    if candidate is None:
        raise PaperIncomeLifecycleError("Missing income candidate")
    if hasattr(candidate, "to_dict"):
        payload = candidate.to_dict()
    elif isinstance(candidate, Mapping):
        payload = dict(candidate)
    else:
        raise PaperIncomeLifecycleError("Malformed income candidate")
    if payload.get("validation_status") != "PASS":
        raise PaperIncomeLifecycleError("Only OI-003 accepted candidates may enter paper lifecycle")
    if payload.get("advisory_only") is not True or payload.get("execution_allowed") is not False:
        raise PaperIncomeLifecycleError("Income candidate advisory flags are unsafe")
    if payload.get("live_trading_blocked") is not True or payload.get("broker_execution_armed") is not False:
        raise PaperIncomeLifecycleError("Income candidate broker safety flags are unsafe")
    return payload


def _strategy(payload: Mapping[str, Any]) -> str:
    strategy = str(payload.get("strategy") or "").strip().upper()
    if strategy not in SUPPORTED_STRATEGIES:
        raise PaperIncomeLifecycleError(f"Unsupported strategy: {strategy}")
    return strategy


def _strategy_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("strategy_summary") or {})
    if summary.get("valid") is not True or summary.get("validation_status") != "PASS":
        raise PaperIncomeLifecycleError("Missing accepted OI-002 strategy summary")
    return summary


def _contracts(strategy: str, summary: Mapping[str, Any]) -> int:
    field = "short_call_quantity" if strategy == COVERED_CALL else "short_put_quantity"
    try:
        contracts = int(summary.get(field))
    except (TypeError, ValueError) as exc:
        raise PaperIncomeLifecycleError("Malformed contract quantity") from exc
    if contracts <= 0:
        raise PaperIncomeLifecycleError("Malformed contract quantity")
    return contracts


def _quantity(strategy: str, payload: Mapping[str, Any], summary: Mapping[str, Any]) -> float:
    if strategy == COVERED_CALL:
        value = summary.get("required_covered_quantity", payload.get("underlying_coverage_required"))
    else:
        exposure = dict(summary.get("assignment_exposure") or payload.get("assignment_exposure") or {})
        value = exposure.get("assigned_underlying_quantity")
    quantity = _positive(value, "quantity")
    return round(quantity, 6)


def _cash_collateral(position: PaperIncomePosition) -> float:
    return round(position.strike * position.quantity, 6)


def _position_id(strategy: str, option_symbol: str, entry_date: str) -> str:
    safe_symbol = "".join(ch if ch.isalnum() else "-" for ch in option_symbol.upper()).strip("-")
    safe_date = "".join(ch if ch.isalnum() else "-" for ch in str(entry_date)).strip("-")
    return f"PAPERINC-{strategy}-{safe_symbol}-{safe_date}"


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PaperIncomeLifecycleError(f"Missing {field}")
    return text


def _positive(value: Any, field: str) -> float:
    number = _float(value, field)
    if number <= 0.0:
        raise PaperIncomeLifecycleError(f"{field} must be positive")
    return number


def _float(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PaperIncomeLifecycleError(f"{field} must be numeric") from exc
    if number != number or number in {float("inf"), float("-inf")}:
        raise PaperIncomeLifecycleError(f"{field} must be finite")
    return number


def _dte(entry_date: str, expiry: str) -> int:
    try:
        start = datetime.fromisoformat(str(entry_date).strip()).date()
        end = datetime.fromisoformat(str(expiry).strip()).date()
    except (TypeError, ValueError) as exc:
        raise PaperIncomeLifecycleError("Invalid lifecycle timestamp") from exc
    if end < start:
        raise PaperIncomeLifecycleError("Expiry cannot precede entry date")
    return max(0, (end - start).days)


def _event_name_for_outcome(outcome: str) -> str:
    return {
        EXPIRED_WORTHLESS: "Expired Worthless",
        ASSIGNED: "Assigned",
        EXERCISED: "Exercised",
        CLOSED_EARLY: "Closed Early",
    }[outcome]


__all__ = ["PaperIncomeLifecycleEngine", "PaperIncomeLifecycleError", "SUPPORTED_STRATEGIES"]
