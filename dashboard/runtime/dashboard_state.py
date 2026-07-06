from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List


DASHBOARD_PAYLOAD_VERSION = "1.0.0"
DASHBOARD_PAYLOAD_SCHEMA = "css.dashboard.frontend.v1"
DASHBOARD_PAYLOAD_SOURCE = "dashboard.runtime.DashboardState"


# =========================================================
# MARKET STATE PAYLOAD
# =========================================================

@dataclass
class MarketStatePayload:
    trend_state: str = "UNKNOWN"
    volatility_state: str = "UNKNOWN"
    liquidity_state: str = "UNKNOWN"
    mean_reversion_state: str = "UNKNOWN"
    probability_state: str = "UNKNOWN"
    velocity_state: str = "UNKNOWN"

    vwap_state: str = "UNKNOWN"
    vwap_distance: float = 0.0
    vwap_elasticity: float = 0.0

    momentum_state: str = "UNKNOWN"
    pressure_state: str = "UNKNOWN"
    acceleration_state: str = "UNKNOWN"

    regime_state: str = "UNKNOWN"
    spread_state: str = "UNKNOWN"
    execution_cost_state: str = "UNKNOWN"
    signal_confluence_state: str = "UNKNOWN"


# =========================================================
# ASSET CLASS SUMMARY
# =========================================================

@dataclass
class AssetClassSummary:
    asset_class: str

    open_positions: int = 0

    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    exposure: float = 0.0

    winners: int = 0
    losers: int = 0

    win_rate: float = 0.0

    market_state: MarketStatePayload = field(
        default_factory=MarketStatePayload
    )


# =========================================================
# BROKER STATE
# =========================================================

@dataclass
class BrokerState:
    selected_broker: str = "NONE"

    broker_mode: str = "paper"

    connected: bool = False

    live_trading_enabled: bool = False

    last_heartbeat: str = ""

    api_health: str = "UNKNOWN"

    reconnect_state: str = "NONE"

    supported_assets: List[str] = field(default_factory=list)

    account_readiness: str = "UNKNOWN"

    missing_credentials: bool = False

    latency_ms: float = 0.0

    readiness_status: str = "BROKER_BLOCKED"

    readiness_reasons: List[str] = field(default_factory=list)

    account_snapshot: Dict[str, Any] = field(default_factory=dict)

    position_snapshot: List[Dict[str, Any]] = field(default_factory=list)

    coinbase_live_validation: Dict[str, Any] = field(default_factory=dict)


# =========================================================
# GOVERNANCE STATE
# =========================================================

@dataclass
class GovernanceState:
    governance_enabled: bool = True

    session_locked: bool = False

    defensive_mode_active: bool = False

    unified_trade_gate_active: bool = True

    audit_enabled: bool = True

    last_governance_event: str = ""


# =========================================================
# DASHBOARD STATE CONTRACT
# =========================================================

