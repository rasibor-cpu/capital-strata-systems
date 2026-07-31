from __future__ import annotations

from typing import Any, Mapping

from backend.runtime.broker_credential_diagnostics import diagnostics_payload
from backend.runtime.broker_readiness_framework import compute_broker_readiness_score
from backend.runtime.canonical_broker_runtime_state import (
    OVERALL_GREEN,
    STATUS_FAIL,
    STATUS_NOT_TESTED,
    STATUS_PASS,
    CanonicalBrokerRuntimeState,
    canonical_status,
)
from backend.runtime.canonical_broker_state_builder import (
    build_canonical_broker_runtime_state,
    canonical_state_from_payload,
)


# Diagnostic failure reasons that mean material is present but structurally invalid.
# Canonical credential_status=FAIL is NOT limited to total absence: diagnostics set
# credentials_present=False for both missing fields and invalid PEM/key material.
_STRUCTURAL_INVALID_CREDENTIAL_REASONS = frozenset(
    {
        "PEM_INVALID",
        "PRIVATE_KEY_INVALID",
        "JWT_GENERATION_FAILED",
        "JWT_SIGNATURE_INVALID",
    }
)


def map_canonical_credential_status_to_reporting(
    status: Any,
    *,
    diagnostics: Mapping[str, Any] | None = None,
) -> str:
    """Map canonical validation vocabulary to human/reporting credential vocabulary.

    Intentional dual-schema mapping (not an inconsistency):

    - Canonical validation schema (``CanonicalBrokerRuntimeState.credential_status``):
      ``PASS`` | ``FAIL`` | ``NOT_TESTED`` | ``UNKNOWN`` | …
    - Human/reporting / legacy credential schema:
      ``PRESENT`` | ``MISSING`` | ``INVALID`` | ``NOT_TESTED`` | ``UNKNOWN`` | …

    Canonical ``FAIL`` means diagnostics reported ``credentials_present=False``.
    That boolean is false both when required material is absent **and** when
    material is present but fails structural validation (e.g. ``PEM_INVALID``).
    Therefore FAIL is not mapped blindly to MISSING: diagnostic evidence selects
    ``MISSING`` vs ``INVALID``. ``INVALID`` is already used for credential display
    in ``scripts/css_live_dashboard.py`` and is the least-misleading supported
    reporting value for present-but-invalid material. Precise reason remains in
    ``failure_reason`` / credential diagnostics.

    Rules:
    - ``PASS`` → ``PRESENT``
    - ``FAIL`` + structural-invalid evidence → ``INVALID``
    - ``FAIL`` + absent/incomplete material → ``MISSING``
    - ``NOT_TESTED`` stays ``NOT_TESTED`` (never coerced to ``MISSING``)
    """
    normalized = canonical_status(status)
    if normalized == STATUS_PASS:
        return "PRESENT"
    if normalized == STATUS_NOT_TESTED:
        return STATUS_NOT_TESTED
    if normalized != STATUS_FAIL:
        return normalized

    diag = dict(diagnostics or {})
    reason = str(diag.get("failure_reason") or diag.get("canonical_failure_reason") or "").strip().upper()
    material_present = any(
        bool(diag.get(key))
        for key in (
            "key_present",
            "key_identifier_present",
            "secret_present",
            "private_key_present",
            "token_present",
            "account_present",
            "account_identifier_present",
            "base_url_present",
        )
    )
    # Present-but-invalid: structural failure reason, typically with partial material flags set.
    if reason in _STRUCTURAL_INVALID_CREDENTIAL_REASONS and (material_present or reason == "PEM_INVALID"):
        return "INVALID"
    # Absent or incomplete required fields (KEY_MISSING, SECRET_MISSING, MISSING_CREDENTIALS, …).
    return "MISSING"


