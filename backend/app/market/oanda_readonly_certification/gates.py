"""Phase 187A — read-only certification gates (documentation + offline evaluation).

No gate grants execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    name: str
    passed: bool
    reason: str
    grants_execution: bool = False

    def __post_init__(self) -> None:
        if self.grants_execution:
            raise ValueError("read-only gates must not grant execution")


# Gate catalog — offline evaluation uses boolean evidence keys only.
READ_ONLY_GATES: tuple[tuple[str, str, str], ...] = (
    ("G01", "credentials_present", "config_present"),
    ("G02", "environment_valid", "config_validated"),
    ("G03", "endpoint_valid", "config_validated"),
    ("G04", "dns_ok", "dns_ok"),
    ("G05", "tls_certificate_valid", "tls_ok"),
    ("G06", "clock_skew_ok", "tls_ok"),
    ("G07", "authentication_ok", "auth_ok"),
    ("G08", "account_permissions_ok", "account_ok"),
    ("G09", "account_scope_ok", "account_scope_ok"),
    ("G10", "instrument_visibility_ok", "marketdata_ok"),
    ("G11", "rate_limits_ok", "marketdata_ok"),
    ("G12", "schema_compatibility_ok", "config_validated"),
    ("G13", "provider_version_ok", "config_validated"),
    ("G14", "market_freshness_ok", "marketdata_ok"),
)


def evaluate_gates(evidence: Mapping[str, bool]) -> tuple[GateResult, ...]:
    results: list[GateResult] = []
    for gate_id, name, evidence_key in READ_ONLY_GATES:
        passed = bool(evidence.get(evidence_key, False))
        results.append(
            GateResult(
                gate_id=gate_id,
                name=name,
                passed=passed,
                reason="pass" if passed else f"missing_or_false:{evidence_key}",
                grants_execution=False,
            )
        )
    return tuple(results)
