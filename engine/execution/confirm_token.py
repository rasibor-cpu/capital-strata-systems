# engine/execution/confirm_token.py
"""
6-char confirmation token generator (runtime only).
Alphanumeric, uppercase. TTL enforced elsewhere.
"""

from __future__ import annotations
import secrets
import string

ALPHABET = string.ascii_uppercase + string.digits

def generate_token(length: int = 6) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))
