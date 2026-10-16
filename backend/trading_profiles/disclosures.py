"""User disclosures for operating modes and copy trading.

A user must acknowledge the current disclosure version before any copied or
autonomous trade is evaluated. Changing the text requires a new version, which
forces re-acknowledgement.
"""
from __future__ import annotations

import hashlib

DISCLOSURE_VERSION = "CSS-TP-DISCLOSURE-2026-10-16.1"

DISCLOSURE_TEXT = (
    "Trading profiles and copy trading in CSS.\n"
    "1. All activity in this release is simulated or paper only. Selecting a mode, a risk "
    "personality or a trader does not authorize live trading or send orders to a broker.\n"
    "2. Copying a CSS trader does not copy their orders one-for-one. Your risk personality "
    "decides which of the trader's signals you take, how large your positions are, and when "
    "they are exited. Your fills, positions and profit or loss will differ from the trader's.\n"
    "3. Every copied trade must still pass the CSS safety gates (unified trade gate, "
    "profitability gate, AntiBleedGuard costs, minimum size and cooldown, margin and risk "
    "limits, kill switch and position caps). Many signals will be skipped for that reason.\n"
    "4. Past results of a trader or a personality do not predict future results. Trading "
    "losses are possible, including in simulation, and ordinary trading losses are not "
    "reimbursed or guaranteed.\n"
    "5. Your copy authorization is limited to the trader, personality, scope and expiry you "
    "approve, must be renewed on the agreed schedule, and can be revoked at any time. When it "
    "expires or is revoked, no new trades are copied; open positions are only managed to a "
    "safe exit.\n"
)

DISCLOSURE_SHA256 = hashlib.sha256(DISCLOSURE_TEXT.encode("utf-8")).hexdigest()


def current_disclosure() -> dict:
    return {"version": DISCLOSURE_VERSION, "sha256": DISCLOSURE_SHA256, "text": DISCLOSURE_TEXT}