@dataclass
class DashboardState:

    # -----------------------------------------------------
    # SESSION
    # -----------------------------------------------------

    session_id: str = ""

    user_id: str = ""

    role: str = "TRADER"

    cycle_number: int = 0

    # -----------------------------------------------------
    # ENGINE
    # -----------------------------------------------------

    engine_mode: str = "SAFE"

    live_or_paper: str = "paper"

    mtm_enabled: bool = True

    mtm_source: str = "runtime"

    mtm_frequency: str = "cycle"

    # -----------------------------------------------------
    # ACCOUNT
    # -----------------------------------------------------

    cash_balance: float = 0.0

    total_equity: float = 0.0

    realized_pnl: float = 0.0

    unrealized_pnl: float = 0.0

    # -----------------------------------------------------
    # POSITIONS
    # -----------------------------------------------------

    total_open_positions: int = 0

    open_positions_by_asset: Dict[str, int] = field(
        default_factory=dict
    )

    # -----------------------------------------------------
    # MARKET STATES
    # -----------------------------------------------------

    global_market_state: MarketStatePayload = field(
        default_factory=MarketStatePayload
    )

    # -----------------------------------------------------
    # ASSET SUMMARIES
    # -----------------------------------------------------

    asset_class_summaries: Dict[str, AssetClassSummary] = field(
        default_factory=dict
    )

    # -----------------------------------------------------
    # BROKER
    # -----------------------------------------------------

    broker_state: BrokerState = field(
        default_factory=BrokerState
    )

    # -----------------------------------------------------
    # GOVERNANCE
    # -----------------------------------------------------

    governance_state: GovernanceState = field(
        default_factory=GovernanceState
    )

    # -----------------------------------------------------
    # REPORTING
    # -----------------------------------------------------

    last_scan_results: Dict[str, Any] = field(
        default_factory=dict
    )

    dashboard_messages: List[str] = field(
        default_factory=list
    )

    # -----------------------------------------------------
    # TRADE WAREHOUSE
    # -----------------------------------------------------

    trade_warehouse_enabled: bool = True

    trade_warehouse_status: str = "READY"

    def resolved_mode(self) -> str:
        """
        Resolve dashboard execution mode with paper-first safety.

        Live mode is exposed only when both the session and broker state
        explicitly agree on live. Missing, unknown, simulated, or conflicting
        values resolve to paper.
        """

        session_mode = self._normalize_mode(self.live_or_paper)
        broker_mode = self._normalize_mode(self.broker_state.broker_mode)

        if session_mode == "live" and broker_mode == "live":
            return "live"

        return "paper"

    def to_dict(self) -> Dict[str, Any]:
        """
        Return a JSON-safe dashboard projection for UI/API boundaries.

        The projection is intentionally side-effect free and strips sensitive
        credential-shaped keys from nested payloads before returning.
        """

        account_summary = self._scan_summary("account_summary")
        pnl_summary = self._scan_summary("pnl_summary")
        risk_summary = self._scan_summary("risk_summary")
        execution_summary = self._scan_summary("execution_summary")
        position_state = self._scan_summary("position_state")
        execution_history = self._scan_list("execution_history")
        opportunities = self._scan_list("opportunities")

        if not pnl_summary:
            pnl_summary = {
                "realized_pnl": self.realized_pnl,
                "unrealized_pnl": self.unrealized_pnl,
                "net_pnl": self.realized_pnl + self.unrealized_pnl,
            }

        pnl_source = self.last_scan_results.get(
            "pnl_source",
            "dashboard.runtime.summary_builders.pnl_summary_builder.PnLSummaryBuilder",
        )

        generated_at = datetime.now(timezone.utc).isoformat()

        payload = {
            "payload_version": DASHBOARD_PAYLOAD_VERSION,
            "payload_schema": DASHBOARD_PAYLOAD_SCHEMA,
            "timestamp": generated_at,
            "generated_at": generated_at,
            "session_identifier": self.session_id,
            "source_metadata": {
                "source": DASHBOARD_PAYLOAD_SOURCE,
                "canonical_state": "DashboardState",
                "generator": "DashboardState.to_dict",
                "transport": "snapshot",
                "frontend_safe": True,
                "secrets_redacted": True,
            },
            "session": {
                "session_id": self.session_id,
                "user_id": self.user_id,
                "role": self.role,
                "cycle_number": self.cycle_number,
                "engine_mode": self.engine_mode,
                "live_or_paper": self.live_or_paper,
                "resolved_mode": self.resolved_mode(),
            },
            "session_id": self.session_id,
            "user_id": self.user_id,
            "role": self.role,
            "cycle_number": self.cycle_number,
            "engine_mode": self.engine_mode,
            "live_or_paper": self.live_or_paper,
            "broker_mode": self.broker_state.broker_mode,
            "resolved_mode": self.resolved_mode(),
            "broker_summary": self._json_safe(self.broker_state),
            "account_summary": account_summary,
            "pnl_summary": pnl_summary,
            "pnl_source": pnl_source,
            "risk_summary": risk_summary,
            "governance_summary": self._json_safe(self.governance_state),
            "market_summary": self._json_safe(self.global_market_state),
            "execution_summary": execution_summary,
            "position_state": position_state,
            "execution_history": execution_history,
            "opportunities": opportunities,
            "open_positions": {
                "total": self.total_open_positions,
                "by_asset": dict(self.open_positions_by_asset),
            },
            "asset_class_summaries": self._json_safe(
                self.asset_class_summaries
            ),
            "mtm": {
                "enabled": self.mtm_enabled,
                "source": self.mtm_source,
                "frequency": self.mtm_frequency,
            },
            "trade_warehouse": {
                "enabled": self.trade_warehouse_enabled,
                "status": self.trade_warehouse_status,
            },
            "dashboard_messages": list(self.dashboard_messages),
        }

        return payload

    @staticmethod
    def _normalize_mode(value: Any) -> str:
        mode = str(value or "").strip().lower()

        if mode == "live":
            return "live"

        return "paper"

    def _scan_summary(self, key: str) -> Dict[str, Any]:
        summary = self.last_scan_results.get(key, {})

        if isinstance(summary, dict):
            return self._json_safe(summary)

        return {}

    def _scan_list(self, key: str) -> List[Any]:
        items = self.last_scan_results.get(key, [])

        if isinstance(items, list):
            return self._json_safe(items)

        return []

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            return cls._json_safe(asdict(value))

        if isinstance(value, dict):
            return {
                str(key): (
                    "REDACTED"
                    if cls._is_sensitive_key(str(key))
                    else cls._json_safe(item)
                )
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [cls._json_safe(item) for item in value]

        if isinstance(value, Decimal):
            return format(value, "f")

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if isinstance(value, (str, int, float, bool)) or value is None:
            return value

        return str(value)

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        normalized = key.strip().lower()
        safe_metadata_keys = {
            "secrets_redacted",
            "credentials_redacted",
            "missing_credentials",
        }

        if normalized in safe_metadata_keys:
            return False

        sensitive_fragments = (
            "api_key",
            "access_key",
            "private_key",
            "secret",
            "token",
            "password",
            "passphrase",
            "credential",
            "pem",
            "authorization",
            "bearer",
            "oauth",
            "session_cookie",
        )

        return normalized == "key" or any(
            fragment in normalized for fragment in sensitive_fragments
        )


__all__ = [
    "AssetClassSummary",
    "BrokerState",
    "DASHBOARD_PAYLOAD_SCHEMA",
    "DASHBOARD_PAYLOAD_SOURCE",
    "DASHBOARD_PAYLOAD_VERSION",
    "DashboardState",
    "GovernanceState",
    "MarketStatePayload",
]
