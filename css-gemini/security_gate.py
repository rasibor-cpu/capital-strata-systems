# security_gate.py
"""
CSS-GEMINI OPERATIONAL FIREWALL
Acts as the master kill-switch and system health check.
"""
from audit_logger import get_audit

class SecurityGate:
    def __init__(self):
        self.audit = get_audit()
        self.is_halted = False
        self.reason = None

    def check_system_integrity(self) -> bool:
        """The master check that the Orchestrator calls before every cycle."""
        if self.is_halted:
            self.audit.log("ENGINE_HALT", "security_gate", {"reason": self.reason}, level="CRITICAL")
            return False
        return True

    def trigger_kill_switch(self, reason: str):
        """Emergency method to stop all system activity instantly."""
        self.is_halted = True
        self.reason = reason
        self.audit.log("ENGINE_HALT", "security_gate", {"action": "emergency_stop", "reason": reason}, level="CRITICAL")

    def reset_gate(self):
        """Manual reset required after a halt event."""
        self.is_halted = False
        self.reason = None
        self.audit.log("ENGINE_RESUME", "security_gate", {"status": "operational"})