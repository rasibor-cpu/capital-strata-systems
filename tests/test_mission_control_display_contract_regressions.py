from __future__ import annotations

from dashboard.mission_control.contracts import _reported_cycle
from dashboard.mission_control.layout import _broker_quick_control, _global_balance_bar


def test_reported_cycle_rejects_legacy_zero_and_status_tokens():
    assert _reported_cycle(None, "NOT_REPORTED", 0, "0") == "UNAVAILABLE"
    assert _reported_cycle(None, "UNKNOWN", 7, 0) == 7
    assert _reported_cycle("12", 0) == 12


def test_global_balance_does_not_append_unavailable_as_currency():
    html = _global_balance_bar(
        {
            "broker_balance_summary": {
                "account_summary": {
                    "effective_available_balance": {
                        "availability_state": "AVAILABLE",
                        "value": 596.7317,
                        "currency": "UNAVAILABLE",
                        "verification_state": "SIMULATED_VERIFIED",
                    },
                    "total_account_value": {
                        "availability_state": "AVAILABLE",
                        "value": 601.0005,
                        "currency": "UNAVAILABLE",
                    },
                    "pending_debits": {"availability_state": "UNAVAILABLE"},
                    "pending_credits": {"availability_state": "UNAVAILABLE"},
                },
                "account_context": {"base_currency": "UNAVAILABLE"},
                "asset_breakdown": [],
            }
        }
    )
    assert "596.7317 UNAVAILABLE" not in html
    assert "601.0005 UNAVAILABLE" not in html
    assert "596.7317" in html
    assert "601.0005" in html


def test_stale_runtime_labels_saved_selection_as_preferred_broker():
    html = _broker_quick_control(
        {
            "authorization_context": {
                "authenticated": True,
                "active": True,
                "user_id": "00000",
            },
            "platform": {
                "runtime_mode": "DISABLED",
                "selected_broker": "COINBASE",
            },
            "runtime": {"heartbeat_status": "STALE"},
            "brokers": {
                "operator_selection": {
                    "selected_broker": "COINBASE",
                    "broker_mode": "LIVE_READ_ONLY",
                    "confirmed": True,
                },
                "active_broker": {
                    "selected_broker": "COINBASE",
                    "broker_mode": "LIVE_READ_ONLY",
                },
                "broker_list": [],
            },
        }
    )
    assert "Preferred Broker" in html
    assert "COINBASE" in html


def test_stale_runtime_without_saved_preference_does_not_claim_active_broker():
    html = _broker_quick_control(
        {
            "authorization_context": {
                "authenticated": False,
                "active": False,
            },
            "platform": {
                "runtime_mode": "DISABLED",
                "selected_broker": "COINBASE",
            },
            "runtime": {"heartbeat_status": "STALE"},
            "brokers": {
                "operator_selection": {},
                "active_broker": {
                    "selected_broker": "COINBASE",
                    "broker_mode": "LIVE_READ_ONLY",
                },
                "broker_list": [],
            },
        }
    )
    assert "Preferred Broker" in html
    assert "UNAVAILABLE" in html
    assert "COINBASE" not in html
