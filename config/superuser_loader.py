# config/superuser_loader.py
"""
Superuser loader (file-based).

Source of truth: config/superuser.json
Fail-closed: if missing/invalid, raises RuntimeError.

Expected schema:
{
  "primary": {"name": "...", "email": "...", "phone_e164": "+1..."},
  "delegates": [...],
  "notify_channels": {"email": true, "sms": true}
}
"""

from __future__ import annotations
import json
import os
from typing import Any, Dict


PATH = os.path.join("config", "superuser.json")


def load_superuser() -> Dict[str, Any]:
    if not os.path.exists(PATH):
        raise RuntimeError("superuser.json missing (config/superuser.json)")
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        raise RuntimeError(f"superuser.json unreadable: {e}") from e

    primary = d.get("primary") or {}
    email = str(primary.get("email", "")).strip()
    phone = str(primary.get("phone_e164", "")).strip()

    if not email or "@" not in email:
        raise RuntimeError("superuser primary.email missing/invalid")
    if not phone or not phone.startswith("+") or len(phone) < 8:
        raise RuntimeError("superuser primary.phone_e164 missing/invalid")

    return d
