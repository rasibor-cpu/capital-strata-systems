"""Offline tests for the Binance authenticated READ-ONLY client and eligibility gate.

All HTTP is served by an in-memory fake transport; no network access occurs.
The credentials below are random test values, not real keys.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

from backend.binance_readonly import eligibility as elig
from backend.binance_readonly.client import (
    ACCOUNT_READ_PATHS,
    BinanceAPIError,
    BinanceReadOnlyClient,
    EligibilityNotConfirmedError,
    EndpointNotAllowedError,
    RateLimitedError,
    RestrictedLocationError,
)
from backend.binance_readonly.credentials import (
    BinanceCredentials,
    CredentialPolicyError,
    load_credentials,
)
from backend.binance_readonly.readonly_check import (
    EXIT_ATTESTATION,
    EXIT_CREDENTIALS,
    EXIT_NOT_ELIGIBLE,
    EXIT_OK,
    EXIT_PUBLIC_BLOCKED,
    JOURNAL_FILENAME,
    run_check,
)
from backend.shadow_paper.journal import read_journal

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_KEY = "k" * 20 + "TESTKEY0000000000000000000000000000000000000000000"[:44]
TEST_SECRET = "s" * 20 + "TESTSECRET000000000000000000000000000000000000000"[:44]
ENV = {"BINANCE_API_KEY": TEST_KEY, "BINANCE_API_SECRET": TEST_SECRET}
NOW_MS = 1_760_400_000_000

READ_ONLY_RESTRICTIONS = {
    "ipRestrict": True,
    "createTime": 1700000000000,
    "enableReading": True,
    "enableSpotAndMarginTrading": False,
    "enableWithdrawals": False,
    "enableInternalTransfer": False,
    "enableMargin": False,
    "enableFutures": False,
    "permitsUniversalTransfer": False,
    "enableVanillaOptions": False,
    "enablePortfolioMarginTrading": False,
}
GOOD_ATTESTATION = {"operating_country": "NG", "kyc_country": "NG", "no_geo_bypass": True, "read_only_key": True}


class FakeBinance:
    def __init__(self, restrictions=None, status=None, public_status=200, account_status_payload=None):
        self.calls: list[tuple[str, dict]] = []
        self.restrictions = dict(READ_ONLY_RESTRICTIONS if restrictions is None else restrictions)
        self.public_status = public_status
        self.account_status_payload = account_status_payload or {"data": "Normal"}
        self.signed_status = status

    def __call__(self, url, headers, timeout):
        parts = urlsplit(url)
        self.calls.append((parts.path, dict(headers)))
        path = parts.path
        if path in ("/api/v3/ping", "/api/v3/time", "/api/v3/exchangeInfo") and self.public_status != 200:
            return self.public_status, {"code": 0, "msg": "Service unavailable from a restricted location"}
        if self.signed_status and path.startswith(("/sapi", "/api/v3/account", "/api/v3/allOrders", "/api/v3/myTrades")):
            return self.signed_status, {"code": -2015, "msg": "Invalid API-key, IP, or permissions for action."}
        if path == "/api/v3/ping":
            return 200, {}
        if path == "/api/v3/time":
            return 200, {"serverTime": NOW_MS + 120}
        if path == "/api/v3/exchangeInfo":
            return 200, {"symbols": [{"symbol": "BTCUSDT", "status": "TRADING"}, {"symbol": "ETHUSDT", "status": "TRADING"}]}
        if path == "/sapi/v1/account/apiRestrictions":
            return 200, self.restrictions
        if path == "/sapi/v1/account/status":
            return 200, self.account_status_payload
        if path == "/api/v3/account":
            return 200, {"accountType": "SPOT", "canTrade": True, "canWithdraw": True, "canDeposit": True,
                         "permissions": ["SPOT"], "balances": [{"asset": "USDT", "free": "12.5", "locked": "0"},
                                                               {"asset": "BTC", "free": "0", "locked": "0"}]}
        if path == "/api/v3/allOrders":
            return 200, [{"symbol": dict(parse_qsl(parts.query))["symbol"], "orderId": 1, "status": "FILLED"}]
        if path == "/api/v3/myTrades":
            return 200, [{"symbol": dict(parse_qsl(parts.query))["symbol"], "id": 9, "price": "1"}]
        return 404, {"code": -1, "msg": "unexpected"}

    def paths(self):
        return [p for p, _ in self.calls]


def creds() -> BinanceCredentials:
    return BinanceCredentials(TEST_KEY, TEST_SECRET)


# ---------------------------------------------------------------- credentials

def test_credentials_are_never_printed_and_sign_correctly():
    c = creds()
    assert TEST_SECRET not in repr(c) and TEST_KEY not in repr(c) and TEST_SECRET not in str(c)
    assert c.fingerprint == "sha256:" + hashlib.sha256(TEST_KEY.encode()).hexdigest()[:12]
    assert c.sign("a=1") == hmac.new(TEST_SECRET.encode(), b"a=1", hashlib.sha256).hexdigest()
    with pytest.raises(AttributeError):
        c._secret = b"x"


@pytest.mark.parametrize("environ", [{}, {"BINANCE_API_KEY": TEST_KEY}, {"BINANCE_API_KEY": "short", "BINANCE_API_SECRET": TEST_SECRET},
                                     {"BINANCE_API_KEY": TEST_KEY, "BINANCE_API_SECRET": "bad secret with spaces" * 3}])
def test_missing_or_malformed_credentials_refused(tmp_path, environ):
    with pytest.raises(CredentialPolicyError):
        load_credentials(environ, tmp_path)


def test_credentials_inside_repository_env_file_refused(tmp_path):
    (tmp_path / ".env").write_text("BINANCE_API_SECRET=abc\n", encoding="utf-8")
    with pytest.raises(CredentialPolicyError, match="repository"):
        load_credentials(ENV, tmp_path)


def test_no_credentials_committed_in_repository():
    tracked_env = [p for p in REPO_ROOT.glob(".env*") if p.name != ".env.example"]
    for path in tracked_env:
        assert "BINANCE_API_SECRET" not in path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- client allowlist

@pytest.mark.parametrize("path", [
    "/api/v3/order", "/api/v3/order/test", "/api/v3/openOrders", "/api/v3/orderList/oco",
    "/sapi/v1/capital/withdraw/apply", "/sapi/v1/asset/transfer", "/sapi/v1/margin/loan",
    "/sapi/v1/margin/order", "/fapi/v1/order", "/sapi/v1/sub-account/transfer/subToSub",
])
def test_write_endpoints_are_not_reachable(path):
    client = BinanceReadOnlyClient(creds(), transport=FakeBinance(), clock_ms=lambda: NOW_MS)
    client.confirm_eligibility(elig.EligibilityDecision(True, []))
    for signed in (True, False):
        with pytest.raises(EndpointNotAllowedError):
            client._request("GET", path, {}, signed=signed)


@pytest.mark.parametrize("method", ["POST", "DELETE", "PUT", "PATCH"])
def test_only_get_is_possible(method):
    client = BinanceReadOnlyClient(creds(), transport=FakeBinance(), clock_ms=lambda: NOW_MS)
    with pytest.raises(EndpointNotAllowedError):
        client._request(method, "/api/v3/account", {}, signed=True)


def test_account_endpoints_refused_until_eligibility_confirmed():
    fake = FakeBinance()
    client = BinanceReadOnlyClient(creds(), transport=fake, clock_ms=lambda: NOW_MS)
    with pytest.raises(EligibilityNotConfirmedError):
        client.account()
    with pytest.raises(EligibilityNotConfirmedError):
        client.my_trades("BTCUSDT")
    with pytest.raises(EligibilityNotConfirmedError):
        client.confirm_eligibility(elig.EligibilityDecision(False, []))
    assert not any(p in ACCOUNT_READ_PATHS for p in fake.paths())


def test_signed_request_is_correct_and_leaks_nothing():
    fake = FakeBinance()
    client = BinanceReadOnlyClient(creds(), transport=fake, clock_ms=lambda: NOW_MS)
    client.api_restrictions()
    url_path, headers = fake.calls[-1]
    assert url_path == "/sapi/v1/account/apiRestrictions"
    assert headers["X-MBX-APIKEY"] == TEST_KEY
    assert TEST_SECRET not in str(fake.calls)


def test_signature_matches_binance_hmac_scheme():
    seen = {}

    def transport(url, headers, timeout):
        seen["url"] = url
        return 200, {}

    BinanceReadOnlyClient(creds(), transport=transport, clock_ms=lambda: NOW_MS).api_restrictions()
    query = urlsplit(seen["url"]).query
    payload, signature = query.rsplit("&signature=", 1)
    assert signature == hmac.new(TEST_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    params = dict(parse_qsl(payload))
    assert params["recvWindow"] == "5000" and params["timestamp"] == str(NOW_MS)


def test_http_451_and_rate_limits_fail_closed_without_leaking_query():
    with pytest.raises(RestrictedLocationError):
        BinanceReadOnlyClient(transport=FakeBinance(public_status=451)).ping()
    for status in (418, 429):
        with pytest.raises(RateLimitedError):
            BinanceReadOnlyClient(creds(), transport=FakeBinance(status=status), clock_ms=lambda: NOW_MS).api_restrictions()
    with pytest.raises(BinanceAPIError) as exc:
        BinanceReadOnlyClient(creds(), transport=FakeBinance(status=401), clock_ms=lambda: NOW_MS).api_restrictions()
    assert "signature" not in str(exc.value) and TEST_KEY not in str(exc.value)


def test_package_contains_no_write_capable_http_calls():
    files = list((REPO_ROOT / "backend" / "binance_readonly").glob("*.py"))
    files += [REPO_ROOT / "scripts" / "css_binance_readonly_check.py", REPO_ROOT / "backend" / "shadow_paper" / "binance_market_data.py"]
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute) and node.attr in {"post", "put", "delete", "patch", "request", "Session"}:
                pytest.fail(f"{path.name} uses .{node.attr}")


# ---------------------------------------------------------------- eligibility rules

def test_read_only_key_is_eligible():
    decision = elig.evaluate_api_restrictions(READ_ONLY_RESTRICTIONS)
    assert decision.eligible is True


@pytest.mark.parametrize("flag", elig.REQUIRED_FALSE)
def test_any_write_permission_makes_key_ineligible(flag):
    assert elig.evaluate_api_restrictions({**READ_ONLY_RESTRICTIONS, flag: True}).eligible is False


def test_unknown_permission_flag_fails_closed_and_reading_required():
    assert elig.evaluate_api_restrictions({**READ_ONLY_RESTRICTIONS, "enableSomethingNew": True}).eligible is False
    assert elig.evaluate_api_restrictions({**READ_ONLY_RESTRICTIONS, "enableReading": False}).eligible is False
    assert elig.evaluate_api_restrictions(None).eligible is False


def test_missing_ip_restriction_is_a_warning_not_a_pass_condition():
    decision = elig.evaluate_api_restrictions({**READ_ONLY_RESTRICTIONS, "ipRestrict": False})
    assert decision.eligible is True
    assert any(f["check"] == "ipRestrict" and f["status"] == "WARN" for f in decision.findings)


@pytest.mark.parametrize("country", ["CA", "US", "ca"])
def test_operating_from_unsupported_jurisdiction_refused(country):
    assert elig.evaluate_attestation({**GOOD_ATTESTATION, "operating_country": country}).eligible is False


@pytest.mark.parametrize("missing", ["no_geo_bypass", "read_only_key"])
def test_attestations_are_mandatory(missing):
    assert elig.evaluate_attestation({**GOOD_ATTESTATION, missing: False}).eligible is False


def test_nigeria_kyc_requires_review_warning_but_is_not_blocked():
    decision = elig.evaluate_attestation(GOOD_ATTESTATION)
    assert decision.eligible is True
    assert any(f["check"] == "kyc_country" and f["status"] == "WARN" for f in decision.findings)


def test_account_status_must_be_normal():
    assert elig.evaluate_account_status({"data": "Normal"}).eligible is True
    assert elig.evaluate_account_status({"data": "Frozen"}).eligible is False


# ---------------------------------------------------------------- staged check

def _run(tmp_path, fake, attestation=GOOD_ATTESTATION, environ=ENV):
    return run_check(
        evidence_dir=tmp_path / "ev", operator_id="op", attestation=attestation, environ=environ,
        repo_root=tmp_path, commit_sha="test", transport=fake,
    )


def test_full_read_only_check_passes_and_evidence_contains_no_secrets(tmp_path):
    fake = FakeBinance()
    result = _run(tmp_path, fake)
    assert result.exit_code == EXIT_OK
    assert result.summary["account"]["non_zero_balances"] == [{"asset": "USDT", "free": "12.5", "locked": "0"}]
    assert result.summary["history_counts"]["BTCUSDT"] == {"orders_returned": 1, "trades_returned": 1}
    raw = (tmp_path / "ev" / JOURNAL_FILENAME).read_text(encoding="ascii")
    assert TEST_KEY not in raw and TEST_SECRET not in raw and "signature" not in raw
    types = [r["type"] for r in read_journal(tmp_path / "ev" / JOURNAL_FILENAME)]
    assert types[:5] == ["CHECK_STARTED", "PUBLIC_CONNECTIVITY", "OPERATOR_ATTESTATION", "CREDENTIALS", "KEY_PERMISSIONS"]
    assert types[-1] == "CHECK_COMPLETED"
    assert fake.paths().index("/sapi/v1/account/apiRestrictions") < fake.paths().index("/api/v3/account")


def test_restricted_location_stops_before_credentials(tmp_path):
    fake = FakeBinance(public_status=451)
    result = _run(tmp_path, fake)
    assert result.exit_code == EXIT_PUBLIC_BLOCKED
    types = [r["type"] for r in read_journal(tmp_path / "ev" / JOURNAL_FILENAME)]
    assert "CREDENTIALS" not in types
    assert all(not p.startswith("/sapi") for p in fake.paths())


def test_unsupported_operating_country_stops_before_any_signed_call(tmp_path):
    fake = FakeBinance()
    result = _run(tmp_path, fake, attestation={**GOOD_ATTESTATION, "operating_country": "CA"})
    assert result.exit_code == EXIT_ATTESTATION
    assert all(not p.startswith(("/sapi", "/api/v3/account")) for p in fake.paths())


def test_trading_enabled_key_is_refused_before_account_reads(tmp_path):
    fake = FakeBinance(restrictions={**READ_ONLY_RESTRICTIONS, "enableSpotAndMarginTrading": True})
    result = _run(tmp_path, fake)
    assert result.exit_code == EXIT_NOT_ELIGIBLE
    assert "/api/v3/account" not in fake.paths() and "/api/v3/myTrades" not in fake.paths()


def test_withdrawal_enabled_key_is_refused(tmp_path):
    fake = FakeBinance(restrictions={**READ_ONLY_RESTRICTIONS, "enableWithdrawals": True})
    assert _run(tmp_path, fake).exit_code == EXIT_NOT_ELIGIBLE


def test_missing_credentials_refused(tmp_path):
    assert _run(tmp_path, FakeBinance(), environ={}).exit_code == EXIT_CREDENTIALS


def test_cli_refuses_evidence_dir_inside_repository():
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import css_binance_readonly_check as cli
    finally:
        sys.path.pop(0)
    code = cli.main([
        "--evidence-dir", str(REPO_ROOT / "artifacts" / "x"), "--operator-id", "op",
        "--operating-country", "NG", "--kyc-country", "NG",
    ])
    assert code == 2
