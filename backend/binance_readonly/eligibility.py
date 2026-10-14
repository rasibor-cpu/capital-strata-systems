"""Eligibility gate for authenticated Binance read-only access.

Three independent checks, all of which must pass before any account endpoint other
than the key-permission report itself may be called:

1. Operator attestation: current operating country, KYC country, no geo-bypass
   (VPN/proxy) and a read-only key. Operating from a jurisdiction Binance.com does
   not serve is refused here, before any credential is loaded.
2. API key permissions (GET /sapi/v1/account/apiRestrictions): reading must be
   enabled and EVERY trading, transfer, withdrawal, margin, futures and options
   permission must be off. Any unknown permission flag reported as true fails closed.
3. Account status (GET /sapi/v1/account/status) must be "Normal".

The restricted-jurisdiction list reflects Binance.com's published restrictions as
known when this was written; it must be re-verified against Binance's current Terms
of Use. A Binance HTTP 451 response is always treated as authoritative.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

# ISO 3166-1 alpha-2. Verify against Binance.com Terms of Use before relying on it.
RESTRICTED_OPERATING_COUNTRIES = frozenset({
    "CA",  # Binance exited Canada (2023)
    "US",  # served only by Binance.US, a separate platform
    "NL",
    "CU", "IR", "KP", "SY",
})
REVIEW_REQUIRED_KYC_COUNTRIES = frozenset({
    "NG",  # Binance's Nigerian services were materially changed in 2024; confirm current status
})

REQUIRED_TRUE = ("enableReading",)
REQUIRED_FALSE = (
    "enableSpotAndMarginTrading",
    "enableWithdrawals",
    "enableInternalTransfer",
    "enableMargin",
    "enableFutures",
    "permitsUniversalTransfer",
    "enableVanillaOptions",
    "enablePortfolioMarginTrading",
    "enableFixApiTrade",
)
# Permission-like flags that may be true without granting any write capability.
ALLOWED_TRUE = frozenset({"enableReading", "ipRestrict", "enableFixReadOnly"})
_PERMISSION_FLAG = re.compile(r"^(enable|permits)[A-Z]")
_COUNTRY = re.compile(r"^[A-Z]{2}$")


@dataclass
class EligibilityDecision:
    eligible: bool
    findings: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"eligible": self.eligible, "findings": list(self.findings)}


def _finding(findings: list[dict[str, str]], check: str, status: str, detail: str) -> None:
    findings.append({"check": check, "status": status, "detail": detail})


def evaluate_attestation(attestation: Mapping[str, Any]) -> EligibilityDecision:
    findings: list[dict[str, str]] = []
    operating = str(attestation.get("operating_country", "")).strip().upper()
    kyc = str(attestation.get("kyc_country", "")).strip().upper()

    if not _COUNTRY.match(operating):
        _finding(findings, "operating_country", "FAIL", "two-letter ISO country of the host's current location is required")
    elif operating in RESTRICTED_OPERATING_COUNTRIES:
        _finding(findings, "operating_country", "FAIL",
                 f"{operating} is a jurisdiction Binance.com does not serve; authenticated access refused")
    else:
        _finding(findings, "operating_country", "PASS", operating)

    if not _COUNTRY.match(kyc):
        _finding(findings, "kyc_country", "FAIL", "two-letter ISO KYC country is required")
    elif kyc in REVIEW_REQUIRED_KYC_COUNTRIES:
        _finding(findings, "kyc_country", "WARN",
                 f"{kyc}: confirm with Binance that the account is in good standing for this KYC jurisdiction")
    else:
        _finding(findings, "kyc_country", "PASS", kyc)

    if attestation.get("no_geo_bypass") is not True:
        _finding(findings, "no_geo_bypass", "FAIL", "operator must attest that no VPN/proxy is used to change location")
    else:
        _finding(findings, "no_geo_bypass", "PASS", "attested")
    if attestation.get("read_only_key") is not True:
        _finding(findings, "read_only_key", "FAIL", "operator must attest the API key was created with reading only")
    else:
        _finding(findings, "read_only_key", "PASS", "attested")

    return EligibilityDecision(not any(f["status"] == "FAIL" for f in findings), findings)


def evaluate_api_restrictions(payload: Any) -> EligibilityDecision:
    findings: list[dict[str, str]] = []
    if not isinstance(payload, Mapping):
        _finding(findings, "api_restrictions", "FAIL", "permission report unavailable or malformed")
        return EligibilityDecision(False, findings)

    for name in REQUIRED_TRUE:
        status = "PASS" if payload.get(name) is True else "FAIL"
        _finding(findings, name, status, f"{name}={payload.get(name)!r} (must be true)")
    for name in REQUIRED_FALSE:
        value = payload.get(name)
        status = "PASS" if value in (False, None) else "FAIL"
        _finding(findings, name, status, f"{name}={value!r} (must be false)")
    for name, value in sorted(payload.items()):
        if _PERMISSION_FLAG.match(str(name)) and name not in REQUIRED_FALSE and name not in ALLOWED_TRUE:
            if value is True:
                _finding(findings, name, "FAIL", f"unknown permission {name}=true (fail closed)")
    if payload.get("ipRestrict") is True:
        _finding(findings, "ipRestrict", "PASS", "key is IP-restricted")
    else:
        _finding(findings, "ipRestrict", "WARN", "key is not IP-restricted; restricting it to this host's IP is recommended")

    return EligibilityDecision(not any(f["status"] == "FAIL" for f in findings), findings)


def evaluate_account_status(payload: Any) -> EligibilityDecision:
    data = payload.get("data") if isinstance(payload, Mapping) else None
    ok = data == "Normal"
    return EligibilityDecision(ok, [{
        "check": "account_status", "status": "PASS" if ok else "FAIL", "detail": f"data={data!r} (must be 'Normal')",
    }])


def combine(*decisions: EligibilityDecision) -> EligibilityDecision:
    findings = [f for d in decisions for f in d.findings]
    return EligibilityDecision(all(d.eligible for d in decisions), findings)
