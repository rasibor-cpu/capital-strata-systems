import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Prevent infinite loop on import
os.environ["CSS_TEST_MODE"] = "1"
os.environ["OANDA_API_KEY"] = "mock"
os.environ["OANDA_ACCOUNT_ID"] = "mock"

# Patch things BEFORE import so module level stuff doesn't hang
mock_auth = MagicMock()
mock_auth.await_login_ready_state.return_value = {
    "user_id": "test", 
    "role": "admin", 
    "display_name": "test", 
    "unit_code": "test", 
    "home_branch": "test"
}
sys.modules["dashboard.auth.css_sign_on"] = mock_auth
sys.modules["builtins"].input = lambda prompt: "1"

import scripts.css_live_dashboard as dashboard

def test_manual_mode_default_pauses_for_input():
    if "CSS_AUTO_CYCLE" in os.environ:
        del os.environ["CSS_AUTO_CYCLE"]
        
    with patch("builtins.input", return_value="1") as mock_input, \
         patch("time.sleep") as mock_sleep:
        
        result = dashboard.pcnrass_wait_for_next_cycle(1)
        
        assert result is True
        mock_input.assert_called_once()
        mock_sleep.assert_not_called()

def test_auto_cycle_mode_skips_input_and_sleeps():
    with patch.dict(os.environ, {"CSS_AUTO_CYCLE": "true", "CSS_CYCLE_SLEEP_SECONDS": "10"}):
        with patch("builtins.input") as mock_input, \
             patch("time.sleep") as mock_sleep:
            
            result = dashboard.pcnrass_wait_for_next_cycle(2)
            
            assert result is True
            mock_input.assert_not_called()
            mock_sleep.assert_called_once_with(10)
