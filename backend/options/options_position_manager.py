from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List


CONTRACT_MULTIPLIER = 100.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


@dataclass
class OptionsPosition:
    option_symbol: str
    underlying_symbol: str
    side: str
    option_type: str
    strike: float
    expiry: str
    entry_price: float
    contracts: int
    contract_multiplier: float
    take_profit_price: float
    stop_loss_price: float
    max_hold_cycles: int
    opened_at: str
    opened_cycle: int
    status: str = "OPEN"
    confidence: float = 0.0
    tier: str = "WATCH"
    note: str = ""
    peak_price_seen: float = 0.0
    trailing_active: bool = False
    trailing_stop_pct: float = 0.12

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OptionsPositionManager:
    def __init__(self) -> None:
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed_log: List[Dict[str, Any]] = []

    def open_long_option(
        self,
        *,
        option_symbol: str,
        underlying_symbol: str,
        option_type: str,
        strike: float,
        expiry: str,
        entry_price: float,
        contracts: int = 1,
        take_profit_pct: float = 0.25,
        stop_loss_pct: float = 0.20,
        max_hold_cycles: int = 3,
        current_cycle: int = 0,
        confidence: float = 0.0,
        tier: str = "WATCH",
        note: str = "",
    ) -> Dict[str, Any]:
        option_symbol = str(option_symbol).strip().upper()
        underlying_symbol = str(underlying_symbol).strip().upper()
        option_type = str(option_type).strip().upper()
        tier = str(tier).strip().upper() or "WATCH"

        if not option_symbol:
            return {"status": "REJECTED", "reason": "missing_option_symbol"}

        if option_symbol in self.positions:
            return {"status": "REJECTED", "reason": "position_already_open"}

        if option_type not in {"CALL", "PUT"}:
            return {"status": "REJECTED", "reason": "invalid_option_type"}

        entry_price = _safe_float(entry_price)
        strike = _safe_float(strike)
        contracts = max(1, _safe_int(contracts, 1))
        take_profit_pct = max(0.01, _safe_float(take_profit_pct, 0.25))
        stop_loss_pct = max(0.01, _safe_float(stop_loss_pct, 0.20))
        max_hold_cycles = max(1, _safe_int(max_hold_cycles, 3))
        confidence = _safe_float(confidence, 0.0)

        if entry_price <= 0:
            return {"status": "REJECTED", "reason": "invalid_entry_price"}

        trailing_stop_pct = self._trail_pct_for_tier(tier)
        take_profit_price = entry_price * (1.0 + take_profit_pct)
        stop_loss_price = max(0.01, entry_price * (1.0 - stop_loss_pct))

        position = OptionsPosition(
            option_symbol=option_symbol,
            underlying_symbol=underlying_symbol,
            side="LONG",
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            entry_price=entry_price,
            contracts=contracts,
            contract_multiplier=CONTRACT_MULTIPLIER,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            max_hold_cycles=max_hold_cycles,
            opened_at=datetime.utcnow().isoformat(),
            opened_cycle=current_cycle,
            confidence=confidence,
            tier=tier,
            note=note,
            peak_price_seen=entry_price,
            trailing_active=False,
            trailing_stop_pct=trailing_stop_pct,
        ).to_dict()

        self.positions[option_symbol] = position

        return {
            "status": "OPENED",
            "option_symbol": option_symbol,
            "underlying_symbol": underlying_symbol,
            "entry_price": entry_price,
            "contracts": contracts,
            "take_profit_price": take_profit_price,
            "stop_loss_price": stop_loss_price,
            "trailing_stop_pct": trailing_stop_pct,
        }

    def update_positions(
        self,
        option_price_map: Dict[str, float],
        *,
        current_cycle: int,
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        for option_symbol, pos in list(self.positions.items()):
            current_price = _safe_float(option_price_map.get(option_symbol))
            if current_price <= 0:
                continue

            held_cycles = max(0, current_cycle - _safe_int(pos.get("opened_cycle"), 0))
            entry_price = _safe_float(pos.get("entry_price"))
            peak_price_seen = max(
                _safe_float(pos.get("peak_price_seen"), entry_price),
                current_price,
            )
            trailing_active = bool(pos.get("trailing_active", False))
            trailing_stop_pct = max(
                0.01,
                _safe_float(
                    pos.get("trailing_stop_pct"),
                    self._trail_pct_for_tier(str(pos.get("tier", "WATCH"))),
                ),
            )

            pos["current_price"] = current_price
            pos["held_cycles"] = held_cycles
            pos["peak_price_seen"] = peak_price_seen
            pos["trailing_stop_pct"] = trailing_stop_pct
            pos["unrealized_pnl"] = self._compute_pnl_value(
                entry_price=entry_price,
                exit_price=current_price,
                contracts=_safe_int(pos.get("contracts"), 1),
                contract_multiplier=_safe_float(
                    pos.get("contract_multiplier"), CONTRACT_MULTIPLIER
                ),
            )

            if current_price <= _safe_float(pos.get("stop_loss_price")):
                events.append(
                    self.close_position(
                        option_symbol,
                        exit_price=current_price,
                        reason="SL",
                        closed_cycle=current_cycle,
                    )
                )
                continue

            if not trailing_active and current_price >= _safe_float(pos.get("take_profit_price")):
                trailing_active = True
                pos["trailing_active"] = True
                pos["note"] = self._append_note(
                    str(pos.get("note", "")),
                    f"TRAILING_ACTIVATED@cycle{current_cycle}",
                )

            if trailing_active:
                trailing_floor = peak_price_seen * (1.0 - trailing_stop_pct)
                pos["trailing_floor"] = trailing_floor

                if current_price <= trailing_floor:
                    events.append(
                        self.close_position(
                            option_symbol,
                            exit_price=current_price,
                            reason="TRAIL_TP",
                            closed_cycle=current_cycle,
                        )
                    )
                    continue

            if held_cycles >= _safe_int(pos.get("max_hold_cycles"), 3):
                if trailing_active and current_price >= entry_price:
                    pos["max_hold_cycles"] = held_cycles + 1
                    pos["note"] = self._append_note(
                        str(pos.get("note", "")),
                        f"TIME_EXTENDED@cycle{current_cycle}",
                    )
                else:
                    events.append(
                        self.close_position(
                            option_symbol,
                            exit_price=current_price,
                            reason="TIME",
                            closed_cycle=current_cycle,
                        )
                    )
                    continue

        return events

    def close_position(
        self,
        option_symbol: str,
        *,
        exit_price: float,
        reason: str,
        closed_cycle: int,
    ) -> Dict[str, Any]:
        option_symbol = str(option_symbol).strip().upper()
        pos = self.positions.get(option_symbol)

        if not pos:
            return {"status": "NOT_FOUND", "option_symbol": option_symbol}

        exit_price = _safe_float(exit_price)
        entry_price = _safe_float(pos.get("entry_price"))
        contracts = _safe_int(pos.get("contracts"), 1)
        multiplier = _safe_float(pos.get("contract_multiplier"), CONTRACT_MULTIPLIER)

        pnl_value = self._compute_pnl_value(
            entry_price=entry_price,
            exit_price=exit_price,
            contracts=contracts,
            contract_multiplier=multiplier,
        )
        pnl_pct = ((exit_price - entry_price) / entry_price) if entry_price > 0 else 0.0

        closed_trade = {
            **pos,
            "status": "CLOSED",
            "exit_price": exit_price,
            "closed_at": datetime.utcnow().isoformat(),
            "closed_cycle": closed_cycle,
            "reason": reason,
            "pnl": pnl_value,
            "pnl_pct": pnl_pct,
        }

        self.closed_log.append(closed_trade)
        self.positions.pop(option_symbol, None)

        return {
            "status": "CLOSED",
            "option_symbol": option_symbol,
            "reason": reason,
            "exit_price": exit_price,
            "pnl": pnl_value,
            "pnl_pct": pnl_pct,
        }

    def get_open_positions(self) -> List[Dict[str, Any]]:
        return list(self.positions.values())

    def get_closed_positions(self) -> List[Dict[str, Any]]:
        return list(self.closed_log)

    def get_total_open_unrealized(self, option_price_map: Dict[str, float]) -> float:
        total = 0.0
        for option_symbol, pos in self.positions.items():
            current_price = _safe_float(option_price_map.get(option_symbol))
            if current_price <= 0:
                continue
            total += self._compute_pnl_value(
                entry_price=_safe_float(pos.get("entry_price")),
                exit_price=current_price,
                contracts=_safe_int(pos.get("contracts"), 1),
                contract_multiplier=_safe_float(
                    pos.get("contract_multiplier"), CONTRACT_MULTIPLIER
                ),
            )
        return total

    def get_total_closed_realized(self) -> float:
        return sum(_safe_float(t.get("pnl")) for t in self.closed_log)

    def get_win_count(self) -> int:
        return sum(1 for t in self.closed_log if _safe_float(t.get("pnl")) > 0)

    def get_loss_count(self) -> int:
        return sum(1 for t in self.closed_log if _safe_float(t.get("pnl")) < 0)

    def _compute_pnl_value(
        self,
        *,
        entry_price: float,
        exit_price: float,
        contracts: int,
        contract_multiplier: float,
    ) -> float:
        if entry_price <= 0 or exit_price <= 0 or contracts <= 0 or contract_multiplier <= 0:
            return 0.0
        return (exit_price - entry_price) * contracts * contract_multiplier

    def _trail_pct_for_tier(self, tier: str) -> float:
        tier = str(tier).strip().upper()
        if tier == "ELITE":
            return 0.15
        if tier == "QUALIFIED":
            return 0.12
        return 0.10

    def _append_note(self, current_note: str, new_note: str) -> str:
        current_note = str(current_note or "").strip()
        new_note = str(new_note or "").strip()
        if not new_note:
            return current_note
        if not current_note:
            return new_note
        return f"{current_note} | {new_note}"
