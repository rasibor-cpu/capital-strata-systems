import os
import sys
import tempfile
import pytest

from launcher.css_service_manager import CSSServiceManager
from launcher.css_runtime_launcher import check_environment

def test_css_service_manager_lifecycle():
    # Use a simple cross-platform command that exits quickly
    cmd = [sys.executable, "-c", "print('Hello World')"]
    svc = CSSServiceManager("Test Service", cmd, os.getcwd())
    
    assert svc.status == "STOPPED"
    
    # Start service
    started = svc.start()
    assert started is True
    assert svc.status == "RUNNING"
    assert svc.pid is not None
    
    # Wait for it to finish
    svc.process.wait()
    
    # Check status again
    status = svc.check_status()
    assert status == "STOPPED"
    assert svc.pid is None
    
def test_css_service_manager_failure():
    # A command that intentionally fails
    cmd = [sys.executable, "-c", "import sys; sys.exit(1)"]
    svc = CSSServiceManager("Fail Service", cmd, os.getcwd())
    
    svc.start()
    svc.process.wait()
    
    status = svc.check_status()
    assert status == "FAILED"

def test_css_service_manager_stop():
    # A command that sleeps
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    svc = CSSServiceManager("Sleep Service", cmd, os.getcwd())
    
    svc.start()
    assert svc.status == "RUNNING"
    
    svc.stop()
    assert svc.status == "STOPPED"
    assert svc.pid is None

def test_check_environment_fails_when_port_in_use(monkeypatch):
    import socket
    # Mock is_port_in_use to True
    monkeypatch.setattr("launcher.css_runtime_launcher.is_port_in_use", lambda p: True)
    
    # Even if files exist, port check should fail it
    assert check_environment() is False
