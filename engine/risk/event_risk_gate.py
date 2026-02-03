"""
Event risk window gate.
Blocks NEW trades around high-impact macro events.
"""

from datetime import datetime, timedelta, timezone
from typing import List


class EventRiskGate:
    def __init__(
        self,
        block_before_minutes: int = 30,
        block_after_minutes: int = 30,
        min_severity: float = 0.6,
    ):
        self.block_before = timedelta(minutes=block_before_minutes)
        self.block_after = timedelta(minutes=block_after_minutes)
        self.min_severity = min_severity

    def _now(self):
        return datetime.now(timezone.utc)

    def _event_time(self, envelope) -> datetime | None:
        ts = envelope.get("ts_utc") or envelope.get("event_ts_utc")
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def _is_high_impact(self, envelope) -> bool:
        return (
            envelope.get("signal_class") in {"macro", "event"}
            and envelope.get("confidence", 0.0) >= self.min_severity
        )

    def blocks_new_trade(self, intel_envelopes: List[dict]) -> bool:
        """
        Returns True if NEW trades must be blocked.
        """
        now = self._now()

        for env in intel_envelopes:
            if not self._is_high_impact(env):
                continue

            evt_time = self._event_time(env)
            if not evt_time:
                continue

            if (evt_time - self.block_before) <= now <= (evt_time + self.block_after):
                return True

        return False

    def status(self, intel_envelopes: List[dict]) -> dict:
        blocked = self.blocks_new_trade(intel_envelopes)
        return {
            "event_risk_blocked": blocked,
            "checked_events": len(intel_envelopes),
            "block_before_minutes": int(self.block_before.total_seconds() / 60),
            "block_after_minutes": int(self.block_after.total_seconds() / 60),
        }


if __name__ == "__main__":
    # smoke test
    gate = EventRiskGate()

    future_event = {
        "signal_class": "event",
        "confidence": 0.9,
        "ts_utc": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }

    print("BLOCK:", gate.blocks_new_trade([future_event]))
    print("STATUS:", gate.status([future_event]))
