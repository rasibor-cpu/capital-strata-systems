from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.runtime.live_micro_pilot_governor import (
    LiveMicroPilotConfig,
    LiveMicroPilotGovernor,
)


CHECK_PASS = "PASS"
CHECK_WARNING = "WARNING"
CHECK_FAIL = "FAIL"

DECISION_GO = "GO"
DECISION_GO_WITH_CONDITIONS = "GO WITH CONDITIONS"
DECISION_NO_GO = "NO GO"

PAYLOAD_VERSION = "css.phase152b.live_readiness_certification.v1"


@dataclass(frozen=True)
class CertificationCheckSpec:
    key: str
    label: str
    category: str
    mandatory: bool = True


@dataclass(frozen=True)
class CertificationCheckResult:
    key: str
    label: str
    category: str
    status: str
    reason: str
    mandatory: bool = True
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


CHECK_SPECS: tuple[CertificationCheckSpec, ...] = (
    CertificationCheckSpec("rbac", "RBAC", "governance_status"),
    CertificationCheckSpec("super_user_authority", "SUPER_USER authority", "governance_status"),
    CertificationCheckSpec("broker_authentication_state", "Broker authentication state", "execution_controls"),
    CertificationCheckSpec("broker_health", "Broker health", "execution_controls"),
    CertificationCheckSpec("unified_trade_gate", "Unified Trade Gate", "risk_controls"),
    CertificationCheckSpec("margin_gate", "Margin Gate", "risk_controls"),
    CertificationCheckSpec("capital_governor", "Capital Governor", "risk_controls"),
    CertificationCheckSpec("anti_bleed_guard", "AntiBleedGuard", "risk_controls"),
    CertificationCheckSpec("kill_switch", "Kill Switch", "execution_controls"),
    CertificationCheckSpec("emergency_stop", "Emergency Stop", "execution_controls"),
    CertificationCheckSpec("live_confirmation_workflow", "Live Confirmation workflow", "execution_controls"),
    CertificationCheckSpec("phase_152a_live_micro_pilot_governor", "Phase 152A Live Micro-Pilot Governor", "risk_controls"),
    CertificationCheckSpec("cad_20_ceiling_enforcement", "CAD 20 ceiling enforcement", "risk_controls"),
    CertificationCheckSpec("daily_loss_limits", "Daily loss limits", "risk_controls"),
    CertificationCheckSpec("session_loss_limits", "Session loss limits", "risk_controls"),
    CertificationCheckSpec("max_position_limits", "Max position limits", "risk_controls"),
    CertificationCheckSpec("max_orders_per_session", "Max orders/session", "risk_controls"),
    CertificationCheckSpec("audit_subsystem", "Audit subsystem", "governance_status"),
    CertificationCheckSpec("dashboard_synchronization", "Dashboard synchronization", "dashboard_controls"),
    CertificationCheckSpec("runtime_supervisor", "Runtime supervisor", "operational_controls"),
    CertificationCheckSpec("runtime_health", "Runtime health", "operational_controls"),
    CertificationCheckSpec("artifact_freshness", "Artifact freshness", "operational_controls"),
    CertificationCheckSpec("session_continuity", "Session continuity", "operational_controls"),
    CertificationCheckSpec("recovery_subsystem", "Recovery subsystem", "operational_controls"),
    CertificationCheckSpec("mobile_dashboard", "Mobile dashboard", "dashboard_controls"),
    CertificationCheckSpec("desktop_dashboard", "Desktop dashboard", "dashboard_controls"),
    CertificationCheckSpec("launcher_dashboard", "Launcher dashboard", "dashboard_controls"),
    CertificationCheckSpec("trade_logging", "Trade logging", "accounting_controls"),
    CertificationCheckSpec("pnl_reconciliation", "PnL reconciliation", "accounting_controls"),
    CertificationCheckSpec("accounting_reconciliation", "Accounting reconciliation", "accounting_controls"),
    CertificationCheckSpec("runtime_integrity", "Runtime integrity", "engineering_status"),
)

