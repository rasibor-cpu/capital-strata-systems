# engine/execution/notify_outbox.py
"""
Runtime notification outbox (email + SMS).
Writes masked destination + token. No real sending here.
"""

from __future__ import annotations
import os
from datetime import datetime, timezone

OUT_EMAIL = os.path.join("audit", "outbox_emails")
OUT_SMS = os.path.join("audit", "outbox_sms")

def _utc():
    return datetime.now(timezone.utc).isoformat()

def _mask_email(e: str) -> str:
    name, _, dom = e.partition("@")
    return f"{name[:2]}***@{dom}"

def _mask_phone(p: str) -> str:
    return f"+***{p[-4:]}"

def write_email(email: str, token: str) -> str:
    os.makedirs(OUT_EMAIL, exist_ok=True)
    fn = os.path.join(OUT_EMAIL, f"confirm_{token}.txt")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(f"UTC: {_utc()}\nCHANNEL: email\nTO: {_mask_email(email)}\nTOKEN: {token}\n")
    return fn

def write_sms(phone_e164: str, token: str) -> str:
    os.makedirs(OUT_SMS, exist_ok=True)
    fn = os.path.join(OUT_SMS, f"confirm_{token}.txt")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(f"UTC: {_utc()}\nCHANNEL: sms\nTO: {_mask_phone(phone_e164)}\nTOKEN: {token}\n")
    return fn
