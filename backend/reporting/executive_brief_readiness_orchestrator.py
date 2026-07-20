"""
Phase 176J — Executive Brief Readiness Orchestrator (reporting layer).

Strictly advisory / read-only. Does not affect trading, portfolio management,
execution, broker connectivity, or runtime scheduling.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "css.executive_brief_readiness_report.v1"

STATE_GREEN = "GREEN"
STATE_AMBER = "AMBER"
STATE_RED = "RED"
STATE_NOT_READY = "NOT_READY"

STATUS_READY = "ready"
STATUS_WARNING = "warning"
STATUS_MISSING = "missing"
STATUS_OUTDATED = "outdated"
STATUS_UNAVAILABLE = "unavailable"

SEVERITY_BLOCKING = "blocking"
SEVERITY_WARNING = "warning"
SEVERITY_ADVISORY = "advisory"

# Default freshness thresholds (seconds) for reporting-layer advisory checks.
DEFAULT_FRESHNESS_SECONDS = 900
DEFAULT_SOFT_FRESHNESS_SECONDS = 1800

# Approximate DEB generation time estimates (seconds).
BASE_GENERATION_SECONDS = 45
PER_MISSING_SECONDS = 8
PER_OUTDATED_SECONDS = 5
PER_WARNING_SECONDS = 2


@dataclass(frozen=True)
class ComponentSpec:
    key: str
    label: str
    severity: str
    evidence_keys: tuple[str, ...] = ()


COMPONENT_SPECS: tuple[ComponentSpec, ...] = (
    ComponentSpec("runtime", "Runtime", SEVERITY_BLOCKING, ("runtime", "platform")),
    ComponentSpec(
        "broker_connectivity",
        "Broker Connectivity",
        SEVERITY_BLOCKING,
        ("broker_connectivity", "brokers", "broker"),
    ),
    ComponentSpec(
        "portfolio_snapshot",
        "Portfolio Snapshot",
        SEVERITY_BLOCKING,
        ("portfolio_snapshot", "portfolio"),
    ),
    ComponentSpec("risk_metrics", "Risk Metrics", SEVERITY_WARNING, ("risk_metrics", "risk")),
    ComponentSpec("pnl", "PnL", SEVERITY_WARNING, ("pnl", "portfolio")),
    ComponentSpec(
        "income_statement",
        "Income Statement",
        SEVERITY_ADVISORY,
        ("income_statement",),
    ),
    ComponentSpec(
        "balance_sheet",
        "Balance Sheet",
        SEVERITY_ADVISORY,
        ("balance_sheet",),
    ),
    ComponentSpec("cash_flow", "Cash Flow", SEVERITY_ADVISORY, ("cash_flow",)),
    ComponentSpec(
        "market_intelligence",
        "Market Intelligence",
        SEVERITY_WARNING,
        ("market_intelligence", "market"),
    ),
    ComponentSpec(
        "ai_recommendation_summary",
        "AI Recommendation Summary",
        SEVERITY_ADVISORY,
        ("ai_recommendation_summary", "ai_recommendations"),
    ),
    ComponentSpec("open_alerts", "Open Alerts", SEVERITY_WARNING, ("open_alerts", "alerts")),
    ComponentSpec(
        "system_health",
        "System Health",
        SEVERITY_WARNING,
        ("system_health", "platform", "runtime"),
    ),
    ComponentSpec(
        "reporting_data_freshness",
        "Reporting Data Freshness",
        SEVERITY_BLOCKING,
        ("reporting_data_freshness", "data_freshness"),
    ),
)


@dataclass
class ComponentAssessment:
    key: str
    label: str
    severity: str
    status: str
    message: str = ""
    age_seconds: float | None = None
    freshness_timestamp: str | None = None
    classification: str = ""
    recommended_action: str = ""
    source_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "severity": self.severity,
            "status": self.status,
            "message": self.message,
            "age_seconds": self.age_seconds,
            "freshness_timestamp": self.freshness_timestamp,
            "classification": self.classification or self.severity,
            "recommended_action": self.recommended_action,
            "source_available": self.source_available,
        }


@dataclass
class ExecutiveBriefReadinessReport:
    """Canonical advisory readiness report for Executive Brief generation."""

    timestamp: str
    overall_state: str
    score: float
    blocking_items: list[str] = field(default_factory=list)
    warning_items: list[str] = field(default_factory=list)
    advisories: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    estimated_generation_time: str = "unknown"
    estimated_generation_seconds: int = 0
    missing_datasets: list[str] = field(default_factory=list)
    outdated_datasets: list[str] = field(default_factory=list)
    components: list[ComponentAssessment] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    advisory_only: bool = True
    trading_impact: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "overall_state": self.overall_state,
            "overall_readiness_score": self.score,
            "score": self.score,
            "blocking_items": list(self.blocking_items),
            "warning_items": list(self.warning_items),
            "advisories": list(self.advisories),
            "recommended_actions": list(self.recommended_actions),
            "estimated_generation_time": self.estimated_generation_time,
            "estimated_generation_seconds": self.estimated_generation_seconds,
            "missing_datasets": list(self.missing_datasets),
            "outdated_datasets": list(self.outdated_datasets),
            "components": [c.to_dict() for c in self.components],
            "advisory_only": self.advisory_only,
            "trading_impact": self.trading_impact,
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _pick_evidence(evidence: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in evidence and evidence[key] is not None:
            return evidence[key]
    return None


def _is_unavailable_token(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        token = value.strip().upper()
        return token in {
            "",
            "UNAVAILABLE",
            "DATA UNAVAILABLE",
            "UNKNOWN",
            "MISSING",
            "NOT_READY",
            "N/A",
            "NONE",
        }
    return False


def _extract_status(payload: Any) -> str | None:
    mapping = _as_mapping(payload)
    if mapping is None:
        if isinstance(payload, bool):
            return STATUS_READY if payload else STATUS_MISSING
        if isinstance(payload, (int, float)):
            return STATUS_READY
        if isinstance(payload, str):
            return None if _is_unavailable_token(payload) else STATUS_READY
        return None
    for key in ("status", "state", "health", "readiness", "overall_state", "overall_freshness"):
        raw = mapping.get(key)
        if raw is None:
            continue
        token = str(raw).strip().upper().replace(" ", "_")
        if token in {
            "READY",
            "GREEN",
            "OK",
            "HEALTHY",
            "PASS",
            "AVAILABLE",
            "FRESH",
            "ONLINE",
            "NORMAL",
        }:
            return STATUS_READY
        if token in {"WARNING", "WARN", "AMBER", "DEGRADED", "MONITOR", "STALE"}:
            return STATUS_WARNING
        if token in {"OUTDATED", "EXPIRED"}:
            return STATUS_OUTDATED
        if token in {"MISSING", "ABSENT"}:
            return STATUS_MISSING
        if token in {
            "UNAVAILABLE",
            "DATA_UNAVAILABLE",
            "FAILED",
            "FAIL",
            "RED",
            "BLOCKED",
            "OFFLINE",
            "NOT_READY",
            "ERROR",
        }:
            return STATUS_UNAVAILABLE
    return None


def _extract_age_seconds(payload: Any) -> float | None:
    mapping = _as_mapping(payload)
    if mapping is None:
        return None
    for key in ("age_seconds", "staleness_seconds", "freshness_age_seconds"):
        raw = mapping.get(key)
        if isinstance(raw, (int, float)):
            return float(raw)
    return None


def _extract_freshness_timestamp(payload: Any) -> str | None:
    """Return an upstream freshness/measured timestamp when present; never invent one."""
    mapping = _as_mapping(payload)
    if mapping is None:
        return None
    for key in (
        "freshness_timestamp",
        "measured_at",
        "generated_at",
        "as_of",
        "timestamp",
        "last_runtime_heartbeat",
        "updated_at",
    ):
        raw = mapping.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text and not _is_unavailable_token(text):
            return text
    return None


def _component_recommended_action(label: str, status: str, severity: str) -> str:
    if status == STATUS_READY:
        return f"No action required for {label}."
    if status == STATUS_MISSING:
        return f"Restore missing {label} evidence before generating an Executive Brief."
    if status == STATUS_UNAVAILABLE:
        return f"Investigate unavailable {label} source; do not invent substitute values."
    if status == STATUS_OUTDATED:
        return f"Refresh outdated {label} data and re-check readiness."
    if status == STATUS_WARNING:
        if severity == SEVERITY_BLOCKING:
            return f"Resolve degraded {label} before treating readiness as green."
        if severity == SEVERITY_ADVISORY:
            return f"Optionally enrich {label}; advisory gap only."
        return f"Review warning on {label} and confirm operators accept residual risk."
    return f"Re-evaluate {label} after the next snapshot."


def _payload_present(payload: Any) -> bool:
    if payload is None:
        return False
    if _is_unavailable_token(payload):
        return False
    mapping = _as_mapping(payload)
    if mapping is not None:
        if mapping.get("available") is False:
            return False
        if mapping.get("present") is False:
            return False
        if not mapping:
            return False
        # Explicit missing flag
        if bool(mapping.get("missing")):
            return False
        return True
    if isinstance(payload, (list, tuple, set)):
        return True
    if isinstance(payload, (int, float, bool)):
        return True
    if isinstance(payload, str):
        return not _is_unavailable_token(payload)
    return True


def _assess_open_alerts(payload: Any) -> tuple[str, str]:
    mapping = _as_mapping(payload)
    count = None
    if mapping is not None:
        for key in ("count", "open_count", "active_count"):
            raw = mapping.get(key)
            if isinstance(raw, (int, float)):
                count = int(raw)
                break
        items = mapping.get("items") or mapping.get("alerts")
        if count is None and isinstance(items, (list, tuple)):
            count = len(items)
    elif isinstance(payload, (list, tuple)):
        count = len(payload)
    elif isinstance(payload, (int, float)):
        count = int(payload)

    if count is None:
        if not _payload_present(payload):
            return STATUS_MISSING, "Open alerts dataset missing"
        return STATUS_READY, "Open alerts evidence present"
    if count <= 0:
        return STATUS_READY, "No open alerts"
    if count <= 3:
        return STATUS_WARNING, f"{count} open alert(s)"
    return STATUS_WARNING, f"{count} open alerts (elevated)"


def _assess_pnl(payload: Any) -> tuple[str, str]:
    mapping = _as_mapping(payload)
    if mapping is None:
        if not _payload_present(payload):
            return STATUS_MISSING, "PnL dataset missing"
        return STATUS_READY, "PnL evidence present"
    # Prefer explicit pnl fields; portfolio maps often carry these.
    keys = ("realized_pnl", "unrealized_pnl", "net_pnl", "pnl")
    found = False
    unavailable = 0
    for key in keys:
        if key not in mapping:
            continue
        found = True
        if _is_unavailable_token(mapping.get(key)):
            unavailable += 1
    if not found:
        # portfolio-only payload without pnl keys → treat as missing pnl slice
        return STATUS_MISSING, "PnL fields not present in evidence"
    if unavailable == found:
        return STATUS_MISSING, "PnL values unavailable"
    if unavailable:
        return STATUS_WARNING, "Partial PnL coverage"
    return STATUS_READY, "PnL evidence present"


def _assess_reporting_freshness(payload: Any, *, soft_limit: float, hard_limit: float) -> tuple[str, str, float | None]:
    age = _extract_age_seconds(payload)
    status = _extract_status(payload)
    if status == STATUS_READY and age is None:
        return STATUS_READY, "Reporting data freshness acceptable", age
    if status == STATUS_WARNING:
        return STATUS_WARNING, "Reporting data freshness degraded", age
    if status in {STATUS_OUTDATED, STATUS_UNAVAILABLE, STATUS_MISSING}:
        return status or STATUS_MISSING, "Reporting data freshness not acceptable", age
    if not _payload_present(payload) and age is None and status is None:
        return STATUS_MISSING, "Reporting data freshness evidence missing", None
    if age is not None:
        if age > hard_limit:
            return STATUS_OUTDATED, f"Reporting data outdated ({int(age)}s)", age
        if age > soft_limit:
            return STATUS_WARNING, f"Reporting data aging ({int(age)}s)", age
        return STATUS_READY, "Reporting data freshness acceptable", age
    if status == STATUS_READY:
        return STATUS_READY, "Reporting data freshness acceptable", age
    return STATUS_WARNING, "Reporting data freshness inconclusive", age


def _score_component(status: str, severity: str) -> float:
    """Return 0..1 contribution for a component."""
    base = {
        STATUS_READY: 1.0,
        STATUS_WARNING: 0.55,
        STATUS_OUTDATED: 0.15,
        STATUS_MISSING: 0.0,
        STATUS_UNAVAILABLE: 0.0,
    }.get(status, 0.0)
    weight = {
        SEVERITY_BLOCKING: 1.0,
        SEVERITY_WARNING: 0.85,
        SEVERITY_ADVISORY: 0.65,
    }.get(severity, 0.75)
    # Weight scales importance of gaps but ready advisory still scores full for that slot.
    if status == STATUS_READY:
        return 1.0
    return base * weight


def _format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"~{seconds}s"
    minutes = seconds // 60
    rem = seconds % 60
    if rem == 0:
        return f"~{minutes}m"
    return f"~{minutes}m {rem}s"


def evidence_from_mission_control_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Map Mission Control state sections into readiness evidence (read-only)."""
    if not isinstance(state, Mapping):
        return {}
    platform = state.get("platform") if isinstance(state.get("platform"), Mapping) else {}
    runtime = state.get("runtime") if isinstance(state.get("runtime"), Mapping) else {}
    portfolio = state.get("portfolio") if isinstance(state.get("portfolio"), Mapping) else {}
    risk = state.get("risk") if isinstance(state.get("risk"), Mapping) else {}
    market = (
        state.get("market_intelligence")
        if isinstance(state.get("market_intelligence"), Mapping)
        else {}
    )
    alerts = state.get("alerts") if isinstance(state.get("alerts"), Mapping) else {}
    freshness = (
        state.get("data_freshness") if isinstance(state.get("data_freshness"), Mapping) else {}
    )
    brokers = state.get("brokers") if isinstance(state.get("brokers"), Mapping) else {}
    reporting = (
        state.get("institutional_reporting")
        if isinstance(state.get("institutional_reporting"), Mapping)
        else {}
    )
    kpis = state.get("executive_kpis") if isinstance(state.get("executive_kpis"), Mapping) else {}

    broker_health = platform.get("broker_health") or brokers.get("health") or brokers.get("status")
    runtime_health = (
        platform.get("runtime_health")
        or runtime.get("heartbeat_status")
        or runtime.get("status")
    )
    system_health = {
        "status": platform.get("platform_status") or runtime_health or "UNKNOWN",
        "runtime_health": runtime_health,
        "broker_health": broker_health,
    }

    income_statement = reporting.get("income_statement") or state.get("income_statement")
    balance_sheet = reporting.get("balance_sheet") or state.get("balance_sheet")
    cash_flow = reporting.get("cash_flow") or state.get("cash_flow")

    # Phase 178: when MC lacks statement blobs, derive 176J evidence from Phase 177 package.
    financial_report_package = (
        state.get("financial_report_package")
        or reporting.get("financial_report_package")
        or state.get("executive_financial_report")
    )
    if not (income_statement and balance_sheet and cash_flow):
        try:
            from backend.executive_reporting.service import ExecutiveFinancialReportingService

            if not isinstance(financial_report_package, Mapping):
                financial_report_package = ExecutiveFinancialReportingService().generate_from_state(
                    dict(state)
                )
            from backend.executive_reporting.evidence_bridge import merge_financial_evidence_into_176j

            bridged = merge_financial_evidence_into_176j(
                {
                    "income_statement": income_statement,
                    "balance_sheet": balance_sheet,
                    "cash_flow": cash_flow,
                },
                financial_report_package,
            )
            income_statement = bridged.get("income_statement") or income_statement
            balance_sheet = bridged.get("balance_sheet") or balance_sheet
            cash_flow = bridged.get("cash_flow") or cash_flow
            financial_report_package = bridged.get("financial_report_package") or financial_report_package
        except Exception:
            pass

    evidence = {
        "runtime": {
            "status": runtime_health,
            "heartbeat": runtime.get("heartbeat") or platform.get("heartbeat"),
            "mode": platform.get("runtime_mode"),
        },
        "broker_connectivity": {
            "status": broker_health,
            "brokers": brokers,
        },
        "portfolio_snapshot": portfolio,
        "risk_metrics": risk,
        "pnl": {
            "realized_pnl": portfolio.get("realized_pnl"),
            "unrealized_pnl": portfolio.get("unrealized_pnl"),
            "net_pnl": portfolio.get("net_pnl"),
        },
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
        "market_intelligence": market,
        "ai_recommendation_summary": state.get("ai_recommendation_summary")
        or reporting.get("ai_recommendation_summary")
        or kpis.get("ai_recommendation_summary"),
        "open_alerts": alerts,
        "system_health": system_health,
        "reporting_data_freshness": {
            "status": freshness.get("overall_freshness") or freshness.get("status"),
            "age_seconds": freshness.get("age_seconds"),
            "last_runtime_heartbeat": freshness.get("last_runtime_heartbeat"),
            "generated_at": freshness.get("generated_at"),
        },
    }
    if isinstance(financial_report_package, Mapping):
        evidence["financial_report_package"] = {
            "present": True,
            "schema_version": financial_report_package.get("schema_version"),
            "report_id": financial_report_package.get("report_id"),
            "advisory_only": True,
            "trading_impact": False,
        }
    return evidence


