from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_live_certification_audit_is_read_only_and_uses_canonical_endpoints():
    text = (ROOT / "scripts" / "audit_css_live_certification.ps1").read_text(
        encoding="utf-8"
    )
    assert '"/mission-control/api/state"' in text
    assert '"/mission-control/api/final-certification"' in text
    assert '"/mission-control/api/health"' in text
    assert '"/mission-control/api/runtime"' in text
    assert "Invoke-RestMethod" in text
    assert "-Method Get" in text
    assert "POST" not in text
    assert "execution_allowed" in text
    assert "live_trading_blocked" in text
    assert "broker_execution_armed" in text


def test_live_certification_audit_avoids_powershell7_ternary_syntax():
    text = (ROOT / "scripts" / "audit_css_live_certification.ps1").read_text(
        encoding="utf-8"
    )
    assert " ? " not in text
    assert " : " not in text
    assert "[string]::IsNullOrWhiteSpace" in text
