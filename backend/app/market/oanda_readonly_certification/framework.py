"""Phase 187A / 187A-R1 — offline OANDA read-only certification framework.

NO NETWORK. NO AUTHENTICATION. NO LIVE CONNECTION. NO EXECUTION.
All progress is driven by injected boolean evidence / diagnostic maps only.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping

from backend.app.market.oanda_readonly_certification.contracts import (
    FRAMEWORK_VERSION,
    PROVIDER_NAME,
    PROVIDER_VERSION,
    SCHEMA_VERSION,
    OandaAccountStatus,
    OandaAuthenticationStatus,
    OandaConnectionStatus,
    OandaMarketDataStatus,
    OandaReadOnlyCertification,
)
from backend.app.market.oanda_readonly_certification.evidence import build_evidence_package
from backend.app.market.oanda_readonly_certification.fingerprint import (
    ProviderFingerprint,
    build_provider_fingerprint,
)
from backend.app.market.oanda_readonly_certification.gates import evaluate_gates
from backend.app.market.oanda_readonly_certification.invalidation import evaluate_invalidation
from backend.app.market.oanda_readonly_certification.replay import (
    ReplayProtectionRegistry,
    evaluate_replay,
)
from backend.app.market.oanda_readonly_certification.state_machine import OandaReadOnlyStateMachine


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _make_certification_id(generation: int, timestamp: str, fingerprint_hash: str) -> str:
    material = f"{generation}|{timestamp}|{fingerprint_hash}|{SCHEMA_VERSION}".encode("utf-8")
    return "orc-" + hashlib.sha256(material).hexdigest()[:24]


class OandaReadOnlyCertificationFramework:
    """Architectural certification runner — offline evidence only."""

    FORBIDDEN_METHODS: frozenset[str] = frozenset(
        {
            "submit_order",
            "place_order",
            "cancel_order",
            "modify_order",
            "arm_live_authority",
            "enable_execution",
            "set_anti_bleed",
            "modify_anti_bleed",
            "modify_risk_governor",
            "modify_phase152a",
            "modify_margin",
            "disable_kill_switch",
            "fetch_market_data",
            "authenticate",
            "connect",
            "request",
        }
    )

    def __init__(self) -> None:
        self._machine = OandaReadOnlyStateMachine()
        self._generation = 0
        self._current_cert_id = ""
        self._parent_cert_id = ""
        self._previous_evidence_hash = ""
        self._fingerprint: ProviderFingerprint | None = None
        self._replay = ReplayProtectionRegistry()
        self._last_cert: OandaReadOnlyCertification | None = None

    @property
    def state(self) -> str:
        return self._machine.state

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def provider_fingerprint(self) -> ProviderFingerprint | None:
        return self._fingerprint

    def certify(
        self,
        evidence_flags: Mapping[str, bool],
        *,
        blocked: bool = False,
        failed: bool = False,
        failure_reason: str = "",
        diagnostics: Mapping[str, Any] | None = None,
        timestamp: str | None = None,
        fingerprint: ProviderFingerprint | None = None,
    ) -> OandaReadOnlyCertification:
        """Run initial certification path from injected flags."""
        ts = timestamp or _utc_now()
        diag = dict(diagnostics or {})
        fp = fingerprint or build_provider_fingerprint(
            endpoint=str(diag.get("endpoint") or ""),
            api_version=str(diag.get("api_version") or "v3"),
        )

        # Fingerprint change against an active certified lineage forces invalidation first.
        if self._fingerprint is not None and self._machine.state in {
            "READ_ONLY_CERTIFIED",
            "REVALIDATED",
        }:
            inv = evaluate_invalidation(
                prior_fingerprint=self._fingerprint,
                current_fingerprint=fp,
            )
            if inv.invalidated:
                return self.invalidate(
                    current_fingerprint=fp,
                    explicit_triggers=inv.triggers,
                    timestamp=ts,
                    diagnostics=diag,
                )

        final_state, history = self._machine.run_to_completion(
            evidence_flags,
            blocked=blocked,
            failed=failed,
            failure_reason=failure_reason,
        )
        return self._finalize(
            final_state=final_state,
            history=history,
            evidence_flags=evidence_flags,
            diag=diag,
            ts=ts,
            fp=fp,
            failure_reason=failure_reason,
            increment_generation=final_state == "READ_ONLY_CERTIFIED" and self._generation == 0,
        )

    def invalidate(
        self,
        *,
        current_fingerprint: ProviderFingerprint | None = None,
        explicit_triggers: tuple[str, ...] | list[str] | None = None,
        certificate_rotated: bool = False,
        credential_rotated: bool = False,
        timestamp: str | None = None,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> OandaReadOnlyCertification:
        """Move to REVALIDATION_PENDING. Never to CERTIFIED."""
        ts = timestamp or _utc_now()
        diag = dict(diagnostics or {})
        fp = current_fingerprint or self._fingerprint or build_provider_fingerprint(
            endpoint=str(diag.get("endpoint") or ""),
        )
        inv = evaluate_invalidation(
            prior_fingerprint=self._fingerprint,
            current_fingerprint=fp,
            explicit_triggers=explicit_triggers,
            certificate_rotated=certificate_rotated,
            credential_rotated=credential_rotated,
        )
        if not inv.invalidated and not explicit_triggers and not certificate_rotated and not credential_rotated:
            # Force pending when caller explicitly asks invalidate with no delta:
            # still require an explicit trigger list for clarity.
            if explicit_triggers is None:
                inv = evaluate_invalidation(
                    prior_fingerprint=self._fingerprint,
                    current_fingerprint=fp,
                    explicit_triggers=("provider_version_change",),
                )
        reason = inv.reason or "invalidation:explicit"
        transition = self._machine.invalidate_to_revalidation_pending(reason)
        # Unlock fingerprint so revalidation can adopt the new fingerprint.
        self._replay._locked_fingerprint_hash = ""
        self._fingerprint = fp
        return self._finalize(
            final_state="REVALIDATION_PENDING",
            history=(transition,),
            evidence_flags={},
            diag={**diag, "invalidation_triggers": list(inv.triggers or ("explicit",))},
            ts=ts,
            fp=fp,
            failure_reason=reason,
            increment_generation=False,
        )

    def begin_revalidation(
        self,
        *,
        timestamp: str | None = None,
        diagnostics: Mapping[str, Any] | None = None,
        fingerprint: ProviderFingerprint | None = None,
    ) -> OandaReadOnlyCertification:
        if self._machine.state != "REVALIDATION_PENDING":
            raise ValueError("begin_revalidation requires REVALIDATION_PENDING")
        ts = timestamp or _utc_now()
        fp = fingerprint or self._fingerprint or build_provider_fingerprint()
        flags = {"revalidation_start": True}
        final_state, history = self._machine.run_to_completion(flags)
        return self._finalize(
            final_state=final_state,
            history=history,
            evidence_flags=flags,
            diag=dict(diagnostics or {}),
            ts=ts,
            fp=fp,
            failure_reason="",
            increment_generation=False,
        )

    def complete_revalidation(
        self,
        evidence_flags: Mapping[str, bool],
        *,
        timestamp: str | None = None,
        diagnostics: Mapping[str, Any] | None = None,
        fingerprint: ProviderFingerprint | None = None,
        failed: bool = False,
        failure_reason: str = "",
    ) -> OandaReadOnlyCertification:
        """Complete revalidation; generation increments only on success."""
        if self._machine.state != "REVALIDATION_RUNNING":
            raise ValueError("complete_revalidation requires REVALIDATION_RUNNING")
        ts = timestamp or _utc_now()
        diag = dict(diagnostics or {})
        fp = fingerprint or self._fingerprint or build_provider_fingerprint(
            endpoint=str(diag.get("endpoint") or ""),
        )
        flags = dict(evidence_flags)
        flags["revalidation_complete"] = True
        flags.setdefault("read_only_certified", True)
        final_state, history = self._machine.run_to_completion(
            flags,
            failed=failed,
            failure_reason=failure_reason,
        )
        success = final_state in {"REVALIDATED", "READ_ONLY_CERTIFIED"} and not failed
        return self._finalize(
            final_state=final_state if success else final_state,
            history=history,
            evidence_flags=flags,
            diag=diag,
            ts=ts,
            fp=fp,
            failure_reason=failure_reason,
            increment_generation=success,
        )

    def _finalize(
        self,
        *,
        final_state: str,
        history: tuple[Any, ...],
        evidence_flags: Mapping[str, bool],
        diag: Mapping[str, Any],
        ts: str,
        fp: ProviderFingerprint,
        failure_reason: str,
        increment_generation: bool,
    ) -> OandaReadOnlyCertification:
        gate_results = evaluate_gates(evidence_flags) if evidence_flags else ()
        gate_payloads = [
            {
                "gate_id": g.gate_id,
                "name": g.name,
                "passed": g.passed,
                "reason": g.reason,
                "grants_execution": False,
            }
            for g in gate_results
        ]

        parent_id = self._current_cert_id
        previous_hash = self._previous_evidence_hash
        if not parent_id and self._last_cert is not None:
            parent_id = self._last_cert.certification_id or parent_id
            previous_hash = self._last_cert.evidence_hash or previous_hash

        next_generation = self._generation
        if increment_generation:
            next_generation = self._generation + 1

        provisional_id = _make_certification_id(next_generation or 1, ts, fp.fingerprint_hash())
        # Include a nonce from history length so distinct attempts differ before accept.
        if not increment_generation and final_state not in {
            "READ_ONLY_CERTIFIED",
            "REVALIDATED",
        }:
            provisional_id = _make_certification_id(
                max(next_generation, 0),
                ts + f"|{final_state}|{len(history)}",
                fp.fingerprint_hash(),
            )
        elif not increment_generation and final_state in {"READ_ONLY_CERTIFIED", "REVALIDATED"}:
            # Never mint a replacement certified id without controlled revalidation.
            provisional_id = self._current_cert_id or provisional_id

        evidence = build_evidence_package(
            timestamp=ts,
            certification_state=final_state,
            connection_diagnostics={
                "history": [
                    {
                        "from": h.from_state,
                        "to": h.to_state,
                        "success": h.success,
                        "failure_reason": h.failure_reason,
                    }
                    for h in history
                ],
                **{k: v for k, v in diag.items() if k not in {"token", "api_key", "password"}},
            },
            provider_versions={
                "framework": FRAMEWORK_VERSION,
                "provider": PROVIDER_VERSION,
                "adapter": fp.adapter_version,
                "api": fp.api_version,
            },
            schema_versions={
                "contracts": SCHEMA_VERSION,
                "evidence": SCHEMA_VERSION,
            },
            latency_ms=dict(diag.get("latency_ms") or {}),
            endpoint=fp.endpoint or str(diag.get("endpoint") or ""),
            certificate_info=dict(diag.get("certificate_info") or {}),
            account_scope=dict(diag.get("account_scope") or {}),
            market_data_quality=dict(diag.get("market_data_quality") or {}),
            gate_results=gate_payloads,
            parent_certification_id=parent_id if increment_generation and parent_id else (
                parent_id if final_state.startswith("REVALIDATION") else ""
            ),
            previous_evidence_hash=previous_hash if (increment_generation or final_state.startswith("REVALIDATION")) else "",
            lineage_generation=next_generation,
            provider_fingerprint_hash=fp.fingerprint_hash(),
            certification_id=provisional_id,
        )

        # Replay protection on successful certified/revalidated outcomes.
        if final_state in {"READ_ONLY_CERTIFIED", "REVALIDATED"} and increment_generation:
            decision = evaluate_replay(
                registry=self._replay,
                evidence_hash=evidence.current_evidence_hash,
                fingerprint=fp,
                certification_generation=next_generation,
                schema_version=SCHEMA_VERSION,
            )
            # First generation: registry may have empty lock — allow then lock.
            if self._replay._locked_fingerprint_hash == "" and self._generation == 0:
                decision = type(decision)(True, "")
            if not decision.accepted:
                self._machine.force_state("FAILED", reason=decision.reason)
                return self._build_cert(
                    final_state="FAILED",
                    ts=ts,
                    fp=fp,
                    evidence_hash=evidence.current_evidence_hash,
                    certification_id=provisional_id,
                    generation=self._generation,
                    reason=decision.reason,
                    evidence_flags=evidence_flags,
                    gate_results=gate_results,
                    parent_id=parent_id,
                    evidence=evidence,
                )
            self._replay.register_accepted(evidence.current_evidence_hash, next_generation)
            self._replay.lock_fingerprint(fp)
            self._generation = next_generation
            self._current_cert_id = provisional_id
            self._previous_evidence_hash = evidence.current_evidence_hash
            self._parent_cert_id = parent_id
            self._fingerprint = fp

        reason = ""
        if final_state in {"FAILED", "BLOCKED", "REVALIDATION_PENDING"}:
            reason = failure_reason or (
                history[-1].failure_reason if history else final_state
            )
        elif final_state not in {"READ_ONLY_CERTIFIED", "REVALIDATED"}:
            reason = history[-1].failure_reason if history else "incomplete"

        cert = self._build_cert(
            final_state=final_state,
            ts=ts,
            fp=fp,
            evidence_hash=evidence.current_evidence_hash,
            certification_id=provisional_id,
            generation=next_generation if increment_generation else self._generation,
            reason=reason,
            evidence_flags=evidence_flags,
            gate_results=gate_results,
            parent_id=evidence.parent_certification_id,
            evidence=evidence,
        )
        if increment_generation or final_state.startswith("REVALIDATION") or self._last_cert is None:
            self._last_cert = cert
        if final_state.startswith("REVALIDATION"):
            self._fingerprint = fp
        return cert

    def _build_cert(
        self,
        *,
        final_state: str,
        ts: str,
        fp: ProviderFingerprint,
        evidence_hash: str,
        certification_id: str,
        generation: int,
        reason: str,
        evidence_flags: Mapping[str, bool],
        gate_results: tuple[Any, ...],
        parent_id: str,
        evidence: Any,
    ) -> OandaReadOnlyCertification:
        lineage_kwargs = {
            "certification_id": certification_id,
            "certification_generation": generation,
            "certification_timestamp": ts,
        }
        connection = OandaConnectionStatus(
            timestamp=ts,
            certification_state=final_state,
            failure_reason=reason if final_state in {"FAILED", "BLOCKED", "REVALIDATION_PENDING"} else "",
            diagnostics={"endpoint": fp.endpoint},
            **lineage_kwargs,
        )
        authentication = OandaAuthenticationStatus(
            timestamp=ts,
            certification_state=final_state,
            failure_reason=reason if "AUTH" in final_state or final_state in {"FAILED", "BLOCKED"} else "",
            diagnostics={"auth_ok": bool(evidence_flags.get("auth_ok"))},
            **lineage_kwargs,
        )
        account = OandaAccountStatus(
            timestamp=ts,
            certification_state=final_state,
            failure_reason="",
            diagnostics={"account_scope": dict(evidence.account_scope)},
            **lineage_kwargs,
        )
        market_data = OandaMarketDataStatus(
            timestamp=ts,
            certification_state=final_state,
            failure_reason="",
            diagnostics={"quality": dict(evidence.market_data_quality)},
            **lineage_kwargs,
        )
        return OandaReadOnlyCertification(
            timestamp=ts,
            certification_state=final_state,
            failure_reason=reason,
            diagnostics={
                "provider_name": PROVIDER_NAME,
                "gates_passed": sum(1 for g in gate_results if g.passed),
                "gates_total": len(gate_results),
                "network_performed": False,
                "authentication_performed": False,
                "execution_authority": False,
                "lineage_generation": generation,
                "provider_fingerprint": fp.as_dict(),
            },
            connection=connection,
            authentication=authentication,
            account=account,
            market_data=market_data,
            evidence_hash=evidence_hash,
            execution_authority=False,
            certification_id=certification_id,
            certification_generation=generation,
            certification_timestamp=ts,
            provider_fingerprint_hash=fp.fingerprint_hash(),
            parent_certification_id=parent_id,
        )

    def __getattribute__(self, name: str) -> Any:
        if name in OandaReadOnlyCertificationFramework.FORBIDDEN_METHODS:
            raise AttributeError(
                f"Phase 187A forbids execution/network method '{name}' on "
                "OandaReadOnlyCertificationFramework"
            )
        return object.__getattribute__(self, name)
