from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.runtime.runtime_session_continuity import RuntimeSessionContinuityMonitor


NOW = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)


def _session(age_seconds: int, max_seconds: int = 3600, **extra):
    payload = {
        "session": {
            "start_time": (NOW - timedelta(seconds=age_seconds)).isoformat(),
            "max_session_seconds": max_seconds,
            "engine_mode": "PAPER",
        }
    }
    payload["session"].update(extra)
    return payload


def test_session_continuity_active_session() -> None:
    result = RuntimeSessionContinuityMonitor().evaluate(_session(300), now=NOW)

    assert result["session_continuity_status"] == "ACTIVE"
    assert result["can_paper_execute"] is True
    assert result["can_live_execute"] is False
    assert result["reauth_required"] is False


def test_session_continuity_expiring_soon_warning() -> None:
    result = RuntimeSessionContinuityMonitor().evaluate(_session(3500), now=NOW)

    assert result["session_continuity_status"] == "EXPIRING_SOON"
    assert "session_expiring_soon" in result["warnings"]
    assert result["can_paper_execute"] is True


def test_session_continuity_expired_requires_reauth() -> None:
    result = RuntimeSessionContinuityMonitor().evaluate(_session(3700), now=NOW)

    assert result["session_continuity_status"] == "EXPIRED"
    assert result["reauth_required"] is True
    assert result["can_paper_execute"] is False
    assert result["execution_allowed"] is False


def test_session_continuity_quiet_mode_requires_reauth() -> None:
    result = RuntimeSessionContinuityMonitor().evaluate(_session(300, session_expired_quiet_mode=True), now=NOW)

    assert result["session_continuity_status"] == "REAUTH_REQUIRED"
    assert result["quiet_mode_active"] is True
    assert result["reauth_required"] is True


def test_session_continuity_resumed_state_clears_blocker() -> None:
    result = RuntimeSessionContinuityMonitor().evaluate(_session(300, session_continuity_status="RESUMED"), now=NOW)

    assert result["session_continuity_status"] == "RESUMED"
    assert result["reauth_required"] is False
    assert result["can_paper_execute"] is True


def test_session_continuity_has_no_credential_storage_or_login_bypass() -> None:
    source = Path("backend/runtime/runtime_session_continuity.py").read_text(encoding="utf-8")

    assert "password" not in source.lower()
    assert "credential" not in source.lower()
    assert "login(" not in source.lower()
