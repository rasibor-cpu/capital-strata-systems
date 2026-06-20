import os
import pytest
from unittest.mock import patch, MagicMock
import scripts.start_css_mobile_app as startup
from scripts.start_css_mobile_app import build_startup_config, print_instructions, get_local_ip
import io
import sys
import socket
from pathlib import Path

def test_repo_root_in_sys_path():
    # The module level code already ran when we imported it.
    repo_root = str(Path(__file__).parent.parent.parent.absolute())
    assert repo_root in sys.path
    assert os.environ.get("PYTHONPATH") == repo_root

def test_app_import_resolvable():
    # Because sys.path is correct, we should be able to import the target app
    try:
        from dashboard.mobile.mobile_app import app
        assert app is not None
    except ImportError:
        pytest.fail("Could not import dashboard.mobile.mobile_app:app. sys.path is likely incorrect.")

def test_ip_preference_192_over_10():
    # Mock socket getaddrinfo to return both a 10.x and 192.168.x IP
    with patch('socket.getaddrinfo') as mock_getaddrinfo:
        # getaddrinfo returns a list of tuples: (family, type, proto, canonname, sockaddr)
        # where sockaddr is (IP, port)
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('10.2.0.2', 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('192.168.86.86', 0))
        ]
        
        with patch('socket.gethostname', return_value='test-host'):
            ip = get_local_ip()
            assert ip == "192.168.86.86"

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