class ExecutiveBriefReadinessOrchestrator:
    """
    Canonical advisory readiness layer for Executive Brief generation.

    Read-only: evaluates evidence only; never mutates brokers, runtime,
    execution, or schedulers.
    """

    def __init__(
        self,
        *,
        freshness_soft_seconds: float = DEFAULT_SOFT_FRESHNESS_SECONDS,
        freshness_hard_seconds: float = DEFAULT_FRESHNESS_SECONDS * 2,
        component_specs: Sequence[ComponentSpec] | None = None,
    ) -> None:
        self.freshness_soft_seconds = float(freshness_soft_seconds)
        self.freshness_hard_seconds = float(freshness_hard_seconds)
        self.component_specs = tuple(component_specs or COMPONENT_SPECS)

    def get_readiness(
        self,
        evidence: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a compact readiness summary dict."""
        report = self.generate_report(evidence=evidence)
        return {
            "overall_state": report.overall_state,
            "overall_readiness_score": report.score,
            "score": report.score,
            "blocking_items": list(report.blocking_items),
            "warning_items": list(report.warning_items),
            "advisories": list(report.advisories),
            "missing_datasets": list(report.missing_datasets),
            "outdated_datasets": list(report.outdated_datasets),
            "estimated_generation_time": report.estimated_generation_time,
            "advisory_only": True,
            "trading_impact": False,
            "timestamp": report.timestamp,
        }

    def generate_report(
        self,
        evidence: Mapping[str, Any] | None = None,
    ) -> ExecutiveBriefReadinessReport:
        """Build the full ExecutiveBriefReadinessReport from evidence."""
        # Deep copy so assessment never mutates caller-supplied evidence.
        payload = copy.deepcopy(dict(evidence or {}))
        assessments: list[ComponentAssessment] = []

        for spec in self.component_specs:
            assessments.append(self._assess_component(spec, payload))

        # Deterministic exclusive classification (COMPONENT_SPECS order).
        missing = [a.label for a in assessments if a.status == STATUS_MISSING]
        outdated = [a.label for a in assessments if a.status == STATUS_OUTDATED]
        blocking: list[str] = []
        warnings: list[str] = []
        advisories: list[str] = []
        seen_blocking: set[str] = set()
        seen_warnings: set[str] = set()
        seen_advisories: set[str] = set()

        for a in assessments:
            item = f"{a.label}: {a.message or a.status}"
            if a.severity == SEVERITY_BLOCKING and a.status != STATUS_READY:
                if item not in seen_blocking:
                    blocking.append(item)
                    seen_blocking.add(item)
            elif a.severity == SEVERITY_WARNING and a.status != STATUS_READY:
                if item not in seen_warnings:
                    warnings.append(item)
                    seen_warnings.add(item)
            elif a.severity == SEVERITY_ADVISORY and a.status != STATUS_READY:
                if item not in seen_advisories:
                    advisories.append(item)
                    seen_advisories.add(item)
            elif a.status == STATUS_WARNING:
                if item not in seen_warnings:
                    warnings.append(item)
                    seen_warnings.add(item)

        score = self._calculate_score(assessments)
        overall_state = self._resolve_state(
            score=score,
            blocking=blocking,
            warning_items=warnings,
            assessments=assessments,
        )
        score = self._align_score_with_state(score, overall_state)
        actions = self._recommended_actions(
            overall_state=overall_state,
            blocking=blocking,
            warnings=warnings,
            missing=missing,
            outdated=outdated,
        )
        est_seconds = self._estimate_generation_seconds(assessments)
        return ExecutiveBriefReadinessReport(
            timestamp=_utc_now_iso(),
            overall_state=overall_state,
            score=round(score, 1),
            blocking_items=blocking,
            warning_items=warnings,
            advisories=advisories,
            recommended_actions=actions,
            estimated_generation_time=_format_duration(est_seconds),
            estimated_generation_seconds=est_seconds,
            missing_datasets=missing,
            outdated_datasets=outdated,
            components=assessments,
        )

    def to_dict(self, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Convenience: generate_report(...).to_dict()."""
        return self.generate_report(evidence=evidence).to_dict()

    def _assess_component(
        self,
        spec: ComponentSpec,
        evidence: Mapping[str, Any],
    ) -> ComponentAssessment:
        try:
            raw = _pick_evidence(evidence, (spec.key, *spec.evidence_keys))
            age = _extract_age_seconds(raw)
            freshness_ts = _extract_freshness_timestamp(raw)

            if spec.key == "open_alerts":
                status, message = _assess_open_alerts(raw)
            elif spec.key == "pnl":
                status, message = _assess_pnl(raw)
            elif spec.key == "reporting_data_freshness":
                status, message, age = _assess_reporting_freshness(
                    raw,
                    soft_limit=self.freshness_soft_seconds,
                    hard_limit=self.freshness_hard_seconds,
                )
            else:
                status, message = self._generic_status(spec, raw, age)

            source_available = status not in {
                STATUS_MISSING,
                STATUS_UNAVAILABLE,
            } and _payload_present(raw)
            return ComponentAssessment(
                key=spec.key,
                label=spec.label,
                severity=spec.severity,
                status=status,
                message=message,
                age_seconds=age,
                freshness_timestamp=freshness_ts,
                classification=spec.severity,
                recommended_action=_component_recommended_action(
                    spec.label, status, spec.severity
                ),
                source_available=bool(source_available),
            )
        except Exception as exc:  # noqa: BLE001 — isolate provider/component failures
            return ComponentAssessment(
                key=spec.key,
                label=spec.label,
                severity=spec.severity,
                status=STATUS_UNAVAILABLE,
                message=f"{spec.label} assessment failed safely ({type(exc).__name__})",
                age_seconds=None,
                freshness_timestamp=None,
                classification=spec.severity,
                recommended_action=(
                    f"Investigate {spec.label} provider exception; "
                    "readiness remains advisory-only."
                ),
                source_available=False,
            )

    def _generic_status(
        self,
        spec: ComponentSpec,
        raw: Any,
        age: float | None,
    ) -> tuple[str, str]:
        explicit = _extract_status(raw)
        if not _payload_present(raw) and explicit is None:
            return STATUS_MISSING, f"{spec.label} dataset missing"
        if explicit == STATUS_MISSING:
            return STATUS_MISSING, f"{spec.label} marked missing"
        if explicit == STATUS_UNAVAILABLE:
            return STATUS_UNAVAILABLE, f"{spec.label} unavailable"
        if explicit == STATUS_OUTDATED:
            return STATUS_OUTDATED, f"{spec.label} outdated"
        if age is not None:
            hard = self.freshness_hard_seconds
            soft = self.freshness_soft_seconds
            if age > hard:
                return STATUS_OUTDATED, f"{spec.label} outdated ({int(age)}s)"
            if age > soft or explicit == STATUS_WARNING:
                return STATUS_WARNING, f"{spec.label} aging or degraded"
        if explicit == STATUS_WARNING:
            return STATUS_WARNING, f"{spec.label} degraded"
        if explicit == STATUS_READY or _payload_present(raw):
            return STATUS_READY, f"{spec.label} ready"
        return STATUS_MISSING, f"{spec.label} dataset missing"

    def _calculate_score(self, assessments: Sequence[ComponentAssessment]) -> float:
        if not assessments:
            return 0.0
        total = sum(_score_component(a.status, a.severity) for a in assessments)
        return max(0.0, min(100.0, (total / len(assessments)) * 100.0))

    def _resolve_state(
        self,
        *,
        score: float,
        blocking: Sequence[str],
        warning_items: Sequence[str],
        assessments: Sequence[ComponentAssessment],
    ) -> str:
        blocking_hard = [
            a
            for a in assessments
            if a.severity == SEVERITY_BLOCKING
            and a.status in {STATUS_MISSING, STATUS_UNAVAILABLE, STATUS_OUTDATED}
        ]
        # Precedence: NOT_READY > RED > AMBER > GREEN
        if any(
            a.status in {STATUS_MISSING, STATUS_UNAVAILABLE} for a in blocking_hard
        ):
            return STATE_NOT_READY
        if any(a.status == STATUS_OUTDATED for a in blocking_hard):
            return STATE_RED
        if blocking and score < 70:
            return STATE_RED
        if warning_items or (blocking and score >= 70) or score < 85.0:
            if score < 60.0 and not warning_items and not blocking:
                return STATE_RED
            if score < 60.0:
                return STATE_RED
            return STATE_AMBER
        if score >= 85.0 and not blocking and not warning_items:
            return STATE_GREEN
        return STATE_AMBER

    def _align_score_with_state(self, score: float, overall_state: str) -> float:
        """Prevent contradictory high scores for degraded overall states."""
        if overall_state == STATE_NOT_READY:
            return min(score, 49.0)
        if overall_state == STATE_RED:
            return min(score, 69.0)
        if overall_state == STATE_AMBER:
            return min(score, 84.9)
        return score

    def _recommended_actions(
        self,
        *,
        overall_state: str,
        blocking: Sequence[str],
        warnings: Sequence[str],
        missing: Sequence[str],
        outdated: Sequence[str],
    ) -> list[str]:
        actions: list[str] = []
        if overall_state == STATE_GREEN:
            actions.append("Executive Brief inputs look ready; generation may proceed when requested.")
            return actions
        if missing:
            actions.append(
                "Restore missing datasets before generating: " + ", ".join(missing[:6])
            )
        if outdated:
            actions.append(
                "Refresh outdated datasets before generating: " + ", ".join(outdated[:6])
            )
        if blocking:
            actions.append("Resolve blocking readiness items (advisory gate only — no auto-trading).")
        if warnings and overall_state in {STATE_AMBER, STATE_RED, STATE_NOT_READY}:
            actions.append("Review warning components and confirm operators accept residual risk.")
        if not actions:
            actions.append("Re-check Executive Brief readiness after the next runtime snapshot.")
        actions.append("This readiness layer is advisory-only and does not alter trading or execution.")
        return actions

    def _estimate_generation_seconds(self, assessments: Sequence[ComponentAssessment]) -> int:
        seconds = BASE_GENERATION_SECONDS
        for a in assessments:
            if a.status == STATUS_MISSING:
                seconds += PER_MISSING_SECONDS
            elif a.status == STATUS_OUTDATED:
                seconds += PER_OUTDATED_SECONDS
            elif a.status == STATUS_WARNING:
                seconds += PER_WARNING_SECONDS
            elif a.status == STATUS_UNAVAILABLE:
                seconds += PER_MISSING_SECONDS
        return int(seconds)


__all__ = [
    "COMPONENT_SPECS",
    "ComponentAssessment",
    "ComponentSpec",
    "ExecutiveBriefReadinessOrchestrator",
    "ExecutiveBriefReadinessReport",
    "STATE_AMBER",
    "STATE_GREEN",
    "STATE_NOT_READY",
    "STATE_RED",
    "evidence_from_mission_control_state",
]
