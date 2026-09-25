from __future__ import annotations

from pathlib import Path

from launcher.css_mobile_launcher import __file__ as mobile_launcher_file


REPO_ROOT = Path(mobile_launcher_file).resolve().parents[1]


def test_canonical_restart_helper_exists_and_verifies_runtime():
    script = REPO_ROOT / "scripts" / "restart_css_canonical.ps1"
    text = script.read_text(encoding="utf-8")
    assert "CapitalStrataSystems-CanonicalRuntime" in text
    assert "Stop-ScheduledTask" in text
    assert "Start-ScheduledTask" in text
    assert "verify_css_persistent_runtime.ps1" in text
    assert "Port 8765 is still occupied" in text


def test_standalone_mobile_guard_points_to_canonical_restart():
    text = (REPO_ROOT / "launcher" / "css_mobile_launcher.py").read_text(encoding="utf-8")
    assert "scripts\\\\restart_css_canonical.ps1" in text
    assert "CSS_ALLOW_STANDALONE_MOBILE=1" in text
