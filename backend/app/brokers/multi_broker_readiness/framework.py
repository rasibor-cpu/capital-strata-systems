"""Phase 189 — multi-broker operational readiness orchestrator.

Offline / config-only. Does not authenticate. Does not enable execution.
Certification scope: broker + asset class + provider version.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping

from backend.app.brokers.multi_broker_readiness.audit_matrix import (
    broker_readiness_from_audit,
    get_capability_profile,
)
from backend.app.brokers.multi_broker_readiness.auth_ttl import AuthorizationTTLRegistry
from backend.app.brokers.multi_broker_readiness.contracts import (
    FRAMEWORK_VERSION,
    SCHEMA_VERSION,
    AssetClass,
    BrokerOperationalReadiness,
    BrokerProviderFingerprint,
    BrokerReadOnlyCertification,
    BrokerType,
)
from backend.app.brokers.multi_broker_readiness.evidence import build_broker_evidence
from backend.app.brokers.multi_broker_readiness.firewall import verify_multi_broker_firewall
from backend.app.brokers.multi_broker_readiness.precheck import run_controlled_online_precheck
from backend.app.brokers.multi_broker_readiness.rc004 import evaluate_rc004_readiness
from backend.app.brokers.multi_broker_readiness.state_machine import BrokerCertificationStateMachine


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _broker_key(broker: BrokerType | str) -> str:
    return broker.value if isinstance(broker, BrokerType) else str(broker).upper()


def _asset_key(asset_class: AssetClass | str) -> str:
    return asset_class.value if isinstance(asset_class, AssetClass) else str(asset_class).upper()


class MultiBrokerReadinessFramework:
    FORBIDDEN_METHODS: frozenset[str] = frozenset(
        {
            "place_order",
            "submit_order",
            "cancel_order",
            "modify_order",
            "arm_live_authority",
            "enable_execution",
            "authenticate",
            "bypass_anti_bleed",
            "bypass_margin",
            "bypass_risk_governor",
            "bypass_phase152a",
        }
    )

    def __init__(self, *, ttl_registry: AuthorizationTTLRegistry | None = None) -> None:
        self._ttl = ttl_registry or AuthorizationTTLRegistry()
        self._generation: dict[str, int] = {}
        self._last_cert: dict[str, BrokerReadOnlyCertification] = {}
        self._last_evidence_hash: dict[str, str] = {}

    @property
    def ttl_registry(self) -> AuthorizationTTLRegistry:
        return self._ttl

    def evaluate_operational_readiness(
        self,
        broker: BrokerType | str,
        *,
        asset_class: AssetClass | str = AssetClass.NONE,
        env: Mapping[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> BrokerOperationalReadiness:
        import os

        source = env if isinstance(env, Mapping) else os.environ
        broker_key = _broker_key(broker)
        asset_key = _asset_key(asset_class)
        ts = timestamp or _utc_now()
        audit = broker_readiness_from_audit(broker_key)
        profile = get_capability_profile(broker_key)
        precheck = run_controlled_online_precheck(broker_key, source, asset_class=asset_key)
        blockers = list(precheck.blockers)
        if audit.get("classification") == "BLOCKED":
            blockers.append("roadmap_or_policy_blocked")
        classification = str(audit.get("classification") or "NOT_STARTED")
        if precheck.status == "BLOCKED" or classification == "BLOCKED":
            readiness_state = "BLOCKED"
        elif classification == "COMPLETE" and precheck.status == "PASS":
            readiness_state = "READY"
        else:
            readiness_state = "PARTIAL"
        return BrokerOperationalReadiness(
            broker_type=broker_key,
            asset_class=asset_key,
            timestamp=ts,
            readiness_state=readiness_state,
            classification=classification,
            credentials_present=precheck.credentials_present,
            endpoint_valid=precheck.endpoint_valid,
            environment_valid=precheck.environment_valid,
            configuration_complete=precheck.configuration_complete,
            provider_compatible=precheck.provider_compatible,
            schema_compatible=precheck.schema_compatible,
            capability_compatible=precheck.capability_compatible,
            market_data_capable=bool(profile.market_data),
            account_capable=bool(profile.account_information),
            execution_capable=False,
            paper_supported=bool(profile.paper_trading),
            live_read_only_supported=bool(profile.market_data and profile.account_information),
            certification_ready=bool(audit.get("certification_readiness")),
            evidence_ready=bool(audit.get("evidence_readiness")),
            remaining_blockers=tuple(dict.fromkeys(blockers)),
            capability_profile=profile.as_dict(),
            diagnostics={
                "precheck_status": precheck.status,
                "audit_notes": audit.get("notes", ""),
                "authentication_performed": False,
                "execution_authority": False,
            },
            execution_authority=False,
        )

    def certify_readonly(
        self,
        broker: BrokerType | str,
        *,
        asset_class: AssetClass | str = AssetClass.NONE,
        env: Mapping[str, Any] | None = None,
        evidence_flags: Mapping[str, bool] | None = None,
        timestamp: str | None = None,
        issue_ttl_seconds: int | None = None,
        signoff_artifact_present: bool | None = None,
        endpoint: str = "",
        adapter_version: str = "",
        api_version: str = "",
    ) -> BrokerReadOnlyCertification:
        import os

        source = env if isinstance(env, Mapping) else os.environ
        broker_key = _broker_key(broker)
        asset_key = _asset_key(asset_class)
        scope_key = f"{broker_key}:{asset_key}"
        ts = timestamp or _utc_now()
        profile = get_capability_profile(broker_key)
        readiness = self.evaluate_operational_readiness(
            broker_key, asset_class=asset_key, env=source, timestamp=ts
        )
        precheck = run_controlled_online_precheck(broker_key, source, asset_class=asset_key)
        rc004 = evaluate_rc004_readiness(
            broker_key,
            signoff_artifact_present=signoff_artifact_present,
            extra_blockers=readiness.remaining_blockers,
        )
        fw = verify_multi_broker_firewall()
        fingerprint = BrokerProviderFingerprint(
            broker_type=broker_key,
            asset_class=asset_key,
            adapter_version=adapter_version or FRAMEWORK_VERSION,
            endpoint=endpoint,
            api_version=api_version or "v1",
        )

        machine = BrokerCertificationStateMachine()
        flags = dict(evidence_flags or {})
        if precheck.status == "BLOCKED" or readiness.classification == "BLOCKED":
            reason = "precheck_blocked:" + ",".join(
                precheck.blockers or readiness.remaining_blockers
            )
            final_state, history = machine.run_to_completion(
                flags, blocked=True, failure_reason=reason
            )
        elif not fw["ok"]:
            final_state, history = machine.run_to_completion(
                flags, failed=True, failure_reason="firewall_violation"
            )
        else:
            flags.setdefault("config_present", precheck.credentials_present)
            flags.setdefault(
                "config_validated",
                precheck.configuration_complete and precheck.capability_compatible,
            )
            final_state, history = machine.run_to_completion(flags)

        # TTL is broker-independent and asset-independent (execution remains disabled).
        if issue_ttl_seconds is not None and final_state not in {"BLOCKED", "FAILED"}:
            self._ttl.issue(broker_key, ttl_seconds=issue_ttl_seconds)
        ttl_status = self._ttl.status(broker_key)

        gen = self._generation.get(scope_key, 0)
        parent_id = ""
        prev_hash = self._last_evidence_hash.get(scope_key, "")
        if final_state == "READ_ONLY_CERTIFIED":
            gen += 1
            self._generation[scope_key] = gen
            parent = self._last_cert.get(scope_key)
            parent_id = parent.certification_id if parent else ""

        cert_id = "brc-" + hashlib.sha256(
            f"{scope_key}|{gen}|{ts}|{fingerprint.fingerprint_hash()}|{FRAMEWORK_VERSION}".encode()
        ).hexdigest()[:24]

        blockers = tuple(
            dict.fromkeys(
                list(readiness.remaining_blockers)
                + list(rc004.remaining_blockers)
                + ([] if fw["ok"] else ["firewall_violation"])
            )
        )

        evidence = build_broker_evidence(
            broker_type=broker_key,
            asset_class=asset_key,
            timestamp=ts,
            certification_state=final_state,
            provider_fingerprint_hash=fingerprint.fingerprint_hash(),
            capability_profile=profile.as_dict(),
            operational_readiness=readiness.as_dict(),
            remaining_blockers=blockers,
            ttl_status=ttl_status.as_dict(),
            rc004_readiness=rc004.as_dict(),
            provider_versions={
                "framework": FRAMEWORK_VERSION,
                "broker": broker_key,
                "asset_class": asset_key,
            },
            schema_versions={"contracts": SCHEMA_VERSION, "evidence": SCHEMA_VERSION},
            gate_results=[
                {"gate": "precheck", "passed": precheck.status == "PASS", "grants_execution": False},
                {"gate": "firewall", "passed": fw["ok"], "grants_execution": False},
                {"gate": "capability", "passed": precheck.capability_compatible, "grants_execution": False},
                {"gate": "rc004_live_unlock", "passed": False, "grants_execution": False},
            ],
            diagnostics={
                "history": [
                    {
                        "from": h.from_state,
                        "to": h.to_state,
                        "success": h.success,
                        "failure_reason": h.failure_reason,
                    }
                    for h in history
                ],
                "authentication_performed": False,
                "network_performed": False,
            },
            parent_certification_id=parent_id,
            previous_evidence_hash=prev_hash,
            lineage_generation=gen,
        )

        reason = ""
        if final_state in {"BLOCKED", "FAILED"}:
            reason = history[-1].failure_reason if history else final_state
        elif final_state != "READ_ONLY_CERTIFIED":
            reason = history[-1].failure_reason if history else "incomplete"

        cert = BrokerReadOnlyCertification(
            broker_type=broker_key,
            asset_class=asset_key,
            timestamp=ts,
            certification_state=final_state,
            failure_reason=reason,
            diagnostics={
                "authentication_performed": False,
                "network_performed": False,
                "execution_authority": False,
                "firewall_ok": fw["ok"],
            },
            certification_id=cert_id,
            certification_generation=gen,
            certification_timestamp=ts,
            provider_fingerprint_hash=fingerprint.fingerprint_hash(),
            parent_certification_id=parent_id,
            evidence_hash=evidence.evidence_hash,
            capability_profile=profile.as_dict(),
            operational_readiness=readiness,
            ttl_status=ttl_status.as_dict(),
            rc004_readiness=rc004.as_dict(),
            remaining_blockers=blockers,
            execution_authority=False,
        )
        self._last_cert[scope_key] = cert
        self._last_evidence_hash[scope_key] = evidence.evidence_hash
        return cert

    def __getattribute__(self, name: str) -> Any:
        if name in MultiBrokerReadinessFramework.FORBIDDEN_METHODS:
            raise AttributeError(
                f"Phase 189 forbids '{name}' on MultiBrokerReadinessFramework"
            )
        return object.__getattribute__(self, name)
