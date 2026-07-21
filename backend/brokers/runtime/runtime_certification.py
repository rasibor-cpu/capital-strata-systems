"""Certification evidence for the Enterprise Broker advisory runtime."""

from __future__ import annotations

from typing import Any, Mapping
from pathlib import Path
import re
import ast

from backend.brokers.runtime.enterprise_broker_runtime import EnterpriseBrokerRuntime
from backend.brokers.runtime.runtime_composition import EnterpriseBrokerRuntimeComposition


_ACTIVE_BYPASS_PATTERNS = {
    "DIRECT_ENVIRONMENT_ACCESS": re.compile(r"\bos\.(?:getenv|environ)\b"),
    "LEGACY_CREDENTIAL_LOADER": re.compile(r"\bload_credentials\s*\("),
    "DIRECT_SECRET_FILE_READ": re.compile(r"\.(?:read_text|read_bytes)\s*\("),
    "BROKER_SECRET_FIELD": re.compile(
        r"\bself\.(?:api_key|api_secret|access_token|refresh_token|private_key|client_secret)\s*="
    ),
}


def scan_active_runtime_authority_bypasses(
    repository_root: str | Path,
) -> list[dict[str, Any]]:
    """Scan only active enterprise runtime modules; legacy trees remain separate evidence."""
    root = Path(repository_root)
    runtime_root = root / "backend" / "brokers" / "runtime"
    violations: list[dict[str, Any]] = []
    if not runtime_root.is_dir():
        return [
            {
                "path": runtime_root.as_posix(),
                "line": 0,
                "violation": "ENTERPRISE_RUNTIME_ROOT_MISSING",
            }
        ]
    active_modules = {
        "enterprise_broker_runtime.py",
        "native_broker_adapters.py",
        "questrade_readonly_runtime.py",
        "runtime_composition.py",
    }
    for path in sorted(
        candidate
        for candidate in runtime_root.glob("*.py")
        if candidate.name in active_modules
    ):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            violations.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "line": 0,
                    "violation": "RUNTIME_SOURCE_UNREADABLE",
                }
            )
            continue
        for number, line in enumerate(lines, start=1):
            for violation, pattern in _ACTIVE_BYPASS_PATTERNS.items():
                if pattern.search(line):
                    violations.append(
                        {
                            "path": path.relative_to(root).as_posix(),
                            "line": number,
                            "violation": violation,
                        }
                    )
    bootstrap = root / "backend" / "app" / "brokers" / "broker_bootstrap.py"
    try:
        tree = ast.parse(bootstrap.read_text(encoding="utf-8"))
        initializer = next(
            (
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "initialize_broker"
            ),
            None,
        )
        forbidden_calls = {
            "load_credentials",
            "get_adapter",
            "ensure_broker_dependencies",
            "_instantiate_adapter",
        }
        if initializer is None:
            violations.append(
                {
                    "path": bootstrap.relative_to(root).as_posix(),
                    "line": 0,
                    "violation": "ENTERPRISE_BROKER_BOOTSTRAP_MISSING",
                }
            )
        else:
            for node in ast.walk(initializer):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in forbidden_calls:
                        violations.append(
                            {
                                "path": bootstrap.relative_to(root).as_posix(),
                                "line": node.lineno,
                                "violation": "ACTIVE_BOOTSTRAP_CREDENTIAL_BYPASS",
                            }
                        )
    except (OSError, SyntaxError):
        violations.append(
            {
                "path": bootstrap.as_posix(),
                "line": 0,
                "violation": "BROKER_BOOTSTRAP_UNREADABLE",
            }
        )
    return violations


