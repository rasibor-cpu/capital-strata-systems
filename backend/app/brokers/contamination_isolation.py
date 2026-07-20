"""
Phase 177C — Cross-broker contamination isolation.

Detects when one broker inherits endpoint, credentials, configuration,
telemetry, API version, health, or runtime state fields belonging to another.

Does not expose secret values — only key names and finding codes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from backend.app.brokers.canonical_tier1 import (
    TIER1_BROKERS,
    get_canonical_broker_registry,
)

SCHEMA_VERSION = "css.broker.contamination.v1"

# Host tokens that must not appear under another broker's endpoint keys
_HOST_TOKENS: dict[str, tuple[str, ...]] = {
    "COINBASE": ("coinbase.com", "coinbase"),
    "BINANCE": ("binance.com", "binance"),
    "OANDA": ("oanda.com", "fxtrade", "fxpractice"),
    "QUESTRADE": ("questrade.com", "questrade"),
}


@dataclass(frozen=True)
class ContaminationFinding:
    code: str
    severity: str
    owner_broker: str
    foreign_broker: str
    field: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContaminationReport:
    status: str
    findings: list[ContaminationFinding] = field(default_factory=list)
    environment_contamination: bool = False
    cross_broker_contamination: bool = False
    isolated_brokers: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    generated_at: str = ""
    advisory_only: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "findings": [f.as_dict() for f in self.findings],
            "environment_contamination": self.environment_contamination,
            "cross_broker_contamination": self.cross_broker_contamination,
            "isolated_brokers": list(self.isolated_brokers),
            "schema_version": self.schema_version,
            "generated_at": self.generated_at or _utc_now(),
            "advisory_only": True,
            "execution_allowed": False,
        }

    def findings_by_broker(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {b: [] for b in TIER1_BROKERS}
        for finding in self.findings:
            out.setdefault(finding.owner_broker, []).append(finding.code)
            out.setdefault(finding.foreign_broker, []).append(finding.code)
        return out


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def analyze_environment_contamination(
    env: Mapping[str, Any] | None = None,
    *,
    selected_broker: str | None = None,
) -> ContaminationReport:
    """Scan process env (or provided mapping) for cross-broker endpoint/credential bleed."""
    import os

    source: Mapping[str, Any] = env if isinstance(env, Mapping) else os.environ
    registry = get_canonical_broker_registry()
    findings: list[ContaminationFinding] = []

    # 1) Endpoint values under broker A containing host tokens of broker B
    for owner in registry.list_brokers():
        spec = registry.get(owner)
        for key in spec.endpoint_env_keys:
            raw = source.get(key)
            if not _present(raw):
                continue
            text = str(raw).strip().lower()
            for foreign, tokens in _HOST_TOKENS.items():
                if foreign == owner:
                    continue
                if any(token in text for token in tokens):
                    findings.append(
                        ContaminationFinding(
                            code="CROSS_BROKER_ENDPOINT",
                            severity="HIGH",
                            owner_broker=owner,
                            foreign_broker=foreign,
                            field=key,
                            detail=f"{owner} endpoint key contains {foreign} host token",
                        )
                    )

    # 2) API version keys of A holding B identity markers
    for owner in registry.list_brokers():
        spec = registry.get(owner)
        for key in spec.api_version_env_keys:
            raw = source.get(key)
            if not _present(raw):
                continue
            text = str(raw).strip().lower()
            for foreign, tokens in _HOST_TOKENS.items():
                if foreign == owner:
                    continue
                if any(token in text for token in tokens):
                    findings.append(
                        ContaminationFinding(
                            code="CROSS_BROKER_API_VERSION",
                            severity="HIGH",
                            owner_broker=owner,
                            foreign_broker=foreign,
                            field=key,
                            detail=f"{owner} API version field references {foreign}",
                        )
                    )

    # 3) Selected broker must not advertise foreign credential prefixes as its own
    selected = str(selected_broker or "").strip().upper()
    if selected in registry.list_brokers():
        selected_prefixes = registry.get(selected).credential_prefixes
        for foreign in registry.list_brokers():
            if foreign == selected:
                continue
            for prefix in registry.get(foreign).credential_prefixes:
                for env_key, value in source.items():
                    key_u = str(env_key).upper()
                    if not key_u.startswith(tuple(p.upper() for p in selected_prefixes)):
                        continue
                    # selected broker's own key containing foreign broker name as value marker
                    if _present(value) and any(t in str(value).lower() for t in _HOST_TOKENS.get(foreign, ())):
                        findings.append(
                            ContaminationFinding(
                                code="CROSS_BROKER_CREDENTIAL_VALUE",
                                severity="CRITICAL",
                                owner_broker=selected,
                                foreign_broker=foreign,
                                field=str(env_key),
                                detail="Selected broker credential value references foreign broker host",
                            )
                        )

    # 4) Classic paper/sandbox tokens in live-oriented keys (environment contamination)
    env_contam = False
    live_keys = (
        "COINBASE_ENABLE_LIVE_ORDERS",
        "COINBASE_ENABLE_LIVE_TRADING",
        "OANDA_ENABLE_LIVE_ORDERS",
        "OANDA_ENABLE_LIVE_TRADING",
        "BINANCE_ENABLE_LIVE_ORDERS",
        "QUESTRADE_ENABLE_LIVE_ORDERS",
    )
    for key in live_keys:
        if not _present(source.get(key)):
            continue
        # Presence of sandbox URL alongside live enable is contamination signal
        for url_key in ("COINBASE_SANDBOX_URL", "BINANCE_TESTNET_URL", "OANDA_BASE_URL"):
            url_val = str(source.get(url_key) or "").lower()
            if any(tok in url_val for tok in ("sandbox", "practice", "testnet", "demo")):
                env_contam = True
                findings.append(
                    ContaminationFinding(
                        code="ENVIRONMENT_CONTAMINATION",
                        severity="HIGH",
                        owner_broker=_owner_from_key(key),
                        foreign_broker=_owner_from_key(url_key),
                        field=f"{key}+{url_key}",
                        detail="Live-enable flag coexists with sandbox/practice endpoint",
                    )
                )

    cross = any(f.code.startswith("CROSS_BROKER") for f in findings)
    isolated = [b for b in TIER1_BROKERS if not any(f.owner_broker == b or f.foreign_broker == b for f in findings)]
    status = "PASS" if not findings else ("FAIL_CROSS_BROKER" if cross else "FAIL_ENVIRONMENT")
    return ContaminationReport(
        status=status,
        findings=findings,
        environment_contamination=env_contam or any(f.code == "ENVIRONMENT_CONTAMINATION" for f in findings),
        cross_broker_contamination=cross,
        isolated_brokers=isolated,
    )


def analyze_runtime_state_contamination(state: Mapping[str, Any] | None) -> ContaminationReport:
    """
    Detect nested runtime/telemetry dicts where OANDA subtree carries Coinbase
    endpoint/version fields (and vice versa).
    """
    findings: list[ContaminationFinding] = []
    if not isinstance(state, Mapping):
        return ContaminationReport(status="PASS", isolated_brokers=list(TIER1_BROKERS))

    forbidden_pairs = (
        ("oanda", "coinbase"),
        ("oanda", "binance"),
        ("coinbase", "oanda"),
        ("binance", "oanda"),
        ("questrade", "coinbase"),
        ("questrade", "oanda"),
        ("questrade", "binance"),
        ("coinbase", "questrade"),
        ("binance", "questrade"),
        ("oanda", "questrade"),
        ("binance", "coinbase"),
        ("coinbase", "binance"),
    )

    def walk(obj: Any, path: str) -> None:
        if isinstance(obj, Mapping):
            path_l = path.lower()
            keys_l = {str(k).lower(): k for k in obj.keys()}
            for owner_token, foreign_token in forbidden_pairs:
                if owner_token not in path_l:
                    continue
                for key_l, orig in keys_l.items():
                    if foreign_token in key_l:
                        findings.append(
                            ContaminationFinding(
                                code="CROSS_BROKER_RUNTIME_FIELD",
                                severity="HIGH",
                                owner_broker=owner_token.upper(),
                                foreign_broker=foreign_token.upper(),
                                field=f"{path}.{orig}",
                                detail="Runtime state nests foreign broker field under owner path",
                            )
                        )
                    val = obj.get(orig)
                    if isinstance(val, str) and foreign_token in val.lower() and any(
                        x in key_l for x in ("url", "endpoint", "base", "api_version", "host")
                    ):
                        findings.append(
                            ContaminationFinding(
                                code="CROSS_BROKER_RUNTIME_VALUE",
                                severity="CRITICAL",
                                owner_broker=owner_token.upper(),
                                foreign_broker=foreign_token.upper(),
                                field=f"{path}.{orig}",
                                detail="Runtime endpoint/version value references foreign broker",
                            )
                        )
            for k, v in obj.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(obj, list):
            for i, item in enumerate(obj[:50]):
                walk(item, f"{path}[{i}]")

    walk(state, "")
    cross = bool(findings)
    isolated = [b for b in TIER1_BROKERS if not any(b.lower() in f.owner_broker.lower() or b.lower() in f.foreign_broker.lower() for f in findings)]
    return ContaminationReport(
        status="PASS" if not findings else "FAIL_CROSS_BROKER",
        findings=findings,
        environment_contamination=False,
        cross_broker_contamination=cross,
        isolated_brokers=isolated,
    )


def merge_contamination_reports(*reports: ContaminationReport) -> ContaminationReport:
    findings: list[ContaminationFinding] = []
    for report in reports:
        findings.extend(report.findings)
    # dedupe by code+field
    seen: set[tuple[str, str]] = set()
    unique: list[ContaminationFinding] = []
    for finding in findings:
        key = (finding.code, finding.field)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    cross = any(f.code.startswith("CROSS_BROKER") for f in unique)
    env = any(f.code == "ENVIRONMENT_CONTAMINATION" for f in unique)
    isolated = [b for b in TIER1_BROKERS if not any(f.owner_broker == b or f.foreign_broker == b for f in unique)]
    status = "PASS" if not unique else ("FAIL_CROSS_BROKER" if cross else "FAIL_ENVIRONMENT")
    return ContaminationReport(
        status=status,
        findings=unique,
        environment_contamination=env,
        cross_broker_contamination=cross,
        isolated_brokers=isolated,
    )


def _owner_from_key(key: str) -> str:
    text = str(key or "").upper()
    for broker in TIER1_BROKERS:
        if text.startswith(broker):
            return broker
    return "UNKNOWN"


def profile_keys_for_broker(broker: str) -> frozenset[str]:
    """Return env key frozenset owned exclusively by a broker (for profile scrubbing)."""
    registry = get_canonical_broker_registry()
    key = str(broker or "").strip().upper()
    if not registry.is_tier1(key):
        return frozenset()
    spec = registry.get(key)
    # Include common credential naming patterns for each broker
    extras: dict[str, tuple[str, ...]] = {
        "COINBASE": (
            "COINBASE_CDP_KEY_NAME",
            "COINBASE_KEY_NAME",
            "COINBASE_API_KEY",
            "COINBASE_CDP_PRIVATE_KEY",
            "COINBASE_PRIVATE_KEY",
            "COINBASE_API_SECRET",
            "COINBASE_BASE_URL",
            "COINBASE_API_URL",
            "COINBASE_REST_URL",
            "COINBASE_SANDBOX_URL",
            "COINBASE_API_VERSION",
            "COINBASE_ENABLE_LIVE_ORDERS",
            "COINBASE_ENABLE_LIVE_TRADING",
        ),
        "BINANCE": (
            "BINANCE_API_KEY",
            "BINANCE_API_SECRET",
            "BINANCE_BASE_URL",
            "BINANCE_API_URL",
            "BINANCE_REST_URL",
            "BINANCE_TESTNET_URL",
            "BINANCE_API_VERSION",
            "BINANCE_ENABLE_LIVE_ORDERS",
        ),
        "OANDA": (
            "OANDA_API_KEY",
            "OANDA_ACCESS_TOKEN",
            "OANDA_TOKEN",
            "OANDA_ACCOUNT_ID",
            "OANDA_LIVE_ACCOUNT_ID",
            "OANDA_PRACTICE_ACCOUNT_ID",
            "OANDA_BASE_URL",
            "OANDA_API_URL",
            "OANDA_API_VERSION",
            "OANDA_ENABLE_LIVE_ORDERS",
            "OANDA_ENABLE_LIVE_TRADING",
        ),
        "QUESTRADE": (
            "QUESTRADE_REFRESH_TOKEN",
            "QUESTRADE_ACCESS_TOKEN",
            "QUESTRADE_API_KEY",
            "QUESTRADE_BASE_URL",
            "QUESTRADE_API_URL",
            "QUESTRADE_AUTH_URL",
            "QUESTRADE_API_VERSION",
            "QUESTRADE_ENABLE_LIVE_ORDERS",
            "QT_REFRESH_TOKEN",
            "QT_ACCESS_TOKEN",
        ),
    }
    owned = set(extras.get(key, ()))
    owned.update(spec.endpoint_env_keys)
    owned.update(spec.api_version_env_keys)
    return frozenset(owned)


__all__ = [
    "ContaminationFinding",
    "ContaminationReport",
    "SCHEMA_VERSION",
    "analyze_environment_contamination",
    "analyze_runtime_state_contamination",
    "merge_contamination_reports",
    "profile_keys_for_broker",
]
