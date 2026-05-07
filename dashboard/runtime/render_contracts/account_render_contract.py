from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountRenderContract:
    """
    PCNRASS-safe immutable render contract for account display.

    Rules:
    - Renderer consumes this contract only.
    - Renderer performs no account calculations.
    - Account values must come from normalized account state.
    """

    cash_balance: float
    total_equity: float
    buying_power: float
    margin_used: float
    available_margin: float
    currency: str
    broker: str
    account_mode: str

    @classmethod
    def from_account_state(cls, account_state: dict) -> "AccountRenderContract":
        state = account_state or {}

        return cls(
            cash_balance=float(state.get("cash_balance", state.get("balance", 0.0))),
            total_equity=float(state.get("total_equity", state.get("equity", 0.0))),
            buying_power=float(state.get("buying_power", 0.0)),
            margin_used=float(state.get("margin_used", 0.0)),
            available_margin=float(state.get("available_margin", 0.0)),
            currency=str(state.get("currency", "USD")),
            broker=str(state.get("broker", state.get("selected_broker", "UNKNOWN"))),
            account_mode=str(state.get("account_mode", state.get("mode", "paper"))),
        )