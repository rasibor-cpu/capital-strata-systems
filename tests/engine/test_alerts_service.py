import pytest
from engine.information.alerts import AlertService, AlertEventType, get_alert_service

def test_alert_service_records_history():
    service = AlertService()
    service.dispatch_alert(AlertEventType.INFO, "Test message", {"foo": "bar"})
    
    assert len(service.history) == 1
    assert service.history[0]["type"] == "INFO"
    assert service.history[0]["message"] == "Test message"
    assert service.history[0]["context"] == {"foo": "bar"}

def test_alert_service_fail_safe():
    service = AlertService()
    # Mocking internal state to force an exception
    service.history = None
    
    # Should not raise an exception
    service.dispatch_alert(AlertEventType.INFO, "Fail-safe test")

def test_global_service_singleton():
    service1 = get_alert_service()
    service2 = get_alert_service()
    assert service1 is service2
