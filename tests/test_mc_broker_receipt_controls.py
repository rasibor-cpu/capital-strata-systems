from __future__ import annotations

from dashboard.mission_control.pages.broker_management_mobile import render as render_broker_management_mobile
from dashboard.mission_control.pages.transaction_history import render as render_transaction_history


def test_broker_picker_greys_unavailable_brokers_and_requires_confirmation() -> None:
    body = render_broker_management_mobile({
        "authorization_context": {
            "authenticated": True,
            "active": True,
            "user_id": "12345",
            "role": "ADMIN",
        },
        "brokers": {
            "active_broker": {
                "selected_broker": "COINBASE",
                "broker_mode": "LIVE_READ_ONLY",
                "connection_status": "OK",
                "authentication_status": "AUTHENTICATED",
                "account_status": "AVAILABLE",
                "market_data_status": "OK",
                "execution_scope": "READ_ONLY",
            },
            "operator_selection": {
                "selected_broker": "COINBASE",
                "broker_mode": "LIVE_READ_ONLY",
                "confirmed": True,
            },
            "broker_list": [
                {
                    "broker": "COINBASE",
                    "operational_state": "READ_ONLY_READY",
                    "readiness": "READ_ONLY_READY",
                    "certification": "READ_ONLY_VALIDATED",
                },
                {
                    "broker": "OANDA",
                    "operational_state": "CONFIGURATION_REQUIRED",
                    "readiness": "EVIDENCE_MISSING",
                    "certification": "NOT_CERTIFIED",
                },
            ],
            "safety": {"status": "FAIL_CLOSED"},
        },
        "enterprise_broker_runtime": {
            "advisory_readiness": "READ_ONLY",
            "holdings_readiness": {"status": "AVAILABLE"},
            "provider_health": {"status": "OK"},
            "certification": {"outcome": "NOT_CERTIFIED"},
        },
    })
    assert 'id="mc-selected-broker-card"' in body
    assert "Tap to choose and confirm" in body
    assert "COINBASE — Available" in body
    assert "OANDA — Unavailable: CONFIGURATION REQUIRED" in body
    assert '<option value="OANDA" disabled' in body
    assert 'name="confirm_choice" value="YES" required' in body
    assert "Confirm Broker Choice" in body
    assert "Execution remains subject to all CSS safety and certification gates" in body


def test_account_ledger_entry_exposes_generate_receipt_link() -> None:
    body = render_transaction_history({
        "transaction_history": {
            "transactions": [{
                "ledger_id": "12345-20260924220000000000",
                "user_id": "12345",
                "entry_type": "DEBIT",
                "amount": "5.00",
                "currency": "USD",
                "description": "CSS trade commission",
                "transaction_date": "2026-09-24T22:00:00-04:00",
                "value_date": "2026-09-24",
                "settlement_date": "2026-09-24",
            }]
        }
    })
    assert "Generate Receipt" in body
    assert "/mission-control/transaction-receipt/12345-20260924220000000000" in body
