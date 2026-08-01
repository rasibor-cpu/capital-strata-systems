"""Phase 189 — multi-broker operational readiness tests (offline only)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.app.brokers.multi_broker_readiness import (
    AssetClass,
    AuthorizationTTLRegistry,
    BrokerCapabilityProfile,
    BrokerReadOnlyCertification,
    BrokerType,
    MultiBrokerReadinessFramework,
    evaluate_rc004_readiness,
    get_capability_profile,
    register_plugin_capability,
    run_controlled_online_precheck,
    verify_multi_broker_firewall,
)
from backend.app.brokers.multi_broker_readiness.auth_ttl import AuthorizationTTL
from backend.app.brokers.multi_broker_readiness.state_machine import BrokerCertificationStateMachine


def _oanda_env() -> dict[str, str]:
    return {
        "OANDA_API_KEY": "secret-token",
        "OANDA_ACCOUNT_ID": "001-001-9999999-001",
        "OANDA_BASE_URL": "https://api-fxtrade.oanda.com",
    }


def test_capability_profiles_declared_not_inferred() -> None:
    oanda = get_capability_profile("OANDA")
    assert oanda.fx is True
    assert oanda.crypto is False
    assert oanda.execution_authority is False
    coinbase = get_capability_profile("COINBASE")
    assert coinbase.crypto is True
    assert coinbase.fx is False
    ibkr = get_capability_profile("IBKR")
    assert ibkr.equities is True
    assert ibkr.account_information is False


def test_capability_profile_rejects_execution_authority() -> None:
    with pytest.raises(ValueError):
        BrokerCapabilityProfile(broker_type="X", execution_authority=True)


def test_precheck_blocks_without_auth() -> None:
    result = run_controlled_online_precheck("OANDA", {}, asset_class=AssetClass.FX)
    assert result.status == "BLOCKED"
    assert result.authentication_performed is False
    assert "credentials_missing" in result.blockers


def test_precheck_capability_mismatch_blocks() -> None:
    result = run_controlled_online_precheck(
        "OANDA", _oanda_env(), asset_class=AssetClass.CRYPTO
    )
    assert result.status == "BLOCKED"
    assert result.capability_compatible is False
    assert any("capability_incompatible" in b for b in result.blockers)


def test_precheck_pass_oanda_fx() -> None:
    result = run_controlled_online_precheck("OANDA", _oanda_env(), asset_class=AssetClass.FX)
    assert result.status == "PASS"
    assert result.authentication_performed is False


def test_ibkr_blocked_classification() -> None:
    fw = MultiBrokerReadinessFramework()
    readiness = fw.evaluate_operational_readiness("IBKR", asset_class=AssetClass.EQUITIES, env={})
    assert readiness.classification == "BLOCKED"
    assert readiness.execution_authority is False


def test_state_machine_happy_path() -> None:
    sm = BrokerCertificationStateMachine()
    flags = {
        "config_present": True,
        "config_validated": True,
        "dns_ok": True,
        "tls_ok": True,
        "auth_pending": True,
        "auth_ok": True,
        "account_ok": True,
        "account_scope_ok": True,
        "marketdata_ok": True,
        "read_only_certified": True,
    }
    final, _ = sm.run_to_completion(flags)
    assert final == "READ_ONLY_CERTIFIED"


def test_certify_blocked_on_precheck() -> None:
    fw = MultiBrokerReadinessFramework()
    cert = fw.certify_readonly("OANDA", asset_class=AssetClass.FX, env={})
    assert cert.certification_state == "BLOCKED"
    assert cert.execution_authority is False
    assert cert.asset_class == "FX"


def test_certify_with_injected_flags_no_network() -> None:
    fw = MultiBrokerReadinessFramework()
    flags = {
        "dns_ok": True,
        "tls_ok": True,
        "auth_pending": True,
        "auth_ok": True,
        "account_ok": True,
        "account_scope_ok": True,
        "marketdata_ok": True,
        "read_only_certified": True,
    }
    cert = fw.certify_readonly(
        BrokerType.OANDA,
        asset_class=AssetClass.FX,
        env=_oanda_env(),
        evidence_flags=flags,
        issue_ttl_seconds=60,
        timestamp="2026-08-01T12:00:00Z",
    )
    assert cert.certification_state == "READ_ONLY_CERTIFIED"
    assert cert.certification_generation == 1
    assert cert.capability_profile["fx"] is True
    assert cert.diagnostics["authentication_performed"] is False
    assert cert.ttl_status["active"] is True
    assert cert.ttl_status["trading_authorization"] is False
    assert "secret-token" not in str(cert.as_dict())


def test_authorization_ttl_expires_and_restart_safe(tmp_path: Path) -> None:
    clock = {"now": datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)}

    def now() -> datetime:
        return clock["now"]

    path = tmp_path / "ttl.json"
    reg = AuthorizationTTLRegistry(durable_path=path, now=now)
    issued = reg.issue("OANDA", ttl_seconds=30)
    assert issued.trading_authorization is False
    assert reg.status("OANDA").active is True
    clock["now"] = clock["now"] + timedelta(seconds=31)
    assert reg.status("OANDA").expired is True
    # Restart reload — still expired, cannot silently re-arm
    reg2 = AuthorizationTTLRegistry(durable_path=path, now=now)
    assert reg2.status("OANDA").expired is True
    with pytest.raises(AttributeError):
        getattr(reg2, "arm_live_authority")


def test_ttl_rejects_trading_authorization() -> None:
    with pytest.raises(ValueError):
        AuthorizationTTL(
            ttl_id="x",
            broker_type="OANDA",
            scope="READ_ONLY_OPERATIONAL",
            issued_at="2026-08-01T12:00:00Z",
            expires_at="2026-08-01T12:01:00Z",
            generation=1,
            trading_authorization=True,
        )


def test_rc004_never_authorizes_live() -> None:
    rc = evaluate_rc004_readiness("COINBASE", signoff_artifact_present=True)
    assert rc.live_trading_authorized is False
    assert "LIVE_TRADING_NOT_AUTHORIZED" in rc.remaining_blockers


def test_firewall_static() -> None:
    report = verify_multi_broker_firewall()
    assert report["ok"] is True
    assert report["grants_execution"] is False
    assert report["can_place_orders"] is False


def test_framework_forbids_execution_methods() -> None:
    fw = MultiBrokerReadinessFramework()
    for name in (
        "place_order",
        "submit_order",
        "cancel_order",
        "modify_order",
        "arm_live_authority",
        "enable_execution",
        "authenticate",
    ):
        with pytest.raises(AttributeError):
            getattr(fw, name)


def test_plugin_registration_extensible() -> None:
    profile = BrokerCapabilityProfile(
        broker_type="ACME",
        equities=True,
        account_information=True,
        market_data=True,
    )
    register_plugin_capability(profile)
    assert get_capability_profile("ACME").equities is True


def test_certification_rejects_execution_authority() -> None:
    with pytest.raises(ValueError):
        BrokerReadOnlyCertification(execution_authority=True)
