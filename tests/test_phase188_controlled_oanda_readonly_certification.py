"""Phase 188 — controlled OANDA read-only certification tests (offline / injected)."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest

from backend.app.market.oanda_controlled_readonly import certified_provider as cert_mod
from backend.app.market.oanda_controlled_readonly.certified_provider import (
    CertifiedOandaReadOnlyProvider,
    run_controlled_certification,
)
from backend.app.market.oanda_controlled_readonly.firewall import verify_phase188_firewall
from backend.app.market.oanda_controlled_readonly.readonly_transport import (
    OandaReadOnlyHttpTransport,
)
from backend.runtime.oanda_live_read_only_adapter import OandaLiveReadOnlyAdapter


class FakeOandaReadClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_account_summary(self):
        self.calls.append("get_account_summary")
        return {
            "ok": True,
            "account": {
                "id": "001-001-1234567-001",
                "balance": "100.00",
                "NAV": "105.00",
                "marginAvailable": "90.00",
                "currency": "CAD",
            },
        }

    def get_open_positions(self):
        self.calls.append("get_open_positions")
        return {"positions": []}

    def get_open_trades(self):
        self.calls.append("get_open_trades")
        return {"trades": []}

    def get_instruments(self):
        self.calls.append("get_instruments")
        return {"instruments": [{"name": "EUR_USD"}, {"name": "USD_CAD"}]}

    def get_pricing(self):
        self.calls.append("get_pricing")
        return {
            "prices": [
                {
                    "instrument": "EUR_USD",
                    "closeoutBid": "1.0850",
                    "closeoutAsk": "1.0852",
                }
            ]
        }

    def heartbeat(self):
        self.calls.append("heartbeat")
        return {"ok": True}

    def get_account_metadata(self):
        self.calls.append("get_account_metadata")
        return {"id": "001-001-1234567-001", "currency": "CAD"}

    def place_order(self, *a, **k):
        raise AssertionError("must never call place_order")

    def submit_order(self, *a, **k):
        raise AssertionError("must never call submit_order")


def _env() -> dict[str, str]:
    return {
        "OANDA_API_KEY": "secret-token-value",
        "OANDA_ACCOUNT_ID": "001-001-1234567-001",
        "OANDA_BASE_URL": "https://api-fxtrade.oanda.com",
    }


def test_phase188_missing_credentials_fail_closed() -> None:
    provider = CertifiedOandaReadOnlyProvider(env={}, allow_controlled_network=False)
    cert = provider.certify(timestamp="2026-08-01T10:00:00Z")
    assert cert.certification_state != "READ_ONLY_CERTIFIED"
    assert cert.execution_authority is False
    evidence = provider.last_evidence
    assert evidence is not None


def test_phase188_injected_client_reaches_certified() -> None:
    client = FakeOandaReadClient()
    provider = CertifiedOandaReadOnlyProvider(
        env=_env(),
        read_client=client,
        allow_controlled_network=False,
        now=lambda: datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
    )
    cert = provider.certify(timestamp="2026-08-01T12:00:00Z")
    assert cert.certification_state == "READ_ONLY_CERTIFIED"
    assert cert.certification_generation == 1
    assert cert.execution_authority is False
    assert cert.provider_fingerprint_hash
    assert provider.last_evidence is not None
    assert provider.last_evidence.current_evidence_hash
    assert provider.last_evidence.lineage_generation == 1
    blob = str(provider.last_evidence.as_dict())
    assert "secret-token-value" not in blob
    assert provider.last_evidence.account_scope.get("financials_excluded") is True
    redacted = str(provider.last_evidence.account_scope.get("account_id_redacted") or "")
    assert "1234567" not in redacted
    assert redacted.startswith("...")
    assert "secret-token-value" not in redacted
    assert "place_order" not in client.calls
    assert "submit_order" not in client.calls
    assert isinstance(provider.adapter, OandaLiveReadOnlyAdapter)


def test_phase188_execution_methods_denied() -> None:
    provider = CertifiedOandaReadOnlyProvider(env=_env(), read_client=FakeOandaReadClient())
    for name in (
        "place_order",
        "submit_order",
        "cancel_order",
        "modify_order",
        "arm_live_authority",
        "enable_execution",
        "modify_anti_bleed",
        "modify_margin",
        "modify_risk_governor",
        "modify_phase152a",
    ):
        with pytest.raises(AttributeError):
            getattr(provider, name)


def test_phase188_transport_denies_writes() -> None:
    transport = OandaReadOnlyHttpTransport(
        base_url="https://api-fxtrade.oanda.com",
        token="x",
        account_id="y",
    )
    with pytest.raises(PermissionError):
        transport.place_order()
    with pytest.raises(PermissionError):
        transport.request("POST", "v3/accounts/y/orders")


def test_phase188_firewall_static() -> None:
    report = verify_phase188_firewall()
    assert report["ok"] is True
    assert report["grants_execution"] is False
    assert report["can_arm_live_authority"] is False
    assert report["can_modify_antibleed"] is False
    assert report["violations"] == []


def test_phase188_run_entry_without_credentials() -> None:
    cert = run_controlled_certification(env={}, allow_controlled_network=True)
    assert cert.certification_state != "READ_ONLY_CERTIFIED"
    assert cert.execution_authority is False


def test_phase188_does_not_import_execution_adapter() -> None:
    src = inspect.getsource(cert_mod)
    assert "from backend.app.brokers.oanda_adapter" not in src
    assert "import backend.app.brokers.oanda_adapter" not in src
    assert "from backend.app.brokers import oanda_adapter" not in src
