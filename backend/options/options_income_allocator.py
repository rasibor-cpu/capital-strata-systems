from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from backend.options.options_income_constraints import OptionsIncomeConstraintEngine, OptionsIncomeConstraintError
from backend.options.paper_position_repository import PaperIncomePosition, SAFE_FLAGS


@dataclass(frozen=True)
class OptionsIncomeAllocationPlan:
    allocations: list[dict[str, Any]]
    allocated_capital: float
    available_capital: float
    reserved_collateral: float
    utilized_collateral: float
    unused_collateral: float
    portfolio_utilization: float
    blockers: list[str]
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allocations": self.allocations,
            "allocated_capital": self.allocated_capital,
            "available_capital": self.available_capital,
            "reserved_collateral": self.reserved_collateral,
            "utilized_collateral": self.utilized_collateral,
            "unused_collateral": self.unused_collateral,
            "portfolio_utilization": self.portfolio_utilization,
            "blockers": self.blockers,
            **SAFE_FLAGS,
        }


class OptionsIncomeAllocator:
    def __init__(self, constraints: OptionsIncomeConstraintEngine | None = None) -> None:
        self.constraints = constraints or OptionsIncomeConstraintEngine()

    def allocate(
        self,
        *,
        total_capital: float,
        opportunities: Sequence[Any] | None = None,
        existing_positions: Sequence[PaperIncomePosition] | None = None,
        sector_by_underlying: Mapping[str, str] | None = None,
    ) -> OptionsIncomeAllocationPlan:
        capital = self.constraints.validate_capital(total_capital)
        positions = list(existing_positions or [])
        for position in positions:
            self.constraints.validate_position(position)
        existing_rows = [_row_from_position(position) for position in positions if position.collateral_reserved > position.collateral_released]
        reserved = sum(float(row["collateral"]) for row in existing_rows)
        available = capital - reserved
        if available < 0:
            raise OptionsIncomeConstraintError("Existing reserved collateral exceeds total capital")

        rows = list(existing_rows)
        blockers: list[str] = []
        seen_symbols = {row["option_symbol"] for row in rows}
        candidates = [_candidate_payload(item) for item in opportunities or []]
        candidates.sort(key=lambda row: (-float(row.get("ranking_score", 0.0) or 0.0), row.get("expiry", ""), row.get("strike", 0.0), row.get("option_contract_identity", {}).get("option_symbol", "")))
        for candidate in candidates:
            try:
                self.constraints.validate_candidate(candidate)
                symbol = str(candidate.get("option_contract_identity", {}).get("option_symbol") or "").strip()
                if not symbol:
                    raise OptionsIncomeConstraintError("Missing option symbol")
                if symbol in seen_symbols:
                    raise OptionsIncomeConstraintError(f"Duplicate opportunity: {symbol}")
                row = _row_from_candidate(candidate)
                prospective = [*rows, row]
                self.constraints.validate_allocations(prospective, total_capital=capital, sector_by_underlying=sector_by_underlying)
            except OptionsIncomeConstraintError as exc:
                blockers.append(str(exc))
                continue
            rows.append(row)
            seen_symbols.add(symbol)
            available -= float(row["collateral"])

        self.constraints.validate_allocations(rows, total_capital=capital, sector_by_underlying=sector_by_underlying)
        used = sum(float(row["collateral"]) for row in rows)
        return OptionsIncomeAllocationPlan(
            allocations=rows,
            allocated_capital=round(used, 6),
            available_capital=round(capital - used, 6),
            reserved_collateral=round(reserved, 6),
            utilized_collateral=round(used, 6),
            unused_collateral=round(capital - used, 6),
            portfolio_utilization=round(used / capital, 8),
            blockers=sorted(set(blockers)),
        )


def _candidate_payload(candidate: Any) -> dict[str, Any]:
    if hasattr(candidate, "to_dict"):
        return candidate.to_dict()
    if isinstance(candidate, Mapping):
        return dict(candidate)
    raise OptionsIncomeConstraintError("Malformed opportunity")


def _row_from_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    identity = dict(candidate.get("option_contract_identity") or {})
    underlying = str(candidate.get("underlying_symbol") or identity.get("underlying_symbol") or "").strip().upper()
    collateral = round(float(candidate["collateral_required"]), 6)
    premium = round(float(candidate.get("total_premium", 0.0)), 6)
    return {
        "allocation_id": f"OPPORTUNITY-{identity.get('option_symbol')}",
        "source": "OI-003_OPPORTUNITY",
        "position_id": "",
        "option_symbol": str(identity.get("option_symbol") or "").strip(),
        "underlying": underlying,
        "strategy": str(candidate.get("strategy") or "").strip().upper(),
        "expiry": str(candidate.get("expiry") or "").strip(),
        "strike": round(float(candidate.get("strike")), 6),
        "collateral": collateral,
        "expected_premium": premium,
        "assignment_exposure": collateral,
        "ranking_score": round(float(candidate.get("ranking_score", 0.0) or 0.0), 6),
        **SAFE_FLAGS,
    }


def _row_from_position(position: PaperIncomePosition) -> dict[str, Any]:
    collateral = round(max(0.0, position.collateral_reserved - position.collateral_released), 6)
    return {
        "allocation_id": f"POSITION-{position.position_id}",
        "source": "OI-004_POSITION",
        "position_id": position.position_id,
        "option_symbol": position.option_symbol,
        "underlying": position.underlying,
        "strategy": position.strategy_type,
        "expiry": position.expiry,
        "strike": position.strike,
        "collateral": collateral,
        "expected_premium": position.premium_remaining,
        "assignment_exposure": collateral,
        "ranking_score": 0.0,
        **SAFE_FLAGS,
    }


__all__ = ["OptionsIncomeAllocationPlan", "OptionsIncomeAllocator"]