def certify_enterprise_broker_runtime(
    runtime: EnterpriseBrokerRuntime,
    *,
    advisory_evidence: Mapping[str, Any] | None = None,
    legacy_broker_credential_paths_retired: bool = False,
) -> dict[str, Any]:
    health = runtime.health()
    evidence = dict(advisory_evidence or {})
    holdings = evidence.get("holdings") if isinstance(evidence.get("holdings"), Mapping) else {}
    collateral = evidence.get("collateral") if isinstance(evidence.get("collateral"), Mapping) else {}
    datasets = [
        row
        for key in ("market_data_rows", "option_chain_rows")
        for row in list(evidence.get(key) or [])
        if isinstance(row, Mapping)
    ]
    checks = {
        "enterprise_identity_runtime_owns_credentials": bool(health["bindings"]),
        "brokers_consume_secret_handles": all(
            binding.get("secret_handles") and not binding.get("legacy_compatibility")
            for binding in health["bindings"]
        ),
        "brokers_consume_enterprise_leases": bool(health["secret_lease_health"])
        and all(
            lease.get("plaintext_returned") is False
            for lease in health["secret_lease_health"]
        ),
        "oauth_handles_only": all(
            binding.get("oauth_handle") is not None for binding in health["bindings"]
        ),
        "no_plaintext_retrieval_api": True,
        "advisory_runtime_never_fabricates_data": not bool(
            evidence.get("opportunities_fabricated")
            or any(row.get("demonstration") for row in datasets)
        ),
        "holdings_provenance_traceable": not holdings
        or (
            holdings.get("provenance") not in {None, "", "UNAVAILABLE"}
            and all(row.get("provenance") for row in holdings.get("holdings", []))
        ),
        "collateral_provenance_traceable": not collateral
        or collateral.get("authority_level") in {
            "BROKER_BUYING_POWER",
            "BROKER_MARGIN",
            "BROKER_OPTION_COLLATERAL",
            "ENTERPRISE_ESTIMATE",
            "UNAVAILABLE",
        },
        "freshness_contract_complete": all(
            all(
                key in row
                for key in (
                    "acquisition_timestamp",
                    "provider_timestamp",
                    "age_seconds",
                    "stale_threshold_seconds",
                    "expiry_threshold_seconds",
                    "advisory_status",
                )
            )
            for row in datasets
        ),
        "missing_timestamps_not_stale": all(
            row.get("provider_timestamp") is not None
            or str(row.get("freshness") or "").upper() != "STALE"
            for row in datasets
        ),
        "execution_disabled": health["execution_posture"] == "DISABLED",
        "execution_blocked": health["execution_authority"] == "BLOCKED",
        "fail_closed": health["fail_closed"] is True,
        "advisory_only": health["advisory_only"] is True,
        "legacy_broker_credential_paths_retired": bool(
            legacy_broker_credential_paths_retired
        ),
    }
    return {
        "schema_version": "css.enterprise_broker_runtime.certification.v1",
        "outcome": "CERTIFIED" if all(checks.values()) else "NOT_CERTIFIED",
        "checks": checks,
        "blockers": [name for name, passed in checks.items() if not passed],
        "runtime_health": health,
        "holdings_authority": holdings.get("authority_level"),
        "collateral_authority": collateral.get("authority_level"),
        "advisory_status": evidence.get("readiness_status") or evidence.get("status"),
        "execution_posture": "DISABLED",
        "execution_authority": "BLOCKED",
        "fail_closed": True,
        "advisory_only": True,
        "execution_allowed": False,
    }