def project_broker_reporting_fields(
    source: CanonicalBrokerRuntimeState | Mapping[str, Any] | None = None,
    *,
    credential_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Single reporting projection for startup, launcher, and Mission Control.

    Keeps credential presence, authentication, connection, operational readiness,
    and execution authority as separate concepts. Prefer this helper (or the
    canonical state it wraps) over recomputing incompatible defaults.
    """
    if isinstance(source, CanonicalBrokerRuntimeState):
        canonical = source
        payload: dict[str, Any] = {}
    else:
        payload = dict(source or {})
        embedded = payload.get("canonical_broker_runtime_state")
        if isinstance(embedded, Mapping) and embedded.get("broker"):
            canonical = canonical_state_from_payload({**payload, **dict(embedded)})
        else:
            canonical = build_canonical_broker_runtime_state(
                broker=str(payload.get("broker") or payload.get("selected_broker") or "NONE"),
                mode=str(payload.get("mode") or payload.get("broker_mode") or "paper"),
                runtime_payload=payload,
                env=payload.get("env") if isinstance(payload.get("env"), Mapping) else None,
            )

    diagnostics = diagnostics_payload(
        credential_diagnostics
        or payload.get("broker_credential_diagnostics")
        or payload.get("credential_diagnostics")
    )
    credentials_present = (
        canonical.credential_status == STATUS_PASS
        or bool(diagnostics.get("credentials_present"))
        or str(diagnostics.get("credential_status") or diagnostics.get("readiness_status") or "").upper()
        in {"PRESENT", "PASS", "READY"}
    )
    credential_status = map_canonical_credential_status_to_reporting(
        STATUS_PASS if credentials_present else canonical.credential_status,
        diagnostics=diagnostics,
    )
    credential_failure_reason = str(
        diagnostics.get("failure_reason")
        or diagnostics.get("canonical_failure_reason")
        or canonical.failure_reason
        or "NONE"
    )
    authentication_status = _surface_attempt_status(canonical.authentication_status)
    connection_status = _surface_attempt_status(canonical.connection_status)
    market_data_status = _surface_attempt_status(canonical.market_data_status)
    environment = dict(canonical.environment_evidence) if isinstance(canonical.environment_evidence, Mapping) else {}
    contamination_keys = [str(item) for item in environment.get("contamination_keys", []) if str(item)]
    environment_status = str(environment.get("status") or "PASS").upper()
    failure_reason = str(canonical.failure_reason or "NO_FAILURE")
    if failure_reason == "ENVIRONMENT_CONTAMINATION" and not (
        environment_status == "FAIL" and contamination_keys
    ):
        failure_reason = "NO_FAILURE"

    recommended_action = _recommended_action(
        credentials_present=credentials_present,
        diagnostics=diagnostics,
        authentication_status=authentication_status,
        operator_requested_live=_operator_requested_live(canonical, payload),
        failure_reason=failure_reason if failure_reason not in {"", "NO_FAILURE", "NONE"} else credential_failure_reason,
        credential_status=credential_status,
    )
    # Phase 154A readiness_score contract (pre-existing in broker_readiness_framework).
    # Prefer the score stamped on canonical state so surfaces stay identical.
    readiness_score = float(canonical.readiness_score)
    if readiness_score <= 0:
        readiness_score = compute_broker_readiness_score(
            credentials_present=credentials_present,
            authenticated=authentication_status == STATUS_PASS or authentication_status == "AUTHENTICATED",
            connected=connection_status == STATUS_PASS or connection_status == "CONNECTED",
            account_loaded=canonical.account_status == STATUS_PASS,
            market_data_ready=canonical.market_data_status == STATUS_PASS,
            execution_enabled=False,
        )

    # Live readiness progression (CLIENT_CREATED, …) is distinct from canonical
    # readiness_state which may mirror overall_status (RED/GREEN). Prefer the
    # progression enum when present on the payload.
    live_readiness_state = str(payload.get("readiness_state") or "").strip()
    if live_readiness_state in {
        "NOT_INITIALIZED",
        "CREDENTIALS_PRESENT",
        "CLIENT_CREATED",
        "TRANSPORT_CONNECTED",
        "AUTHENTICATED",
        "ACCOUNT_ACCESSIBLE",
        "ACCOUNT_DATA_AVAILABLE",
        "MARKET_DATA_AVAILABLE",
        "FULLY_OPERATIONAL",
    }:
        reporting_readiness_state = live_readiness_state
    else:
        reporting_readiness_state = str(canonical.readiness_state)

    return {
        "broker": canonical.broker,
        "broker_mode": canonical.mode,
        "credentials_present": credentials_present,
        "credential_status": credential_status,
        "credentials": credential_status,
        "credential_failure_reason": credential_failure_reason,
        "authentication_status": authentication_status,
        "connection_status": connection_status,
        "market_data_status": market_data_status,
        "operator_requested_live": _operator_requested_live(canonical, payload),
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "live_authority_state": str(payload.get("live_authority_state") or "BLOCKED"),
        "authority_reason": str(
            payload.get("authority_reason")
            or ("Operator Intent Missing" if canonical.operator_intent != "LIVE" else canonical.failure_reason or "Broker Execution Disabled")
        ),
        "execution_scope": canonical.execution_scope,
        "overall_status": canonical.overall_status,
        "failure_reason": failure_reason,
        "readiness_score": readiness_score,
        "readiness_state": reporting_readiness_state,
        "canonical_readiness_state": canonical.readiness_state,
        "status_provenance": dict(canonical.status_provenance),
        "contamination_keys": contamination_keys,
        "environment_validation_status": environment_status,
        "recommended_action": recommended_action,
        "canonical_broker_runtime_state": canonical.to_dict(),
        "state_hash": canonical.stable_hash(),
    }


def adapt_canonical_state_to_legacy_broker_payload(
    state: CanonicalBrokerRuntimeState | Mapping[str, Any],
    *,
    base_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = state if isinstance(state, CanonicalBrokerRuntimeState) else canonical_state_from_payload(state)
    base = dict(base_payload or {})
    account_snapshot = dict(canonical.account_snapshot) if isinstance(canonical.account_snapshot, Mapping) else {}
    balances_loaded = account_snapshot.get("balances_loaded") is True
    diagnostics = diagnostics_payload(
        base.get("broker_credential_diagnostics") or base.get("credential_diagnostics")
    )
    reporting_credential_status = map_canonical_credential_status_to_reporting(
        canonical.credential_status,
        diagnostics=diagnostics,
    )
    payload = {
        **base,
        "canonical_broker_runtime_state": canonical.to_dict(),
        "canonical_account_snapshot": account_snapshot,
        "account_snapshot": account_snapshot,
        "selected_broker": canonical.broker,
        "broker": canonical.broker,
        "broker_mode": canonical.mode,
        "credential_status": reporting_credential_status,
        "credentials": reporting_credential_status,
        "credentials_present": canonical.credential_status == STATUS_PASS,
        "credential_failure_reason": str(diagnostics.get("failure_reason") or canonical.failure_reason or "NONE"),
        "transport_status": "REACHABLE" if canonical.transport_status == STATUS_PASS else canonical.transport_status,
        "authentication_status": "AUTHENTICATED" if canonical.authentication_status == STATUS_PASS else canonical.authentication_status,
        "auth_status": (
            "AUTHENTICATED"
            if canonical.authentication_status == STATUS_PASS
            else ("NOT_TESTED" if canonical.authentication_status == STATUS_NOT_TESTED else "NOT_AUTHENTICATED")
        ),
        "broker_authenticated": canonical.authentication_status == STATUS_PASS,
        "authenticated": canonical.authentication_status == STATUS_PASS,
        "connection_status": "CONNECTED" if canonical.connection_status == STATUS_PASS else canonical.connection_status,
        "broker_connected": canonical.connection_status == STATUS_PASS,
        "connected": canonical.connection_status == STATUS_PASS,
        "account_data_health": "READY" if canonical.account_status == STATUS_PASS else canonical.account_status,
        "balance_position_status": "OK" if canonical.balance_status == STATUS_PASS else canonical.balance_status,
        "market_data_status": "OK" if canonical.market_data_status == STATUS_PASS else canonical.market_data_status,
        "product_price_status": "OK" if canonical.product_status == STATUS_PASS else canonical.product_status,
        "broker_health": canonical.overall_status,
        "readiness_state": canonical.readiness_state,
        "readiness_score": canonical.readiness_score,
        "go_no_go": "GO" if canonical.overall_status == OVERALL_GREEN else "NO GO",
        "execution_scope": canonical.execution_scope,
        "order_submission_status": canonical.order_submission_status,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        "can_live_execute": False,
        "broker_execution_status": "DISABLED",
        "live_micro_pilot_state": canonical.pilot_state,
        "authority_reason": str(base.get("authority_reason") or canonical.failure_reason or "Broker Execution Disabled"),
        "connection_error": (
            ""
            if canonical.failure_reason in {"", "NO_FAILURE", "NONE"}
            or (
                canonical.failure_reason == "ENVIRONMENT_CONTAMINATION"
                and str(dict(canonical.environment_evidence).get("status", "")).upper() != "FAIL"
            )
            else canonical.failure_reason
        ),
        "http_status": canonical.http_status,
        "error_code": canonical.error_code,
        "failure_reason": canonical.failure_reason,
        "warning_reasons": list(canonical.warning_reasons),
        "environment_diagnostics": dict(canonical.environment_evidence),
        "broker_environment_profile": dict(canonical.environment_evidence),
        "profile": dict(canonical.environment_evidence).get("profile", "UNSELECTED"),
        "environment": dict(canonical.environment_evidence).get("environment", canonical.mode),
        "permissions_classification": dict(canonical.environment_evidence).get("permissions_classification", "UNKNOWN"),
        "profile_fingerprint": dict(canonical.environment_evidence).get("profile_fingerprint", ""),
        "contamination_status": dict(canonical.environment_evidence).get("status", "UNKNOWN"),
        "account_evidence": dict(canonical.account_evidence),
        "status_provenance": dict(canonical.status_provenance),
        "state_hash": canonical.stable_hash(),
    }
    if account_snapshot:
        payload["account_loaded"] = account_snapshot.get("account_loaded", canonical.account_status == STATUS_PASS)
        payload["balances_loaded"] = balances_loaded
        payload["portfolio_loaded"] = account_snapshot.get("portfolio_loaded", False)
        payload["market_data_loaded"] = account_snapshot.get("market_data_loaded", canonical.market_data_status == STATUS_PASS)
        payload["currency"] = account_snapshot.get("currency", base.get("currency"))
        if balances_loaded:
            payload["account_equity"] = account_snapshot.get("equity")
            payload["cash"] = account_snapshot.get("cash")
            payload["buying_power"] = account_snapshot.get("buying_power")
            payload["available_balance"] = account_snapshot.get("available_balance")
            payload["margin_available"] = account_snapshot.get("margin_available")
        elif canonical.mode == "live":
            payload["account_equity"] = None
            payload["cash"] = None
            payload["buying_power"] = None
            payload["available_balance"] = None
            payload["margin_available"] = None
    return payload


def broker_environment_profile_view(
    profile_source: Mapping[str, Any] | None = None,
    *,
    fallback: Mapping[str, Any] | None = None,
    default_profile: str = "UNSELECTED",
    default_environment: str = "paper",
    inactive: bool = False,
) -> dict[str, Any]:
    source = dict(profile_source) if isinstance(profile_source, Mapping) else {}
    fallback_payload = dict(fallback) if isinstance(fallback, Mapping) else {}
    if inactive:
        return {
            "profile": default_profile,
            "environment": "inactive",
            "permissions_classification": "NOT_APPLICABLE",
            "profile_fingerprint": "",
            "contamination_status": "NOT_APPLICABLE",
            "contamination_keys": [],
            "credential_values_redacted": True,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }

    contamination_keys = source.get("contamination_keys", fallback_payload.get("contamination_keys", [])) or []
    return {
        "profile": str(source.get("profile", fallback_payload.get("profile", default_profile))),
        "environment": str(source.get("environment", fallback_payload.get("environment", default_environment))),
        "permissions_classification": str(
            source.get("permissions_classification", fallback_payload.get("permissions_classification", "UNKNOWN"))
        ),
        "profile_fingerprint": str(source.get("profile_fingerprint", fallback_payload.get("profile_fingerprint", ""))),
        "contamination_status": str(source.get("status", fallback_payload.get("contamination_status", "UNKNOWN"))),
        "contamination_keys": [str(item) for item in contamination_keys if str(item)],
        "credential_values_redacted": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def adapt_legacy_payload_to_canonical_state(payload: Mapping[str, Any] | None = None) -> CanonicalBrokerRuntimeState:
    return canonical_state_from_payload(payload or {})


def _surface_attempt_status(status: str) -> str:
    normalized = canonical_status(status)
    if normalized in {STATUS_NOT_TESTED, "NOT_ATTEMPTED"}:
        return STATUS_NOT_TESTED
    return normalized


def _operator_requested_live(canonical: CanonicalBrokerRuntimeState, payload: Mapping[str, Any]) -> bool:
    if canonical.operator_intent == "LIVE":
        return True
    value = payload.get("operator_requested_live")
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "live"}


def _recommended_action(
    *,
    credentials_present: bool,
    diagnostics: Mapping[str, Any],
    authentication_status: str,
    operator_requested_live: bool,
    failure_reason: str,
    credential_status: str = "",
) -> str:
    diagnostic_action = str(diagnostics.get("recommended_action") or diagnostics.get("remediation_hint") or "").strip()
    if credential_status == "INVALID":
        return diagnostic_action or "Verify the Coinbase private key file or value"
    if credentials_present:
        if diagnostic_action and "configure" in diagnostic_action.lower() and "credential" in diagnostic_action.lower():
            diagnostic_action = ""
        if failure_reason == "ENVIRONMENT_CONTAMINATION":
            return "Remove practice/sandbox contamination from the live environment"
        if not operator_requested_live or authentication_status == STATUS_NOT_TESTED:
            return diagnostic_action or "No credential remediation required"
        if authentication_status == STATUS_FAIL:
            return diagnostic_action or "Verify broker credentials and read-only permissions"
        return diagnostic_action or "No credential remediation required"
    return diagnostic_action or "Configure broker credentials"


__all__ = [
    "adapt_canonical_state_to_legacy_broker_payload",
    "adapt_legacy_payload_to_canonical_state",
    "broker_environment_profile_view",
    "map_canonical_credential_status_to_reporting",
    "project_broker_reporting_fields",
]