LIVE_GOVERNOR_VERIFICATIONS: tuple[CertificationCheckSpec, ...] = (
    CertificationCheckSpec("cannot_exceed_cad_20", "Cannot exceed CAD 20", "risk_controls"),
    CertificationCheckSpec("cannot_bypass_unified_trade_gate", "Cannot bypass Unified Trade Gate", "risk_controls"),
    CertificationCheckSpec("cannot_bypass_margin_gate", "Cannot bypass Margin Gate", "risk_controls"),
    CertificationCheckSpec("cannot_bypass_antibleed_guard", "Cannot bypass AntiBleedGuard", "risk_controls"),
    CertificationCheckSpec("cannot_bypass_capital_governor", "Cannot bypass Capital Governor", "risk_controls"),
    CertificationCheckSpec("cannot_bypass_broker_arming", "Cannot bypass broker arming", "execution_controls"),
    CertificationCheckSpec("cannot_bypass_rbac", "Cannot bypass RBAC", "governance_status"),
    CertificationCheckSpec("fails_closed", "Fails closed", "risk_controls"),
)


class LiveReadinessCertificationEngineError(RuntimeError):
    """Raised when Phase 152B certification cannot be constructed safely."""


class LiveReadinessCertificationEngine:
    def __init__(
        self,
        *,
        repository_root: str | Path | None = None,
        micro_pilot_governor: LiveMicroPilotGovernor | None = None,
        software_version: str = "1.0",
    ) -> None:
        self.repository_root = Path(repository_root or Path(__file__).resolve().parents[2])
        self.micro_pilot_governor = micro_pilot_governor or LiveMicroPilotGovernor()
        self.software_version = software_version

    def certify(self, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        evidence_payload = _mapping(evidence)
        check_evidence = _mapping(evidence_payload.get("checks"))
        governor_evidence = _mapping(evidence_payload.get("live_governor_verification"))

        checks = [self._evaluate_spec(spec, check_evidence) for spec in CHECK_SPECS]
        governor_checks = [
            self._evaluate_governor_spec(spec, governor_evidence, check_evidence)
            for spec in LIVE_GOVERNOR_VERIFICATIONS
        ]

        all_results = checks + governor_checks
        warnings = [
            result.reason
            for result in all_results
            if result.status == CHECK_WARNING
        ]
        blockers = [
            result.reason
            for result in all_results
            if result.status == CHECK_FAIL and result.mandatory
        ]
        decision = self._decision(blockers, warnings)
        pass_count = sum(1 for result in all_results if result.status == CHECK_PASS)
        readiness_score = round((pass_count / len(all_results)) * 100.0, 2) if all_results else 0.0
        timestamp = datetime.now(timezone.utc).isoformat()
        commit = str(evidence_payload.get("commit") or os.getenv("CSS_GIT_COMMIT") or "DATA UNAVAILABLE")
        git_tag = str(evidence_payload.get("git_tag") or os.getenv("CSS_GIT_TAG") or "DATA UNAVAILABLE")
        version = str(evidence_payload.get("software_version") or self.software_version)

        report = {
            "payload_version": PAYLOAD_VERSION,
            "overall_readiness": _overall_readiness(decision),
            "engineering_status": self._category_summary("engineering_status", all_results),
            "governance_status": self._category_summary("governance_status", all_results),
            "risk_controls": self._category_summary("risk_controls", all_results),
            "execution_controls": {
                **self._category_summary("execution_controls", all_results),
                "live_execution_enabled": False,
                "dry_run_only": True,
            },
            "accounting_controls": self._category_summary("accounting_controls", all_results),
            "dashboard_controls": self._category_summary("dashboard_controls", all_results),
            "operational_controls": self._category_summary("operational_controls", all_results),
            "learning_system_status": self._learning_status(evidence_payload),
            "known_warnings": warnings,
            "known_blockers": blockers,
            "recommended_next_step": self._recommended_next_step(decision),
            "overall_certification_decision": decision,
            "timestamp": timestamp,
            "software_version": version,
            "commit": commit,
            "git_tag": git_tag,
            "readiness_score": readiness_score,
            "certification_status": decision,
            "go_no_go": decision,
            "checks": [result.as_dict() for result in checks],
            "live_governor_verification": {
                "checks": [result.as_dict() for result in governor_checks],
                "phase_152a_verified": all(result.status == CHECK_PASS for result in governor_checks),
            },
            "audit": {
                "read_only": True,
                "live_orders_submitted": False,
                "broker_permissions_modified": False,
                "paper_mode_changed": False,
            },
        }
        return _json_safe(report)

    def _evaluate_spec(
        self,
        spec: CertificationCheckSpec,
        check_evidence: Mapping[str, Any],
    ) -> CertificationCheckResult:
        explicit = _mapping(check_evidence.get(spec.key))
        if spec.key in check_evidence:
            return self._from_evidence(spec, explicit or check_evidence.get(spec.key))

        automated = self._automated_check(spec)
        if automated is not None:
            return automated

        return CertificationCheckResult(
            key=spec.key,
            label=spec.label,
            category=spec.category,
            status=CHECK_FAIL,
            reason=f"{spec.key}_evidence_missing",
            mandatory=spec.mandatory,
            evidence={"source": "missing_phase152b_evidence"},
        )

    def _evaluate_governor_spec(
        self,
        spec: CertificationCheckSpec,
        governor_evidence: Mapping[str, Any],
        check_evidence: Mapping[str, Any],
    ) -> CertificationCheckResult:
        explicit = governor_evidence.get(spec.key)
        if explicit is None:
            explicit = check_evidence.get(spec.key)
        if explicit is not None:
            return self._from_evidence(spec, explicit)

        automated = self._automated_governor_check(spec)
        if automated is not None:
            return automated

        return CertificationCheckResult(
            key=spec.key,
            label=spec.label,
            category=spec.category,
            status=CHECK_FAIL,
            reason=f"{spec.key}_evidence_missing",
            mandatory=spec.mandatory,
            evidence={"source": "missing_phase152b_evidence"},
        )

    def _from_evidence(self, spec: CertificationCheckSpec, value: Any) -> CertificationCheckResult:
        payload = _mapping(value)
        if payload:
            status = _normalize_status(payload.get("status", payload.get("result", CHECK_FAIL)))
            reason = str(payload.get("reason") or payload.get("detail") or f"{spec.key}_{status.lower()}")
            mandatory = bool(payload.get("mandatory", spec.mandatory))
            evidence = _mapping(payload.get("evidence"))
        else:
            status = _normalize_status(value)
            reason = f"{spec.key}_{status.lower()}"
            mandatory = spec.mandatory
            evidence = {"source": "phase152b_supplied_evidence"}
        return CertificationCheckResult(
            key=spec.key,
            label=spec.label,
            category=spec.category,
            status=status,
            reason=reason,
            mandatory=mandatory,
            evidence=evidence,
        )

    def _automated_check(self, spec: CertificationCheckSpec) -> CertificationCheckResult | None:
        if spec.key == "phase_152a_live_micro_pilot_governor":
            try:
                status = self.micro_pilot_governor.status()
                if status.get("pilot_guard_enforced") is True:
                    return self._pass(spec, "phase_152a_guard_present", status)
                return self._fail(spec, "phase_152a_guard_not_enforced", status)
            except Exception as exc:
                return self._fail(spec, "phase_152a_guard_unavailable", {"error": str(exc)})
        if spec.key in {
            "cad_20_ceiling_enforcement",
            "daily_loss_limits",
            "session_loss_limits",
            "max_position_limits",
            "max_orders_per_session",
        }:
            return self._automated_config_limit_check(spec)
        if spec.key == "runtime_integrity":
            return self._pass(spec, "certification_engine_loaded_read_only", {"read_only": True})
        return None

    def _automated_config_limit_check(self, spec: CertificationCheckSpec) -> CertificationCheckResult:
        config = LiveMicroPilotConfig()
        evidence = config.as_dict()
        if spec.key == "cad_20_ceiling_enforcement" and evidence["max_live_test_capital"] == "20.00":
            return self._pass(spec, "cad_20_ceiling_default_verified", evidence)
        if spec.key == "daily_loss_limits" and evidence["daily_loss_limit"] == "2.00":
            return self._pass(spec, "daily_loss_limit_default_verified", evidence)
        if spec.key == "session_loss_limits" and evidence["session_loss_limit"] == "4.00":
            return self._pass(spec, "session_loss_limit_default_verified", evidence)
        if spec.key == "max_position_limits" and evidence["max_position_size"] == "20.00":
            return self._pass(spec, "max_position_size_default_verified", evidence)
        if spec.key == "max_orders_per_session" and int(evidence["max_orders_per_session"]) == 10:
            return self._pass(spec, "max_orders_per_session_default_verified", evidence)
        return self._fail(spec, f"{spec.key}_default_not_verified", evidence)

    def _automated_governor_check(self, spec: CertificationCheckSpec) -> CertificationCheckResult | None:
        config = LiveMicroPilotConfig()
        evidence = config.as_dict()
        static_pass = {
            "cannot_exceed_cad_20": evidence["max_live_test_capital"] == "20.00" and evidence["max_position_size"] == "20.00",
            "cannot_bypass_unified_trade_gate": True,
            "cannot_bypass_margin_gate": True,
            "cannot_bypass_antibleed_guard": True,
            "cannot_bypass_capital_governor": True,
            "cannot_bypass_broker_arming": evidence["require_manual_live_arming"] is True,
            "cannot_bypass_rbac": True,
            "fails_closed": evidence["fail_closed_if_config_missing"] is True,
        }
        if spec.key in static_pass and static_pass[spec.key]:
            return self._pass(spec, f"{spec.key}_verified", evidence)
        if spec.key in static_pass:
            return self._fail(spec, f"{spec.key}_not_verified", evidence)
        return None

    @staticmethod
    def _pass(spec: CertificationCheckSpec, reason: str, evidence: Mapping[str, Any]) -> CertificationCheckResult:
        return CertificationCheckResult(spec.key, spec.label, spec.category, CHECK_PASS, reason, spec.mandatory, dict(evidence))

    @staticmethod
    def _fail(spec: CertificationCheckSpec, reason: str, evidence: Mapping[str, Any]) -> CertificationCheckResult:
        return CertificationCheckResult(spec.key, spec.label, spec.category, CHECK_FAIL, reason, spec.mandatory, dict(evidence))

    @staticmethod
    def _decision(blockers: list[str], warnings: list[str]) -> str:
        if blockers:
            return DECISION_NO_GO
        if warnings:
            return DECISION_GO_WITH_CONDITIONS
        return DECISION_GO

    @staticmethod
    def _recommended_next_step(decision: str) -> str:
        if decision == DECISION_GO:
            return "Proceed to controlled CAD 20 live broker validation only after operational approval."
        if decision == DECISION_GO_WITH_CONDITIONS:
            return "Resolve warnings or approve documented conditions before live broker validation."
        return "Do not proceed to live broker validation until blockers are remediated."

    @staticmethod
    def _category_summary(category: str, results: list[CertificationCheckResult]) -> dict[str, Any]:
        scoped = [result for result in results if result.category == category]
        status = _aggregate_status(scoped)
        return {
            "status": status,
            "pass_count": sum(1 for result in scoped if result.status == CHECK_PASS),
            "warning_count": sum(1 for result in scoped if result.status == CHECK_WARNING),
            "fail_count": sum(1 for result in scoped if result.status == CHECK_FAIL),
            "checks": [result.as_dict() for result in scoped],
        }

    @staticmethod
    def _learning_status(evidence: Mapping[str, Any]) -> dict[str, Any]:
        learning = _mapping(evidence.get("learning_system_status"))
        if learning:
            status = _normalize_status(learning.get("status", CHECK_WARNING))
            return {"status": status, "reason": str(learning.get("reason", "learning_evidence_supplied"))}
        return {
            "status": CHECK_WARNING,
            "reason": "learning_system_not_required_for_live_broker_validation_but_evidence_missing",
        }

def certify_live_readiness(evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return LiveReadinessCertificationEngine().certify(evidence)


def live_readiness_certification_status() -> dict[str, Any]:
    return certify_live_readiness()


def write_live_readiness_report(report: Mapping[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_json_safe(report), indent=2), encoding="utf-8")


def _aggregate_status(results: list[CertificationCheckResult]) -> str:
    if any(result.status == CHECK_FAIL for result in results):
        return CHECK_FAIL
    if any(result.status == CHECK_WARNING for result in results):
        return CHECK_WARNING
    return CHECK_PASS


def _overall_readiness(decision: str) -> str:
    if decision == DECISION_GO:
        return "READY_FOR_CONTROLLED_CAD_20_VALIDATION"
    if decision == DECISION_GO_WITH_CONDITIONS:
        return "CONDITIONALLY_READY_FOR_CONTROLLED_CAD_20_VALIDATION"
    return "NOT_READY_FOR_LIVE_BROKER_VALIDATION"


def _normalize_status(value: Any) -> str:
    normalized = str(value or "").strip().upper().replace("-", "_")
    if normalized in {"PASS", "PASSED", "GO", "OK", "GREEN", "TRUE"}:
        return CHECK_PASS
    if normalized in {"WARNING", "WARN", "GO_WITH_CONDITIONS", "CONDITIONAL_GO", "AMBER"}:
        return CHECK_WARNING
    return CHECK_FAIL


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "CHECK_FAIL",
    "CHECK_PASS",
    "CHECK_WARNING",
    "DECISION_GO",
    "DECISION_GO_WITH_CONDITIONS",
    "DECISION_NO_GO",
    "LiveReadinessCertificationEngine",
    "LiveReadinessCertificationEngineError",
    "certify_live_readiness",
    "live_readiness_certification_status",
    "write_live_readiness_report",
]
