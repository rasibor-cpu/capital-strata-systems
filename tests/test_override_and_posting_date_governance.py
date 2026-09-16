import json
from datetime import date

import pytest

import backend.app.override_log as override_log
import backend.app.period_close as period_close
import backend.app.posting_date_policy as posting_date_policy


def test_override_log_is_hash_chained_and_captures_approval_fields(tmp_path, monkeypatch):
    path = tmp_path / "overrides.jsonl"
    monkeypatch.setattr(override_log, "_log_path", lambda: path)

    first = override_log.write_override(
        actor_user_id="maker-1",
        override_type="BACKDATE",
        reason="approved correction",
        scope={"entry_id": "E-1"},
        approval_level="CHECKER",
        approver_user_id="checker-1",
        target="posting_date",
        old_value="2026-09-16",
        new_value="2026-09-15",
    )
    second = override_log.write_override(
        actor_user_id="maker-2",
        override_type="BACKDATE",
        reason="approved correction 2",
        scope={"entry_id": "E-2"},
        approval_level="CHECKER",
        approver_user_id="checker-2",
        target="posting_date",
        old_value="2026-09-16",
        new_value="2026-09-14",
    )

    assert first["prev_hash"] == "GENESIS"
    assert second["prev_hash"] == first["hash"]
    assert first["approver_user_id"] == "checker-1"
    assert first["target"] == "posting_date"
    assert first["old_value"] == "2026-09-16"
    assert first["new_value"] == "2026-09-15"


def test_corrupt_existing_override_log_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "overrides.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")
    monkeypatch.setattr(override_log, "_log_path", lambda: path)

    with pytest.raises((json.JSONDecodeError, ValueError, UnicodeDecodeError)):
        override_log.write_override(
            actor_user_id="maker-1",
            override_type="BACKDATE",
            reason="must not restart chain",
            approval_level="CHECKER",
            approver_user_id="checker-1",
        )


def test_override_requires_actor_and_approver(tmp_path, monkeypatch):
    path = tmp_path / "overrides.jsonl"
    monkeypatch.setattr(override_log, "_log_path", lambda: path)

    with pytest.raises(ValueError, match="actor_user_id"):
        override_log.write_override(
            actor_user_id="",
            override_type="BACKDATE",
            reason="x",
            approver_user_id="checker-1",
        )

    with pytest.raises(ValueError, match="approver_user_id"):
        override_log.write_override(
            actor_user_id="maker-1",
            override_type="BACKDATE",
            reason="x",
        )


def test_posting_date_outside_today_requires_approved_override(tmp_path, monkeypatch):
    path = tmp_path / "overrides.jsonl"
    monkeypatch.setattr(override_log, "_log_path", lambda: path)
    monkeypatch.setattr(
        posting_date_policy,
        "_today_utc",
        lambda: date(2026, 9, 16),
    )
    period_close._PERIODS.clear()

    blocked = posting_date_policy.evaluate_posting_date(
        posting_date="2026-09-15",
        actor_user_id="maker-1",
    )
    assert blocked.allowed is False
    assert blocked.requires_override is True

    with pytest.raises(ValueError, match="approver_user_id"):
        posting_date_policy.evaluate_posting_date(
            posting_date="2026-09-15",
            actor_user_id="maker-1",
            override={
                "reason": "approved correction",
                "approval_level": "CHECKER",
            },
        )

    allowed = posting_date_policy.evaluate_posting_date(
        posting_date="2026-09-15",
        actor_user_id="maker-1",
        override={
            "reason": "approved correction",
            "approval_level": "CHECKER",
            "approver_id": "checker-1",
        },
    )
    assert allowed.allowed is True
    assert allowed.override_record["approver_user_id"] == "checker-1"
    assert allowed.override_record["new_value"] == "2026-09-15"


def test_closed_period_cannot_be_overridden(tmp_path, monkeypatch):
    path = tmp_path / "overrides.jsonl"
    monkeypatch.setattr(override_log, "_log_path", lambda: path)
    monkeypatch.setattr(
        posting_date_policy,
        "_today_utc",
        lambda: date(2026, 9, 16),
    )
    period_close._PERIODS.clear()
    period_close.close_month(2026, 9, "controller")

    decision = posting_date_policy.evaluate_posting_date(
        posting_date="2026-09-15",
        actor_user_id="maker-1",
        override={
            "reason": "should not bypass close",
            "approver_id": "checker-1",
        },
    )
    assert decision.allowed is False
    assert decision.requires_override is False
    assert not path.exists()
