"""
Instruments Package – Startup Validation
=======================================

This package enforces the governance-locked instrument mapping invariant.

On import:
- Validate Strategy → Canonical → Broker mapping integrity.
- Hard-fail if mapping is missing/ambiguous.

Note:
This does not validate per-adapter symbol availability at import time,
because adapter selection is session-specific. That check happens at resolution time.
"""

from __future__ import annotations

from engine.instruments.mapping import validate_or_raise

# Hard-fail on mapping integrity issues (governance invariant)
validate_or_raise()
