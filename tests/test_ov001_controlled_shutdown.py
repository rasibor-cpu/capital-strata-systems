"""OV-001 controlled shutdown observation tests."""

from __future__ import annotations

from pathlib import Path

from backend.certification.controlled_shutdown_observation import (
    capture_controlled_shutdown_observation,
    run_repeated_start_stop_cycles,
)
from backend.certification.ov001_operational_validation import (
    assemble_complete_oat,
    redact_secrets,
)


def test_controlled_shutdown_observation_pass(tmp_path: Path) -> None:
    result = capture_controlled_shutdown_observation(tmp_path / "shutdown")
    assert result["shutdown_performed"] is True
    assert result["execution_allowed"] is False
    assert result["ok"] is True
    assert result["status"] == "PASS"
    assert result["process_alive_after"] is False
    assert result["port_in_use_after"] is False
    assert result["service_status_final"] == "STOPPED"
    assert result["shutdown_complete"] is True
    assert (tmp_path / "shutdown" / "SHUTDOWN_OBSERVATION.json").is_file()


def test_repeated_shutdown_cycles(tmp_path: Path) -> None:
    summary = run_repeated_start_stop_cycles(tmp_path / "cycles", cycles=2)
    assert summary["ok"] is True
    assert summary["cycle_count"] == 2


def test_oat_reaches_100_with_shutdown(tmp_path: Path) -> None:
    shutdown = capture_controlled_shutdown_observation(tmp_path / "shutdown")
    assert shutdown["ok"] is True
    oat = assemble_complete_oat(tmp_path / "oat", shutdown_observation=shutdown)
    assert oat["percentage"] == 100.0
    assert oat["ok"] is True
    assert not oat["blockers"]
    assert oat["fabricated"] is False


def test_redact_secrets_never_echoes_values() -> None:
    payload = {
        "api_key": "super-secret-value",
        "nested": {"token": "abc123", "ok": True},
        "market": "BTC-USD",
    }
    redacted = redact_secrets(payload)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["token"] == "[REDACTED]"
    assert redacted["nested"]["ok"] is True
    assert redacted["market"] == "BTC-USD"
    assert "super-secret-value" not in str(redacted)
