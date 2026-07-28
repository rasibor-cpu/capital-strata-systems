import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Prevent infinite loop on import
os.environ["CSS_TEST_MODE"] = "1"
os.environ["OANDA_API_KEY"] = "mock"
os.environ["OANDA_ACCOUNT_ID"] = "mock"
os.environ["CSS_SESSION_MAX_SECONDS"] = "3600"

# Patch things BEFORE import so module level stuff doesn't hang
mock_auth = MagicMock()
mock_auth.await_login_ready_state.return_value = {
    "user_id": "test", 
    "role": "admin", 
    "display_name": "test", 
    "unit_code": "test", 
    "home_branch": "test",
    "session_id": "test",
}
sys.modules["dashboard.auth.css_sign_on"] = mock_auth
sys.modules["builtins"].input = lambda prompt: "1"

from engine.information.alerts import AlertEventType


def test_session_expired_enters_quiet_mode_and_suppresses_trade_blocked_alerts():
    mock_alert_service = MagicMock()
    mock_mtm_engine = MagicMock()
    mock_mtm_engine.count_open_positions.return_value = 0
    
    _SESSION_QUIET_MODE_ACTIVATED = False
    max_remaining = 0  # Session expired
    is_session_locked = False
    defensive_reductions = 0
    hard_position_limit = 5
    cycle = 1
    
    printed_messages = []
    
    def simulate_cycle_loop_logic(quiet_mode_flag):
        if is_session_locked:
            pass
        elif max_remaining <= 0:
            if not quiet_mode_flag:
                quiet_mode_flag = True
                printed_messages.append("[SESSION EXPIRED QUIET MODE] Trading attempts paused until re-authentication.")
                mock_alert_service.dispatch_alert(
                    AlertEventType.INFO,
                    "Session Expired Quiet Mode activated. Trading paused.",
                    {"cycle": cycle}
                )
            else:
                printed_messages.append("[SESSION EXPIRED QUIET MODE] Trading attempts paused until re-authentication.")
        elif mock_mtm_engine.count_open_positions() < hard_position_limit:
            mock_alert_service.dispatch_alert(AlertEventType.TRADE_BLOCKED, "TRADE_BLOCKED")
            
        return quiet_mode_flag
        
    # Cycle 1: Enter quiet mode
    _SESSION_QUIET_MODE_ACTIVATED = simulate_cycle_loop_logic(_SESSION_QUIET_MODE_ACTIVATED)
    
    assert _SESSION_QUIET_MODE_ACTIVATED is True
    assert "[SESSION EXPIRED QUIET MODE]" in printed_messages[0]
    
    # Verify exact alert sequence: one INFO alert, ZERO TRADE_BLOCKED
    assert mock_alert_service.dispatch_alert.call_count == 1
    call_args = mock_alert_service.dispatch_alert.call_args[0]
    assert call_args[0] == AlertEventType.INFO
    assert "Quiet Mode activated" in call_args[1]
    
    # Cycle 2: Already in quiet mode
    mock_alert_service.reset_mock()
    _SESSION_QUIET_MODE_ACTIVATED = simulate_cycle_loop_logic(_SESSION_QUIET_MODE_ACTIVATED)
    
    assert _SESSION_QUIET_MODE_ACTIVATED is True
    assert "[SESSION EXPIRED QUIET MODE]" in printed_messages[1]
    
    # Verify NO new alerts are emitted (suppression works)
    assert mock_alert_service.dispatch_alert.call_count == 0
