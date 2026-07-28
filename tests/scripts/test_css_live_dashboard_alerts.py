import os
import sys
import pytest
from unittest.mock import patch, MagicMock
import builtins

from backend.monitoring.css_alert_models import AlertSeverity


@pytest.fixture(scope="module")
def dashboard():
    os.environ["CSS_TEST_MODE"] = "1"

    mock_auth = MagicMock()
    mock_auth.await_login_ready_state.return_value = {"user_id": "test_user", "role": "admin"}
    sys.modules["dashboard.auth.css_sign_on"] = mock_auth

    builtins.input = lambda prompt="": "1"

    import scripts.css_live_dashboard as db
    return db


def test_safe_emit_alert_emits_successfully(dashboard):
    with patch.object(dashboard, 'css_runtime_alert_service') as mock_service:
        dashboard._safe_emit_alert("emit_engine_alert", severity=AlertSeverity.INFO, message="Test Start", metadata={"key": "secret", "cycle": 1})
        
        mock_service.emit_engine_alert.assert_called_once()
        _, kwargs = mock_service.emit_engine_alert.call_args
        assert kwargs["severity"] == AlertSeverity.INFO
        assert kwargs["message"] == "Test Start"
        assert kwargs["source"] == "css_live_dashboard"
        assert kwargs["metadata"]["cycle"] == 1
        assert "key" not in kwargs["metadata"]  # Sanitized

def test_safe_emit_alert_does_not_crash_on_exception(dashboard):
    with patch.object(dashboard, 'css_runtime_alert_service') as mock_service:
        mock_service.emit_engine_alert.side_effect = Exception("Simulated Alert Failure")
        
        # Should not raise
        dashboard._safe_emit_alert("emit_engine_alert", severity=AlertSeverity.INFO, message="Will Fail")

def test_safe_emit_alert_ignores_if_service_none(dashboard):
    with patch.object(dashboard, 'css_runtime_alert_service', None):
        # Should not raise and just return
        dashboard._safe_emit_alert("emit_engine_alert", severity=AlertSeverity.INFO, message="Ignored")
