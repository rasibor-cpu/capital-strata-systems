"""
Trade & Position Event Vocabulary (v1)
-------------------------------------
Canonical vocabulary for all trading, ledger, and exposure-relevant events.

Why this exists:
- Prevents inconsistent action strings across modules
- Guarantees reporting, exposure tracking, and audits align
- Enables safe future upgrades (MTM, GL, IFRS, Basel, etc.)

RULE:
All trade / ledger / position actions MUST come from this file.
"""

from enum import Enum


class TradeEvent(str, Enum):
    # ─────────────────────────────
    # Orders & execution
    # ─────────────────────────────
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_CANCELLED = "ORDER_CANCELLED"

    EXECUTE_TRADE = "EXECUTE_TRADE"     # definitive execution event

    # ─────────────────────────────
    # Position lifecycle
    # ─────────────────────────────
    OPEN_POSITION = "OPEN_POSITION"
    CLOSE_POSITION = "CLOSE_POSITION"

    # ─────────────────────────────
    # Directional exposure events
    # (used by exposure tracker)
    # ─────────────────────────────
    BUY = "BUY"
    SELL = "SELL"

    # ─────────────────────────────
    # Ledger-style movements
    # (used for balances & GL mapping)
    # ─────────────────────────────
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"

    # ─────────────────────────────
    # Administrative / risk actions
    # ─────────────────────────────
    LIMIT_SET = "LIMIT_SET"
    LIMIT_BREACH_ATTEMPT = "LIMIT_BREACH_ATTEMPT"
    LIMIT_BREACH_BLOCKED = "LIMIT_BREACH_BLOCKED"

    RISK_OVERRIDE_REQUESTED = "RISK_OVERRIDE_REQUESTED"
    RISK_OVERRIDE_APPROVED = "RISK_OVERRIDE_APPROVED"
    RISK_OVERRIDE_REJECTED = "RISK_OVERRIDE_REJECTED"