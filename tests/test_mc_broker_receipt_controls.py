from __future__ import annotations

from dashboard.mission_control.pages.broker_management_mobile import render as render_broker_management_mobile
from dashboard.mission_control.pages.transaction_history import render as render_transaction_history
from launcher.css_mobile_launcher import _launcher_forgot_password_page, _launcher_login_page, _launcher_password_change_page, _launcher_recovery_challenge_page, _launcher_recovery_enrollment_page, validate_mobile_paper_trade_request


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


def test_launcher_exposes_mobile_login_and_password_change_pages() -> None:
    login = _launcher_login_page()
    assert "<title>CSS Sign In</title>" in login
    assert 'form method="post" action="/login"' in login
    assert 'name="user_id"' in login
    assert 'name="password"' in login
    assert "Masked:" in login
    assert "one-way hash" in login
    assert "Log on to CSS" in login

    password_change = _launcher_password_change_page()
    assert "<title>CSS Password Change</title>" in password_change
    assert 'form method="post" action="/password-change"' in password_change
    assert 'name="new_password"' in password_change
    assert 'name="confirm_password"' in password_change


def test_full_trade_ticket_validation_preserves_transaction_fields() -> None:
    record = validate_mobile_paper_trade_request({
        "broker": "COINBASE",
        "broker_mode": "paper",
        "instrument": "BTC-USD",
        "asset_class": "CRYPTO",
        "side": "BUY",
        "quantity": "0.01",
        "amount": "500",
        "currency": "USD",
        "tenor": "SPOT",
        "rate": "50000",
        "order_type": "LIMIT",
        "value_date": "2026-09-25",
        "settlement_date": "2026-09-25",
        "time_in_force": "DAY",
        "paper_only": "true",
        "broker_execution_allowed": "false",
    })
    assert record["broker"] == "COINBASE"
    assert record["instrument"] == "BTC-USD"
    assert record["asset_class"] == "CRYPTO"
    assert record["side"] == "BUY"
    assert record["quantity"] == 0.01
    assert record["amount"] == 500.0
    assert record["tenor"] == "SPOT"
    assert record["rate"] == 50000.0
    assert record["value_date"] == "2026-09-25"
    assert record["settlement_date"] == "2026-09-25"
    assert record["execution_allowed"] is False
    assert record["live_trading_blocked"] is True


def test_launcher_exposes_mobile_forgot_password_recovery() -> None:
    login = _launcher_login_page()
    assert 'href="/forgot-password"' in login
    assert "Forgot password?" in login
    assert "does not consume another sign-on attempt" in login

    forgot = _launcher_forgot_password_page()
    assert "<title>CSS Password Recovery</title>" in forgot
    assert 'form method="post" action="/forgot-password/lookup"' in forgot
    assert 'name="user_id"' in forgot
    assert "existing password cannot be retrieved" in forgot

    challenge = _launcher_recovery_challenge_page("What city were you born in?")
    assert "<title>CSS Reset Password</title>" in challenge
    assert "What city were you born in?" in challenge
    assert 'form method="post" action="/forgot-password/reset"' in challenge
    assert 'name="recovery_answer"' in challenge
    assert 'name="new_password"' in challenge
    assert 'name="confirm_password"' in challenge
    assert "clears the failed sign-on counter" in challenge


def test_launcher_requires_recovery_setup_screen_before_first_access() -> None:
    page = _launcher_recovery_enrollment_page()
    assert "<title>CSS Recovery Setup</title>" in page
    assert "Set Up Password Recovery" in page
    assert 'form method="post" action="/recovery-setup"' in page
    for index in range(1, 6):
        assert f'name="recovery_answer_{index}"' in page
    assert "All five recovery answers are required before first access" in page
    assert "Save All 5 Answers and Continue" in page
    assert "stored only as one-way hashes" in page


def test_global_mission_control_broker_badge_is_clickable_for_authenticated_user() -> None:
    from dashboard.mission_control.layout import render_mission_control_shell

    html = render_mission_control_shell(
        {
            "schema_version": "test",
            "generated_at": "2026-09-25T00:00:00Z",
            "authorization_context": {
                "authenticated": True,
                "active": True,
                "user_id": "00000",
                "role": "SUPER_USER",
            },
            "platform": {
                "product": "CSS Mission Control",
                "runtime_mode": "DISABLED",
                "broker_health": "PASS",
                "platform_status": "AMBER",
            },
            "platform_status": {"runtime_mode": "DISABLED", "execution_state": "BLOCKED"},
            "safety": {
                "live_trading_blocked": True,
                "safety_status": "PASS",
                "execution_allowed": False,
                "advisory_only": True,
            },
            "runtime": {"heartbeat_status": "ACTIVE"},
            "brokers": {
                "operator_selection": {
                    "selected_broker": "OANDA",
                    "broker_mode": "LIVE_READ_ONLY",
                    "confirmed": True,
                },
                "active_broker": {
                    "selected_broker": "COINBASE",
                    "broker_mode": "LIVE_READ_ONLY",
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
                        "operational_state": "READ_ONLY_READY",
                        "readiness": "READ_ONLY_READY",
                        "certification": "READ_ONLY_VALIDATED",
                    },
                    {
                        "broker": "QUESTRADE",
                        "operational_state": "REACTIVATION_REQUIRED",
                        "readiness": "CONFIGURED_REACTIVATION_REQUIRED",
                        "certification": "NOT_CERTIFIED",
                    },
                ],
            },
        },
        active_section="executive_overview",
    )
    assert 'class="mc-broker-quick"' in html
    assert '<span class="mc-badge-value">OANDA</span>' in html
    assert 'name="broker"' in html
    assert "COINBASE — Available" in html
    assert "OANDA — Available" in html
    assert "QUESTRADE — Unavailable: REACTIVATION REQUIRED" in html
    assert '<option value="QUESTRADE" disabled' in html
    assert "Use This Broker" in html


def test_recovery_challenge_page_masks_answer_and_password() -> None:
    page = _launcher_recovery_challenge_page("What was your best subject in secondary school?")
    assert 'id="recovery_answer" name="recovery_answer" type="password"' in page
    assert 'id="recovery_new_password" name="new_password" type="password"' in page
    assert "Masked:" in page
    assert "stored as one-way hash" in page
    assert "Show / Hide Entries" in page
