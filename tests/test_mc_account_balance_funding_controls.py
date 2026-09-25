from __future__ import annotations

from backend.accounting.account_funding_control import assess_trade_funding
from backend.brokers.account_balance_contract import build_broker_balance_summary
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.pages.account_funding import render as render_account_funding


def test_balance_contract_nets_pending_when_provider_available_is_absent() -> None:
    summary = build_broker_balance_summary(
        {
            "paper_capital": 1000,
            "pending_debits": 150,
            "pending_credits": 50,
            "held_reserved": 100,
            "currency": "USD",
            "freshness": "FRESH",
        },
        broker="PAPER",
        mode="PAPER",
        base_currency="USD",
    )
    account = summary["account_summary"]
    assert account["available_to_trade"]["value"] == 800.0
    assert account["effective_available_balance"]["value"] == 800.0
    assert account["pending_debits"]["value"] == 150.0
    assert account["pending_credits"]["value"] == 50.0
    assert account["available_to_trade"]["verification_state"] == "SIMULATED_VERIFIED"


def test_global_balance_bar_is_on_every_mission_control_shell_and_maskable() -> None:
    html = render_mission_control_shell(
        {
            "schema_version": "test",
            "generated_at": "2026-09-25T00:00:00Z",
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
            "broker_balance_summary": {
                "account_summary": {
                    "available_to_trade": {
                        "value": 1250.75,
                        "currency": "CAD",
                        "availability_state": "AVAILABLE",
                        "verification_state": "BROKER_VERIFIED",
                    },
                    "total_account_value": {
                        "value": 2000,
                        "currency": "CAD",
                        "availability_state": "AVAILABLE",
                        "verification_state": "BROKER_VERIFIED",
                    },
                    "pending_debits": {
                        "value": 75,
                        "currency": "CAD",
                        "availability_state": "AVAILABLE",
                        "verification_state": "BROKER_VERIFIED",
                    },
                    "pending_credits": {
                        "value": 20,
                        "currency": "CAD",
                        "availability_state": "AVAILABLE",
                        "verification_state": "BROKER_VERIFIED",
                    },
                },
                "asset_breakdown": [
                    {"asset_currency": "CAD", "available": 1250.75},
                    {"asset_currency": "USD", "available": 400.25},
                ],
                "account_context": {"base_currency": "CAD"},
            },
        },
        active_section="executive_overview",
    )
    assert 'class="mc-global-balance"' in html
    assert "Available Balance" in html
    assert "1250.75 CAD" in html
    assert "CAD 1250.75" in html
    assert "USD 400.25" in html
    assert 'class="mc-balance-eye"' in html
    assert "Mask balance" in html
    assert "Unmask balance" in html
    assert "css_balance_masked" in html


def test_trade_funding_gate_blocks_overdraft_without_verified_margin() -> None:
    account_summary = {
        "available_to_trade": {
            "value": 500,
            "currency": "USD",
            "availability_state": "AVAILABLE",
            "verification_state": "BROKER_VERIFIED",
        },
        "margin_available": {
            "value": 1000,
            "currency": "USD",
            "availability_state": "AVAILABLE",
            "verification_state": "BROKER_VERIFIED",
        },
    }
    blocked = assess_trade_funding(
        requested_amount=750,
        currency="USD",
        account_summary=account_summary,
        margin_control={"status": "DISABLED", "margin_limit": "0", "setoff_executed": False},
    )
    assert blocked["allowed"] is False

    allowed = assess_trade_funding(
        requested_amount=750,
        currency="USD",
        account_summary=account_summary,
        margin_control={
            "status": "ACTIVE_VERIFIED",
            "currency": "USD",
            "margin_limit": "500",
            "setoff_executed": True,
        },
    )
    assert allowed["allowed"] is True
    assert allowed["funding_source"] == "AVAILABLE_CASH_PLUS_VERIFIED_MARGIN"
    assert allowed["margin_used"] == "250"


def test_funding_page_exposes_verification_and_setoff_controls() -> None:
    body = render_account_funding(
        {
            "authorization_context": {"user_id": "12345", "role": "TRADER"},
            "broker_balance_summary": {
                "account_summary": {
                    "effective_available_balance": {
                        "value": 900,
                        "currency": "USD",
                        "availability_state": "AVAILABLE",
                        "verification_state": "BROKER_VERIFIED",
                    },
                    "pending_debits": {
                        "value": 100,
                        "currency": "USD",
                        "availability_state": "AVAILABLE",
                        "verification_state": "BROKER_VERIFIED",
                    },
                    "pending_credits": {
                        "value": 50,
                        "currency": "USD",
                        "availability_state": "AVAILABLE",
                        "verification_state": "BROKER_VERIFIED",
                    },
                }
            },
            "account_controls": {
                "user_id": "12345",
                "funding_requests": [],
                "margin_control": {
                    "status": "PENDING",
                    "currency": "USD",
                    "margin_limit": "1000",
                    "setoff_form_version": "CSS-SETOFF-2026-09",
                    "setoff_executed": False,
                },
            },
        }
    )
    assert "Balances &amp; Funding" in body or "Balances & Funding" in body
    assert "Submit Funding for Verification" in body
    assert "/account/funding/request" in body
    assert "PENDING VERIFICATION" in body
    assert "Margin / Set-Off Control" in body
    assert "Execute Set-Off Instruction" in body
    assert "/account/margin/setoff/accept" in body
