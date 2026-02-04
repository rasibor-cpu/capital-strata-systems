# config/superuser.py
"""
Superuser loader stub (file-based, fail-closed)

Source of truth: config/superuser.json

This is a minimal, stable loader so the engine can always resolve:
- primary.email
- primary.phone_e164
- optional delegates

No sending logic lives here.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict


PATH = os.path.join("config", "superuser.json")


def _fail(msg: str) -> RuntimeError:
    return RuntimeError(f"superuser config error: {msg}")


def load_superuser() -> Dict[str, Any]:
    if not os.path.exists(PATH):
        raise _fail("missing config/superuser.json")

    try:
        with open(PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        raise _fail(f"unreadable JSON: {e}")

    primary = d.get("primary")
    if not isinstance(primary, dict):
        raise _fail("primary object missing")

    email = str(primary.get("email", "")).strip()
    phone = str(primary.get("phone_e164", "")).strip()

    if not email or "@" not in email:
        raise _fail("primary.email missing/invalid")
    if not phone or not phone.startswith("+") or len(phone) < 8:
        raise _fail("primary.phone_e164 missing/invalid")

    # Delegates optional
    delegates = d.get("delegates", [])
    if delegates is None:
        delegates = []
    if not isinstance(delegates, list):
        raise _fail("delegates must be a list if present")

    # notify_channels optional; default to both enabled
    nc = d.get("notify_channels", {"email": True, "sms": True})
    if not isinstance(nc, dict):
        nc = {"email": True, "sms": True}

    # Normalize output
    d["primary"]["email"] = email
    d["primary"]["phone_e164"] = phone
    d["delegates"] = delegates
    d["notify_channels"] = {
        "email": bool(nc.get("email", True)),
        "sms": bool(nc.get("sms", True)),
    }
    return d
