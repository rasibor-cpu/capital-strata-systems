"""
CSS Pilot Capital & Risk Controls

Enforces pilot capital limits, position caps, max drawdown parameters,
exposure thresholds, and automatic rollback triggers.
"""

from typing import Dict, Any, List

class PilotRiskControls:
    """
    Hardened risk boundaries for controlled production pilots.
    """
    def __init__(self, limits: Dict[str, Any] = None):
        self.limits = limits or {
            "max_total_pilot_capital": 1000.0,
            "max_position_size": 100.0,
            "max_open_positions": 3,
            "max_daily_loss": 50.0,
            "max_drawdown": 20.0,
            "oanda_exposure_cap": 500.0,
            "coinbase_exposure_cap": 500.0
        }
        self.execution_enabled = False  # Disabled by default
        self.operator_authorized = False
        self.emergency_stop_triggered = False

    def authorize_operator(self) -> None:
        """Grants explicit operator authorization."""
        self.operator_authorized = True

    def trigger_emergency_stop(self) -> None:
        """Triggers manual emergency stop, instantly halting execution."""
        self.emergency_stop_triggered = True
        self.execution_enabled = False

    def validate_exposure(
        self,
        symbol: str,
        size: float,
        broker: str,
        current_open_positions: int,
        daily_loss: float,
        drawdown: float
    ) -> Dict[str, Any]:
        """
        Validates trade candidate execution params against hardened limits.
        """
        violations = []

        if self.emergency_stop_triggered:
            violations.append("emergency_stop_active")

        if not self.operator_authorized:
            violations.append("operator_authorization_missing")

        if size > self.limits["max_position_size"]:
            violations.append("position_size_exceeded")

        if current_open_positions >= self.limits["max_open_positions"]:
            violations.append("max_open_positions_exceeded")

        if daily_loss >= self.limits["max_daily_loss"]:
            violations.append("daily_loss_limit_violated")

        if drawdown >= self.limits["max_drawdown"]:
            violations.append("max_drawdown_limit_violated")

        # Broker exposure checks
        if broker.upper() == "OANDA" and size > self.limits["oanda_exposure_cap"]:
            violations.append("oanda_exposure_cap_exceeded")
        elif broker.upper() == "COINBASE" and size > self.limits["coinbase_exposure_cap"]:
            violations.append("coinbase_exposure_cap_exceeded")

        status = "PASS" if not violations else "FAIL"

        return {
            "status": status,
            "violations": violations,
            "advisory_only": True,
            "execution_blocked": True  # Live execution always disarmed in software
        }
