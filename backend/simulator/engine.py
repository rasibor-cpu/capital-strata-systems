from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from .models import (
    ChallengeDefinition,
    ChallengeProgress,
    ChallengeType,
    SimulatedFill,
    SimulatedPortfolio,
    SimulatedPosition,
    SimulationScore,
    ZERO,
)


class SimulationEngine:
    """Deterministic, broker-independent paper portfolio engine.

    The engine accepts only explicit simulated fills. It has no broker,
    credential, order-routing, transfer, withdrawal, or funding surface.
    """

    @staticmethod
    def create(initial_cash: Decimal, as_of_utc: datetime | None = None) -> SimulatedPortfolio:
        if initial_cash < ZERO:
            raise ValueError("initial_cash must be non-negative")
        stamp = as_of_utc or datetime.now(timezone.utc)
        return SimulatedPortfolio(
            cash=initial_cash,
            positions={},
            realized_pnl=ZERO,
            high_water_mark=initial_cash,
            starting_equity=initial_cash,
            as_of_utc=stamp,
        )

    @staticmethod
    def apply_fill(portfolio: SimulatedPortfolio, fill: SimulatedFill) -> SimulatedPortfolio:
        positions = dict(portfolio.positions)
        current = positions.get(fill.symbol)
        current_qty = current.quantity if current else ZERO
        current_avg = current.average_cost if current else ZERO
        realized = portfolio.realized_pnl
        cash = portfolio.cash
        notional = fill.quantity * fill.price

        if fill.side == "BUY":
            if notional > cash:
                raise ValueError("insufficient simulated cash")
            new_qty = current_qty + fill.quantity
            new_avg = ((current_qty * current_avg) + notional) / new_qty
            positions[fill.symbol] = SimulatedPosition(
                symbol=fill.symbol,
                quantity=new_qty,
                average_cost=new_avg,
                mark_price=fill.price,
            )
            cash -= notional
        else:
            if current is None or fill.quantity > current_qty:
                raise ValueError("simulator does not permit naked/short sells")
            realized += fill.quantity * (fill.price - current_avg)
            remaining = current_qty - fill.quantity
            cash += notional
            if remaining == ZERO:
                positions.pop(fill.symbol, None)
            else:
                positions[fill.symbol] = SimulatedPosition(
                    symbol=fill.symbol,
                    quantity=remaining,
                    average_cost=current_avg,
                    mark_price=fill.price,
                )

        provisional = SimulatedPortfolio(
            cash=cash,
            positions=positions,
            realized_pnl=realized,
            high_water_mark=portfolio.high_water_mark,
            starting_equity=portfolio.starting_equity,
            as_of_utc=fill.timestamp_utc,
        )
        return replace(provisional, high_water_mark=max(portfolio.high_water_mark, provisional.equity))

    @staticmethod
    def mark_to_market(
        portfolio: SimulatedPortfolio,
        prices: dict[str, Decimal],
        as_of_utc: datetime,
    ) -> SimulatedPortfolio:
        positions = dict(portfolio.positions)
        for symbol, position in tuple(positions.items()):
            if symbol in prices:
                positions[symbol] = replace(position, mark_price=prices[symbol])

        provisional = SimulatedPortfolio(
            cash=portfolio.cash,
            positions=positions,
            realized_pnl=portfolio.realized_pnl,
            high_water_mark=portfolio.high_water_mark,
            starting_equity=portfolio.starting_equity,
            as_of_utc=as_of_utc,
        )
        return replace(provisional, high_water_mark=max(portfolio.high_water_mark, provisional.equity))


class AcademyScorer:
    @staticmethod
    def score(
        portfolio: SimulatedPortfolio,
        benchmark_return_pct: Decimal = ZERO,
        accepted_good_decisions: int = 0,
        rejected_bad_decisions: int = 0,
        total_decisions: int = 0,
    ) -> SimulationScore:
        if total_decisions < 0:
            raise ValueError("total_decisions must be non-negative")
        correct = accepted_good_decisions + rejected_bad_decisions
        if correct < 0 or correct > total_decisions:
            raise ValueError("decision counts are inconsistent")

        if portfolio.starting_equity > ZERO:
            return_pct = (portfolio.equity - portfolio.starting_equity) / portfolio.starting_equity
        else:
            return_pct = ZERO

        quality = (
            Decimal(correct) / Decimal(total_decisions)
            if total_decisions
            else ZERO
        )

        return SimulationScore(
            return_pct=return_pct,
            max_drawdown_pct=portfolio.drawdown_pct,
            benchmark_excess_pct=return_pct - benchmark_return_pct,
            decision_quality_pct=quality,
            capital_preserved=portfolio.equity >= portfolio.starting_equity,
        )

    @staticmethod
    def evaluate_challenge(
        challenge: ChallengeDefinition,
        score: SimulationScore,
        observations: int,
    ) -> ChallengeProgress:
        if observations < 0:
            raise ValueError("observations must be non-negative")

        if challenge.challenge_type == ChallengeType.CAPITAL_PRESERVATION:
            metric = Decimal("1") if score.capital_preserved else ZERO
            met = score.capital_preserved
        elif challenge.challenge_type == ChallengeType.BENCHMARK_OUTPERFORMANCE:
            metric = score.benchmark_excess_pct
            met = metric >= challenge.target
        elif challenge.challenge_type == ChallengeType.DRAWDOWN_CONTROL:
            metric = score.max_drawdown_pct
            met = metric <= challenge.target
        else:
            metric = score.decision_quality_pct
            met = metric >= challenge.target

        complete = observations >= challenge.minimum_observations and met
        return ChallengeProgress(
            challenge_id=challenge.challenge_id,
            observations=observations,
            metric_value=metric,
            complete=complete,
        )

    @staticmethod
    def badge_ids(progress: Iterable[ChallengeProgress]) -> tuple[str, ...]:
        return tuple(sorted(item.challenge_id for item in progress if item.complete))
