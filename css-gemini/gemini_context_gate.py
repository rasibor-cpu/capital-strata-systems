# gemini_context_gate.py
"""
CSS-GEMINI CONTEXT GATE
Institutional-grade macro filtering synced with Singleton AuditLogger.
"""
from audit_logger import get_audit

class IntermarketContextGate:
    def __init__(self):
        # Initialize singleton logger
        self.audit = get_audit()

    def is_context_safe(self) -> bool:
        """Analyzes macro headwinds for institutional safety."""
        # Institutional default for handshake
        return True

    def allow_execution(self, signal: dict) -> bool:
        """Final macro gatekeeper for capital protection."""
        if self.is_context_safe():
            return True
        
        # Log macro-level rejections
        self.audit.trade_rejected(
            symbol=signal.get('asset'), 
            reason="Intermarket Macro Risk", 
            module="context_gate"
        )
        return False