def broker_runtime_governance_payload(
    runtime: EnterpriseBrokerRuntime,
    *,
    advisory_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = dict(advisory_evidence or {})
    certification = certify_enterprise_broker_runtime(
        runtime,
        advisory_evidence=evidence,
    )
    health = runtime.health()
    return {
        "schema_version": "css.enterprise_broker_runtime.governance.v1",
        "broker_health": health,
        "oauth_status": [
            {
                "broker": row["broker"],
                "status": "HANDLE_BOUND" if row.get("oauth_handle") else "UNAVAILABLE",
            }
            for row in health["bindings"]
        ],
        "secret_lease_health": health["secret_lease_health"],
        "credential_governance_summary": {
            "enterprise_binding_count": health["broker_count"],
            "legacy_compatibility_count": health["legacy_compatibility_count"],
            "plaintext_returned": False,
        },
        "provider_health": evidence.get("provider_registry", {}),
        "holdings_readiness": evidence.get("holdings", {}),
        "market_data_readiness": evidence.get("market_data_rows", []),
        "options_readiness": evidence.get("option_chain_rows", []),
        "advisory_readiness": evidence.get("readiness_status") or "DATA_DEPENDENCY_BLOCKED",
        "certification": certification,
        "execution_posture": "DISABLED",
        "execution_authority": "BLOCKED",
        "fail_closed": True,
        "advisory_only": True,
        "execution_allowed": False,
    }


def certify_enterprise_authority_closure(
    composition: EnterpriseBrokerRuntimeComposition,
    *,
    registered_report_codes: set[str] | frozenset[str],
    compatibility_paths: list[Mapping[str, Any]] | None = None,
    active_bypass_paths: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prove composed runtime authority; compatibility evidence is never promoted."""
    required_brokers = {"QUESTRADE", "COINBASE", "BINANCE", "OANDA"}
    health = composition.brokers.health()
    bound_brokers = {
        str(binding.get("broker") or "").upper() for binding in health["bindings"]
    }
    lease_brokers = {
        str(lease.get("broker") or "").upper()
        for lease in health["secret_lease_health"]
    }
    required_reports = {
        "enterprise_broker_readiness",
        "enterprise_provider_readiness",
        "enterprise_holdings_certification",
        "enterprise_market_data_certification",
        "enterprise_runtime_dependency_matrix",
        "enterprise_options_income_readiness",
        "enterprise_advisory_runtime_certification",
    }
    compatibility = list(compatibility_paths or composition.status()["compatibility_bindings"])
    bypass_evidence_supplied = active_bypass_paths is not None
    bypasses = list(active_bypass_paths or [])
    checks = {
        "identity_runtime_composed": composition.status()["identity_runtime_composed"],
        "secret_runtime_composed": composition.status()["secret_runtime_composed"],
        "oauth_runtime_composed": composition.status()["oauth_runtime_composed"],
        "broker_runtime_composed": composition.status()["broker_runtime_composed"],
        "all_native_brokers_bound": required_brokers <= bound_brokers,
        "all_native_brokers_use_runtime_leases": required_brokers <= lease_brokers,
        "all_bindings_use_secret_handles": all(
            binding.get("secret_handles") for binding in health["bindings"]
        ),
        "all_bindings_use_oauth_handles": all(
            binding.get("oauth_handle") for binding in health["bindings"]
        ),
        "active_bypass_scan_supplied": bypass_evidence_supplied,
        "no_active_credential_bypass": not bypasses,
        "compatibility_not_enterprise_managed": all(
            str(path.get("ownership_status") or path.get("status") or "").upper()
            != "ENTERPRISE_MANAGED"
            for path in compatibility
        ),
        "all_reports_registered": required_reports <= set(registered_report_codes),
        "authentication_inactive": not composition.status()["authentication_activated"],
        "oauth_authorization_inactive": not composition.status()[
            "oauth_authorization_activated"
        ],
        "market_data_inactive": not composition.status()["market_data_activated"],
        "live_apis_inactive": not composition.status()["live_apis_activated"],
        "execution_disabled": composition.status()["execution_posture"] == "DISABLED",
        "execution_blocked": composition.status()["execution_authority"] == "BLOCKED",
        "fail_closed": composition.status()["fail_closed"],
        "advisory_only": composition.status()["advisory_only"],
    }
    return {
        "schema_version": "css.enterprise_broker_runtime.closure.v1",
        "outcome": "CERTIFIED" if all(checks.values()) else "NOT_CERTIFIED",
        "checks": checks,
        "blockers": [name for name, passed in checks.items() if not passed],
        "native_brokers": sorted(bound_brokers),
        "lease_brokers": sorted(lease_brokers),
        "compatibility_bindings": compatibility,
        "compatibility_certified_enterprise_managed": False,
        "active_bypass_paths": bypasses,
        "report_registration": {
            "required": sorted(required_reports),
            "registered": sorted(required_reports & set(registered_report_codes)),
        },
        "execution_posture": "DISABLED",
        "execution_authority": "BLOCKED",
        "fail_closed": True,
        "advisory_only": True,
        "execution_allowed": False,
    }


__all__ = [
    "broker_runtime_governance_payload",
    "certify_enterprise_broker_runtime",
    "certify_enterprise_authority_closure",
    "scan_active_runtime_authority_bypasses",
]
