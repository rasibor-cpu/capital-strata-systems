import os
from pathlib import Path
from unittest.mock import patch

def test_startup_script_exists():
    root = Path(__file__).parent.parent.parent
    script = root / "scripts" / "start_css_mobile_app.py"
    assert script.exists(), "Mobile startup script is missing"

def test_runbook_exists():
    root = Path(__file__).parent.parent.parent
    doc = root / "docs" / "operations" / "CSS_MOBILE_APP_RUNBOOK.md"
    assert doc.exists(), "Mobile app runbook is missing"

def test_final_checklist_exists():
    root = Path(__file__).parent.parent.parent
    doc = root / "docs" / "operations" / "CSS_MOBILE_APP_FINAL_READINESS_CHECKLIST.md"
    assert doc.exists(), "Mobile final readiness checklist is missing"

def test_mobile_app_import_still_works():
    try:
        from dashboard.mobile.mobile_app import app
        assert app is not None
    except ImportError:
        assert False, "Could not import mobile app"

def test_launcher_defaults_safe():
    from scripts.start_css_mobile_app import build_startup_config
    with patch.dict(os.environ, {}, clear=True):
        config = build_startup_config()
        assert config["host"] == "127.0.0.1"
        assert config["allow_lan"] is False

def test_lan_requires_css_mobile_lan_true():
    from scripts.start_css_mobile_app import build_startup_config
    
    # Test False
    with patch.dict(os.environ, {"CSS_MOBILE_LAN": "false"}, clear=True):
        config = build_startup_config()
        assert config["host"] == "127.0.0.1"
        assert config["allow_lan"] is False

    # Test True
    with patch.dict(os.environ, {"CSS_MOBILE_LAN": "true"}, clear=True):
        config = build_startup_config()
        assert config["host"] == "0.0.0.0"
        assert config["allow_lan"] is True
