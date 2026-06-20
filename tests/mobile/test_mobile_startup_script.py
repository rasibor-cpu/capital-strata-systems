import os
import pytest
from unittest.mock import patch
from scripts.start_css_mobile_app import build_startup_config, print_instructions
import io
import sys

def test_default_local_host():
    with patch.dict(os.environ, {}, clear=True):
        config = build_startup_config()
        assert config["host"] == "127.0.0.1"
        assert config["port"] == 8090
        assert config["allow_lan"] is False

def test_lan_host_when_env_var_enabled():
    with patch.dict(os.environ, {"CSS_MOBILE_LAN": "true"}, clear=True):
        config = build_startup_config()
        assert config["host"] == "0.0.0.0"
        assert config["port"] == 8090
        assert config["allow_lan"] is True

def test_startup_command_construction():
    config = build_startup_config()
    assert config["app"] == "dashboard.mobile.mobile_app:app"

def test_no_credentials_printed():
    config = {
        "app": "dashboard.mobile.mobile_app:app",
        "host": "127.0.0.1",
        "port": 8090,
        "allow_lan": False
    }
    
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    print_instructions(config)
    
    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()
    
    assert "CSS MOBILE APP STARTUP" in output
    assert "127.0.0.1:8090" in output
    assert "broker credentials" in output.lower()
    
    assert "API_KEY" not in output
    assert "SECRET" not in output
    assert "PASSWORD" not in output
