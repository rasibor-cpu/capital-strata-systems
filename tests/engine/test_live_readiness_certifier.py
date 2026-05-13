from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from backend.app.brokers.live_readiness_certifier import (
    LIVE_READINESS_FAIL,
    LIVE_READINESS_PASS,
    LIVE_READINESS_PAYLOAD_VERSION,
    append_live_readiness_certification_log,
    certify_live_readiness,
    fresh_session,
)


def _write_oanda_credentials(tmp_path) -> None:
    (tmp_path / ".env.oanda").write_text(
        "\n".join(
            [
                "OANDA_API_KEY=TOKEN_SHOULD_NOT_LEAK",
                "OANDA_ACCOUNT_ID=ACCOUNT_SHOULD_NOT_LEAK",
                "OANDA_BASE_URL=https://api-fxpractice.oanda.com",
            ]
        ),
        encoding="utf-8",
    )


def _approval() -> dict:
    return {
        "approved": True,
        "approver_role": "SUPER_USER",
        "approval_id": "APPROVAL-001",
        "expires_utc": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
    }


def _dry_run_order(**overrides) -> dict:
    payload = {
        "broker": "oanda",
        "symbol": "EUR_USD",
        "asset_class": "fx",
        "side": "BUY",
        "quantity": 1000,
        "order_type": "MARKET",
        "dry_run": True,
        "submitted_to_broker": False,
        "would_place_live_order": False,
        "expected_value": 1.0,
        "cost": 0.0,
        "probability": 1.0,
    }
    payload.update(overrides)
    return payload


def test_live_readiness_passes_only_with_operator_approval_and_dry_run(tmp_path) -> None:
    _write_oanda_credentials(tmp_path)

    result = certify_live_readiness(
        selected_broker="oanda",
        broker_mode="live",
        asset_class="fx",
        capital_source_label="BROKER",
        balance_source="BROKER",
        dry_run_order=_dry_run_order(api_secret="SHOULD_NOT_LEAK"),
        session=fresh_session(role="SUPER_USER"),
        portfolio_state={"fx": 0},
        engine_mode="SAFE",
        operator_approval=_approval(),
        credential_base_dir=tmp_path,
    )
    encoded = json.dumps(result.as_dict(), sort_keys=True)

    assert result.status == LIVE_READINESS_PASS
    assert result.blocking_reasons == ()
    assert result.dry_run_only is True
    assert result.operator_approval_required is True
    assert result.as_dict()["payload_version"] == LIVE_READINESS_PAYLOAD_VERSION
    assert "TOKEN_SHOULD_NOT_LEAK" not in encoded
    assert "ACCOUNT_SHOULD_NOT_LEAK" not in encoded
    assert "SHOULD_NOT_LEAK" not in encoded


def test_live_readiness_fails_closed_without_operator_approval(tmp_path) -> None:
    _write_oanda_credentials(tmp_path)

    result = certify_live_readiness(
        selected_broker="oanda",
        broker_mode="live",
        asset_class="fx",
        capital_source_label="BROKER",
        balance_source="BROKER",
        dry_run_order=_dry_run_order(),
        session=fresh_session(role="SUPER_USER"),
        portfolio_state={"fx": 0},
        engine_mode="SAFE",
        credential_base_dir=tmp_path,
    )

    assert result.status == LIVE_READINESS_FAIL
    assert "operator_approval_missing" in result.blocking_reasons


def test_live_readiness_fails_closed_for_unsupported_asset(tmp_path) -> None:
    _write_oanda_credentials(tmp_path)

    result = certify_live_readiness(
        selected_broker="oanda",
        broker_mode="live",
        asset_class="crypto",
        capital_source_label="BROKER",
        balance_source="BROKER",
        dry_run_order=_dry_run_order(asset_class="crypto", symbol="BTC-USD"),
        session=fresh_session(role="SUPER_USER"),
        portfolio_state={"crypto": 0},
        engine_mode="SAFE",
        operator_approval=_approval(),
        credential_base_dir=tmp_path,
    )

    assert result.status == LIVE_READINESS_FAIL
    assert "asset_class_not_supported" in result.blocking_reasons


def test_live_readiness_fails_closed_for_capital_source_mismatch(tmp_path) -> None:
    _write_oanda_credentials(tmp_path)

    live_result = certify_live_readiness(
        selected_broker="oanda",
        broker_mode="live",
        asset_class="fx",
        capital_source_label="SIMULATED",
        balance_source="PAPER",
        dry_run_order=_dry_run_order(),
        session=fresh_session(role="SUPER_USER"),
        portfolio_state={"fx": 0},
        engine_mode="SAFE",
        operator_approval=_approval(),
        credential_base_dir=tmp_path,
    )
    paper_result = certify_live_readiness(
        selected_broker="oanda",
        broker_mode="paper",
        asset_class="fx",
        capital_source_label="BROKER",
        balance_source="BROKER",
        dry_run_order=_dry_run_order(),
        session=fresh_session(role="SUPER_USER"),
        portfolio_state={"fx": 0},
        engine_mode="SAFE",
        operator_approval=_approval(),
        credential_base_dir=tmp_path,
    )

    assert live_result.status == LIVE_READINESS_FAIL
    assert "live_mode_cannot_use_simulated_capital" in live_result.blocking_reasons
    assert "live_mode_requires_real_capital_source" in live_result.blocking_reasons
    assert "live_mode_requires_broker_balance_source" in live_result.blocking_reasons
    assert paper_result.status == LIVE_READINESS_FAIL
    assert "paper_mode_cannot_use_live_capital" in paper_result.blocking_reasons


def test_live_readiness_audit_log_is_jsonl_and_redacted(tmp_path) -> None:
    _write_oanda_credentials(tmp_path)
    result = certify_live_readiness(
        selected_broker="oanda",
        broker_mode="live",
        asset_class="fx",
        capital_source_label="BROKER",
        balance_source="BROKER",
        dry_run_order=_dry_run_order(secret_token="SHOULD_NOT_LEAK"),
        session=fresh_session(role="SUPER_USER"),
        portfolio_state={"fx": 0},
        engine_mode="SAFE",
        operator_approval=_approval(),
        credential_base_dir=tmp_path,
    )
    log_path = tmp_path / "live_readiness.jsonl"

    append_live_readiness_certification_log(result, log_path)
    encoded = log_path.read_text(encoding="utf-8")
    row = json.loads(encoded)

    assert row["payload_version"] == LIVE_READINESS_PAYLOAD_VERSION
    assert row["status"] == LIVE_READINESS_PASS
    assert "SHOULD_NOT_LEAK" not in encoded
