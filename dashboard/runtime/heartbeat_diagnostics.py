"""Classify a heartbeat observation into a specific failure mode.

OV-002 Attempt 2 raised two ``ENGINE_HEARTBEAT_LOST`` alerts that could not
say *why*: the watchdog only knew "no cycle for 600 s". A dead engine, a hung
process, a blocked event loop, a stalled monitor, a wall-clock jump, a
process still starting up and an operator-requested stop all looked the
same. This classifier separates them using:

* the runtime's heartbeat *sequence number* (not its wall-clock stamp), and
  the monitor's monotonic clock for when that sequence last advanced, so a
  wall-clock jump cannot fake or hide a gap;
* two independent beats from the runtime: a background thread
  (``thread_seq``) and the server's asyncio event loop (``loop_seq``);
* whether the PID is alive, and the supervisor's own state.

Thresholds are the existing governed values from
``runtime_operational_state`` (STALE after 60 s, LOST after 180 s). They are
imported, not redefined, so they cannot be loosened here to make a soak pass.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from dashboard.runtime.runtime_operational_state import (
    _HEARTBEAT_LOST_SECONDS as LOST_SECONDS,
    _HEARTBEAT_STALE_SECONDS as STALE_SECONDS,
)

# Bounded, and shorter than LOST: a runtime that never produces a first beat
# is classified as lost once the grace expires, measured from launch.
STARTUP_GRACE_SECONDS = 120
# Wall clock vs monotonic divergence beyond this is a clock anomaly.
CLOCK_ANOMALY_SECONDS = 30

HEALTHY = "HEALTHY"
STALE = "STALE"
STARTUP_GRACE = "STARTUP_GRACE"
CONTROLLED_SHUTDOWN = "CONTROLLED_SHUTDOWN"
ENGINE_TERMINATED = "ENGINE_TERMINATED"
PROCESS_HUNG = "PROCESS_HUNG"
EVENT_LOOP_BLOCKED = "EVENT_LOOP_BLOCKED"
MONITOR_GAP = "MONITOR_GAP"
CLOCK_ANOMALY = "CLOCK_ANOMALY"
NO_HEARTBEAT_SOURCE = "NO_HEARTBEAT_SOURCE"

# Classes that mean the supervised runtime itself lost its heartbeat.
CRITICAL_RUNTIME_LOSS = frozenset({ENGINE_TERMINATED, PROCESS_HUNG, EVENT_LOOP_BLOCKED, NO_HEARTBEAT_SOURCE})


@dataclass(frozen=True)
class HeartbeatObservation:
    monitor_gap_seconds: float          # monotonic time since the monitor's previous tick
    seconds_since_launch: float         # monotonic, since the current child was launched
    thread_gap_seconds: float | None    # monotonic, since thread_seq last advanced (None: never seen)
    loop_gap_seconds: float | None      # monotonic, since loop_seq last advanced (None: never seen)
    pid: int | None
    pid_alive: bool
    shutdown_requested: bool
    wall_minus_monotonic_drift_seconds: float = 0.0  # step since the previous observation


@dataclass(frozen=True)
class HeartbeatClassification:
    classification: str
    critical: bool
    gap_seconds: float | None
    reason: str
    expected_interval_seconds: float | None = None
    stale_threshold_seconds: int = STALE_SECONDS
    lost_threshold_seconds: int = LOST_SECONDS

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_heartbeat(obs: HeartbeatObservation, *, expected_interval_seconds: float | None = None) -> HeartbeatClassification:
    def result(cls: str, gap: float | None, reason: str) -> HeartbeatClassification:
        return HeartbeatClassification(
            classification=cls,
            critical=cls in CRITICAL_RUNTIME_LOSS,
            gap_seconds=gap,
            reason=reason,
            expected_interval_seconds=expected_interval_seconds,
        )

    if obs.shutdown_requested:
        return result(CONTROLLED_SHUTDOWN, None, "supervisor recorded an operator/signal shutdown request")
    # The monitor itself stalled: whatever the runtime did meanwhile was not
    # observed. Not a runtime failure, but continuity is unverified.
    if obs.monitor_gap_seconds > LOST_SECONDS:
        return result(MONITOR_GAP, obs.monitor_gap_seconds, "the monitor did not run for longer than the LOST threshold")
    if not obs.pid_alive:
        return result(ENGINE_TERMINATED, obs.thread_gap_seconds, "runtime PID is not alive")
    if obs.thread_gap_seconds is None:
        if obs.seconds_since_launch <= STARTUP_GRACE_SECONDS:
            return result(STARTUP_GRACE, None, "runtime launched recently and has not produced a first heartbeat")
        if obs.seconds_since_launch > LOST_SECONDS:
            return result(NO_HEARTBEAT_SOURCE, obs.seconds_since_launch, "no heartbeat ever observed since launch")
        return result(STALE, obs.seconds_since_launch, "first heartbeat overdue")
    if obs.thread_gap_seconds > LOST_SECONDS:
        return result(PROCESS_HUNG, obs.thread_gap_seconds, "PID alive but the heartbeat thread stopped advancing")
    if obs.loop_gap_seconds is not None and obs.loop_gap_seconds > LOST_SECONDS:
        return result(EVENT_LOOP_BLOCKED, obs.loop_gap_seconds, "heartbeat thread alive but the server event loop stopped advancing")
    if obs.loop_gap_seconds is None and obs.seconds_since_launch > LOST_SECONDS:
        return result(EVENT_LOOP_BLOCKED, obs.seconds_since_launch, "server event loop never produced a beat")
    # Checked only after every runtime-loss case: a wall-clock step must never
    # mask a real loss, and gaps are measured monotonically anyway.
    if abs(obs.wall_minus_monotonic_drift_seconds) > CLOCK_ANOMALY_SECONDS:
        return result(CLOCK_ANOMALY, None, "wall clock stepped relative to the monotonic clock since the last observation")
    worst = max(g for g in (obs.thread_gap_seconds, obs.loop_gap_seconds) if g is not None)
    if worst > STALE_SECONDS:
        return result(STALE, worst, "heartbeat older than the STALE threshold")
    return result(HEALTHY, worst, "thread and event-loop beats are current")


__all__ = [
    "CLOCK_ANOMALY", "CONTROLLED_SHUTDOWN", "CRITICAL_RUNTIME_LOSS", "ENGINE_TERMINATED", "EVENT_LOOP_BLOCKED",
    "HEALTHY", "HeartbeatClassification", "HeartbeatObservation", "LOST_SECONDS", "MONITOR_GAP",
    "NO_HEARTBEAT_SOURCE", "PROCESS_HUNG", "STALE", "STALE_SECONDS", "STARTUP_GRACE", "STARTUP_GRACE_SECONDS",
    "classify_heartbeat",
]
