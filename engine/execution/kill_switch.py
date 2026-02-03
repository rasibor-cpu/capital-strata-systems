"""
REA Capital Trading Engine
Global Kill Switch (Execution Control – Layer 5)

Constitutional Authority:
- Layer 5: Execution Control
- This module has GLOBAL VETO power
- Once triggered, execution is frozen until manual reset

Doctrine:
- Unexpected behavior = FREEZE
- No auto-resume
- No retries
- No silent recovery
"""

from dataclasses import dataclass
from typing import Optional
import time


# -----------------------------
# Kill Switch State (Immutable)
# -----------------------------
@dataclass(frozen=True)
class KillSwitchState:
    engaged: bool
    reason: str
    triggered_by: str
    timestamp: float


# -----------------------------
# Kill Switch Controller
# -----------------------------
class KillSwitch:
    """
    KillSwitch enforces global execution freeze.
    Once engaged, it blocks ALL execution paths
    until explicitly reset by an authorized process.
    """

    def __init__(self):
        self._state: Optional[KillSwitchState] = None

    # -------------------------
    # Trigger Kill Switch
    # -------------------------
    def trigger(self, reason: str, triggered_by: str) -> KillSwitchState:
        """
        Engage the kill switch.
        Idempotent: once engaged, state cannot change.
        """
        if self._state is not None:
            return self._state

        self._state = KillSwitchState(
            engaged=True,
            reason=reason,
            triggered_by=triggered_by,
            timestamp=time.time(),
        )
        return self._state

    # -------------------------
    # Check Status
    # -------------------------
    def is_engaged(self) -> bool:
        return self._state is not None and self._state.engaged

    def current_state(self) -> Optional[KillSwitchState]:
        return self._state

    # -------------------------
    # Manual Reset (Governed)
    # -------------------------
    def reset(self, authorized: bool, justification: str) -> bool:
        """
        Reset requires:
        - Explicit authorization
        - Human justification (logged externally)
        """
        if not authorized:
            raise PermissionError(
                "KillSwitch reset denied: authorization required"
            )

        if not justification or justification.strip() == "":
            raise ValueError(
                "KillSwitch reset denied: justification required"
            )

        self._state = None
        return True


# -----------------------------
# Constitutional Assertion
# -----------------------------
if __name__ == "__main__":
    raise RuntimeError(
        "KillSwitch is not executable standalone. "
        "It must be controlled by the Execution Control pipeline."
    )
