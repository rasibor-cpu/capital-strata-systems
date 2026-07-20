"""
Phase 177C — Canonical Tier-1 Multi-Broker Architecture (Revision B).

Approved production brokers:
  Coinbase | Binance | OANDA | Questrade

IBKR is removed from the active implementation roadmap.
Brokers advertise capabilities via plugins; the execution engine must not
hard-code per-broker behaviour beyond registry lookup.

Execution remains blocked at the registry layer for all brokers in this phase.
LIVE_READ_ONLY is advertised as a capability; order submission is never enabled here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

SCHEMA_VERSION = "css.broker.tier1.v1"

# Canonical Tier-1 set — Revision B
TIER1_BROKERS: tuple[str, ...] = ("COINBASE", "BINANCE", "OANDA", "QUESTRADE")

# Explicitly removed from active roadmap (historical stubs may remain on disk)
ROADMAP_EXCLUDED_BROKERS: frozenset[str] = frozenset({"IBKR", "INTERACTIVE_BROKERS", "ALPACA"})


class BrokerType(str, Enum):
    CRYPTO = "CRYPTO"
    FX = "FX"
    EQUITIES_CA = "EQUITIES_CA"
    MULTI_ASSET = "MULTI_ASSET"


class BrokerRole(str, Enum):
    PRIMARY_CRYPTO = "PRIMARY_CRYPTO_BROKER"
    SECONDARY_CRYPTO = "SECONDARY_CRYPTO_BROKER"
    PRIMARY_FX = "PRIMARY_FX_BROKER"
    PRIMARY_CANADIAN_EQUITIES = "PRIMARY_CANADIAN_EQUITIES_BROKER"
    UNASSIGNED = "UNASSIGNED"


class OperationalState(str, Enum):
    REGISTERED = "REGISTERED"
    UNCONFIGURED = "UNCONFIGURED"
    AUTHENTICATING = "AUTHENTICATING"
    LIVE_READ_ONLY = "LIVE_READ_ONLY"
    READY = "READY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class CertificationState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    READ_ONLY_CERTIFIED = "READ_ONLY_CERTIFIED"
    EXECUTION_CERTIFIED = "EXECUTION_CERTIFIED"
    FAILED = "FAILED"
    REVOKED = "REVOKED"


DEFAULT_ROLE_BY_BROKER: dict[str, BrokerRole] = {
    "COINBASE": BrokerRole.PRIMARY_CRYPTO,
    "BINANCE": BrokerRole.SECONDARY_CRYPTO,
    "OANDA": BrokerRole.PRIMARY_FX,
    "QUESTRADE": BrokerRole.PRIMARY_CANADIAN_EQUITIES,
}


@dataclass(frozen=True)
class BrokerCapabilities:
    """Advertised capabilities — plugins declare these; engine must not invent them."""

    authenticate: bool = True
    load_balances: bool = True
    load_positions: bool = True
    load_market_data: bool = True
    synchronize_products: bool = True
    refresh_broker_health: bool = True
    refresh_readiness: bool = True
    live_read_only: bool = True
    spot_markets: bool = False
    market_depth: bool = False
    portfolio_sync: bool = False
    treasury_integration: bool = False
    currency_analytics: bool = False
    fx_risk_management: bool = False
    canadian_equities: bool = False
    etfs: bool = False
    listed_options: bool = False
    registered_accounts_future: bool = False
    margin_futures_future: bool = False
    # Execution is always false at registry advertisement for Phase 177C
    execution_enabled: bool = False
    order_submission: bool = False


@dataclass(frozen=True)
class BrokerPluginSpec:
    name: str
    display_name: str
    broker_type: BrokerType
    role: BrokerRole
    asset_classes: tuple[str, ...]
    supported_runtime_modes: tuple[str, ...]
    capabilities: BrokerCapabilities
    credential_prefixes: tuple[str, ...]
    endpoint_env_keys: tuple[str, ...]
    api_version_env_keys: tuple[str, ...] = ()
    pip_package: str = ""
    credential_file: str = ""
    priority: int = 100
    plugin_module: str = ""
    responsibilities: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["broker_type"] = self.broker_type.value
        payload["role"] = self.role.value
        payload["asset_classes"] = list(self.asset_classes)
        payload["supported_runtime_modes"] = list(self.supported_runtime_modes)
        payload["credential_prefixes"] = list(self.credential_prefixes)
        payload["endpoint_env_keys"] = list(self.endpoint_env_keys)
        payload["api_version_env_keys"] = list(self.api_version_env_keys)
        payload["responsibilities"] = list(self.responsibilities)
        payload["capabilities"] = asdict(self.capabilities)
        return payload


@dataclass
class BrokerHealthSnapshot:
    broker: str
    broker_type: str
    role: str
    asset_classes: list[str]
    authentication_state: str = "NOT_TESTED"
    credential_health: str = "UNKNOWN"
    connection_health: str = "NOT_CONNECTED"
    market_data_health: str = "UNAVAILABLE"
    account_health: str = "UNAVAILABLE"
    execution_capability: str = "DISABLED"
    execution_authority: str = "BLOCKED"
    operational_readiness: str = "UNCONFIGURED"
    certification_state: str = CertificationState.NOT_STARTED.value
    latency_ms: float | None = None
    last_validation: str | None = None
    last_sync: str | None = None
    supported_runtime_modes: list[str] = field(default_factory=list)
    error_state: str | None = None
    readiness_score: float = 0.0
    operational_state: str = OperationalState.REGISTERED.value
    selected: bool = False
    live_read_only_allowed: bool = True
    execution_blocked: bool = True
    advisory_only: bool = True
    contamination_isolated: bool = True
    contamination_findings: list[str] = field(default_factory=list)
    capabilities: dict[str, Any] = field(default_factory=dict)
    responsibilities: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    generated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["generated_at"] = self.generated_at or _utc_now()
        payload["execution_enabled"] = False
        payload["order_submission"] = "BLOCKED"
        payload["live_trading_enabled"] = False
        return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coinbase_spec() -> BrokerPluginSpec:
    return BrokerPluginSpec(
        name="COINBASE",
        display_name="Coinbase",
        broker_type=BrokerType.CRYPTO,
        role=BrokerRole.PRIMARY_CRYPTO,
        asset_classes=("CRYPTO", "SPOT_CRYPTO"),
        supported_runtime_modes=("PAPER", "LIVE_READ_ONLY", "DISABLED"),
        capabilities=BrokerCapabilities(
            spot_markets=True,
            portfolio_sync=True,
            live_read_only=True,
        ),
        credential_prefixes=("COINBASE_",),
        endpoint_env_keys=("COINBASE_BASE_URL", "COINBASE_API_URL", "COINBASE_REST_URL", "COINBASE_SANDBOX_URL"),
        api_version_env_keys=("COINBASE_API_VERSION",),
        pip_package="coinbase-advanced-py",
        credential_file="cdp_api_key.json",
        priority=1,
        plugin_module="backend.app.brokers.plugins.coinbase",
        responsibilities=(
            "Cryptocurrency",
            "Read-only validation",
            "Market data",
            "Future execution (not enabled)",
        ),
    )


def _binance_spec() -> BrokerPluginSpec:
    return BrokerPluginSpec(
        name="BINANCE",
        display_name="Binance",
        broker_type=BrokerType.CRYPTO,
        role=BrokerRole.SECONDARY_CRYPTO,
        asset_classes=("CRYPTO", "SPOT_CRYPTO"),
        supported_runtime_modes=("PAPER", "LIVE_READ_ONLY", "DISABLED"),
        capabilities=BrokerCapabilities(
            spot_markets=True,
            market_depth=True,
            portfolio_sync=True,
            live_read_only=True,
            margin_futures_future=True,
        ),
        credential_prefixes=("BINANCE_",),
        endpoint_env_keys=("BINANCE_BASE_URL", "BINANCE_API_URL", "BINANCE_REST_URL", "BINANCE_TESTNET_URL"),
        api_version_env_keys=("BINANCE_API_VERSION",),
        pip_package="python-binance",
        credential_file=".env.binance",
        priority=2,
        plugin_module="backend.app.brokers.plugins.binance",
        responsibilities=(
            "Cryptocurrency",
            "Spot markets",
            "Market depth",
            "Portfolio synchronization",
            "Read-only validation",
            "Future margin/futures (where legally supported)",
            "Future execution (not enabled)",
        ),
    )


def _oanda_spec() -> BrokerPluginSpec:
    return BrokerPluginSpec(
        name="OANDA",
        display_name="OANDA",
        broker_type=BrokerType.FX,
        role=BrokerRole.PRIMARY_FX,
        asset_classes=("FX", "FOREX"),
        supported_runtime_modes=("PAPER", "LIVE_READ_ONLY", "DISABLED"),
        capabilities=BrokerCapabilities(
            treasury_integration=True,
            currency_analytics=True,
            fx_risk_management=True,
            live_read_only=True,
        ),
        credential_prefixes=("OANDA_",),
        endpoint_env_keys=("OANDA_BASE_URL", "OANDA_API_URL"),
        api_version_env_keys=("OANDA_API_VERSION",),
        pip_package="oandapyV20",
        credential_file=".env.oanda",
        priority=3,
        plugin_module="backend.app.brokers.plugins.oanda",
        responsibilities=(
            "Spot FX",
            "Treasury integration",
            "Currency analytics",
            "FX risk management",
        ),
    )


def _questrade_spec() -> BrokerPluginSpec:
    return BrokerPluginSpec(
        name="QUESTRADE",
        display_name="Questrade",
        broker_type=BrokerType.EQUITIES_CA,
        role=BrokerRole.PRIMARY_CANADIAN_EQUITIES,
        asset_classes=("EQUITY_CA", "ETF", "OPTION"),
        supported_runtime_modes=("PAPER", "LIVE_READ_ONLY", "DISABLED"),
        capabilities=BrokerCapabilities(
            canadian_equities=True,
            etfs=True,
            listed_options=True,
            portfolio_sync=True,
            live_read_only=True,
            registered_accounts_future=True,
        ),
        credential_prefixes=("QUESTRADE_", "QT_"),
        endpoint_env_keys=("QUESTRADE_BASE_URL", "QUESTRADE_API_URL", "QUESTRADE_AUTH_URL"),
        api_version_env_keys=("QUESTRADE_API_VERSION",),
        pip_package="",
        credential_file=".env.questrade",
        priority=4,
        plugin_module="backend.app.brokers.plugins.questrade",
        responsibilities=(
            "Canadian equities",
            "ETFs",
            "Listed options",
            "Canadian portfolio management",
            "Future registered account support",
            "Read-only validation",
        ),
    )


_PLUGIN_BUILDERS: dict[str, Callable[[], BrokerPluginSpec]] = {
    "COINBASE": _coinbase_spec,
    "BINANCE": _binance_spec,
    "OANDA": _oanda_spec,
    "QUESTRADE": _questrade_spec,
}


class CanonicalBrokerRegistry:
    """Capability-advertising broker registry. Future brokers register as plugins."""

    def __init__(self, plugins: Sequence[BrokerPluginSpec] | None = None) -> None:
        specs = list(plugins) if plugins is not None else [builder() for builder in _PLUGIN_BUILDERS.values()]
        self._by_name: dict[str, BrokerPluginSpec] = {spec.name.upper(): spec for spec in specs}

    def list_brokers(self) -> list[str]:
        return sorted(self._by_name.keys(), key=lambda n: self._by_name[n].priority)

    def get(self, broker: str) -> BrokerPluginSpec:
        key = str(broker or "").strip().upper()
        if key not in self._by_name:
            raise KeyError(f"Broker '{broker}' is not in the canonical Tier-1 registry")
        return self._by_name[key]

    def is_tier1(self, broker: str) -> bool:
        return str(broker or "").strip().upper() in self._by_name

    def is_roadmap_excluded(self, broker: str) -> bool:
        return str(broker or "").strip().upper() in ROADMAP_EXCLUDED_BROKERS

    def role_for(self, broker: str) -> BrokerRole:
        key = str(broker or "").strip().upper()
        if key in self._by_name:
            return self._by_name[key].role
        return DEFAULT_ROLE_BY_BROKER.get(key, BrokerRole.UNASSIGNED)

    def primary_roles(self) -> dict[str, str]:
        """Map role → broker name for Mission Control role display."""
        out: dict[str, str] = {}
        for name, spec in self._by_name.items():
            out[spec.role.value] = name
        return out

    def snapshot(
        self,
        broker: str,
        *,
        selected_broker: str | None = None,
        active: Mapping[str, Any] | None = None,
        contamination_findings: Sequence[str] | None = None,
    ) -> BrokerHealthSnapshot:
        spec = self.get(broker)
        active = active if isinstance(active, Mapping) else {}
        selected = str(selected_broker or active.get("selected_broker") or active.get("broker") or "NONE").upper()
        is_selected = selected == spec.name

        auth = "NOT_TESTED"
        cred = "UNKNOWN"
        conn = "NOT_CONNECTED"
        md = "UNAVAILABLE"
        acct = "UNAVAILABLE"
        readiness = "UNCONFIGURED"
        score = 0.0
        latency = None
        last_val = None
        last_sync = None
        error = None
        op_state = OperationalState.REGISTERED.value
        cert = CertificationState.NOT_STARTED.value

        if is_selected:
            auth = str(active.get("authentication_status") or active.get("authentication_health") or auth)
            cred = str(active.get("credential_status") or active.get("credentials_health") or cred)
            conn = str(active.get("connection_status") or active.get("connection_health") or conn)
            md = str(active.get("market_data_status") or active.get("market_data_health") or md)
            acct = str(active.get("account_data_health") or active.get("account_status") or acct)
            readiness = str(
                active.get("overall_status")
                or active.get("readiness_state")
                or active.get("broker_health")
                or readiness
            )
            try:
                score = float(active.get("readiness_score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            try:
                latency = float(active.get("latency_ms")) if active.get("latency_ms") not in (None, "") else None
            except (TypeError, ValueError):
                latency = None
            last_val = active.get("last_validation") or active.get("last_successful_sync")
            last_sync = active.get("last_successful_sync") or active.get("last_broker_sync")
            error = active.get("failure_reason") or active.get("connection_error") or active.get("error_state")
            mode = str(active.get("broker_mode") or "").lower()
            if str(active.get("broker_mode") or "").upper() in {"LIVE_READ_ONLY", "LIVE-READ-ONLY"} or (
                mode == "live" and not bool(active.get("execution_authority"))
            ):
                op_state = OperationalState.LIVE_READ_ONLY.value
                cert = CertificationState.IN_PROGRESS.value
            elif readiness.upper() in {"READY", "FULLY_OPERATIONAL", "PASS"}:
                op_state = OperationalState.READY.value
            elif error:
                op_state = OperationalState.BLOCKED.value
            else:
                op_state = OperationalState.UNCONFIGURED.value
        else:
            op_state = OperationalState.REGISTERED.value
            readiness = "UNCONFIGURED"

        findings = list(contamination_findings or [])
        return BrokerHealthSnapshot(
            broker=spec.name,
            broker_type=spec.broker_type.value,
            role=spec.role.value,
            asset_classes=list(spec.asset_classes),
            authentication_state=auth,
            credential_health=cred,
            connection_health=conn,
            market_data_health=md,
            account_health=acct,
            execution_capability="DISABLED",
            execution_authority="BLOCKED",
            operational_readiness=readiness,
            certification_state=cert,
            latency_ms=latency,
            last_validation=str(last_val) if last_val else None,
            last_sync=str(last_sync) if last_sync else None,
            supported_runtime_modes=list(spec.supported_runtime_modes),
            error_state=str(error) if error else None,
            readiness_score=score,
            operational_state=op_state,
            selected=is_selected,
            live_read_only_allowed=bool(spec.capabilities.live_read_only),
            execution_blocked=True,
            contamination_isolated=len(findings) == 0,
            contamination_findings=findings,
            capabilities=asdict(spec.capabilities),
            responsibilities=list(spec.responsibilities),
        )

    def mission_control_rows(
        self,
        *,
        selected_broker: str | None = None,
        active: Mapping[str, Any] | None = None,
        contamination_by_broker: Mapping[str, Sequence[str]] | None = None,
    ) -> list[dict[str, Any]]:
        contamination_by_broker = contamination_by_broker or {}
        rows: list[dict[str, Any]] = []
        for name in self.list_brokers():
            snap = self.snapshot(
                name,
                selected_broker=selected_broker,
                active=active,
                contamination_findings=contamination_by_broker.get(name, ()),
            )
            rows.append(
                {
                    "broker": snap.broker,
                    "role": snap.role,
                    "broker_type": snap.broker_type,
                    "status": snap.operational_state,
                    "operational_state": snap.operational_state,
                    "mode": (
                        "live_read_only"
                        if snap.selected and snap.operational_state == OperationalState.LIVE_READ_ONLY.value
                        else ("selected" if snap.selected else "available")
                    ),
                    "readiness": snap.operational_readiness,
                    "certification": snap.certification_state,
                    "latency": snap.latency_ms if snap.latency_ms is not None else "UNAVAILABLE",
                    "authentication": snap.authentication_state,
                    "market_data": snap.market_data_health,
                    "account": snap.account_health,
                    "execution": snap.execution_capability,
                    "execution_authority": snap.execution_authority,
                    "last_sync": snap.last_sync or "UNAVAILABLE",
                    "credentials_present": snap.credential_health,
                    "connection_health": snap.connection_health,
                    "error_state": snap.error_state,
                    "readiness_score": snap.readiness_score,
                    "supported_runtime_modes": snap.supported_runtime_modes,
                    "supported_assets": snap.asset_classes,
                    "capabilities": list(snap.capabilities.keys()),
                    "capability_flags": snap.capabilities,
                    "responsibilities": snap.responsibilities,
                    "selected": snap.selected,
                    "priority": self.get(name).priority,
                    "live_read_only_allowed": snap.live_read_only_allowed,
                    "execution_blocked": True,
                    "advisory_only": True,
                    "contamination_isolated": snap.contamination_isolated,
                    "contamination_findings": snap.contamination_findings,
                    "schema_version": SCHEMA_VERSION,
                }
            )
        return rows

    def registry_summary(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "tier1_brokers": list(TIER1_BROKERS),
            "roadmap_excluded": sorted(ROADMAP_EXCLUDED_BROKERS),
            "primary_roles": self.primary_roles(),
            "brokers": [self.get(name).as_dict() for name in self.list_brokers()],
            "execution_policy": {
                "execution_enabled": False,
                "order_submission": "BLOCKED",
                "live_trading_enabled": False,
                "live_read_only_supported": True,
            },
            "generated_at": _utc_now(),
        }


_DEFAULT_REGISTRY: CanonicalBrokerRegistry | None = None


def get_canonical_broker_registry() -> CanonicalBrokerRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = CanonicalBrokerRegistry()
    return _DEFAULT_REGISTRY


def reset_canonical_broker_registry_for_tests() -> None:
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None


__all__ = [
    "BrokerCapabilities",
    "BrokerHealthSnapshot",
    "BrokerPluginSpec",
    "BrokerRole",
    "BrokerType",
    "CanonicalBrokerRegistry",
    "CertificationState",
    "DEFAULT_ROLE_BY_BROKER",
    "OperationalState",
    "ROADMAP_EXCLUDED_BROKERS",
    "SCHEMA_VERSION",
    "TIER1_BROKERS",
    "get_canonical_broker_registry",
    "reset_canonical_broker_registry_for_tests",
]
