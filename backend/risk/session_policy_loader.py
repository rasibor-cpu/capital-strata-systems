"""
Capital Strata Systems (CSS)
Session Policy Loader

Interactive startup loader for selecting or defining the
risk policy that governs the session. The selected policy
is validated and then locked for the duration of the run.

Controlled Risk Governance. Controlled Compounding.
"""

from __future__ import annotations

from dataclasses import replace
from typing import List

from backend.risk.session_risk_policy import (
    SessionRiskPolicy,
    aggressive_test_policy,
    balanced_policy,
    conservative_policy,
    custom_policy,
)


def _prompt_nonempty(prompt_text: str) -> str:
    while True:
        value = input(prompt_text).strip()
        if value:
            return value
        print("Value cannot be blank.")


def _prompt_float(prompt_text: str) -> float:
    while True:
        raw = input(prompt_text).strip()
        try:
            value = float(raw)
            return value
        except ValueError:
            print("Enter a valid number.")


def _prompt_int(prompt_text: str) -> int:
    while True:
        raw = input(prompt_text).strip()
        try:
            value = int(raw)
            return value
        except ValueError:
            print("Enter a valid integer.")


def _prompt_bool(prompt_text: str) -> bool:
    while True:
        raw = input(prompt_text).strip().lower()
        if raw in {"y", "yes", "true", "1"}:
            return True
        if raw in {"n", "no", "false", "0"}:
            return False
        print("Enter yes or no.")


def _prompt_pct(prompt_text: str) -> float:
    while True:
        value = _prompt_float(prompt_text)
        if 0.0 < value <= 1.0:
            return value
        print("Enter a decimal greater than 0.0 and not more than 1.0 (example: 0.60).")


def _prompt_csv_list(prompt_text: str) -> List[str]:
    while True:
        raw = input(prompt_text).strip()
        items = [item.strip() for item in raw.split(",") if item.strip()]
        if items:
            return items
        print("Enter at least one value.")


def _apply_balanced_small_account_override(
    policy: SessionRiskPolicy,
    starting_capital: float,
) -> SessionRiskPolicy:
    """
    Small-account override for Balanced mode.

    For very small accounts, allocator outputs around $60-$75 can exceed
    conservative default single-asset caps. We create and return a new
    replaced frozen dataclass instance with a higher per-asset cap.

    This override is intentionally limited to small accounts.
    """
    if starting_capital > 1000:
        return policy

    replacement_fields = {}

    if hasattr(policy, "max_asset_pct"):
        replacement_fields["max_asset_pct"] = 0.40

    if hasattr(policy, "max_asset_exposure"):
        replacement_fields["max_asset_exposure"] = 0.40

    if hasattr(policy, "max_capital_deployed_pct"):
        replacement_fields["max_capital_deployed_pct"] = 0.90

    if not replacement_fields:
        return policy

    return replace(policy, **replacement_fields)


def choose_session_policy(starting_capital: float) -> SessionRiskPolicy:
    print("\n=== CSS Session Risk Policy Loader ===")
    print("Select a startup policy:")
    print("1. Conservative")
    print("2. Balanced")
    print("3. Aggressive Test")
    print("4. Custom")

    while True:
        choice = input("Enter choice (1/2/3/4): ").strip()

        if choice == "1":
            return conservative_policy(starting_capital)

        if choice == "2":
            policy = balanced_policy(starting_capital)
            return _apply_balanced_small_account_override(policy, starting_capital)

        if choice == "3":
            return aggressive_test_policy(starting_capital)

        if choice == "4":
            return _build_custom_policy(starting_capital)

        print("Invalid choice. Enter 1, 2, 3, or 4.")


def _build_custom_policy(starting_capital: float) -> SessionRiskPolicy:
    print("\n=== CSS Custom Session Policy ===")

    policy_name = _prompt_nonempty("Policy name: ")
    max_capital_deployed_pct = _prompt_pct(
        "Max capital deployed pct (decimal, e.g. 0.60): "
    )
    max_asset_pct = _prompt_pct(
        "Max per-asset exposure pct (decimal, e.g. 0.15): "
    )
    max_concurrent_trades = _prompt_int("Max concurrent trades: ")
    max_daily_loss_usd = _prompt_float("Max daily loss USD: ")
    max_weekly_drawdown_usd = _prompt_float("Max weekly drawdown USD: ")
    allowed_asset_classes = _prompt_csv_list(
        "Allowed asset classes (comma-separated, e.g. crypto_spot,fx_spot): "
    )
    broker_mode = _prompt_nonempty("Broker mode (paper/live): ").lower()
    strategy_mode = _prompt_nonempty("Strategy mode: ")
    session_expiry_time = _prompt_nonempty("Session expiry time (e.g. 17:00): ")
    allow_live_trading = _prompt_bool("Allow live trading? (yes/no): ")

    return custom_policy(
        policy_name=policy_name,
        starting_capital=starting_capital,
        max_capital_deployed_pct=max_capital_deployed_pct,
        max_asset_pct=max_asset_pct,
        max_concurrent_trades=max_concurrent_trades,
        max_daily_loss_usd=max_daily_loss_usd,
        max_weekly_drawdown_usd=max_weekly_drawdown_usd,
        allowed_asset_classes=allowed_asset_classes,
        broker_mode=broker_mode,
        strategy_mode=strategy_mode,
        session_expiry_time=session_expiry_time,
        allow_live_trading=allow_live_trading,
    )