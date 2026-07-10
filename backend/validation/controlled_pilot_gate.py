"""
CSS Controlled Pilot Gate Decision Engine

Implements strict gate verification integrating real endurance validation,
operational acceptance, and governance constraints.
"""

from typing import Dict, Any, List

class ControlledPilotGate:
    """
    Final decision gate verifying Go/No-Go status for controlled live-capital pilots.
    """
    def __init__(
        self,
        endurance_evidence: Any = None,
        operational_acceptance: Any = None,
        governance_framework: Any = None,
        broker_readiness_score: float = 100.0,
        env_config_present: bool = True
    ):
        self.endurance_evidence = endurance_evidence
        self.operational_acceptance = operational_acceptance
        self.governance_framework = governance_framework
        self.broker_readiness_score = broker_readiness_score
        self.env_config_present = env_config_present

    def evaluate_gate(self) -> Dict[str, Any]:
        """
        Evaluates gate criteria. Returns GO, CONDITIONAL GO, or NO GO.
        """
        blockers = []
        warnings = []
        info = []
        actions = []

        # 1. Endurance Validation Checklist
        if self.endurance_evidence:
            endurance_res = self.endurance_evidence.evaluate_result()
            if endurance_res["result"] == "FAIL":
                blockers.append("endurance_check_failed")
                actions.append("Complete the 72-hour paper trading endurance validation run.")
                for b in endurance_res["blockers"]:
                    blockers.append(f"endurance_{b}")
            elif endurance_res["result"] == "CONDITIONAL PASS":
                warnings.append("endurance_check_has_warnings")
        else:
            blockers.append("endurance_evidence_missing")
            actions.append("Initialize endurance validation manager and collect session state.")

        # 2. Broker Readiness Gate
        if self.broker_readiness_score < 100.0:
            blockers.append("broker_readiness_degraded")
            actions.append("Confirm credential authentication and low latency for all active adapters.")
        else:
            info.append("broker_readiness_green")

        # 3. Operational Acceptance Gate
        if self.operational_acceptance:
            acceptance_res = self.operational_acceptance.validate_acceptance()
            if acceptance_res["status"] == "FAIL":
                blockers.append("operational_acceptance_failed")
                actions.append("Resolve failures in the Operational Acceptance Checklist.")
                for f in acceptance_res["failures"]:
                    blockers.append(f"acceptance_{f}")
            else:
                info.append("operational_acceptance_passed")
        else:
            blockers.append("operational_acceptance_unverified")

        # 4. Governance & Approvals Gate
        if self.governance_framework:
            gov_res = self.governance_framework.check_governance()
            if gov_res["status"] == "FAIL":
                blockers.append("governance_approvals_missing")
                actions.append("Collect operator sign-offs, deployment approvals, and risk authorizations.")
                for b in gov_res["blockers"]:
                    blockers.append(f"governance_{b}")
            if not gov_res["advisory_only"]:
                blockers.append("safeguards_not_locked")
                actions.append("Lock execution disarmed status before production pilot deployment.")
        else:
            blockers.append("governance_framework_unverified")

        # 5. Environment & Machine Stability
        if not self.env_config_present:
            blockers.append("environment_config_missing")
            actions.append("Ensure required production environment variables are stored in .env.")
        else:
            info.append("environment_config_verified")

        # Decision score
        status = "NO GO"
        if blockers:
            status = "NO GO"
        elif warnings:
            status = "CONDITIONAL GO"
        else:
            status = "GO"

        return {
            "decision": status,
            "blockers": blockers,
            "warnings": warnings,
            "informational_findings": info,
            "recommended_actions": actions
        }
