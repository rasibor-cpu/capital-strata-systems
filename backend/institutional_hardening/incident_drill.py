from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncidentDrillScenario:
    scenario_id: str
    expected_state: str
    expected_alert: str


SCENARIOS = {
    "broker-disconnect": IncidentDrillScenario("broker-disconnect", "DEGRADED", "BROKER_DISCONNECTED"),
    "reconciliation-divergence": IncidentDrillScenario("reconciliation-divergence", "BLOCKED", "RECONCILIATION_DIVERGENCE"),
    "risk-breach": IncidentDrillScenario("risk-breach", "BLOCKED", "RISK_GATE_BLOCK"),
    "kill-switch": IncidentDrillScenario("kill-switch", "BLOCKED", "KILL_SWITCH_ENGAGED"),
    "session-lock": IncidentDrillScenario("session-lock", "BLOCKED", "SESSION_LOCKED"),
}


def run_incident_drill(scenario_id: str) -> dict:
    scenario = SCENARIOS[scenario_id]
    return {
        "scenario_id": scenario.scenario_id,
        "runtime_state": scenario.expected_state,
        "alert": scenario.expected_alert,
        "execution_allowed": False,
        "money_movement_allowed": False,
        "audit_replay_required": True,
    }
