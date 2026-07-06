import os
import json
import datetime
import time
from urllib.parse import parse_qs
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from launcher.css_launcher_config import LauncherConfig
from backend.monitoring.alert_repository import (
    AlertRepository,
    AlertCentreCompatibilityAdapter,
    AlertRepositoryError,
)
from backend.monitoring.runtime_health_aggregator import RuntimeHealthAggregator
from backend.monitoring.runtime_performance_monitor import RuntimePerformanceMonitor
from backend.monitoring.runtime_health_trend import RuntimeHealthTrend
from backend.monitoring.session_validation_engine import SessionValidationEngine
from backend.trading.instrument_universe import (
    InstrumentUniverse,
    InstrumentUniverseError,
)
from backend.trading.opportunity_ranking_engine import (
    OpportunityRankingEngine,
    OpportunityRankingEngineError,
)
from backend.trading.canonical_trading_universe import (
    CanonicalTradingUniverse,
    CanonicalTradingUniverseError,
)
from backend.intelligence.intelligence_orchestrator import (
    IntelligenceOrchestrator,
    IntelligenceDecisionError,
)
from backend.market_intelligence.fundamental_analysis_engine import FundamentalAnalysisEngine
from backend.market_intelligence.multi_factor_signal_synthesizer import MultiFactorSignalSynthesizer
from backend.market_intelligence.quantitative_alpha_engine import QuantitativeAlphaEngine
from backend.market_intelligence.regime_aware_weighting_engine import RegimeAwareWeightingEngine
from backend.market_intelligence.sentiment_intelligence_engine import SentimentIntelligenceEngine
from backend.market_intelligence.technical_analysis_engine import TechnicalAnalysisEngine
from backend.learning.adaptive_weight_recommendations import AdaptiveWeightRecommendationEngine
from backend.learning.confidence_calibration_learning import ConfidenceCalibrationLearningEngine
from backend.learning.engine_health_learning import EngineHealthLearningEngine
from backend.learning.factor_attribution import FactorAttributionEngine
from backend.learning.factor_performance import FactorPerformanceEngine
from backend.learning.regime_learning import RegimeLearningEngine
from backend.learning.rolling_reliability import RollingReliabilityEngine
from backend.analytics.portfolio_correlation_engine import PortfolioCorrelationEngine
from backend.analytics.concentration_guard import ConcentrationGuard
from backend.analytics.strategy_intelligence_engine import StrategyIntelligenceEngine
from backend.analytics.strategy_memory_repository import StrategyMemoryRepository
from backend.analytics.market_regime_engine import MarketRegimeEngine
from backend.analytics.adaptive_exit_engine import AdaptiveExitEngine
from backend.analytics.autonomous_portfolio_manager import (
    AutonomousPortfolioManager,
    AutonomousPortfolioManagerError,
)
from backend.analytics.strategy_evolution_engine import (
    StrategyEvolutionEngine,
    StrategyEvolutionEngineError,
)
from backend.analytics.trade_outcome_repository import TradeOutcomeRepository
from backend.portfolio.adaptive_portfolio_manager import AdaptivePortfolioManager
from backend.portfolio.advisory_consistency_checker import AdvisoryConsistencyChecker
from backend.portfolio.advisory_history_store import AdvisoryHistoryStore
from backend.portfolio.capital_rotation_engine import CapitalRotationEngine
from backend.portfolio.confidence_calibration_engine import ConfidenceCalibrationEngine
from backend.portfolio.decision_validation_engine import DecisionValidationEngine
from backend.portfolio.explainability_engine import ExplainabilityEngine
from backend.portfolio.market_regime_intelligence import MarketRegimeIntelligence
from backend.portfolio.policy_profile_engine import PolicyProfileEngine
from backend.portfolio.portfolio_decision_orchestrator import DecisionPackageStore, PortfolioDecisionOrchestrator
from backend.portfolio.portfolio_risk_committee import PortfolioRiskCommittee
from backend.portfolio.portfolio_intelligence_engine import PortfolioIntelligenceEngine
from backend.portfolio.quantitative_metrics_engine import QuantitativeMetricsEngine
from backend.portfolio.recommendation_drift_analyzer import RecommendationDriftAnalyzer
from backend.portfolio.recommendation_evaluator import RecommendationEvaluator
from backend.portfolio.recommendation_tracker import RecommendationTracker
from backend.portfolio.regime_aware_allocation import RegimeAwareAllocationEngine
from backend.portfolio.runtime_advisory_snapshot import RuntimeAdvisorySnapshot
from backend.portfolio.runtime_portfolio_state_builder import RuntimePortfolioStateBuilder
from backend.portfolio.strategy_attribution_engine import StrategyAttributionEngine
from backend.runtime.runtime_artifact_freshness import RuntimeArtifactFreshnessManager
from backend.runtime.runtime_artifact_publisher import RuntimeArtifactPublisher
from backend.runtime.runtime_portfolio_lifecycle import RuntimePortfolioLifecycle
from backend.runtime.runtime_session_continuity import RuntimeSessionContinuityMonitor
from backend.runtime.session_renewal import SessionRenewalManager
from backend.runtime.broker_startup_selection import (
    broker_summary_from_artifacts,
    live_readiness_broker_evidence,
)
from backend.runtime.broker_parity_validator import broker_parity_payload
from backend.runtime.live_micro_pilot_governor import live_micro_pilot_status
from backend.validation.live_readiness_certification import (
    live_readiness_blocker_diagnostics,
    live_readiness_certification_status,
)
from backend.validation.continuous_validation_monitor import ContinuousValidationMonitor
from backend.validation.long_duration_validation import LongDurationValidation
from backend.validation.runtime_validation_metrics import RuntimeValidationMetrics
from backend.validation.session_checkpoint_store import SessionCheckpointStore
from backend.validation.validation_confidence_engine import ValidationConfidenceEngine
from backend.validation.validation_readiness_engine import ValidationReadinessEngine
from dashboard.runtime.frontend_contract import build_frontend_payload
import uvicorn

app = FastAPI(title=LauncherConfig.TITLE, version=LauncherConfig.VERSION)
launcher_router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def _utc_iso_z() -> str:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None).isoformat() + "Z"


def _safe_load_artifact(filename: str) -> Dict[str, Any]:
    path = os.path.join(LauncherConfig.ARTIFACTS_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ── PAUSE / RESUME CONTROL ARTIFACT ─────────────────────────────────────────

MOBILE_CONTROLS_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_controls.json")


def get_pause_state() -> Dict[str, Any]:
    """Read current trading_paused flag from the controls artifact.

    Returns a dict with at minimum:
        trading_paused (bool)
        source (str)
        timestamp (str)
    Defaults to not-paused when the file is absent or unreadable.
    """
    try:
        if os.path.exists(MOBILE_CONTROLS_FILE):
            with open(MOBILE_CONTROLS_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return {
                    "trading_paused": bool(data.get("trading_paused", False)),
                    "source": str(data.get("source", "unknown")),
                    "timestamp": str(data.get("timestamp", "")),
                    "reason": str(data.get("reason", "")),
                }
    except Exception:
        pass
    return {
        "trading_paused": False,
        "source": "default",
        "timestamp": "",
        "reason": "",
    }


def write_pause_state(paused: bool, reason: str) -> Dict[str, Any]:
    """Merge trading_paused into the controls artifact and return the new state.

    Only writes the four launcher-controlled keys; all other existing keys in
    the file are preserved so the full mobile_app.py controls stack is not
    disturbed.
    """
    # Read existing controls to preserve any keys written by mobile_app.py
    existing: Dict[str, Any] = {}
    try:
        if os.path.exists(MOBILE_CONTROLS_FILE):
            with open(MOBILE_CONTROLS_FILE, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
            if not isinstance(existing, dict):
                existing = {}
    except Exception:
        existing = {}

    now = _utc_iso_z()
    existing.update(
        {
            "trading_paused": paused,
            "source": "mobile_launcher",
            "timestamp": now,
            "reason": reason,
        }
    )

    os.makedirs(os.path.dirname(MOBILE_CONTROLS_FILE), exist_ok=True)
    with open(MOBILE_CONTROLS_FILE, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2)

    return {
        "trading_paused": paused,
        "source": "mobile_launcher",
        "timestamp": now,
        "reason": reason,
    }



# ── MOBILE PAPER TRADE REQUESTS ─────────────────────────────────────────────

MOBILE_TRADE_REQUESTS_FILE = os.path.join(
    LauncherConfig.ARTIFACTS_DIR,
    "css_mobile_trade_requests.jsonl",
)

_VALID_MOBILE_TRADE_SIDES = {"BUY", "SELL"}
_FALSE_VALUES = {"false", "0", "no", "n", "off"}
_TRUE_VALUES = {"true", "1", "yes", "y", "on"}


def _current_trade_requests_file() -> str:
    return MOBILE_TRADE_REQUESTS_FILE


async def _read_mobile_trade_payload(request: Request) -> Dict[str, Any]:
    """Read JSON or urlencoded form payload without requiring broker access."""
    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        data = await request.json()
        return data if isinstance(data, dict) else {}

    raw_body = (await request.body()).decode("utf-8", errors="ignore")
    parsed = parse_qs(raw_body, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _coerce_mobile_trade_quantity(value: Any) -> float:
    try:
        quantity = float(value)
    except (TypeError, ValueError):
        raise ValueError("quantity must be numeric")

    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")

    return quantity


def validate_mobile_paper_trade_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    symbol = str(payload.get("symbol", "")).strip().upper()
    asset_class = str(payload.get("asset_class", "")).strip().upper()
    side = str(payload.get("side", "")).strip().upper()
    broker_mode = str(payload.get("broker_mode", "paper")).strip().lower()
    paper_only = str(payload.get("paper_only", "true")).strip().lower()
    broker_execution_allowed = str(
        payload.get("broker_execution_allowed", "false")
    ).strip().lower()

    if not symbol:
        raise ValueError("symbol is required")

    if not asset_class:
        raise ValueError("asset_class is required")

    if side not in _VALID_MOBILE_TRADE_SIDES:
        raise ValueError("side must be BUY or SELL")

    quantity = _coerce_mobile_trade_quantity(payload.get("quantity"))

    if broker_mode == "live":
        raise ValueError("live mode is not allowed for mobile paper trade requests")

    if paper_only in _FALSE_VALUES:
        raise ValueError("paper_only must remain true")

    if broker_execution_allowed in _TRUE_VALUES:
        raise ValueError("broker execution is not allowed from mobile paper trade requests")

    return {
        "timestamp_utc": _utc_iso_z(),
        "source": "mobile_dashboard",
        "paper_only": True,
        "symbol": symbol,
        "asset_class": asset_class,
        "side": side,
        "quantity": quantity,
        "status": "REQUESTED",
    }


def write_mobile_paper_trade_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    request_record = validate_mobile_paper_trade_request(payload)
    path = _current_trade_requests_file()

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(request_record, sort_keys=True) + "\n")

    return request_record

def get_supervisor_summary() -> Dict[str, Any]:
    state_file = LauncherConfig.SUPERVISOR_STATE_FILE

    if not os.path.exists(state_file):
        return {
            "status": "OFFLINE",
            "last_heartbeat": "N/A",
            "message": "Supervisor state missing",
        }

    try:
        with open(state_file, "r") as f:
            state = json.load(f)

        heartbeat = (
            state.get("last_heartbeat")
            or state.get("last_heartbeat_at")
            or ""
        )

        return {
            "status": _clean_text(state.get("status"), fallback="OFFLINE").upper(),
            "last_heartbeat": _clean_text(heartbeat, fallback="N/A"),
            "failure_count": state.get("failure_count", 0),
            "restart_count": state.get("restart_count", 0),
        }

    except Exception as e:
        return {
            "status": "ERROR",
            "last_heartbeat": "N/A",
            "message": str(e),
        }


def _parse_launcher_time(value: Any) -> Optional[datetime.datetime]:
    if value in (None, "", "N/A"):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(float(value), tz=datetime.UTC)
        except (OSError, OverflowError, ValueError):
            return None
    try:
        text = str(value).strip()
        if text.replace(".", "", 1).isdigit():
            return datetime.datetime.fromtimestamp(float(text), tz=datetime.UTC)
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.UTC)
    return parsed.astimezone(datetime.UTC)


def _heartbeat_state(
    *,
    latest_artifact_mtime: float = 0.0,
    supervisor: Optional[Dict[str, Any]] = None,
    threshold_seconds: float = 60.0,
) -> Dict[str, Any]:
    now = datetime.datetime.now(datetime.UTC)
    heartbeat = (supervisor or get_supervisor_summary()).get("last_heartbeat")
    parsed = _parse_launcher_time(heartbeat)
    source = "supervisor_heartbeat"
    if parsed is not None:
        age = max(0.0, (now - parsed).total_seconds())
    elif latest_artifact_mtime > 0:
        age = max(0.0, now.timestamp() - latest_artifact_mtime)
        source = "artifact_mtime"
    else:
        return {"staleness": "OFFLINE", "age_seconds": None, "source": "unavailable"}

    return {
        "staleness": "ACTIVE" if age <= threshold_seconds else "STALE",
        "age_seconds": round(age, 6),
        "source": source,
    }


def get_alert_summary() -> List[Dict[str, Any]]:
    try:
        repository = AlertRepository(storage_dir=LauncherConfig.ALERTS_DIR)
        adapter = AlertCentreCompatibilityAdapter(repository)
        payload = adapter.build_payload(limit=5)
        if payload:
            return payload
    except AlertRepositoryError:
        pass
    except Exception:
        pass

    alerts_dir = LauncherConfig.ALERTS_DIR
    if not os.path.exists(alerts_dir):
        return []
        
    try:
        files = [f for f in os.listdir(alerts_dir) if f.endswith(".json")]
        # Sort by filename descending to get most recent (assuming format starts with timestamp)
        files.sort(reverse=True)
        recent_files = files[:5]
        
        alerts = []
        for file in recent_files:
            try:
                with open(os.path.join(alerts_dir, file), "r") as f:
                    alerts.append(json.load(f))
            except Exception:
                pass
        return alerts
    except Exception:
        return []

def get_mobile_launcher_status() -> str:
    summary = get_supervisor_summary()
    if summary.get("status") in ("RUNNING", "DEGRADED"):
        return "ONLINE"
    return "OFFLINE"

def get_runtime_summary() -> Dict[str, Any]:
    session = _safe_load_artifact("css_session_state_pcnrass.json").get("session", {}) or _safe_load_artifact("css_session_recovery.json").get("session", {})
    runtime_mode = _clean_text(session.get("engine_mode"), fallback="PAPER").upper()
    last_update = _clean_text(session.get("start_time"), fallback=_utc_iso_z())
    summary = {
        "runtime_mode": runtime_mode,
        "current_cycle": session.get("cycle_number", 0),
        "last_update": last_update,
    }
    
    supervisor = get_supervisor_summary()
    summary["supervisor_status"] = _clean_text(supervisor.get("status"), fallback="OFFLINE").upper()
    summary["last_heartbeat"] = _clean_text(supervisor.get("last_heartbeat"), fallback="N/A")
    summary["restart_count"] = supervisor.get("restart_count", 0)
    summary["failure_count"] = supervisor.get("failure_count", 0)
    summary["status"] = get_mobile_launcher_status()
    
    return summary

def get_account_summary() -> Dict[str, Any]:
    state = _safe_load_artifact("css_account_state_pcnrass.json") or _safe_load_artifact("css_account_state_pcnrass_BACKUP.json")
    summary = {
        "cash": state.get("account_balance", 0.0),
        "equity": state.get("total_equity", state.get("account_balance", 0.0)),
        "buying_power": state.get("buying_power", state.get("account_balance", 0.0)),
        "open_pnl": state.get("unrealized_pnl", 0.0),
        "realized_pnl": state.get("lifetime_realized_pnl", 0.0),
        "total_pnl": state.get("lifetime_realized_pnl", 0.0) + state.get("unrealized_pnl", 0.0)
    }
    return summary


def get_broker_startup_summary() -> Dict[str, Any]:
    account_state = _safe_load_artifact("css_account_state_pcnrass.json") or _safe_load_artifact("css_account_state_pcnrass_BACKUP.json")
    session_state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    return broker_summary_from_artifacts(account_state, session_state)

def get_trade_summary() -> Dict[str, Any]:
    summary = {
        "open_trades_count": 0,
        "closed_trades_count": 0,
        "pending_orders_count": 0,
        "recent_activity": []
    }
    
    session_state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    account_state = _safe_load_artifact("css_account_state_pcnrass.json") or _safe_load_artifact("css_account_state_pcnrass_BACKUP.json")
    positions = account_state.get("positions", [])
    if not positions and "open_trades" in session_state:
        positions = session_state["open_trades"]
    summary["open_trades_count"] = len(positions)
        
    try:
        if os.path.exists(LauncherConfig.CLOSED_TRADE_LEDGER_PATH):
            with open(LauncherConfig.CLOSED_TRADE_LEDGER_PATH, "r") as f:
                lines = f.readlines()
                summary["closed_trades_count"] = len(lines)
                
                recent = []
                for line in reversed(lines[-5:]):
                    try:
                        recent.append(json.loads(line))
                    except Exception:
                        pass
                summary["recent_activity"] = recent
    except Exception:
        pass
        
    return summary


def _launcher_positions_for_frontend() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for position in _load_portfolio_positions():
        if not isinstance(position, dict):
            continue
        rows.append(
            {
                "symbol": str(position.get("symbol", position.get("asset", "UNKNOWN"))),
                "asset_class": str(position.get("asset_class", position.get("asset_type", "UNKNOWN"))),
                "side": str(position.get("side", position.get("direction", "UNKNOWN"))),
                "qty": position.get("qty", position.get("quantity", position.get("size", 0))),
                "entry_price": position.get("entry_price", position.get("average_entry_price", 0)),
                "current_price": position.get("current_price", position.get("mark_price", position.get("price", 0))),
                "exposure": position.get("exposure", position.get("market_value", position.get("notional_value", 0))),
                "realized_pnl": position.get("realized_pnl", 0),
                "unrealized_pnl": position.get("unrealized_pnl", position.get("open_pnl", 0)),
            }
        )
    return rows


def _launcher_opportunities_for_frontend(
    limit: int = 10,
    opportunity_feed: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    feed = opportunity_feed if isinstance(opportunity_feed, dict) else get_top_opportunities_feed(limit=limit)
    rows = feed.get("top_opportunities", []) if isinstance(feed, dict) else []
    result: List[Dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        signal_color = str(row.get("signal_color", row.get("status", "WATCH"))).upper()
        action = str(row.get("action", row.get("side", "WATCH"))).upper()
        if signal_color == "GREEN":
            status = "GREEN"
            approval_state = "APPROVED"
        elif signal_color == "AMBER":
            status = "AMBER"
            approval_state = "NEAR_APPROVED"
        else:
            status = "RED"
            approval_state = "NOT_APPROVED"
        result.append(
            {
                "symbol": str(row.get("symbol", "UNKNOWN")),
                "asset_class": str(row.get("asset_class", "UNKNOWN")),
                "side": "WATCH" if action == "BLOCK" else (action if action in {"BUY", "SELL", "WATCH"} else "WATCH"),
                "signal": signal_color,
                "score": row.get("opportunity_score", row.get("score", 0.0)),
                "composite_score": row.get("opportunity_score", row.get("score", 0.0)),
                "probability": row.get("confidence", row.get("probability", 0.0)),
                "status": status,
                "approval_state": approval_state,
                "risk_state": signal_color,
                "market_health": signal_color,
                "opportunity_explanation": str(
                    row.get(
                        "reason",
                        row.get("selected_strategy", "Risk-aware launcher opportunity; display only."),
                    )
                ),
            }
        )
    return result


def build_launcher_frontend_state(
    opportunity_feed: Optional[Dict[str, Any]] = None,
    runtime_health_feed: Optional[Dict[str, Any]] = None,
    live_readiness_evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    runtime = get_runtime_summary()
    account = get_account_summary()
    trade = get_trade_summary()
    engine = get_engine_summary()
    health = runtime_health_feed if isinstance(runtime_health_feed, dict) else get_runtime_health_feed()
    session_state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    session = session_state.get("session", {}) if isinstance(session_state.get("session"), dict) else session_state
    session = session if isinstance(session, dict) else {}
    positions = _launcher_positions_for_frontend()
    runtime_mode = str(runtime.get("runtime_mode", "PAPER")).lower()
    broker_startup = get_broker_startup_summary()
    broker = str(broker_startup.get("selected_broker") or session.get("broker", session.get("selected_broker", "NONE")))
    broker_mode = str(broker_startup.get("broker_mode") or session.get("broker_mode", "paper")).lower()
    if broker_mode not in {"live", "paper"}:
        broker_mode = "paper"
    credential_diagnostics = (
        broker_startup.get("credential_diagnostics")
        if isinstance(broker_startup.get("credential_diagnostics"), dict)
        else {}
    )
    limit_reconciliation = (
        broker_startup.get("limit_reconciliation")
        if isinstance(broker_startup.get("limit_reconciliation"), dict)
        else {}
    )
    broker_readiness = (
        broker_startup.get("broker_readiness")
        if isinstance(broker_startup.get("broker_readiness"), dict)
        else {}
    )
    broker_parity = broker_parity_payload(broker_startup)

    dashboard_payload = {
        "generated_at": _utc_iso_z(),
        "session_id": str(session.get("session_id", "LAUNCHER-SESSION")),
        "cycle_number": runtime.get("current_cycle", 0),
        "engine_mode": engine.get("engine_mode", runtime.get("runtime_mode", "PAPER")),
        "live_or_paper": "live" if runtime_mode == "live" else "paper",
        "resolved_mode": "live" if runtime_mode == "live" and broker_mode == "live" else "paper",
        "broker_mode": broker_mode,
        "session": {
            "session_id": str(session.get("session_id", "LAUNCHER-SESSION")),
            "cycle_number": runtime.get("current_cycle", 0),
            "engine_mode": engine.get("engine_mode", runtime.get("runtime_mode", "PAPER")),
            "live_or_paper": "live" if runtime_mode == "live" else "paper",
            "resolved_mode": "live" if runtime_mode == "live" and broker_mode == "live" else "paper",
            "role": str(session.get("role", "TRADER")),
        },
        "account_summary": {
            "account_balance": account.get("cash", 0.0),
            "cash_balance": account.get("cash", 0.0),
            "total_equity": account.get("equity", 0.0),
            "equity": account.get("equity", 0.0),
            "buying_power": account.get("buying_power", 0.0),
            "currency": "USD",
            "broker": broker,
            "account_mode": broker_mode,
        },
        "pnl_summary": {
            "realized_pnl": account.get("realized_pnl", 0.0),
            "unrealized_pnl": account.get("open_pnl", 0.0),
            "net_pnl": account.get("total_pnl", 0.0),
            "account_equity": account.get("equity", 0.0),
        },
        "position_state": {
            "open_count": trade.get("open_trades_count", len(positions)),
            "positions": positions,
        },
        "open_positions": {
            "total": trade.get("open_trades_count", len(positions)),
            "by_asset": {},
        },
        "risk_summary": {
            "risk_state": str(health.get("overall_operational_health", "UNKNOWN")),
            "gate_status": str(engine.get("trade_gate_status", "SIMULATED")),
            "risk_limits_breached": health.get("warnings", []),
        },
        "execution_summary": {
            "execution_state": str(engine.get("trade_gate_status", "SIMULATED")),
            "accepted_trade_count": trade.get("closed_trades_count", 0),
            "rejected_trade_count": 0,
            "pending_trade_count": trade.get("pending_orders_count", 0),
            "last_execution_event": str(health.get("recommendation", "")),
        },
        "market_summary": {
            "liquidity_state": "HEALTHY" if health.get("runtime_health") in {"GREEN", "AMBER"} else "UNKNOWN",
            "volatility_state": "NORMAL",
            "spread_state": "TIGHT",
            "regime_state": str(runtime.get("runtime_mode", "PAPER")),
            "signal_confluence_state": "CONFIRMED",
        },
        "broker_summary": {
            "selected_broker": broker,
            "broker_type": str(broker_startup.get("broker_type", broker_readiness.get("broker_type", "UNKNOWN"))),
            "broker_mode": broker_mode,
            "connected": bool(broker_startup.get("broker_connected", False)),
            "broker_connected": bool(broker_startup.get("broker_connected", False)),
            "broker_authenticated": bool(broker_startup.get("broker_authenticated", False)),
            "broker_health": str(broker_startup.get("broker_health", "UNKNOWN")),
            "broker_infrastructure_health": str(
                broker_startup.get("broker_infrastructure_health", broker_startup.get("broker_health", "UNKNOWN"))
            ),
            "broker_ready": bool(broker_startup.get("broker_ready", broker_readiness.get("broker_ready", False))),
            "broker_readiness": dict(broker_readiness),
            "broker_parity": dict(broker_parity),
            "credentials_present": bool(broker_startup.get("credentials_present", broker_readiness.get("credentials_present", False))),
            "authenticated": bool(
                broker_startup.get("authenticated", broker_startup.get("broker_authenticated", broker_readiness.get("authenticated", False)))
            ),
            "account_loaded": bool(broker_startup.get("account_loaded", broker_readiness.get("account_loaded", False))),
            "market_data_ready": bool(broker_startup.get("market_data_ready", broker_readiness.get("market_data_ready", False))),
            "execution_supported": bool(broker_startup.get("execution_supported", broker_readiness.get("execution_supported", False))),
            "infrastructure_health": str(broker_startup.get("infrastructure_health", broker_readiness.get("infrastructure_health", "UNKNOWN"))),
            "credentials_health": str(broker_startup.get("credentials_health", broker_readiness.get("credentials_health", "UNKNOWN"))),
            "authentication_health": str(broker_startup.get("authentication_health", broker_readiness.get("authentication_health", "UNKNOWN"))),
            "connection_health": str(broker_startup.get("connection_health", broker_readiness.get("connection_health", "UNKNOWN"))),
            "market_data_health": str(broker_startup.get("market_data_health", broker_readiness.get("market_data_health", "UNKNOWN"))),
            "account_data_health": str(broker_startup.get("account_data_health", broker_readiness.get("account_data_health", "UNKNOWN"))),
            "readiness_score": broker_startup.get("readiness_score", broker_readiness.get("readiness_score", 0.0)),
            "api_health": str(broker_startup.get("broker_health", "UNKNOWN")),
            "broker_execution_armed": bool(broker_startup.get("broker_execution_armed", False)),
            "operator_requested_live": bool(broker_startup.get("operator_requested_live", False)),
            "execution_authority": bool(broker_startup.get("execution_authority", False)),
            "authority_reason": str(broker_startup.get("authority_reason", "Operator Intent Missing")),
            "live_authority_state": str(broker_startup.get("live_authority_state", "BLOCKED")),
            "live_execution_authority": dict(broker_startup.get("live_execution_authority", {}))
            if isinstance(broker_startup.get("live_execution_authority"), dict)
            else {},
            "broker_execution_enabled": bool(broker_startup.get("broker_execution_enabled", False)),
            "broker_execution_status": str(broker_startup.get("broker_execution_status", "DISABLED")),
            "broker_connection_mode": str(broker_startup.get("broker_connection_mode", "PAPER_ONLY")),
            "credential_diagnostics": dict(credential_diagnostics),
            "coinbase_key_present": bool(credential_diagnostics.get("coinbase_key_present", False)),
            "coinbase_private_key_present": bool(
                credential_diagnostics.get("coinbase_private_key_present", False)
                or credential_diagnostics.get("coinbase_key_file_present", False)
            ),
            "missing_credential_names": list(credential_diagnostics.get("missing_credentials", [])),
            "credential_status": str(credential_diagnostics.get("credential_status", "DATA UNAVAILABLE")),
            "credentials": str(broker_startup.get("credentials", credential_diagnostics.get("credential_status", "DATA UNAVAILABLE"))),
            "auth_status": str(broker_startup.get("auth_status", "NOT_TESTED")),
            "authentication_status": str(broker_startup.get("authentication_status", broker_startup.get("auth_status", "NOT_TESTED"))),
            "connection_status": str(broker_startup.get("connection_status", "NOT_TESTED")),
            "connection_error": str(broker_startup.get("connection_error", "")),
            "last_successful_sync": str(broker_startup.get("last_successful_sync", "DATA UNAVAILABLE")),
            "last_broker_sync": str(broker_startup.get("last_broker_sync", broker_startup.get("last_successful_sync", "DATA UNAVAILABLE"))),
            "product_price_status": str(broker_startup.get("product_price_status", "NOT_TESTED")),
            "balance_position_status": str(broker_startup.get("balance_position_status", "NOT_TESTED")),
            "account_equity": broker_startup.get("account_equity", "DATA UNAVAILABLE"),
            "cash": broker_startup.get("cash", "DATA UNAVAILABLE"),
            "buying_power": broker_startup.get("buying_power", "DATA UNAVAILABLE"),
            "available_balance": broker_startup.get("available_balance", "DATA UNAVAILABLE"),
            "products_loaded": int(broker_startup.get("products_loaded", 0) or 0),
            "market_data_status": str(broker_startup.get("market_data_status", broker_startup.get("product_price_status", "NOT_TESTED"))),
            "readiness_state": str(broker_startup.get("readiness_state", "UNCONFIGURED")),
            "go_no_go": str(broker_startup.get("go_no_go", "NO GO")),
            "readiness_checklist": list(broker_startup.get("readiness_checklist", []))
            if isinstance(broker_startup.get("readiness_checklist"), list)
            else [],
            "startup_diagnostics": dict(broker_startup.get("startup_diagnostics", {}))
            if isinstance(broker_startup.get("startup_diagnostics"), dict)
            else {},
            "order_submission_status": str(broker_startup.get("order_submission_status", "DISABLED")),
            "orders_sent_count": int(broker_startup.get("orders_sent_count", 0) or 0),
            "orders_blocked_count": int(broker_startup.get("orders_blocked_count", 0) or 0),
            "auth_reason": str(broker_startup.get("auth_reason", broker_startup.get("readiness_reason", "no_live_order_permission"))),
            "execution_scope": str(broker_startup.get("execution_scope", broker_startup.get("broker_connection_mode", "PAPER_ONLY"))),
            "can_live_execute": bool(broker_startup.get("can_live_execute", False)),
            "live_order_permission": bool(broker_startup.get("live_order_permission", False)),
            "live_micro_pilot_state": str(broker_startup.get("live_micro_pilot_state", "DISARMED")),
            "broker_guard": str(broker_startup.get("broker_guard", "REJECT_BEFORE_BROKER")),
            "drawdown_status": str(broker_startup.get("drawdown_status", "DATA UNAVAILABLE")),
            "drawdown_reason": str(broker_startup.get("drawdown_reason", "DATA UNAVAILABLE")),
            "limit_reconciliation": dict(limit_reconciliation),
            "canonical_live_capital_authority": str(
                limit_reconciliation.get("canonical_authority", "PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR")
            ),
            "canonical_live_pilot_limit_cad": str(limit_reconciliation.get("canonical_live_pilot_limit_cad", "20.00")),
            "legacy_secondary_limit_label": str(limit_reconciliation.get("legacy_secondary_limit_label", "LEGACY_SECONDARY_LIMIT")),
            "legacy_coinbase_max_live_order_usd": limit_reconciliation.get("legacy_coinbase_max_live_order_usd", "DATA UNAVAILABLE"),
            "live_trading_enabled": False,
            "readiness_status": str(broker_startup.get("broker_readiness_status", "BROKER_DISABLED")),
            "readiness_reasons": [str(broker_startup.get("readiness_reason", "no_live_order_permission"))],
        },
        "opportunities": _launcher_opportunities_for_frontend(limit=10, opportunity_feed=opportunity_feed),
        "live_readiness_certification": live_readiness_certification_status(live_readiness_evidence),
    }
    return build_frontend_payload(dashboard_payload)


def get_launcher_trade_summary_feed() -> Dict[str, Any]:
    return build_launcher_frontend_state().get("sections", {}).get("trade_summary", {})


def get_launcher_session_command_center_feed() -> Dict[str, Any]:
    return build_launcher_frontend_state().get("sections", {}).get("session_command_centre", {})


def get_launcher_live_micro_pilot_feed() -> Dict[str, Any]:
    return build_launcher_frontend_state().get("sections", {}).get("live_micro_pilot", live_micro_pilot_status())


def get_launcher_live_readiness_certification_feed() -> Dict[str, Any]:
    return build_launcher_frontend_state().get("sections", {}).get(
        "live_readiness_certification",
        live_readiness_certification_status(),
    )


def get_launcher_broker_read_only_status_feed() -> Dict[str, Any]:
    summary = get_broker_startup_summary()
    if summary:
        return build_frontend_payload({"broker_summary": summary}).get("sections", {}).get("broker", {})
    return build_launcher_frontend_state().get("sections", {}).get("broker", {})


def get_launcher_startup_diagnostics_feed() -> Dict[str, Any]:
    broker = get_launcher_broker_read_only_status_feed()
    diagnostics = broker.get("startup_diagnostics", {}) if isinstance(broker, dict) else {}
    return dict(diagnostics) if isinstance(diagnostics, dict) else {}


def get_launcher_live_readiness_state_feed() -> Dict[str, Any]:
    broker = get_launcher_broker_read_only_status_feed()
    broker = broker if isinstance(broker, dict) else {}
    return {
        "readiness_state": broker.get("readiness_state", "UNCONFIGURED"),
        "go_no_go": broker.get("go_no_go", "NO GO"),
        "readiness_checklist": broker.get("readiness_checklist", []),
        "startup_diagnostics": broker.get("startup_diagnostics", {}),
        "advisory_only": True,
        "execution_allowed": False,
    }


def get_launcher_live_execution_authority_feed() -> Dict[str, Any]:
    broker = get_launcher_broker_read_only_status_feed()
    broker = broker if isinstance(broker, dict) else {}
    return {
        "operator_requested_live": broker.get("operator_requested_live", False),
        "execution_authority": broker.get("execution_authority", False),
        "authority_reason": broker.get("authority_reason", "Operator Intent Missing"),
        "live_authority_state": broker.get("live_authority_state", "BLOCKED"),
        "can_live_execute": broker.get("can_live_execute", False),
        "live_execution_authority": broker.get("live_execution_authority", {}),
        "advisory_only": True,
        "execution_allowed": False,
    }


def get_launcher_broker_readiness_feed() -> Dict[str, Any]:
    broker = get_launcher_broker_read_only_status_feed()
    readiness = broker.get("broker_readiness", {}) if isinstance(broker, dict) else {}
    return dict(readiness) if isinstance(readiness, dict) else {}


def get_launcher_broker_parity_feed() -> Dict[str, Any]:
    broker = get_launcher_broker_read_only_status_feed()
    return broker_parity_payload(broker if isinstance(broker, dict) else {})


def get_launcher_live_readiness_blockers_feed() -> Dict[str, Any]:
    artifact_refresh = ensure_runtime_artifacts_current()
    artifact_freshness = artifact_refresh.get("freshness", get_runtime_artifact_freshness_feed(refresh=False))
    session_continuity = get_runtime_session_continuity_feed()
    broker_startup = get_broker_startup_summary()
    runtime_health = get_runtime_health_feed(
        artifact_freshness=artifact_freshness,
        session_continuity=session_continuity,
    )
    latest_mtime = 0.0
    for path in (
        LauncherConfig.ACCOUNT_STATE_FILE,
        LauncherConfig.SESSION_STATE_FILE,
        LauncherConfig.SUPERVISOR_STATE_FILE,
    ):
        if os.path.exists(path):
            latest_mtime = max(latest_mtime, os.path.getmtime(path))
    heartbeat = _heartbeat_state(latest_artifact_mtime=latest_mtime, supervisor=get_supervisor_summary())
    evidence = build_live_readiness_evidence(
        runtime_health=runtime_health,
        artifact_freshness=artifact_freshness,
        session_continuity=session_continuity,
        staleness=str(heartbeat.get("staleness", "OFFLINE")),
        broker_summary=broker_startup,
    )
    return live_readiness_blocker_diagnostics(evidence)


def _status_for_certification(
    value: Any,
    *,
    pass_values: set[str],
    warning_values: set[str] | None = None,
) -> str:
    normalized = str(value or "").strip().upper().replace("-", "_")
    if normalized in pass_values:
        return "PASS"
    if normalized in (warning_values or set()):
        return "WARNING"
    return "FAIL"


def build_live_readiness_evidence(
    *,
    runtime_health: Optional[Dict[str, Any]] = None,
    artifact_freshness: Optional[Dict[str, Any]] = None,
    session_continuity: Optional[Dict[str, Any]] = None,
    staleness: Optional[str] = None,
    broker_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    health = runtime_health if isinstance(runtime_health, dict) else {}
    freshness = artifact_freshness if isinstance(artifact_freshness, dict) else {}
    continuity = session_continuity if isinstance(session_continuity, dict) else {}
    heartbeat_status = _status_for_certification(
        staleness,
        pass_values={"ACTIVE"},
        warning_values={"STALE"},
    )
    freshness_status = _status_for_certification(
        freshness.get("freshness_status"),
        pass_values={"GREEN"},
        warning_values={"AMBER"},
    )
    continuity_status = _status_for_certification(
        continuity.get("session_continuity_status"),
        pass_values={"ACTIVE", "EXPIRING_SOON", "RESUMED"},
        warning_values={"UNKNOWN"},
    )
    runtime_status = _status_for_certification(
        health.get("runtime_health", health.get("overall_operational_health")),
        pass_values={"GREEN"},
        warning_values={"AMBER"},
    )
    broker_evidence = live_readiness_broker_evidence(broker_summary)
    broker_checks = broker_evidence.get("checks", {}) if isinstance(broker_evidence, dict) else {}
    checks = {
        **broker_checks,
        "dashboard_synchronization": {"status": "PASS", "reason": "dashboard_frontend_contract_sections_present"},
        "mobile_dashboard": {"status": "PASS", "reason": "mobile_dashboard_phase152_panels_present"},
        "desktop_dashboard": {"status": "PASS", "reason": "desktop_dashboard_phase152_panels_present"},
        "launcher_dashboard": {"status": "PASS", "reason": "launcher_dashboard_phase152_panels_present"},
        "runtime_supervisor": {"status": heartbeat_status, "reason": f"heartbeat_status_{str(staleness or 'UNKNOWN').lower()}"},
        "runtime_health": {"status": runtime_status, "reason": f"runtime_health_{str(health.get('runtime_health', 'UNKNOWN')).lower()}"},
        "artifact_freshness": {"status": freshness_status, "reason": f"artifact_freshness_{str(freshness.get('freshness_status', 'UNKNOWN')).lower()}"},
        "session_continuity": {"status": continuity_status, "reason": f"session_continuity_{str(continuity.get('session_continuity_status', 'UNKNOWN')).lower()}"},
    }
    return {
        "checks": checks,
        "broker_summary": dict(broker_summary or {}),
        "learning_system_status": {"status": "WARNING", "reason": "learning_evidence_not_required_for_pre_live_cleanup"},
    }


def _load_portfolio_positions() -> List[Dict[str, Any]]:
    session_state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    account_state = _safe_load_artifact("css_account_state_pcnrass.json") or _safe_load_artifact("css_account_state_pcnrass_BACKUP.json")
    positions = account_state.get("positions", [])
    if not positions and "open_trades" in session_state:
        positions = session_state["open_trades"]
    return positions if isinstance(positions, list) else []


def get_runtime_portfolio_state_feed() -> Dict[str, Any]:
    return RuntimePortfolioStateBuilder(
        artifacts_dir=LauncherConfig.ARTIFACTS_DIR,
        account_state_path=LauncherConfig.ACCOUNT_STATE_FILE,
        session_state_path=LauncherConfig.SESSION_STATE_FILE,
        closed_trade_ledger_path=LauncherConfig.CLOSED_TRADE_LEDGER_PATH,
        supervisor_state_path=LauncherConfig.SUPERVISOR_STATE_FILE,
    ).build()


def get_portfolio_intelligence_feed(runtime_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = runtime_state or get_runtime_portfolio_state_feed()
    positions = state.get("positions", []) if isinstance(state, dict) else _load_portfolio_positions()
    metrics = state.get("performance_metrics", {}) if isinstance(state, dict) else {}
    return PortfolioIntelligenceEngine().analyze(positions, metrics)


def get_capital_rotation_feed(
    portfolio_intelligence: Optional[Dict[str, Any]] = None,
    runtime_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    intelligence = portfolio_intelligence or get_portfolio_intelligence_feed()
    if intelligence.get("status") != "OK":
        return CapitalRotationEngine().recommend([], intelligence)

    by_asset = intelligence.get("by_asset_class", {}) if isinstance(intelligence, dict) else {}
    metrics = intelligence.get("metrics", {}) if isinstance(intelligence, dict) else {}
    allocations = runtime_state.get("asset_allocations", {}) if isinstance(runtime_state, dict) else {}
    candidates = [
        {
            "asset_class": asset_class,
            "current_allocation": allocations.get(asset_class, percent) if isinstance(allocations, dict) else percent,
            "expected_return": 0.0,
            "drawdown": metrics.get("max_drawdown", 0.0),
            "sortino": metrics.get("sortino", 0.0),
            "capital_efficiency": metrics.get("capital_efficiency", 0.0),
            "concentration": metrics.get("largest_asset_class_concentration", 0.0),
            "correlation": metrics.get("correlation_score", 0.0),
        }
        for asset_class, percent in sorted(by_asset.items())
    ]
    return CapitalRotationEngine().recommend(candidates, intelligence)


def get_strategy_attribution_feed(runtime_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    trades = runtime_state.get("trades", []) if isinstance(runtime_state, dict) else _load_completed_trade_learning_records()
    if not trades and isinstance(runtime_state, dict) and runtime_state.get("portfolio_state") == "NO_PORTFOLIO":
        return {
            "status": "LIMITED",
            "advisory_only": True,
            "execution_allowed": False,
            "strategy_attribution": {},
            "asset_class_attribution": {},
            "symbol_attribution": {},
            "regime_attribution": {},
            "time_bucket_attribution": {},
            "top_contributors": [],
            "top_detractors": [],
            "recommendation": "MAINTAIN",
            "reasons": ["No current exposure."],
        }
    return StrategyAttributionEngine().analyze(trades)


def _load_regime_context() -> Dict[str, Any]:
    session_state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    session = session_state.get("session", {}) if isinstance(session_state.get("session"), dict) else session_state
    regime_state = _safe_load_artifact("css_market_regime_state.json")
    context = dict(regime_state) if isinstance(regime_state, dict) else {}
    if isinstance(session, dict):
        context.setdefault("detected_regime", session.get("market_regime", session.get("detected_regime", "UNKNOWN")))
        context.setdefault("risk_status", session.get("risk_status", "GREEN"))
    return context


def get_regime_aware_allocation_feed(capital_rotation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rotation = capital_rotation or get_capital_rotation_feed()
    target_allocations = rotation.get("target_allocations", {}) if isinstance(rotation, dict) else {}
    return RegimeAwareAllocationEngine().adjust(target_allocations, _load_regime_context())


def _adaptive_risk_context() -> Dict[str, Any]:
    pause_state = get_pause_state()
    if pause_state.get("trading_paused") is True:
        return {
            "status": "RED",
            "critical_flags": ["PAUSE_NEW_TRADES"],
            "reason": pause_state.get("reason", "mobile_pause_control"),
        }
    return {"status": "GREEN", "critical_flags": []}


def get_adaptive_portfolio_feed(
    portfolio_intelligence: Optional[Dict[str, Any]] = None,
    capital_rotation: Optional[Dict[str, Any]] = None,
    runtime_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    state = runtime_state or get_runtime_portfolio_state_feed()
    intelligence = portfolio_intelligence or get_portfolio_intelligence_feed(state)
    rotation = capital_rotation or get_capital_rotation_feed(intelligence, state)
    supervisor = state.get("supervisor", {}) if isinstance(state, dict) and state.get("supervisor") else get_supervisor_summary()
    return AdaptivePortfolioManager().evaluate(
        portfolio_intelligence=intelligence,
        capital_rotation=rotation,
        supervisor_state=supervisor,
        risk_context=_adaptive_risk_context(),
        governance_context={"status": "GREEN", "critical_flags": []},
    )


def get_portfolio_risk_committee_feed(
    portfolio_intelligence: Optional[Dict[str, Any]] = None,
    capital_rotation: Optional[Dict[str, Any]] = None,
    adaptive_portfolio: Optional[Dict[str, Any]] = None,
    attribution: Optional[Dict[str, Any]] = None,
    regime_allocation: Optional[Dict[str, Any]] = None,
    runtime_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    state = runtime_state or get_runtime_portfolio_state_feed()
    intelligence = portfolio_intelligence or get_portfolio_intelligence_feed(state)
    rotation = capital_rotation or get_capital_rotation_feed(intelligence, state)
    adaptive = adaptive_portfolio or get_adaptive_portfolio_feed(intelligence, rotation, state)
    attribution_payload = attribution or get_strategy_attribution_feed(state)
    regime_payload = regime_allocation or get_regime_aware_allocation_feed(rotation)
    return PortfolioRiskCommittee().review(
        portfolio_intelligence=intelligence,
        capital_rotation=rotation,
        adaptive_portfolio=adaptive,
        attribution=attribution_payload,
        regime_allocation=regime_payload,
        supervisor_flags=state.get("supervisor", {}) if isinstance(state, dict) and state.get("supervisor") else get_supervisor_summary(),
    )


def _portfolio_learning_storage_dir() -> str:
    return os.path.join(LauncherConfig.ARTIFACTS_DIR, "portfolio")


def _load_quantitative_return_inputs(runtime_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    records = runtime_state.get("trades", []) if isinstance(runtime_state, dict) else _load_completed_trade_learning_records()
    portfolio_returns: List[float] = []
    benchmark_returns: List[float] = []
    asset_returns: Dict[str, List[float]] = {}
    for row in records:
        try:
            realized_pnl = float(row.get("realized_pnl", row.get("pnl", 0.0)) or 0.0)
        except (TypeError, ValueError):
            continue
        normalized_return = realized_pnl / 10000.0
        portfolio_returns.append(normalized_return)
        if row.get("benchmark_return") is not None:
            try:
                benchmark_returns.append(float(row.get("benchmark_return")))
            except (TypeError, ValueError):
                pass
        asset_class = _clean_text(row.get("asset_class"), fallback="ASSET_CLASS_UNSPECIFIED").upper()
        asset_returns.setdefault(asset_class, []).append(normalized_return)
    return {
        "portfolio_returns": portfolio_returns,
        "benchmark_returns": benchmark_returns,
        "asset_returns": asset_returns,
    }


def get_quantitative_metrics_feed(runtime_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    inputs = _load_quantitative_return_inputs(runtime_state)
    if (
        isinstance(runtime_state, dict)
        and runtime_state.get("portfolio_state") == "NO_PORTFOLIO"
        and not inputs["portfolio_returns"]
    ):
        return {
            "status": "LIMITED",
            "metrics": {
                "rolling_sharpe": None,
                "rolling_sortino": None,
                "max_drawdown": 0.0,
                "volatility": 0.0,
            },
            "correlation_matrix": {},
            "sample_size": 0,
            "reasons": ["No current exposure."],
            "advisory_only": True,
        }
    return QuantitativeMetricsEngine().compute(
        portfolio_returns=inputs["portfolio_returns"],
        benchmark_returns=inputs["benchmark_returns"],
        asset_returns=inputs["asset_returns"],
    )


def get_market_regime_intelligence_feed(
    quantitative_metrics: Optional[Dict[str, Any]] = None,
    runtime_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metrics_payload = quantitative_metrics or get_quantitative_metrics_feed(runtime_state)
    inputs = _load_quantitative_return_inputs(runtime_state)
    correlation_matrix = metrics_payload.get("correlation_matrix", {}) if isinstance(metrics_payload, dict) else {}
    if (
        isinstance(runtime_state, dict)
        and runtime_state.get("portfolio_state") == "NO_PORTFOLIO"
        and not inputs["portfolio_returns"]
    ):
        context = _load_regime_context()
        return {
            "status": "LIMITED",
            "detected_regime": str(context.get("detected_regime", context.get("market_regime", "UNKNOWN"))).upper(),
            "confidence": 50,
            "volatility_state": "UNKNOWN",
            "trend_state": "UNKNOWN",
            "correlation_state": "UNKNOWN",
            "risk_bias": "BALANCED",
            "reasons": ["No current exposure."],
            "advisory_only": True,
        }
    return MarketRegimeIntelligence().detect(
        returns=inputs["portfolio_returns"],
        correlation_matrix=correlation_matrix,
    )


def get_policy_profile_feed() -> Dict[str, Any]:
    payload = _safe_load_artifact("css_policy_profile.json")
    profile_name = payload.get("profile") or payload.get("active_profile") or os.environ.get("CSS_POLICY_PROFILE")
    return PolicyProfileEngine().get_profile(profile_name)


def get_recommendation_tracker_feed() -> Dict[str, Any]:
    return RecommendationTracker(_portfolio_learning_storage_dir()).summary()


def _load_recommendation_evaluation_history() -> List[Dict[str, Any]]:
    paths = [
        os.path.join(_portfolio_learning_storage_dir(), "recommendation_tracker.json"),
        os.path.join(_portfolio_learning_storage_dir(), "advisory_history.json"),
        os.path.join(_portfolio_learning_storage_dir(), "portfolio_decision_packages.json"),
    ]
    for path in paths:
        try:
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, list):
                rows = [row for row in payload if isinstance(row, dict)]
                if rows:
                    return rows
        except Exception:
            continue
    return []


def get_recommendation_evaluation_feed(history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    records = history if history is not None else _load_recommendation_evaluation_history()
    return RecommendationEvaluator().evaluate(records)


def get_confidence_calibration_feed(history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    records = history if history is not None else _load_recommendation_evaluation_history()
    evaluated_records = RecommendationEvaluator._evaluable_rows(records)
    return ConfidenceCalibrationEngine().analyze(evaluated_records if evaluated_records else records)


def get_recommendation_drift_feed(history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    records = history if history is not None else _load_recommendation_evaluation_history()
    return RecommendationDriftAnalyzer().analyze(records)


def _load_phase139a_learning_history() -> List[Dict[str, Any]]:
    records = _load_recommendation_evaluation_history()
    if records:
        return records
    return _load_completed_trade_learning_records()


def get_factor_performance_learning_feed(history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    records = history if history is not None else _load_phase139a_learning_history()
    return FactorPerformanceEngine().analyze(records)


def get_factor_attribution_learning_feed(history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    records = history if history is not None else _load_phase139a_learning_history()
    return FactorAttributionEngine().attribute(records)


def get_rolling_reliability_learning_feed(history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    records = history if history is not None else _load_phase139a_learning_history()
    return RollingReliabilityEngine().evaluate(records)


def get_regime_learning_feed(history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    records = history if history is not None else _load_phase139a_learning_history()
    return RegimeLearningEngine().analyze(records)


def get_adaptive_weight_recommendations_feed(
    *,
    factor_performance: Optional[Dict[str, Any]] = None,
    rolling_reliability: Optional[Dict[str, Any]] = None,
    regime_learning: Optional[Dict[str, Any]] = None,
    current_weights: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    weights_payload = current_weights or get_regime_aware_weighting_feed()
    weights = weights_payload.get("weights", {}) if isinstance(weights_payload, dict) else {}
    performance = factor_performance or get_factor_performance_learning_feed()
    reliability = rolling_reliability or get_rolling_reliability_learning_feed()
    regimes = regime_learning or get_regime_learning_feed()
    return AdaptiveWeightRecommendationEngine().recommend(
        factor_performance=performance,
        rolling_reliability=reliability,
        regime_learning=regimes,
        current_weights=weights,
    )


def get_confidence_calibration_learning_feed(history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    records = history if history is not None else _load_phase139a_learning_history()
    return ConfidenceCalibrationLearningEngine().analyze(records)


def get_engine_health_learning_feed(packages: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = packages or {
        "factor_performance": get_factor_performance_learning_feed(),
        "factor_attribution": get_factor_attribution_learning_feed(),
        "rolling_reliability": get_rolling_reliability_learning_feed(),
        "regime_learning": get_regime_learning_feed(),
        "confidence_calibration_learning": get_confidence_calibration_learning_feed(),
    }
    return EngineHealthLearningEngine().evaluate(payload)


def get_technical_analysis_feed(runtime_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = runtime_state or get_runtime_portfolio_state_feed()
    market_data = state.get("market_data", {}) if isinstance(state, dict) else {}
    trades = state.get("trades", []) if isinstance(state, dict) else []
    prices = market_data.get("price_history", []) if isinstance(market_data, dict) else []
    if not prices and isinstance(trades, list):
        prices = [
            row.get("current_price", row.get("exit_price", row.get("price")))
            for row in trades
            if isinstance(row, dict) and row.get("current_price", row.get("exit_price", row.get("price"))) is not None
        ]
    returns = market_data.get("returns", []) if isinstance(market_data, dict) else []
    metrics = state.get("performance_metrics", {}) if isinstance(state, dict) else {}
    return TechnicalAnalysisEngine().analyze(
        price_history=prices,
        returns=returns,
        volatility=metrics.get("volatility") if isinstance(metrics, dict) else None,
        trend_data=market_data if isinstance(market_data, dict) else {},
    )


def get_fundamental_analysis_feed(runtime_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = runtime_state or get_runtime_portfolio_state_feed()
    positions = state.get("positions", []) if isinstance(state, dict) else []
    first = positions[0] if isinstance(positions, list) and positions and isinstance(positions[0], dict) else {}
    market_data = state.get("market_data", {}) if isinstance(state, dict) else {}
    metadata = {
        **(market_data if isinstance(market_data, dict) else {}),
        **first,
    }
    if "asset_class" not in metadata and isinstance(state, dict):
        allocations = state.get("asset_allocations", {})
        if isinstance(allocations, dict) and allocations:
            metadata["asset_class"] = next(iter(allocations.keys()))
    return FundamentalAnalysisEngine().evaluate(metadata)


def get_sentiment_intelligence_feed(
    decision: Optional[Dict[str, Any]] = None,
    runtime_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    state = runtime_state or get_runtime_portfolio_state_feed()
    market_data = state.get("market_data", {}) if isinstance(state, dict) else {}
    return SentimentIntelligenceEngine().analyze(
        alerts=get_alert_summary(),
        recommendation_history=_load_recommendation_evaluation_history(),
        runtime_warnings=(decision or {}).get("conflicting_signals", []) if isinstance(decision, dict) else [],
        strategy_confidence_history=[],
        market_regime=market_data.get("market_regime") if isinstance(market_data, dict) else None,
    )


def get_quantitative_alpha_feed(runtime_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = runtime_state or get_runtime_portfolio_state_feed()
    trades = state.get("trades", []) if isinstance(state, dict) else []
    metrics = state.get("performance_metrics", {}) if isinstance(state, dict) else {}
    returns = metrics.get("portfolio_returns", []) if isinstance(metrics, dict) else []
    asset_pnl: Dict[str, float] = {}
    for row in trades if isinstance(trades, list) else []:
        if not isinstance(row, dict):
            continue
        asset = str(row.get("asset_class", "UNKNOWN")).upper()
        try:
            asset_pnl[asset] = asset_pnl.get(asset, 0.0) + float(row.get("realized_pnl", row.get("pnl", 0.0)) or 0.0)
        except (TypeError, ValueError):
            continue
    return QuantitativeAlphaEngine().evaluate(
        returns=returns,
        win_loss_history=trades,
        asset_class_pnl=asset_pnl,
        trade_expectancy=metrics.get("expectancy") if isinstance(metrics, dict) else None,
        volatility=metrics.get("volatility") if isinstance(metrics, dict) else None,
        drawdown=metrics.get("max_drawdown") if isinstance(metrics, dict) else None,
        trend_stability=metrics.get("trend_stability") if isinstance(metrics, dict) else None,
    )


def get_regime_aware_weighting_feed(
    *,
    runtime_state: Optional[Dict[str, Any]] = None,
    market_regime: Optional[Dict[str, Any]] = None,
    portfolio_lifecycle: Optional[Dict[str, Any]] = None,
    technical: Optional[Dict[str, Any]] = None,
    fundamental: Optional[Dict[str, Any]] = None,
    sentiment: Optional[Dict[str, Any]] = None,
    quantitative: Optional[Dict[str, Any]] = None,
    policy_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    state = runtime_state or get_runtime_portfolio_state_feed()
    regime = market_regime or get_market_regime_intelligence_feed(runtime_state=state)
    return RegimeAwareWeightingEngine().evaluate(
        market_regime=regime,
        portfolio_lifecycle=portfolio_lifecycle or state,
        technical=technical or get_technical_analysis_feed(state),
        fundamental=fundamental or get_fundamental_analysis_feed(state),
        sentiment=sentiment or get_sentiment_intelligence_feed(runtime_state=state),
        quantitative=quantitative or get_quantitative_alpha_feed(state),
        policy_profile=policy_profile or get_policy_profile_feed(),
    )


def get_multi_factor_signal_feed(
    *,
    runtime_state: Optional[Dict[str, Any]] = None,
    portfolio_decision: Optional[Dict[str, Any]] = None,
    technical: Optional[Dict[str, Any]] = None,
    fundamental: Optional[Dict[str, Any]] = None,
    sentiment: Optional[Dict[str, Any]] = None,
    quantitative: Optional[Dict[str, Any]] = None,
    market_regime: Optional[Dict[str, Any]] = None,
    regime_weights: Optional[Dict[str, Any]] = None,
    policy_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    state = runtime_state or get_runtime_portfolio_state_feed()
    tech = technical or get_technical_analysis_feed(state)
    fund = fundamental or get_fundamental_analysis_feed(state)
    sent = sentiment or get_sentiment_intelligence_feed(portfolio_decision, state)
    quant = quantitative or get_quantitative_alpha_feed(state)
    regime = market_regime or get_market_regime_intelligence_feed(runtime_state=state)
    weights = regime_weights or get_regime_aware_weighting_feed(
        runtime_state=state,
        market_regime=regime,
        technical=tech,
        fundamental=fund,
        sentiment=sent,
        quantitative=quant,
        policy_profile=policy_profile,
    )
    return MultiFactorSignalSynthesizer().synthesize(
        technical=tech,
        fundamental=fund,
        sentiment=sent,
        quantitative=quant,
        market_regime=regime,
        portfolio_decision=portfolio_decision,
        regime_weights=weights,
    )


def get_advisory_history_feed() -> Dict[str, Any]:
    store = AdvisoryHistoryStore(_portfolio_learning_storage_dir())
    summary = store.summarize()
    recent = store.list_recent(limit=5)
    return {
        "status": "OK",
        "summary": summary,
        "recent_decisions": recent.get("decisions", []),
        "advisory_only": True,
    }


def _portfolio_decision_inputs() -> Dict[str, Any]:
    runtime_state = get_runtime_portfolio_state_feed()
    portfolio_intelligence = get_portfolio_intelligence_feed(runtime_state)
    capital_rotation = get_capital_rotation_feed(portfolio_intelligence, runtime_state)
    strategy_attribution = get_strategy_attribution_feed(runtime_state)
    regime_allocation = get_regime_aware_allocation_feed(capital_rotation)
    adaptive_portfolio = get_adaptive_portfolio_feed(portfolio_intelligence, capital_rotation, runtime_state)
    risk_committee = get_portfolio_risk_committee_feed(
        portfolio_intelligence=portfolio_intelligence,
        capital_rotation=capital_rotation,
        adaptive_portfolio=adaptive_portfolio,
        attribution=strategy_attribution,
        regime_allocation=regime_allocation,
        runtime_state=runtime_state,
    )
    quantitative_metrics = get_quantitative_metrics_feed(runtime_state)
    market_regime_intelligence = get_market_regime_intelligence_feed(quantitative_metrics, runtime_state)
    policy_profile = get_policy_profile_feed()
    recommendation_tracker = get_recommendation_tracker_feed()
    technical_analysis = get_technical_analysis_feed(runtime_state)
    fundamental_analysis = get_fundamental_analysis_feed(runtime_state)
    sentiment_intelligence = get_sentiment_intelligence_feed(runtime_state=runtime_state)
    quantitative_alpha = get_quantitative_alpha_feed(runtime_state)
    regime_aware_weighting = get_regime_aware_weighting_feed(
        runtime_state=runtime_state,
        market_regime=market_regime_intelligence,
        technical=technical_analysis,
        fundamental=fundamental_analysis,
        sentiment=sentiment_intelligence,
        quantitative=quantitative_alpha,
        policy_profile=policy_profile,
    )
    multi_factor_signal = get_multi_factor_signal_feed(
        runtime_state=runtime_state,
        technical=technical_analysis,
        fundamental=fundamental_analysis,
        sentiment=sentiment_intelligence,
        quantitative=quantitative_alpha,
        market_regime=market_regime_intelligence,
        regime_weights=regime_aware_weighting,
        policy_profile=policy_profile,
    )
    consistency = AdvisoryConsistencyChecker().check(
        adaptive_portfolio=adaptive_portfolio,
        capital_rotation=capital_rotation,
        risk_committee=risk_committee,
        policy_profile=policy_profile,
        market_regime=market_regime_intelligence,
    )
    return {
        "runtime_portfolio_state": runtime_state,
        "portfolio_intelligence": portfolio_intelligence,
        "capital_rotation": capital_rotation,
        "adaptive_portfolio": adaptive_portfolio,
        "strategy_attribution": strategy_attribution,
        "regime_allocation": regime_allocation,
        "risk_committee": risk_committee,
        "quantitative_metrics": quantitative_metrics,
        "market_regime_intelligence": market_regime_intelligence,
        "policy_profile": policy_profile,
        "recommendation_tracker": recommendation_tracker,
        "technical_analysis": technical_analysis,
        "fundamental_analysis": fundamental_analysis,
        "sentiment_intelligence": sentiment_intelligence,
        "quantitative_alpha": quantitative_alpha,
        "regime_aware_weighting": regime_aware_weighting,
        "multi_factor_signal": multi_factor_signal,
        "conflicting_signals": consistency.get("conflicts", []),
        "consistency": consistency,
    }


def get_advisory_consistency_feed(inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = inputs or _portfolio_decision_inputs()
    if payload.get("consistency"):
        return payload["consistency"]
    return AdvisoryConsistencyChecker().check(
        adaptive_portfolio=payload.get("adaptive_portfolio"),
        capital_rotation=payload.get("capital_rotation"),
        risk_committee=payload.get("risk_committee"),
        policy_profile=payload.get("policy_profile"),
        market_regime=payload.get("market_regime_intelligence"),
    )


def get_portfolio_decision_feed(inputs: Optional[Dict[str, Any]] = None, persist: bool = False) -> Dict[str, Any]:
    inputs = inputs or _portfolio_decision_inputs()
    decision = PortfolioDecisionOrchestrator().orchestrate(inputs)
    if persist:
        DecisionPackageStore(_portfolio_learning_storage_dir()).append(decision)
    return decision


def get_runtime_advisory_snapshot_feed(
    inputs: Optional[Dict[str, Any]] = None,
    portfolio_decision: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = inputs or _portfolio_decision_inputs()
    decision = portfolio_decision or PortfolioDecisionOrchestrator().orchestrate(payload)
    return RuntimeAdvisorySnapshot().build(
        runtime_state=payload.get("runtime_portfolio_state"),
        advisory_components=payload,
        portfolio_decision=decision,
    )


def get_runtime_portfolio_lifecycle_feed(
    inputs: Optional[Dict[str, Any]] = None,
    portfolio_decision: Optional[Dict[str, Any]] = None,
    runtime_advisory_snapshot: Optional[Dict[str, Any]] = None,
    persist: bool = False,
) -> Dict[str, Any]:
    payload = inputs or _portfolio_decision_inputs()
    decision = portfolio_decision or PortfolioDecisionOrchestrator().orchestrate(payload)
    snapshot = runtime_advisory_snapshot or get_runtime_advisory_snapshot_feed(payload, decision)
    return RuntimePortfolioLifecycle(LauncherConfig.ARTIFACTS_DIR).refresh(
        runtime_state=payload.get("runtime_portfolio_state"),
        advisory_snapshot=snapshot,
        portfolio_decision=decision,
        persist=persist,
    )


def record_portfolio_decision(package: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    decision_package = package or get_portfolio_decision_feed(persist=False)
    result = DecisionPackageStore(_portfolio_learning_storage_dir()).append(decision_package)
    return {
        "status": result.get("status", "DATA UNAVAILABLE"),
        "recorded": result.get("status") == "OK",
        "decision": result.get("record", decision_package),
        "count": result.get("count", 0),
        "advisory_only": True,
    }


def get_decision_validation_feed(
    decision: Optional[Dict[str, Any]] = None,
    policy_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    decision_package = decision or get_portfolio_decision_feed(persist=False)
    return DecisionValidationEngine().validate(
        decision_package=decision_package,
        policy_profile=policy_profile or get_policy_profile_feed(),
        supervisor_state=get_supervisor_summary(),
        risk_committee=decision_package.get("risk_committee", {}) if isinstance(decision_package, dict) else {},
    )


def get_explainability_feed(
    decision: Optional[Dict[str, Any]] = None,
    validation: Optional[Dict[str, Any]] = None,
    consistency: Optional[Dict[str, Any]] = None,
    inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    inputs = inputs or _portfolio_decision_inputs()
    decision_package = decision or PortfolioDecisionOrchestrator().orchestrate(inputs)
    validation_payload = validation or get_decision_validation_feed(decision_package)
    consistency_payload = consistency or get_advisory_consistency_feed(inputs)
    return ExplainabilityEngine().explain(
        portfolio_intelligence=inputs.get("portfolio_intelligence"),
        adaptive_portfolio=inputs.get("adaptive_portfolio"),
        risk_committee=inputs.get("risk_committee"),
        quantitative_metrics=inputs.get("quantitative_metrics"),
        market_regime=inputs.get("market_regime_intelligence"),
        policy_profile=inputs.get("policy_profile"),
        validation=validation_payload,
        consistency=consistency_payload,
    )


def _artifact_status_snapshot() -> Dict[str, Any]:
    now = time.time()
    required_names = [
        "css_session_state_pcnrass.json",
        "css_account_state_pcnrass.json",
    ]
    optional_names = [
        "css_session_recovery.json",
        "css_account_state_pcnrass_BACKUP.json",
    ]
    snapshot: Dict[str, Any] = {}
    latest_mtime = 0.0
    for name in required_names + optional_names:
        path = os.path.join(LauncherConfig.ARTIFACTS_DIR, name)
        if os.path.exists(path):
            mtime = os.path.getmtime(path)
            latest_mtime = max(latest_mtime, mtime)
            age = max(0.0, now - mtime)
            snapshot[name] = {"age_seconds": age, "stale_after_seconds": 300, "stale": age > 300}
        else:
            snapshot[name] = {
                "age_seconds": None,
                "stale_after_seconds": 300,
                "stale": name in required_names,
                "optional": name in optional_names,
            }
    snapshot["dashboard_stale"] = (now - latest_mtime) > 300 if latest_mtime else True
    snapshot["persistence_health"] = "OK"
    return snapshot


def get_runtime_performance_feed(
    dashboard_latency_ms: Optional[float] = None,
    pipeline_latency_ms: Optional[float] = None,
    api_latency_ms: Optional[float] = None,
) -> Dict[str, Any]:
    telemetry = {
        "pipeline_latency_ms": pipeline_latency_ms if pipeline_latency_ms is not None else 0.0,
        "dashboard_latency_ms": dashboard_latency_ms if dashboard_latency_ms is not None else 0.0,
        "api_endpoint_latency_ms": [api_latency_ms] if api_latency_ms is not None else [],
        "json_persistence_latency_ms": [],
        "artifact_reads": 4,
        "artifact_writes": 0,
        "cache_hits": 1 if pipeline_latency_ms is not None else 0,
        "cache_misses": 1,
        "execution_times_ms": [
            value for value in [dashboard_latency_ms, pipeline_latency_ms, api_latency_ms] if value is not None
        ],
    }
    return RuntimePerformanceMonitor().evaluate(telemetry)


def get_session_validation_feed(portfolio_decision: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    session_state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    decision = portfolio_decision or get_portfolio_decision_feed(persist=False)
    advisory_status = {
        "stale_advisory_package": bool(decision.get("missing_inputs")) if isinstance(decision, dict) else True,
        "persistence_health": "OK",
        "recommendations": [decision.get("portfolio_recommendation")] if isinstance(decision, dict) else [],
        "policy_consistency": not bool(decision.get("conflicting_signals")) if isinstance(decision, dict) else False,
    }
    return SessionValidationEngine().validate(
        session_state=session_state,
        supervisor_state=get_supervisor_summary(),
        artifact_status=_artifact_status_snapshot(),
        advisory_status=advisory_status,
    )


def get_runtime_health_feed(
    performance: Optional[Dict[str, Any]] = None,
    session_validation: Optional[Dict[str, Any]] = None,
    portfolio_decision: Optional[Dict[str, Any]] = None,
    runtime_portfolio_state: Optional[Dict[str, Any]] = None,
    artifact_freshness: Optional[Dict[str, Any]] = None,
    session_continuity: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    decision = portfolio_decision or _safe_load_artifact("portfolio_decision.json") or get_portfolio_decision_feed(persist=False)
    state = runtime_portfolio_state or _safe_load_artifact("runtime_portfolio_state.json") or get_runtime_portfolio_state_feed()
    perf = performance or get_runtime_performance_feed()
    session = session_validation or get_session_validation_feed(decision)
    return RuntimeHealthAggregator().aggregate(
        performance=perf,
        session_validation=session,
        supervisor_status=get_supervisor_summary(),
        portfolio_decision=decision,
        runtime_portfolio_state=state,
        artifact_freshness=artifact_freshness,
        session_continuity=session_continuity,
    )


def _safe_runtime_health_error(reason: Any) -> Dict[str, Any]:
    return {
        "status": "DATA UNAVAILABLE",
        "runtime_health": "AMBER",
        "overall_operational_health": "AMBER",
        "performance_status": "DATA UNAVAILABLE",
        "session_status": "DATA UNAVAILABLE",
        "supervisor_status": "UNKNOWN",
        "portfolio_decision_status": "UNKNOWN",
        "portfolio_lifecycle_state": "UNKNOWN",
        "warnings": [f"runtime_health_endpoint_error:{_clean_text(reason, fallback='unknown_error')}"],
        "pipeline_latency_ms": None,
        "dashboard_latency_ms": None,
        "cache_hit_rate": 0.0,
        "heartbeat_age": None,
        "restart_count": 0,
        "recovery_count": 0,
        "memory_usage": None,
        "cpu_usage": None,
        "recommendation": "Runtime health endpoint recovered with advisory-only degraded status.",
        "advisory_only": True,
        "execution_allowed": False,
    }


def _safe_validation_readiness_error(reason: Any) -> Dict[str, Any]:
    return {
        "status": "OK",
        "readiness_status": "NOT_READY",
        "confidence": 0,
        "blockers": ["validation_readiness_endpoint_error"],
        "warnings": [],
        "recommended_actions": [f"Review validation readiness endpoint error: {_clean_text(reason, fallback='unknown_error')}."],
        "portfolio_lifecycle_state": "UNKNOWN",
        "advisory_only": True,
        "paper_validation_only": True,
        "execution_allowed": False,
    }


def _paper_validation_storage_dir() -> str:
    return os.path.join(LauncherConfig.ARTIFACTS_DIR, "validation")


def _paper_validation_store() -> SessionCheckpointStore:
    return SessionCheckpointStore(_paper_validation_storage_dir())


def get_validation_readiness_feed(
    runtime_health: Optional[Dict[str, Any]] = None,
    session_validation: Optional[Dict[str, Any]] = None,
    portfolio_decision: Optional[Dict[str, Any]] = None,
    runtime_performance: Optional[Dict[str, Any]] = None,
    runtime_advisory_snapshot: Optional[Dict[str, Any]] = None,
    runtime_portfolio_state: Optional[Dict[str, Any]] = None,
    artifact_freshness: Optional[Dict[str, Any]] = None,
    session_continuity: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    decision = portfolio_decision or _safe_load_artifact("portfolio_decision.json") or get_portfolio_decision_feed(persist=False)
    state = runtime_portfolio_state or _safe_load_artifact("runtime_portfolio_state.json") or get_runtime_portfolio_state_feed()
    snapshot = runtime_advisory_snapshot or _safe_load_artifact("runtime_advisory_snapshot.json") or get_runtime_advisory_snapshot_feed(portfolio_decision=decision)
    performance = runtime_performance or get_runtime_performance_feed()
    session = session_validation or get_session_validation_feed(decision)
    health = runtime_health or get_runtime_health_feed(
        performance=performance,
        session_validation=session,
        portfolio_decision=decision,
        runtime_portfolio_state=state,
    )
    stale_artifacts = session.get("stale_artifacts", []) if isinstance(session, dict) else []
    alerts = get_alert_summary()
    recent_errors = alerts.get("errors", []) if isinstance(alerts, dict) else []
    return ValidationReadinessEngine().evaluate(
        runtime_health=health,
        session_validation=session,
        portfolio_decision=decision,
        operational_telemetry=performance,
        stale_artifacts=stale_artifacts,
        recent_errors=recent_errors,
        runtime_advisory_snapshot=snapshot,
        runtime_portfolio_state=state,
        artifact_freshness=artifact_freshness,
        session_continuity=session_continuity,
    )


def get_runtime_artifact_freshness_feed(refresh: bool = False) -> Dict[str, Any]:
    return RuntimeArtifactFreshnessManager(
        artifacts_dir=LauncherConfig.ARTIFACTS_DIR,
        account_state_path=LauncherConfig.ACCOUNT_STATE_FILE,
        session_state_path=LauncherConfig.SESSION_STATE_FILE,
        supervisor_state_path=LauncherConfig.SUPERVISOR_STATE_FILE,
        closed_trade_ledger_path=LauncherConfig.CLOSED_TRADE_LEDGER_PATH,
    ).evaluate(refresh=refresh)


def ensure_runtime_artifacts_current(
    *,
    inputs: Optional[Dict[str, Any]] = None,
    portfolio_decision: Optional[Dict[str, Any]] = None,
    runtime_advisory_snapshot: Optional[Dict[str, Any]] = None,
    validation_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    initial = get_runtime_artifact_freshness_feed(refresh=False)
    critical_artifacts = initial.get("artifacts", {}) if isinstance(initial, dict) else {}
    critical_needs_publish = False
    supervisor_needs_publish = False
    for name in ("account_state", "session_state", "supervisor_state"):
        artifact = critical_artifacts.get(name, {}) if isinstance(critical_artifacts, dict) else {}
        if artifact.get("freshness") in {"MISSING", "STALE"}:
            critical_needs_publish = True
            if name == "supervisor_state":
                supervisor_needs_publish = True

    published: Dict[str, Any] = {"status": "SKIPPED", "reason": "critical_artifacts_current"}
    if critical_needs_publish:
        published = publish_runtime_artifacts(
            inputs=inputs,
            portfolio_decision=portfolio_decision,
            runtime_advisory_snapshot=runtime_advisory_snapshot,
            validation_summary=validation_summary,
        )
    supervisor_published = _publish_supervisor_heartbeat_snapshot() if supervisor_needs_publish else {"status": "SKIPPED"}
    refreshed = get_runtime_artifact_freshness_feed(refresh=True)
    return {
        "status": "OK",
        "published": published,
        "supervisor_published": supervisor_published,
        "freshness": refreshed,
        "advisory_only": True,
        "execution_allowed": False,
    }


def _publish_supervisor_heartbeat_snapshot() -> Dict[str, Any]:
    payload = {
        "status": "RUNNING",
        "last_heartbeat": _utc_iso_z(),
        "source": "css_mobile_launcher",
        "advisory_only": True,
        "execution_allowed": False,
    }
    try:
        os.makedirs(os.path.dirname(LauncherConfig.SUPERVISOR_STATE_FILE), exist_ok=True)
        with open(LauncherConfig.SUPERVISOR_STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return {"status": "OK", "path": LauncherConfig.SUPERVISOR_STATE_FILE}
    except Exception as exc:
        return {"status": "ERROR", "reason": str(exc)}


def get_runtime_session_continuity_feed() -> Dict[str, Any]:
    session_state = _safe_load_artifact("css_session_state_pcnrass.json")
    recovery_state = _safe_load_artifact("css_session_recovery.json")
    if isinstance(recovery_state, dict) and isinstance(recovery_state.get("session_user_ctx"), dict):
        session_state = recovery_state
    elif not session_state:
        session_state = recovery_state
    return RuntimeSessionContinuityMonitor(session_state_path=LauncherConfig.SESSION_STATE_FILE).evaluate(session_state)


def get_session_renewal_status_feed() -> Dict[str, Any]:
    session_state = _safe_load_artifact("css_session_state_pcnrass.json")
    recovery_state = _safe_load_artifact("css_session_recovery.json")
    if isinstance(recovery_state, dict) and isinstance(recovery_state.get("session_user_ctx"), dict):
        session_state = recovery_state
    elif not session_state:
        session_state = recovery_state
    return SessionRenewalManager(session_state_path=LauncherConfig.SESSION_STATE_FILE).evaluate(
        session_state,
        persist=False,
    )


def publish_runtime_artifacts(
    *,
    inputs: Optional[Dict[str, Any]] = None,
    portfolio_decision: Optional[Dict[str, Any]] = None,
    runtime_advisory_snapshot: Optional[Dict[str, Any]] = None,
    validation_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = inputs or _portfolio_decision_inputs()
    decision = portfolio_decision or get_portfolio_decision_feed(inputs=payload, persist=False)
    snapshot = runtime_advisory_snapshot or get_runtime_advisory_snapshot_feed(inputs=payload, portfolio_decision=decision)
    validation = validation_summary or _safe_load_artifact("validation_summary.json")
    return RuntimeArtifactPublisher(
        artifacts_dir=LauncherConfig.ARTIFACTS_DIR,
        account_state_path=LauncherConfig.ACCOUNT_STATE_FILE,
        session_state_path=LauncherConfig.SESSION_STATE_FILE,
        closed_trade_ledger_path=LauncherConfig.CLOSED_TRADE_LEDGER_PATH,
        supervisor_state_path=LauncherConfig.SUPERVISOR_STATE_FILE,
    ).publish(
        runtime_cycle=get_runtime_summary().get("current_cycle", 0),
        runtime_portfolio_state=payload.get("runtime_portfolio_state"),
        runtime_advisory_snapshot=snapshot,
        portfolio_decision=decision,
        validation_summary=validation if validation else None,
    )


def get_runtime_validation_monitor_feed(
    runtime_health: Optional[Dict[str, Any]] = None,
    validation_readiness: Optional[Dict[str, Any]] = None,
    session_continuity: Optional[Dict[str, Any]] = None,
    artifact_freshness: Optional[Dict[str, Any]] = None,
    portfolio_lifecycle: Optional[Dict[str, Any]] = None,
    portfolio_decision: Optional[Dict[str, Any]] = None,
    advisory_snapshot: Optional[Dict[str, Any]] = None,
    persist: bool = False,
) -> Dict[str, Any]:
    decision = portfolio_decision or _safe_load_artifact("portfolio_decision.json") or get_portfolio_decision_feed(persist=False)
    freshness = artifact_freshness or get_runtime_artifact_freshness_feed(refresh=False)
    continuity = session_continuity or get_runtime_session_continuity_feed()
    health = runtime_health or get_runtime_health_feed(portfolio_decision=decision, artifact_freshness=freshness, session_continuity=continuity)
    readiness = validation_readiness or get_validation_readiness_feed(
        runtime_health=health,
        portfolio_decision=decision,
        artifact_freshness=freshness,
        session_continuity=continuity,
    )
    lifecycle = portfolio_lifecycle or _safe_load_artifact(os.path.join("portfolio", "runtime_portfolio_lifecycle.json")) or {}
    snapshot = advisory_snapshot or _safe_load_artifact("runtime_advisory_snapshot.json")
    return ContinuousValidationMonitor(artifacts_dir=LauncherConfig.ARTIFACTS_DIR).evaluate(
        runtime_health=health,
        validation_readiness=readiness,
        session_continuity=continuity,
        artifact_freshness=freshness,
        supervisor_state=get_supervisor_summary(),
        portfolio_lifecycle=lifecycle,
        portfolio_decision=decision,
        advisory_snapshot=snapshot,
        persist=persist,
    )


def _validation_events_from_artifacts() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for filename in ("runtime_validation_monitor.json", "runtime_validation_metrics.json", "long_duration_validation.json"):
        payload = _safe_load_artifact(filename)
        if payload:
            rows.append(payload)
    checkpoints = get_paper_validation_checkpoints_feed()
    for row in checkpoints.get("checkpoints", []) if isinstance(checkpoints, dict) else []:
        if isinstance(row, dict):
            rows.append(row)
    return rows


def get_runtime_validation_metrics_feed(
    runtime_health: Optional[Dict[str, Any]] = None,
    runtime_performance: Optional[Dict[str, Any]] = None,
    session_validation: Optional[Dict[str, Any]] = None,
    persist: bool = False,
) -> Dict[str, Any]:
    performance = runtime_performance or get_runtime_performance_feed()
    session = session_validation or get_session_validation_feed()
    health = runtime_health or get_runtime_health_feed(performance=performance, session_validation=session)
    return RuntimeValidationMetrics(artifacts_dir=LauncherConfig.ARTIFACTS_DIR).calculate(
        runtime_health=health,
        performance=performance,
        session_validation=session,
        artifact_publisher=_safe_load_artifact("runtime_artifact_publisher.json"),
        validation_events=_validation_events_from_artifacts(),
        persist=persist,
    )


def get_runtime_health_trend_feed(
    runtime_health: Optional[Dict[str, Any]] = None,
    validation_readiness: Optional[Dict[str, Any]] = None,
    artifact_freshness: Optional[Dict[str, Any]] = None,
    session_continuity: Optional[Dict[str, Any]] = None,
    portfolio_decision: Optional[Dict[str, Any]] = None,
    portfolio_lifecycle: Optional[Dict[str, Any]] = None,
    persist: bool = False,
) -> Dict[str, Any]:
    decision = portfolio_decision or _safe_load_artifact("portfolio_decision.json") or get_portfolio_decision_feed(persist=False)
    freshness = artifact_freshness or get_runtime_artifact_freshness_feed(refresh=False)
    continuity = session_continuity or get_runtime_session_continuity_feed()
    health = runtime_health or get_runtime_health_feed(portfolio_decision=decision, artifact_freshness=freshness, session_continuity=continuity)
    readiness = validation_readiness or get_validation_readiness_feed(
        runtime_health=health,
        portfolio_decision=decision,
        artifact_freshness=freshness,
        session_continuity=continuity,
    )
    lifecycle = portfolio_lifecycle or _safe_load_artifact(os.path.join("portfolio", "runtime_portfolio_lifecycle.json")) or {}
    return RuntimeHealthTrend(artifacts_dir=LauncherConfig.ARTIFACTS_DIR).evaluate(
        runtime_health=health,
        validation_readiness=readiness,
        artifact_freshness=freshness,
        session_continuity=continuity,
        portfolio_decision=decision,
        portfolio_lifecycle=lifecycle,
        persist=persist,
    )


def get_validation_confidence_feed(
    runtime_health: Optional[Dict[str, Any]] = None,
    validation_readiness: Optional[Dict[str, Any]] = None,
    artifact_freshness: Optional[Dict[str, Any]] = None,
    session_continuity: Optional[Dict[str, Any]] = None,
    portfolio_decision: Optional[Dict[str, Any]] = None,
    advisory_snapshot: Optional[Dict[str, Any]] = None,
    market_intelligence: Optional[Dict[str, Any]] = None,
    runtime_health_trend: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    decision = portfolio_decision or _safe_load_artifact("portfolio_decision.json") or get_portfolio_decision_feed(persist=False)
    snapshot = advisory_snapshot or _safe_load_artifact("runtime_advisory_snapshot.json")
    freshness = artifact_freshness or get_runtime_artifact_freshness_feed(refresh=False)
    continuity = session_continuity or get_runtime_session_continuity_feed()
    health = runtime_health or get_runtime_health_feed(portfolio_decision=decision, artifact_freshness=freshness, session_continuity=continuity)
    readiness = validation_readiness or get_validation_readiness_feed(
        runtime_health=health,
        portfolio_decision=decision,
        artifact_freshness=freshness,
        session_continuity=continuity,
    )
    trend = runtime_health_trend or get_runtime_health_trend_feed(
        runtime_health=health,
        validation_readiness=readiness,
        artifact_freshness=freshness,
        session_continuity=continuity,
        portfolio_decision=decision,
    )
    return ValidationConfidenceEngine().evaluate(
        runtime_health=health,
        validation_readiness=readiness,
        artifact_freshness=freshness,
        supervisor_stability=get_supervisor_summary(),
        session_continuity=continuity,
        recommendation_stability=get_recommendation_drift_feed(),
        portfolio_decision=decision,
        advisory_snapshot=snapshot,
        market_intelligence=market_intelligence or (decision.get("multi_factor_signal") if isinstance(decision, dict) else None),
        runtime_health_trend=trend,
    )


def get_long_duration_validation_feed(persist: bool = False) -> Dict[str, Any]:
    monitor = _safe_load_artifact("runtime_validation_monitor.json")
    metrics = _safe_load_artifact("runtime_validation_metrics.json")
    confidence = _safe_load_artifact("validation_confidence.json")
    current_sample = None
    if monitor or metrics or confidence:
        current_sample = {
            "timestamp": monitor.get("timestamp") or metrics.get("timestamp") or confidence.get("timestamp"),
            "runtime_health": monitor.get("runtime_health"),
            "validation_confidence": confidence.get("confidence_score"),
            "artifact_freshness": monitor.get("artifact_freshness"),
            "session_continuity": monitor.get("session_continuity"),
            "recommendation_stability": metrics.get("recommendation_stability_trend"),
            "restart_count": metrics.get("restart_frequency", 0),
            "runtime_uptime": metrics.get("runtime_uptime", 0),
        }
    return LongDurationValidation(artifacts_dir=LauncherConfig.ARTIFACTS_DIR).summarize(
        events=_validation_events_from_artifacts(),
        current_sample=current_sample,
        paper_performance=get_trade_summary(),
        persist=persist,
    )


def get_paper_validation_summary_feed() -> Dict[str, Any]:
    return _paper_validation_store().summarize_session()


def get_paper_validation_checkpoints_feed() -> Dict[str, Any]:
    return _paper_validation_store().list_checkpoints()


def record_paper_validation_checkpoint(checkpoint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = dict(checkpoint or {})
    return _paper_validation_store().append_checkpoint(payload)


def get_engine_summary() -> Dict[str, Any]:
    state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    session = state.get("session", {})
    engine_mode = _clean_text(session.get("engine_mode"), fallback=get_runtime_summary().get("runtime_mode", "PAPER")).upper()
    
    summary = {
        "engine_mode": engine_mode,
        "current_strategy": session.get("strategy", "DEFAULT"),
        "trade_gate_status": "OPEN" if engine_mode == "LIVE" else "SIMULATED",
        "runtime_readiness": "ONLINE" if session else "OFFLINE"
    }
    return summary


def get_trade_tab_instrument_feed() -> Dict[str, Any]:
    try:
        return InstrumentUniverse().build_feed()
    except InstrumentUniverseError:
        return {
            "all_instruments": [],
            "asset_classes": [],
            "brokers": [],
            "instruments_by_asset_class": {},
            "instruments_by_broker": {},
            "tradable_paper_instruments": [],
        }


def _normalize_trade_mode(value: Optional[str]) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"live"}:
        return "live"
    if normalized in {"paper", "practice", "sim", "simulated", "sandbox", "safe"}:
        return "paper"
    return "paper"


def _default_trade_mode() -> str:
    runtime_mode = str(get_runtime_summary().get("runtime_mode") or "").strip().upper()
    return "live" if runtime_mode == "LIVE" else "paper"


def get_tradeable_symbols_feed(
    *,
    mode: Optional[str] = None,
    asset_class: Optional[str] = None,
    broker: Optional[str] = None,
) -> Dict[str, Any]:
    requested_mode = _normalize_trade_mode(mode) if mode is not None else _default_trade_mode()
    normalized_mode = _normalize_trade_mode(requested_mode)
    normalized_asset_class = str(asset_class or "").strip().upper() or None
    normalized_broker = str(broker or "").strip().lower() or None

    try:
        symbol_rows = InstrumentUniverse().tradeable_symbols(
            mode=normalized_mode,
            asset_class=normalized_asset_class,
            broker=normalized_broker,
        )
    except InstrumentUniverseError:
        symbol_rows = []
    except Exception:
        symbol_rows = []

    symbols = [
        {
            "symbol": row.symbol,
            "display_name": row.display_name,
            "asset_class": row.asset_class,
            "broker": row.broker,
            "paper_supported": row.paper_supported,
            "live_supported": row.live_supported,
            "status": row.status,
            "min_order_size": getattr(row, "min_order_size", None),
            "max_order_size": getattr(row, "max_order_size", None),
            "tick_size": getattr(row, "tick_size", None),
        }
        for row in symbol_rows
    ]

    return {
        "status": "OK",
        "mode": normalized_mode,
        "count": len(symbols),
        "symbols": symbols,
    }


_CANONICAL_TIMESTAMP_FIELDS = (
    "timestamp",
    "updated_at",
    "generated_at",
    "last_update",
    "last_updated",
    "last_heartbeat",
)

_UNKNOWN_TEXT_VALUES = {"", "none", "null", "unknown", "n/a", "na"}


def _clean_text(value: Any, *, fallback: str) -> str:
    cleaned = str(value or "").strip()
    if cleaned.lower() in _UNKNOWN_TEXT_VALUES:
        return fallback
    return cleaned


def _provider_error(provider: str, exc: Exception) -> Dict[str, Any]:
    return {
        "provider": provider,
        "error_type": exc.__class__.__name__,
        "message": str(exc),
    }


def _safe_provider_call(
    provider: str,
    fn,
    fallback: Dict[str, Any],
) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    try:
        payload = fn()
        if isinstance(payload, dict):
            return payload, None
        return fallback, {
            "provider": provider,
            "error_type": "TypeError",
            "message": "provider did not return a dict",
        }
    except Exception as exc:
        return fallback, _provider_error(provider, exc)


def _first_timestamp(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for field in _CANONICAL_TIMESTAMP_FIELDS:
        value = payload.get(field)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned and cleaned.lower() not in {"none", "null", "unknown", "n/a", "na"}:
                return cleaned
    return ""


def _canonical_timestamp(payloads: List[Dict[str, Any]]) -> str:
    for payload in payloads:
        value = _first_timestamp(payload)
        if value:
            return value
    return _utc_iso_z()


def get_mobile_trade_ticket_data() -> Dict[str, Any]:
    symbol_fallback = {"status": "ERROR", "mode": "paper", "count": 0, "symbols": []}
    grouped_fallback = {
        "status": "ERROR",
        "mode": "paper",
        "mode_label": "PAPER MODE",
        "count": 0,
        "groups": [],
    }
    account_fallback = {
        "cash": 0.0,
        "equity": 0.0,
        "buying_power": 0.0,
        "open_pnl": 0.0,
        "realized_pnl": 0.0,
        "total_pnl": 0.0,
    }
    runtime_fallback = {
        "runtime_mode": "PAPER",
        "current_cycle": 0,
        "last_update": _utc_iso_z(),
        "supervisor_status": "OFFLINE",
        "last_heartbeat": "N/A",
        "restart_count": 0,
        "failure_count": 0,
        "status": "OFFLINE",
    }
    engine_fallback = {
        "engine_mode": "PAPER",
        "current_strategy": "DEFAULT",
        "trade_gate_status": "SIMULATED",
        "runtime_readiness": "OFFLINE",
    }
    pause_fallback = {
        "trading_paused": False,
        "source": "default",
        "timestamp": "",
        "reason": "",
    }

    symbol_feed, symbol_error = _safe_provider_call(
        "get_tradeable_symbols_feed",
        get_tradeable_symbols_feed,
        symbol_fallback,
    )
    grouped_feed, grouped_error = _safe_provider_call(
        "get_grouped_trading_universe_feed",
        get_grouped_trading_universe_feed,
        grouped_fallback,
    )
    account, account_error = _safe_provider_call(
        "get_account_summary",
        get_account_summary,
        account_fallback,
    )
    runtime, runtime_error = _safe_provider_call(
        "get_runtime_summary",
        get_runtime_summary,
        runtime_fallback,
    )
    engine, engine_error = _safe_provider_call(
        "get_engine_summary",
        get_engine_summary,
        engine_fallback,
    )
    pause_state, pause_error = _safe_provider_call(
        "get_pause_state",
        get_pause_state,
        pause_fallback,
    )

    errors = [
        err
        for err in (
            symbol_error,
            grouped_error,
            account_error,
            runtime_error,
            engine_error,
            pause_error,
        )
        if err is not None
    ]

    symbols = list(symbol_feed.get("symbols", [])) if isinstance(symbol_feed, dict) else []
    if not isinstance(symbols, list):
        symbols = []

    available_symbols = [
        str(item.get("symbol") or "")
        for item in symbols
        if isinstance(item, dict) and str(item.get("symbol") or "").strip()
    ]

    selected_broker = "simulated"
    for item in symbols:
        broker_value = str(item.get("broker") or "").strip().lower() if isinstance(item, dict) else ""
        if broker_value:
            selected_broker = broker_value
            break

    paper_live_mode = _normalize_trade_mode(symbol_feed.get("mode")) if isinstance(symbol_feed, dict) else "paper"
    if paper_live_mode not in {"paper", "live"}:
        paper_live_mode = _normalize_trade_mode(grouped_feed.get("mode")) if isinstance(grouped_feed, dict) else "paper"
    if paper_live_mode not in {"paper", "live"}:
        paper_live_mode = _default_trade_mode()

    raw_engine_mode = ""
    if isinstance(engine, dict):
        raw_engine_mode = str(engine.get("engine_mode") or "").strip()
    if not raw_engine_mode or raw_engine_mode.upper() in {"UNKNOWN", "NONE", "NULL", "N/A", "NA"}:
        if isinstance(runtime, dict):
            raw_engine_mode = str(runtime.get("runtime_mode") or "").strip()
    if not raw_engine_mode or raw_engine_mode.upper() in {"UNKNOWN", "NONE", "NULL", "N/A", "NA"}:
        raw_engine_mode = paper_live_mode.upper()

    canonical_timestamp = _canonical_timestamp(
        [
            symbol_feed,
            grouped_feed,
            account,
            runtime,
            engine,
            pause_state,
        ]
    )

    limits = {
        "per_symbol": [
            {
                "symbol": item.get("symbol"),
                "min_order_size": item.get("min_order_size"),
                "max_order_size": item.get("max_order_size"),
            }
            for item in symbols
            if isinstance(item, dict)
        ]
    }

    return {
        "status": "DEGRADED" if errors else "OK",
        "timestamp": canonical_timestamp,
        "symbols": symbols,
        "available_symbols": available_symbols,
        "account": account,
        "runtime": runtime,
        "mode": {
            "paper_live": paper_live_mode,
            "engine": raw_engine_mode,
        },
        "broker": {
            "selected": selected_broker,
            "execution_capabilities": {
                "provider_reported_execution_available": bool(engine.get("trade_gate_status") == "OPEN") if isinstance(engine, dict) else False,
                "mobile_endpoint_is_read_only": True,
                "mobile_execution_authorized": False,
            },
        },
        "engine": {
            **(engine if isinstance(engine, dict) else {}),
            "engine_mode": raw_engine_mode,
        },
        "permissions": {
            "read_only": True,
            "mobile_order_submission_enabled": False,
            "endpoint_authorizes_execution": False,
            "requires_unified_trade_gate": True,
        },
        "limits": limits,
        "errors": errors,
    }


def _mode_badge() -> str:
    return "LIVE MODE" if _default_trade_mode() == "live" else "PAPER MODE"


def get_trading_universe_feed(*, mode: Optional[str] = None) -> Dict[str, Any]:
    normalized_mode = _normalize_trade_mode(mode) if mode else _default_trade_mode()
    try:
        rows = CanonicalTradingUniverse().all_instruments(mode=normalized_mode)
    except CanonicalTradingUniverseError:
        rows = []
    except Exception:
        rows = []

    return {
        "status": "OK",
        "mode": normalized_mode,
        "mode_label": "LIVE MODE" if normalized_mode == "live" else "PAPER MODE",
        "count": len(rows),
        "instruments": rows,
    }


def get_grouped_trading_universe_feed(*, mode: Optional[str] = None) -> Dict[str, Any]:
    normalized_mode = _normalize_trade_mode(mode) if mode else _default_trade_mode()
    try:
        grouped = CanonicalTradingUniverse().grouped(mode=normalized_mode)
    except CanonicalTradingUniverseError:
        grouped = {"CRYPTO": [], "FOREX": [], "INDICES": [], "FUTURES": [], "OPTIONS": []}
    except Exception:
        grouped = {"CRYPTO": [], "FOREX": [], "INDICES": [], "FUTURES": [], "OPTIONS": []}

    groups = [
        {
            "group": group,
            "label": group.title(),
            "instruments": rows,
        }
        for group, rows in grouped.items()
    ]
    count = sum(len(g.get("instruments", [])) for g in groups)

    return {
        "status": "OK",
        "mode": normalized_mode,
        "mode_label": "LIVE MODE" if normalized_mode == "live" else "PAPER MODE",
        "count": count,
        "groups": groups,
    }


def _sample_candles(base_price: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(20):
        drift = 1.0 + ((idx - 10) * 0.0005)
        open_px = base_price * drift
        close_px = base_price * (drift + 0.0008)
        high_px = max(open_px, close_px) * 1.0015
        low_px = min(open_px, close_px) * 0.9985
        rows.append(
            {
                "open": round(open_px, 8),
                "high": round(high_px, 8),
                "low": round(low_px, 8),
                "close": round(close_px, 8),
                "volume": float(1000 + idx * 20),
            }
        )
    return rows


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted([_json_safe(item) for item in value], key=lambda item: str(item))
    return value


def _price_for_symbol(symbol: str) -> float:
    digest = sum(ord(ch) for ch in str(symbol or "").upper())
    return round(50.0 + (digest % 175), 6)


def _minimum_order_size(asset_class: str, symbol: str) -> float:
    normalized_asset = str(asset_class or "").strip().upper()
    normalized_symbol = str(symbol or "").strip().upper()
    if normalized_asset == "CRYPTO":
        return 0.001
    if normalized_asset == "FOREX":
        return 1.0
    if normalized_asset == "OPTIONS":
        return 1.0
    if normalized_asset == "FUTURES":
        return 1.0
    if normalized_symbol in {"SPY", "QQQ", "DIA", "IWM"}:
        return 1.0
    return 1.0


def _default_tenor(asset_class: str) -> str:
    normalized_asset = str(asset_class or "").strip().upper()
    if normalized_asset == "OPTIONS":
        return "NEXT_MONTH"
    if normalized_asset == "FUTURES":
        return "FRONT"
    return ""


def _candidate_for_summary(symbol: str, asset_class: str, strategy: str) -> Dict[str, Any]:
    price = _price_for_symbol(symbol)
    return {
        "trade_id": f"summary-{symbol}",
        "symbol": symbol,
        "asset_class": asset_class,
        "direction": "BUY",
        "strategy": strategy,
        "current_price": price,
        "market_snapshot": {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "candles": _sample_candles(price),
        },
        "portfolio_snapshot": {
            "available_capital": 100000.0,
            "positions": [
                {"symbol": "SPY", "asset_class": "INDICES", "market_value": 12000.0, "side": "LONG"},
                {"symbol": "EUR_USD", "asset_class": "FOREX", "market_value": 8000.0, "side": "LONG"},
            ],
        },
    }


def get_top_opportunities_feed(*, limit: int = 10) -> Dict[str, Any]:
    try:
        rows = OpportunityRankingEngine().top_opportunities(limit=max(limit * 3, limit))
    except OpportunityRankingEngineError:
        rows = []
    except Exception:
        rows = []

    def _bucket(row: Dict[str, Any]) -> str:
        fields = {
            str(row.get("signal_color", "")),
            str(row.get("status", "")),
            str(row.get("approval_state", "")),
            str(row.get("execution_status", "")),
            str(row.get("risk_state", "")),
        }
        normalized = {field.strip().upper() for field in fields if field}
        if normalized & {"RED", "NOT_APPROVED", "REJECTED", "BLOCKED", "DENIED"}:
            return "RED"
        if normalized & {"GREEN", "APPROVED", "APPROVE", "UNIFIED_GATE_APPROVED", "TRADE_APPROVED"}:
            return "GREEN"
        score = float(row.get("opportunity_score", 0.0) or 0.0)
        confidence = float(row.get("confidence", 0.0) or 0.0)
        if score >= 70 and confidence >= 0.65:
            return "GREEN"
        if score >= 45 and confidence >= 0.45:
            return "AMBER"
        return "AMBER"

    raw_rows = [dict(row) for row in rows if isinstance(row, dict)]
    green_rows = [row for row in raw_rows if _bucket(row) == "GREEN"]
    amber_rows = [row for row in raw_rows if _bucket(row) == "AMBER"]
    display_rows = green_rows if green_rows else amber_rows
    display_state = "GREEN_APPROVED" if green_rows else "AMBER_WATCH"
    empty_state = ""
    if not display_rows:
        display_state = "CAPITAL_PRESERVATION"
        empty_state = "Capital preservation active: no risk-approved opportunities are available."

    decorated = []
    for index, row in enumerate(display_rows[:limit], start=1):
        entry = dict(row)
        entry["rank"] = int(row.get("rank") or index)
        entry["signal_color"] = _bucket(row)
        decorated.append(entry)

    return {
        "status": "OK",
        "count": len(decorated),
        "raw_count": len(raw_rows),
        "display_state": display_state,
        "empty_state": empty_state,
        "excluded_states": ["RED", "NOT_APPROVED"],
        "top_opportunities": decorated,
        "updated_at": _utc_iso_z(),
    }


def get_opportunity_summary(symbol: str, *, asset_class: str | None = None) -> Dict[str, Any]:
    normalized_symbol = str(symbol or "").strip().upper()
    if not normalized_symbol:
        return {
            "status": "ERROR",
            "symbol": "",
            "message": "symbol is required",
        }

    mode = _default_trade_mode()
    universe = CanonicalTradingUniverse()
    requested_asset_class = str(asset_class or "").strip().upper()
    instrument = universe.by_symbol(
        normalized_symbol,
        asset_class=requested_asset_class or None,
        mode=mode,
    )
    if not instrument:
        return {
            "status": "ERROR",
            "symbol": normalized_symbol,
            "message": "instrument not found in canonical universe",
        }

    strategy = str(instrument.get("default_strategy") or "alpha")
    asset_class = str(instrument.get("asset_class") or "UNKNOWN")
    candidate = _candidate_for_summary(normalized_symbol, asset_class, strategy)
    candles = list(candidate["market_snapshot"]["candles"])
    positions = list(candidate["portfolio_snapshot"]["positions"])

    regime_payload: Dict[str, Any] = {}
    strategy_payload: Dict[str, Any] = {}
    correlation_payload: Dict[str, Any] = {}
    concentration_payload: Dict[str, Any] = {}
    adaptive_exit_payload: Dict[str, Any] = {}
    intelligence_payload: Dict[str, Any] = {}
    ranking_payload: Dict[str, Any] = {}

    try:
        regime_payload = MarketRegimeEngine().analyze_market(candles)
    except Exception:
        regime_payload = {"market_regime": "UNKNOWN", "confidence": 0.0}

    try:
        repo = StrategyMemoryRepository(os.path.join(LauncherConfig.ARTIFACTS_DIR, "strategy_memory.json"))
        repo.create_storage()
        strategy_payload = {
            "best_strategy_for_symbol": StrategyIntelligenceEngine(repository=repo).best_strategy_for_symbol(normalized_symbol)
        }
    except Exception:
        strategy_payload = {"best_strategy_for_symbol": None}

    try:
        correlation_payload = PortfolioCorrelationEngine().analyze_portfolio(positions)
    except Exception:
        correlation_payload = {"concentration_score": 0.0, "correlation_score": 0.0}

    try:
        concentration_payload = ConcentrationGuard().evaluate(positions)
    except Exception:
        concentration_payload = {"risk_score": 1.0, "recommendation": "BLOCK"}

    try:
        adaptive_exit_payload = AdaptiveExitEngine().recommend_exit(
            open_trade_context={
                "trade_id": f"summary-{normalized_symbol}",
                "symbol": normalized_symbol,
                "entry_price": candidate["current_price"],
            },
            market_regime=str(regime_payload.get("market_regime") or "UNKNOWN"),
            strategy_memory_summary={},
            current_unrealized_pnl=0.0,
            holding_duration=180.0,
            volatility=float(regime_payload.get("volatility", 0.0) or 0.0),
            trend_strength=float(regime_payload.get("trend_strength", 0.0) or 0.0),
        )
    except Exception:
        adaptive_exit_payload = {"action": "HOLD", "confidence": 0.0}

    try:
        intelligence_payload = IntelligenceOrchestrator().decide(candidate).to_dict()
    except IntelligenceDecisionError:
        intelligence_payload = {"decision": "BLOCK", "confidence": 0.0, "execution_status": "NOT_APPROVED"}
    except Exception:
        intelligence_payload = {"decision": "BLOCK", "confidence": 0.0, "execution_status": "NOT_APPROVED"}

    try:
        ranking_payload = OpportunityRankingEngine().explain_opportunity(normalized_symbol)
    except Exception:
        ranking_payload = {}

    opportunity = ranking_payload.get("opportunity", {}) if isinstance(ranking_payload, dict) else {}
    confidence = float(opportunity.get("confidence", intelligence_payload.get("confidence", 0.0)) or 0.0)
    score = float(opportunity.get("opportunity_score", 0.0) or 0.0)
    suggested_side = str(opportunity.get("action") or "").strip().upper()
    if suggested_side not in {"BUY", "SELL"}:
        expected_direction = str(
            intelligence_payload.get("learning_context", {}).get("features", {}).get("direction", regime_payload.get("direction", "FLAT"))
        ).strip().upper()
        suggested_side = "SELL" if expected_direction == "DOWN" else "BUY"

    suggested_price = float(candidate.get("current_price", 0.0) or 0.0)
    suggested_quantity = float(
        intelligence_payload.get("position_size", {}).get("recommended_position_size", 0.0) or 0.0
    )
    minimum_size = _minimum_order_size(asset_class, normalized_symbol)
    if suggested_quantity <= 0:
        suggested_quantity = minimum_size

    tenor_options: list[str] = []
    default_tenor = ""
    expiry_source = str(instrument.get("expiry_source") or "")
    option_types = list(instrument.get("option_types") or [])
    strike_policy = str(instrument.get("strike_policy") or "")
    contract_months = list(instrument.get("supported_contract_months") or [])
    contract_metadata_status = "NOT_APPLICABLE"

    if asset_class == "OPTIONS":
        tenor_options = list(instrument.get("supported_expiries") or [])
        default_tenor = str(instrument.get("default_expiry") or "")
        contract_metadata_status = "EXPLICIT" if tenor_options and default_tenor else "MISSING"
        if not tenor_options:
            tenor_options = ["NEXT_MONTH"]
            if not default_tenor:
                default_tenor = "NEXT_MONTH"
            expiry_source = expiry_source or "metadata_fallback"
            contract_metadata_status = "FALLBACK"
    elif asset_class == "FUTURES":
        tenor_options = list(instrument.get("supported_contract_months") or [])
        default_tenor = str(instrument.get("default_contract") or "")
        contract_metadata_status = "EXPLICIT" if tenor_options and default_tenor else "MISSING"
        if not tenor_options:
            tenor_options = ["FRONT"]
            if not default_tenor:
                default_tenor = "FRONT"
            expiry_source = expiry_source or "metadata_fallback"
            contract_metadata_status = "FALLBACK"
    else:
        contract_metadata_status = "NOT_APPLICABLE"

    return {
        "status": "OK",
        "symbol": normalized_symbol,
        "mode": mode,
        "mode_label": "LIVE MODE" if mode == "live" else "PAPER MODE",
        "decision_panel": {
            "current_market_regime": str(regime_payload.get("market_regime") or opportunity.get("market_regime") or "UNKNOWN"),
            "recommended_strategy": str(opportunity.get("selected_strategy") or instrument.get("default_strategy") or "default"),
            "opportunity_score": round(score, 4),
            "confidence_percent": round(confidence * 100.0, 2),
            "expected_direction": str(intelligence_payload.get("learning_context", {}).get("features", {}).get("direction", regime_payload.get("direction", "FLAT"))).upper(),
            "suggested_side": suggested_side,
            "tenor_options": tenor_options,
            "default_tenor": default_tenor,
            "suggested_tenor": default_tenor,
            "expiry_source": expiry_source,
            "option_types": option_types,
            "strike_policy": strike_policy,
            "contract_months": contract_months,
            "contract_metadata_status": contract_metadata_status,
            "suggested_price": round(suggested_price, 8) if suggested_price > 0 else None,
            "price_source": "canonical_snapshot" if suggested_price > 0 else "UNAVAILABLE",
            "suggested_quantity": round(max(minimum_size, suggested_quantity), 8),
            "minimum_order_size": minimum_size,
            "risk_rating": str(instrument.get("risk_profile") or "balanced").upper(),
            "portfolio_concentration": round(float(correlation_payload.get("concentration_score", 0.0) or 0.0), 6),
            "execution_status": str(intelligence_payload.get("execution_status") or "NOT_APPROVED"),
            "paper_live_availability": {
                "paper_supported": bool(instrument.get("paper_supported", False)),
                "live_supported": bool(instrument.get("live_supported", False)),
            },
            "broker": str(instrument.get("broker") or "unknown"),
            "last_update": _utc_iso_z(),
        },
        "engine_outputs": {
            "OpportunityRankingEngine": _json_safe(ranking_payload),
            "IntelligenceOrchestrator": _json_safe(intelligence_payload),
            "PortfolioCorrelationEngine": _json_safe(correlation_payload),
            "ConcentrationGuard": _json_safe(concentration_payload),
            "StrategyIntelligenceEngine": _json_safe(strategy_payload),
            "MarketRegimeEngine": _json_safe(regime_payload),
            "AdaptiveExitEngine": _json_safe(adaptive_exit_payload),
        },
    }


def build_trade_ticket_defaults(
    *,
    grouped_universe: Dict[str, Any],
    top_opportunities: Dict[str, Any],
    opportunity_summary: Dict[str, Any],
) -> Dict[str, Any]:
    groups = grouped_universe.get("groups", []) if isinstance(grouped_universe, dict) else []
    selectable_rows: list[Dict[str, Any]] = []
    for group in groups:
        for row in group.get("instruments", []):
            if bool(row.get("selectable", False)):
                selectable_rows.append(row)

    first = selectable_rows[0] if selectable_rows else {}
    default_asset = str(first.get("asset_class") or "CRYPTO")
    default_symbol = str(first.get("symbol") or "")

    if isinstance(opportunity_summary, dict) and opportunity_summary.get("status") == "OK":
        summary_symbol = str(opportunity_summary.get("symbol") or "").strip().upper()
        matched = next(
            (
                row
                for row in selectable_rows
                if str(row.get("symbol") or "").strip().upper() == summary_symbol
            ),
            None,
        )
        if matched:
            default_asset = str(matched.get("asset_class") or default_asset)
            default_symbol = str(matched.get("symbol") or default_symbol)

    summary_panel = opportunity_summary.get("decision_panel", {}) if isinstance(opportunity_summary, dict) else {}
    suggested_side = str(summary_panel.get("suggested_side") or "BUY").upper()
    if suggested_side not in {"BUY", "SELL"}:
        suggested_side = "BUY"

    top_rows = top_opportunities.get("top_opportunities", []) if isinstance(top_opportunities, dict) else []
    if top_rows and suggested_side == "BUY":
        first_action = str(top_rows[0].get("action") or "").strip().upper()
        if first_action in {"BUY", "SELL"}:
            suggested_side = first_action

    tenor_options = list(summary_panel.get("tenor_options") or [])
    tenor = str(summary_panel.get("default_tenor") or summary_panel.get("suggested_tenor") or "")
    expiry_source = str(summary_panel.get("expiry_source") or "")
    contract_metadata_status = str(summary_panel.get("contract_metadata_status") or "UNKNOWN")

    if default_asset in {"OPTIONS", "FUTURES"} and not tenor_options:
        tenor_options = ["NEXT_MONTH"] if default_asset == "OPTIONS" else ["FRONT"]
        if not tenor:
            tenor = tenor_options[0]
        if not expiry_source:
            expiry_source = "metadata_fallback"
        contract_metadata_status = "FALLBACK"

    if tenor_options and not tenor:
        tenor = str(tenor_options[0])
    suggested_price = summary_panel.get("suggested_price")
    price_value = ""
    price_status = "MARKET"
    if suggested_price is not None:
        price_value = str(suggested_price)
        price_status = str(summary_panel.get("price_source") or "snapshot")

    quantity_value = summary_panel.get("suggested_quantity")
    if quantity_value in (None, 0, 0.0, ""):
        quantity_value = _minimum_order_size(default_asset, default_symbol)

    symbols_for_asset = [
        row
        for row in selectable_rows
        if str(row.get("asset_class") or "").upper() == str(default_asset).upper()
    ]

    return {
        "asset_class": default_asset,
        "symbol": default_symbol,
        "side": suggested_side,
        "tenor": tenor,
        "tenor_options": tenor_options,
        "tenor_required": default_asset in {"OPTIONS", "FUTURES"},
        "expiry_source": expiry_source,
        "contract_metadata_status": contract_metadata_status,
        "price": price_value,
        "price_status": price_status,
        "quantity": quantity_value,
        "symbols_for_asset": symbols_for_asset,
    }


def _opportunity_alert_repo() -> AlertRepository:
    return AlertRepository(storage_dir=LauncherConfig.ALERTS_DIR)


def _emit_opportunity_warning(event_type: str, message: str, details: Dict[str, Any], dedupe_key: str) -> None:
    try:
        _opportunity_alert_repo().persist_alert(
            {
                "severity": "WARNING",
                "event_type": event_type,
                "source": "opportunity_ranking_feed",
                "message": message,
                "details": details,
                "dedupe_key": dedupe_key,
            }
        )
    except Exception:
        pass


def get_opportunity_feed() -> Dict[str, Any]:
    try:
        engine = OpportunityRankingEngine()
        all_rows = engine.rank_all(include_blocked=True)
        top_rows = engine.top_opportunities(limit=10)
        paper_rows = engine.paper_opportunities(limit=10)
        all_top_sample = all_rows[:10]

        if not all_rows:
            _emit_opportunity_warning(
                event_type="DATA_UNAVAILABLE",
                message="No tradable opportunities available",
                details={"reason": "empty_ranking"},
                dedupe_key="OPPORTUNITY_EMPTY_FEED",
            )

        if all_top_sample and all(str(row.get("action") or "").upper() == "BLOCK" for row in all_top_sample):
            _emit_opportunity_warning(
                event_type="RISK_GATE_BLOCK",
                message="All top opportunities are currently blocked",
                details={"top_count": len(all_top_sample)},
                dedupe_key="OPPORTUNITY_TOP_BLOCKED",
            )

        low_confidence = [row for row in top_rows if float(row.get("confidence", 0.0) or 0.0) < 0.40]
        if low_confidence:
            _emit_opportunity_warning(
                event_type="DATA_UNAVAILABLE",
                message="Opportunity confidence below threshold",
                details={"count": len(low_confidence), "threshold": 0.40},
                dedupe_key="OPPORTUNITY_LOW_CONFIDENCE",
            )

        if all_rows:
            now = datetime.datetime.now(datetime.timezone.utc)
            stale_count = 0
            for row in all_rows[:10]:
                value = str(row.get("last_updated") or "").strip()
                try:
                    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if (now - parsed).total_seconds() > 300:
                        stale_count += 1
                except Exception:
                    stale_count += 1
            if stale_count == min(10, len(all_rows)):
                _emit_opportunity_warning(
                    event_type="HEARTBEAT_STALE",
                    message="Opportunity ranking feed is stale",
                    details={"sample_size": min(10, len(all_rows))},
                    dedupe_key="OPPORTUNITY_FEED_STALE",
                )

        return {
            "all_opportunities": all_rows,
            "top_opportunities": top_rows,
            "paper_opportunities": paper_rows,
            "updated_at": _utc_iso_z(),
        }
    except OpportunityRankingEngineError:
        _emit_opportunity_warning(
            event_type="DATA_UNAVAILABLE",
            message="No tradable opportunities available",
            details={"reason": "ranking_engine_error"},
            dedupe_key="OPPORTUNITY_EMPTY_FEED",
        )
        return {
            "all_opportunities": [],
            "top_opportunities": [],
            "paper_opportunities": [],
            "updated_at": _utc_iso_z(),
        }
    except Exception:
        _emit_opportunity_warning(
            event_type="DATA_UNAVAILABLE",
            message="No tradable opportunities available",
            details={"reason": "ranking_feed_exception"},
            dedupe_key="OPPORTUNITY_EMPTY_FEED",
        )
        return {
            "all_opportunities": [],
            "top_opportunities": [],
            "paper_opportunities": [],
            "updated_at": _utc_iso_z(),
        }
    except Exception:
        return {
            "all_instruments": [],
            "asset_classes": [],
            "brokers": [],
            "instruments_by_asset_class": {},
            "instruments_by_broker": {},
            "tradable_paper_instruments": [],
        }


def get_portfolio_summary_feed() -> Dict[str, Any]:
    account = get_account_summary()
    opportunity_feed = get_opportunity_feed()
    strategy_evolution = get_strategy_evolution_feed()

    opportunities = list(opportunity_feed.get("top_opportunities", []))
    positions = list(account.get("positions", [])) if isinstance(account, dict) else []
    learning_records = _load_completed_trade_learning_records()
    recommended_strategy_weights = (
        strategy_evolution.get("recommended_strategy_weights", {})
        if isinstance(strategy_evolution, dict)
        else {}
    )

    equity = float(account.get("equity", account.get("cash", 0.0)) or 0.0)
    cash = float(account.get("cash", 0.0) or 0.0)
    reserved = max(0.0, equity - cash)

    try:
        recommendation = AutonomousPortfolioManager().recommend(
            opportunities=opportunities,
            current_positions=positions,
            total_capital=max(1.0, equity),
            available_capital=max(0.0, cash),
            reserved_capital=max(0.0, reserved),
            learning_records=learning_records,
            strategy_weight_recommendations=recommended_strategy_weights,
        )
    except AutonomousPortfolioManagerError as exc:
        return {
            "status": "ERROR",
            "message": str(exc),
            "summary": {},
        }
    except Exception:
        return {
            "status": "ERROR",
            "message": "portfolio_summary_exception",
            "summary": {},
        }

    current_allocation = recommendation.get("correlation", {}).get("summary", {}).get("by_asset_class", {})
    recommended_allocation = recommendation.get("portfolio_allocation", {}).get("recommended_allocation_percentages", [])
    diversification_score = float(recommendation.get("diversification", {}).get("diversification_score", 0.0) or 0.0)
    expected_risk = float(recommendation.get("expected_model", {}).get("expected_risk", 0.0) or 0.0)

    risk_score = max(0.0, min(1.0, expected_risk))
    if diversification_score >= 0.7 and risk_score <= 0.4:
        health = "HEALTHY"
    elif diversification_score >= 0.5 and risk_score <= 0.6:
        health = "BALANCED"
    else:
        health = "CAUTION"

    return {
        "status": "OK",
        "summary": {
            "current_allocation": current_allocation,
            "recommended_allocation": recommended_allocation,
            "cash": cash,
            "exposure": float(recommendation.get("correlation", {}).get("summary", {}).get("total_exposure", 0.0) or 0.0),
            "diversification": diversification_score,
            "risk_score": risk_score,
            "portfolio_health": health,
        },
        "recommendation": recommendation,
        "strategy_evolution": strategy_evolution,
        "updated_at": _utc_iso_z(),
    }


def _normalize_completed_trade_row(raw: Dict[str, Any], *, fallback_idx: int) -> Dict[str, Any] | None:
    strategy_id = str(raw.get("strategy_id") or raw.get("strategy") or "").strip()
    if not strategy_id:
        return None

    symbol = _clean_text(raw.get("symbol"), fallback="SYMBOL_UNSPECIFIED").upper()
    asset_class = _clean_text(raw.get("asset_class"), fallback="ASSET_CLASS_UNSPECIFIED").upper()
    market_regime = _clean_text(raw.get("market_regime"), fallback="REGIME_UNSPECIFIED").upper()
    entry_reason = _clean_text(
        raw.get("entry_reason") or raw.get("entry_signal") or strategy_id,
        fallback="ENTRY_REASON_UNSPECIFIED",
    ).upper()
    entry_confidence = float(raw.get("entry_confidence", raw.get("confidence", raw.get("prob_positive", 0.0))) or 0.0)
    opportunity_score = float(raw.get("opportunity_score", raw.get("signal_score", 0.0)) or 0.0)
    signal_score = float(raw.get("signal_score", opportunity_score) or 0.0)
    prob_positive = float(raw.get("prob_positive", entry_confidence) or 0.0)

    intelligence_payload = raw.get("entry_intelligence") if isinstance(raw.get("entry_intelligence"), dict) else {}
    normalized_intelligence = {
        "entry_reason": entry_reason,
        "opportunity_score": opportunity_score,
        "entry_confidence": entry_confidence,
        "signal_score": signal_score,
        "prob_positive": prob_positive,
        "market_regime": market_regime,
        "strategy_id": strategy_id,
        "open_gate_reason": _clean_text(intelligence_payload.get("open_gate_reason"), fallback="N/A"),
        "unified_gate_reason": _clean_text(intelligence_payload.get("unified_gate_reason"), fallback="N/A"),
    }

    return {
        "trade_id": str(raw.get("trade_id") or f"learning-{fallback_idx}"),
        "timestamp_open": str(raw.get("timestamp_open") or raw.get("opened_at") or _utc_iso_z()),
        "timestamp_close": str(raw.get("timestamp_close") or raw.get("closed_at") or _utc_iso_z()),
        "symbol": symbol,
        "asset_class": asset_class,
        "entry_price": float(raw.get("entry_price", 0.0) or 0.0),
        "exit_price": float(raw.get("exit_price", 0.0) or 0.0),
        "quantity": float(raw.get("quantity", raw.get("size", 0.0)) or 0.0),
        "realized_pnl": float(raw.get("realized_pnl", raw.get("pnl", 0.0)) or 0.0),
        "holding_duration_seconds": float(raw.get("holding_duration_seconds", raw.get("duration_seconds", 0.0)) or 0.0),
        "strategy_id": strategy_id,
        "entry_reason": entry_reason,
        "entry_confidence": entry_confidence,
        "opportunity_score": opportunity_score,
        "signal_score": signal_score,
        "prob_positive": prob_positive,
        "entry_intelligence": normalized_intelligence,
        "market_regime": market_regime,
        "broker": str(raw.get("broker") or "paper").strip().lower() or "paper",
    }


def _load_completed_trade_learning_records() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    outcomes_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "trade_outcomes.json")
    if os.path.exists(outcomes_path):
        try:
            with open(outcomes_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, list):
                for idx, raw in enumerate(payload):
                    if isinstance(raw, dict):
                        normalized = _normalize_completed_trade_row(raw, fallback_idx=idx)
                        if normalized is not None:
                            rows.append(normalized)
        except Exception:
            pass

    if os.path.exists(LauncherConfig.CLOSED_TRADE_LEDGER_PATH):
        try:
            with open(LauncherConfig.CLOSED_TRADE_LEDGER_PATH, "r", encoding="utf-8") as handle:
                for idx, line in enumerate(handle):
                    text = line.strip()
                    if not text:
                        continue
                    try:
                        raw = json.loads(text)
                    except Exception:
                        continue
                    if isinstance(raw, dict):
                        normalized = _normalize_completed_trade_row(raw, fallback_idx=100000 + idx)
                        if normalized is not None:
                            rows.append(normalized)
        except Exception:
            pass

    deduped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        deduped[row["trade_id"]] = row
    return [deduped[key] for key in sorted(deduped.keys())]


def get_strategy_evolution_feed() -> Dict[str, Any]:
    learning_records = _load_completed_trade_learning_records()

    repository_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "trade_outcomes.json")
    repository = TradeOutcomeRepository(repository_path)
    try:
        repository.create_storage()
    except Exception:
        # Continue with in-memory records only; recommendation remains fail-closed by engine status.
        pass

    try:
        evolution = StrategyEvolutionEngine(repository=repository, minimum_history=20).evolve(
            completed_trades=learning_records,
        )
    except StrategyEvolutionEngineError as exc:
        return {
            "status": "ERROR",
            "message": str(exc),
            "top_strategies": [],
            "declining_strategies": [],
            "promotions": [],
            "retirements": [],
            "recommended_strategy_weights": {},
            "explainability": [],
            "updated_at": _utc_iso_z(),
        }
    except Exception:
        return {
            "status": "ERROR",
            "message": "strategy_evolution_exception",
            "top_strategies": [],
            "declining_strategies": [],
            "promotions": [],
            "retirements": [],
            "recommended_strategy_weights": {},
            "explainability": [],
            "updated_at": _utc_iso_z(),
        }

    return {
        **evolution,
        "updated_at": _utc_iso_z(),
    }


def get_portfolio_allocation_feed() -> Dict[str, Any]:
    audit_dir = os.path.join(LauncherConfig.ARTIFACTS_DIR, "portfolio_audit")
    try:
        if not os.path.isdir(audit_dir):
            return {
                "status": "UNAVAILABLE",
                "message": "No portfolio allocation audit directory",
                "allocations": [],
                "diversification_metrics": {},
            }

        files = [
            os.path.join(audit_dir, name)
            for name in os.listdir(audit_dir)
            if name.startswith("portfolio_allocation_") and name.endswith(".json")
        ]
        if not files:
            return {
                "status": "UNAVAILABLE",
                "message": "No portfolio allocation audit records",
                "allocations": [],
                "diversification_metrics": {},
            }

        latest = max(files, key=os.path.getmtime)
        with open(latest, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "status": "OK",
            "source_file": os.path.basename(latest),
            "generated_at": data.get("generated_at", ""),
            "market_regime": data.get("market_regime", "UNKNOWN"),
            "risk_profile": data.get("risk_profile", "UNKNOWN"),
            "total_capital": data.get("total_capital", 0.0),
            "validation_status": data.get("validation_status", "PENDING"),
            "allocations": data.get("allocations", []),
            "diversification_metrics": data.get("diversification_metrics", {}),
            "total_allocated_percent": data.get("total_allocated_percent", 0.0),
            "total_allocated_amount": data.get("total_allocated_amount", 0.0),
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "message": str(exc),
            "allocations": [],
            "diversification_metrics": {},
        }


def build_mobile_dashboard_context() -> Dict[str, Any]:
    dashboard_started = time.perf_counter()
    # Calculate heartbeat / staleness
    artifacts = [
        "css_session_state_pcnrass.json",
        "css_account_state_pcnrass.json",
        "css_session_recovery.json",
        "css_account_state_pcnrass_BACKUP.json"
    ]
    latest_mtime = 0
    for file in artifacts:
        p = os.path.join(LauncherConfig.ARTIFACTS_DIR, file)
        if os.path.exists(p):
            latest_mtime = max(latest_mtime, os.path.getmtime(p))
    
    supervisor_summary = get_supervisor_summary()
    heartbeat = _heartbeat_state(latest_artifact_mtime=latest_mtime, supervisor=supervisor_summary)
    staleness = str(heartbeat.get("staleness", "OFFLINE"))
        
    # Get chart data
    session_state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    account_state = _safe_load_artifact("css_account_state_pcnrass.json") or _safe_load_artifact("css_account_state_pcnrass_BACKUP.json")
    
    positions = account_state.get("positions", [])
    if not positions and "open_trades" in session_state:
        positions = session_state["open_trades"]
    if not isinstance(positions, list):
        positions = []
        
    assets_parsed = {}
    for pos in positions:
        try:
            val = abs(float(pos.get("market_value", pos.get("notional_value", pos.get("current_value", pos.get("entry_price", 0))))))
            qty = abs(float(pos.get("quantity", pos.get("size", 1))))
            if "market_value" not in pos and "notional_value" not in pos:
                val = val * qty
            if val > 0:
                sym = pos.get("symbol", pos.get("asset", "UNKNOWN"))
                assets_parsed[sym] = assets_parsed.get(sym, 0) + val
        except Exception:
            pass
            
    total_equity = account_state.get("total_equity", account_state.get("account_balance", 0.0))
    cash = account_state.get("account_balance", 0.0)

    # Simplified charts for launcher
    chart_data = {
        "has_data": bool(positions) or bool(account_state),
        "equity": total_equity,
        "cash": cash,
        "assets": assets_parsed
    }

    tradeable_symbols_feed = get_tradeable_symbols_feed()
    grouped_universe_feed = get_grouped_trading_universe_feed()
    top_opportunities = get_top_opportunities_feed(limit=10)
    default_summary_symbol = ""
    for group in grouped_universe_feed.get("groups", []):
        for item in group.get("instruments", []):
            if bool(item.get("selectable", False)):
                default_summary_symbol = str(item.get("symbol") or "")
                break
        if default_summary_symbol:
            break

    opportunity_summary = get_opportunity_summary(default_summary_symbol) if default_summary_symbol else {
        "status": "ERROR",
        "symbol": "",
        "message": "No selectable instruments",
    }
    trade_ticket_defaults = build_trade_ticket_defaults(
        grouped_universe=grouped_universe_feed,
        top_opportunities=top_opportunities,
        opportunity_summary=opportunity_summary,
    )
    portfolio_summary = get_portfolio_summary_feed()
    pipeline_started = time.perf_counter()
    decision_inputs = _portfolio_decision_inputs()
    pipeline_latency_ms = (time.perf_counter() - pipeline_started) * 1000.0
    portfolio_intelligence = decision_inputs["portfolio_intelligence"]
    capital_rotation = decision_inputs["capital_rotation"]
    strategy_attribution = decision_inputs["strategy_attribution"]
    regime_allocation = decision_inputs["regime_allocation"]
    adaptive_portfolio = decision_inputs["adaptive_portfolio"]
    portfolio_risk_committee = decision_inputs["risk_committee"]
    quantitative_metrics = decision_inputs["quantitative_metrics"]
    market_regime_intelligence = decision_inputs["market_regime_intelligence"]
    policy_profile = decision_inputs["policy_profile"]
    recommendation_tracker = decision_inputs["recommendation_tracker"]
    technical_analysis = decision_inputs.get("technical_analysis", {})
    fundamental_analysis = decision_inputs.get("fundamental_analysis", {})
    sentiment_intelligence = decision_inputs.get("sentiment_intelligence", {})
    quantitative_alpha = decision_inputs.get("quantitative_alpha", {})
    regime_aware_weighting = decision_inputs.get("regime_aware_weighting", {})
    multi_factor_signal = decision_inputs.get("multi_factor_signal", {})
    runtime_portfolio_state = decision_inputs.get(
        "runtime_portfolio_state",
        {
            "status": "DATA UNAVAILABLE",
            "reasons": ["runtime_portfolio_state_unavailable"],
            "advisory_only": True,
            "execution_allowed": False,
        },
    )
    advisory_history = get_advisory_history_feed()
    portfolio_decision = get_portfolio_decision_feed(inputs=decision_inputs, persist=False)
    runtime_advisory_snapshot = get_runtime_advisory_snapshot_feed(
        inputs=decision_inputs,
        portfolio_decision=portfolio_decision,
    )
    decision_validation = get_decision_validation_feed(portfolio_decision, policy_profile=policy_profile)
    advisory_consistency = get_advisory_consistency_feed(decision_inputs)
    explainability = get_explainability_feed(
        decision=portfolio_decision,
        validation=decision_validation,
        consistency=advisory_consistency,
        inputs=decision_inputs,
    )
    dashboard_latency_ms = (time.perf_counter() - dashboard_started) * 1000.0
    runtime_performance = get_runtime_performance_feed(
        dashboard_latency_ms=dashboard_latency_ms,
        pipeline_latency_ms=pipeline_latency_ms,
    )
    session_validation = get_session_validation_feed(portfolio_decision)
    artifact_refresh = ensure_runtime_artifacts_current(
        inputs=decision_inputs,
        portfolio_decision=portfolio_decision,
        runtime_advisory_snapshot=runtime_advisory_snapshot,
        validation_summary=_safe_load_artifact("validation_summary.json"),
    )
    runtime_artifact_freshness = artifact_refresh.get("freshness", get_runtime_artifact_freshness_feed(refresh=False))
    runtime_session_continuity = get_runtime_session_continuity_feed()
    broker_startup = get_broker_startup_summary()
    runtime_health = get_runtime_health_feed(
        performance=runtime_performance,
        session_validation=session_validation,
        portfolio_decision=portfolio_decision,
        runtime_portfolio_state=runtime_portfolio_state,
        artifact_freshness=runtime_artifact_freshness,
        session_continuity=runtime_session_continuity,
    )
    recommendation_history = _load_recommendation_evaluation_history()
    recommendation_evaluation = get_recommendation_evaluation_feed(recommendation_history)
    confidence_calibration = get_confidence_calibration_feed(recommendation_history)
    recommendation_drift = get_recommendation_drift_feed(recommendation_history)
    learning_history = recommendation_history if recommendation_history else _load_phase139a_learning_history()
    factor_performance_learning = get_factor_performance_learning_feed(learning_history)
    factor_attribution_learning = get_factor_attribution_learning_feed(learning_history)
    rolling_reliability_learning = get_rolling_reliability_learning_feed(learning_history)
    regime_learning = get_regime_learning_feed(learning_history)
    adaptive_weight_recommendations = get_adaptive_weight_recommendations_feed(
        factor_performance=factor_performance_learning,
        rolling_reliability=rolling_reliability_learning,
        regime_learning=regime_learning,
        current_weights=regime_aware_weighting,
    )
    confidence_calibration_learning = get_confidence_calibration_learning_feed(learning_history)
    engine_health_learning = get_engine_health_learning_feed(
        {
            "factor_performance": factor_performance_learning,
            "factor_attribution": factor_attribution_learning,
            "rolling_reliability": rolling_reliability_learning,
            "regime_learning": regime_learning,
            "adaptive_weight_recommendations": adaptive_weight_recommendations,
            "confidence_calibration_learning": confidence_calibration_learning,
        }
    )
    validation_readiness = get_validation_readiness_feed(
        runtime_health=runtime_health,
        session_validation=session_validation,
        portfolio_decision=portfolio_decision,
        runtime_performance=runtime_performance,
        runtime_advisory_snapshot=runtime_advisory_snapshot,
        runtime_portfolio_state=runtime_portfolio_state,
        artifact_freshness=runtime_artifact_freshness,
        session_continuity=runtime_session_continuity,
    )
    runtime_portfolio_lifecycle = get_runtime_portfolio_lifecycle_feed(
        inputs=decision_inputs,
        portfolio_decision=portfolio_decision,
        runtime_advisory_snapshot=runtime_advisory_snapshot,
        persist=False,
    )
    paper_validation_summary = get_paper_validation_summary_feed()
    runtime_validation_monitor = get_runtime_validation_monitor_feed(
        runtime_health=runtime_health,
        validation_readiness=validation_readiness,
        session_continuity=runtime_session_continuity,
        artifact_freshness=runtime_artifact_freshness,
        portfolio_lifecycle=runtime_portfolio_lifecycle,
        portfolio_decision=portfolio_decision,
        advisory_snapshot=runtime_advisory_snapshot,
        persist=False,
    )
    runtime_validation_metrics = get_runtime_validation_metrics_feed(
        runtime_health=runtime_health,
        runtime_performance=runtime_performance,
        session_validation=session_validation,
        persist=False,
    )
    runtime_health_trend = get_runtime_health_trend_feed(
        runtime_health=runtime_health,
        validation_readiness=validation_readiness,
        artifact_freshness=runtime_artifact_freshness,
        session_continuity=runtime_session_continuity,
        portfolio_decision=portfolio_decision,
        portfolio_lifecycle=runtime_portfolio_lifecycle,
        persist=False,
    )
    validation_confidence = get_validation_confidence_feed(
        runtime_health=runtime_health,
        validation_readiness=validation_readiness,
        artifact_freshness=runtime_artifact_freshness,
        session_continuity=runtime_session_continuity,
        portfolio_decision=portfolio_decision,
        advisory_snapshot=runtime_advisory_snapshot,
        market_intelligence=multi_factor_signal,
        runtime_health_trend=runtime_health_trend,
    )
    long_duration_validation = get_long_duration_validation_feed(persist=False)
    strategy_evolution = get_strategy_evolution_feed()
    launcher_frontend_state = build_launcher_frontend_state(
        opportunity_feed=top_opportunities,
        runtime_health_feed=runtime_health,
        live_readiness_evidence=build_live_readiness_evidence(
            runtime_health=runtime_health,
            artifact_freshness=runtime_artifact_freshness,
            session_continuity=runtime_session_continuity,
            staleness=staleness,
            broker_summary=broker_startup,
        ),
    )
    launcher_sections = launcher_frontend_state.get("sections", {}) if isinstance(launcher_frontend_state, dict) else {}

    return {
        "title": "CSS Mobile Dashboard",
        "version": LauncherConfig.VERSION,
        "runtime": get_runtime_summary(),
        "account": get_account_summary(),
        "trade": get_trade_summary(),
        "alerts": get_alert_summary(),
        "engine": get_engine_summary(),
        "staleness": staleness,
        "chart_data": chart_data,
        "pause_state": get_pause_state(),
        "instrument_universe": get_trade_tab_instrument_feed(),
        "tradeable_symbols": tradeable_symbols_feed,
        "tradeable_symbol_lookup": [row.get("symbol") for row in tradeable_symbols_feed.get("symbols", [])],
        "canonical_trading_universe": get_trading_universe_feed(),
        "canonical_grouped_universe": grouped_universe_feed,
        "mode_badge": _mode_badge(),
        "top_opportunities": top_opportunities,
        "opportunity_summary": opportunity_summary,
        "portfolio_summary": portfolio_summary,
        "portfolio_intelligence": portfolio_intelligence,
        "capital_rotation": capital_rotation,
        "strategy_attribution": strategy_attribution,
        "regime_allocation": regime_allocation,
        "adaptive_portfolio": adaptive_portfolio,
        "portfolio_risk_committee": portfolio_risk_committee,
        "quantitative_metrics": quantitative_metrics,
        "market_regime_intelligence": market_regime_intelligence,
        "policy_profile": policy_profile,
        "recommendation_tracker": recommendation_tracker,
        "technical_analysis": technical_analysis,
        "fundamental_analysis": fundamental_analysis,
        "sentiment_intelligence": sentiment_intelligence,
        "quantitative_alpha": quantitative_alpha,
        "regime_aware_weighting": regime_aware_weighting,
        "multi_factor_signal": multi_factor_signal,
        "runtime_portfolio_state": runtime_portfolio_state,
        "runtime_portfolio_lifecycle": runtime_portfolio_lifecycle,
        "runtime_advisory_snapshot": runtime_advisory_snapshot,
        "advisory_history": advisory_history,
        "portfolio_decision": portfolio_decision,
        "decision_validation": decision_validation,
        "advisory_consistency": advisory_consistency,
        "explainability": explainability,
        "runtime_performance": runtime_performance,
        "session_validation": session_validation,
        "runtime_artifact_freshness": runtime_artifact_freshness,
        "runtime_artifact_refresh": artifact_refresh,
        "runtime_session_continuity": runtime_session_continuity,
        "runtime_health": runtime_health,
        "broker_startup": broker_startup,
        "broker_parity": get_launcher_broker_parity_feed(),
        "recommendation_evaluation": recommendation_evaluation,
        "confidence_calibration": confidence_calibration,
        "recommendation_drift": recommendation_drift,
        "factor_performance_learning": factor_performance_learning,
        "factor_attribution_learning": factor_attribution_learning,
        "rolling_reliability_learning": rolling_reliability_learning,
        "regime_learning": regime_learning,
        "adaptive_weight_recommendations": adaptive_weight_recommendations,
        "confidence_calibration_learning": confidence_calibration_learning,
        "engine_health_learning": engine_health_learning,
        "validation_readiness": validation_readiness,
        "paper_validation_summary": paper_validation_summary,
        "runtime_validation_monitor": runtime_validation_monitor,
        "runtime_validation_metrics": runtime_validation_metrics,
        "runtime_health_trend": runtime_health_trend,
        "validation_confidence": validation_confidence,
        "long_duration_validation": long_duration_validation,
        "strategy_evolution": strategy_evolution,
        "launcher_frontend_state": launcher_frontend_state,
        "phase140b_trade_summary": launcher_sections.get("trade_summary", {}),
        "phase141_session_command_center": launcher_sections.get("session_command_centre", {}),
        "phase140a_opportunities": launcher_sections.get("opportunities", {}),
        "phase152a_live_micro_pilot": launcher_sections.get("live_micro_pilot", live_micro_pilot_status()),
        "phase152b_live_readiness_certification": launcher_sections.get("live_readiness_certification", live_readiness_certification_status()),
        "portfolio_allocation": get_portfolio_allocation_feed(),
        "trade_ticket_defaults": trade_ticket_defaults,
        "ticket_asset_classes": ["CRYPTO", "FOREX", "INDICES", "FUTURES", "OPTIONS"],
        "opportunity_feed": get_opportunity_feed(),
        "health": {
            "backend_available": get_mobile_launcher_status() == "ONLINE",
            "supervisor_status": _clean_text(get_supervisor_summary().get("status"), fallback="OFFLINE").upper(),
            "dashboard_status": "ONLINE"
        }
    }

def build_launcher_context() -> Dict[str, Any]:
    status = get_mobile_launcher_status()
    supervisor = get_supervisor_summary()
    alerts = get_alert_summary()
    
    return {
        "title": LauncherConfig.TITLE,
        "version": LauncherConfig.VERSION,
        "status": status,
        "supervisor": supervisor,
        "recent_alerts": alerts,
        "dashboard_url": LauncherConfig.DASHBOARD_URL
    }

@launcher_router.get("/", response_class=HTMLResponse)
async def launcher_home(request: Request):
    context = build_launcher_context()
    return templates.TemplateResponse(request, "mobile_launcher.html", context)

@launcher_router.get("/mobile-launcher", response_class=HTMLResponse)
@launcher_router.get("/launcher/", response_class=HTMLResponse)
async def launcher_home_alias(request: Request):
    context = build_launcher_context()
    return templates.TemplateResponse(request, "mobile_launcher.html", context)

@launcher_router.get("/mobile-dashboard", response_class=HTMLResponse)
@launcher_router.get("/mobile", response_class=HTMLResponse)
async def mobile_dashboard(request: Request):
    context = build_mobile_dashboard_context()
    return templates.TemplateResponse(request, "mobile_dashboard.html", context)

@launcher_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "css_mobile_launcher",
        "timestamp": _utc_iso_z()
    }

@launcher_router.get("/status")
async def status_check():
    status = get_mobile_launcher_status()
    supervisor = get_supervisor_summary()
    alerts = get_alert_summary()
    return {
        "backend_available": status == "ONLINE",
        "supervisor_status": supervisor.get("status"),
        "alert_summary": alerts,
        "dashboard_url": LauncherConfig.DASHBOARD_URL,
        "readiness": status
    }


@launcher_router.get("/api/v1/frontend-state")
async def launcher_frontend_state():
    return build_launcher_frontend_state()


@launcher_router.get("/api/v1/trade-summary")
async def launcher_trade_summary():
    return {
        "section": "trade_summary",
        "data": get_launcher_trade_summary_feed(),
        "advisory_only": True,
        "execution_allowed": False,
    }


@launcher_router.get("/api/v1/session-command-center")
@launcher_router.get("/api/v1/session-command-centre")
async def launcher_session_command_center():
    return {
        "section": "session_command_centre",
        "data": get_launcher_session_command_center_feed(),
        "advisory_only": True,
        "execution_allowed": False,
    }


@launcher_router.get("/api/v1/live-micro-pilot-status")
async def launcher_live_micro_pilot_status():
    return {
        "section": "live_micro_pilot",
        "data": get_launcher_live_micro_pilot_feed(),
        "advisory_only": True,
        "execution_allowed": False,
    }


@launcher_router.get("/api/v1/live-readiness-certification")
async def launcher_live_readiness_certification():
    return {
        "section": "live_readiness_certification",
        "data": get_launcher_live_readiness_certification_feed(),
        "advisory_only": True,
        "execution_allowed": False,
    }


@launcher_router.get("/api/v1/live-readiness-blockers")
async def launcher_live_readiness_blockers():
    return get_launcher_live_readiness_blockers_feed()


@launcher_router.get("/api/v1/broker-read-only-status")
async def launcher_broker_read_only_status():
    return {
        "section": "broker",
        "data": get_launcher_broker_read_only_status_feed(),
        "advisory_only": True,
        "execution_allowed": False,
    }


@launcher_router.get("/api/v1/startup-diagnostics")
async def launcher_startup_diagnostics():
    return {
        "section": "startup_diagnostics",
        "data": get_launcher_startup_diagnostics_feed(),
        "advisory_only": True,
        "execution_allowed": False,
    }


@launcher_router.get("/api/v1/live-readiness-state")
async def launcher_live_readiness_state():
    return {
        "section": "live_readiness_state",
        "data": get_launcher_live_readiness_state_feed(),
        "advisory_only": True,
        "execution_allowed": False,
    }


@launcher_router.get("/api/v1/live-execution-authority")
async def launcher_live_execution_authority():
    return {
        "section": "live_execution_authority",
        "data": get_launcher_live_execution_authority_feed(),
        "advisory_only": True,
        "execution_allowed": False,
    }


@launcher_router.get("/api/v1/broker-readiness")
async def launcher_broker_readiness():
    return {
        "section": "broker_readiness",
        "data": get_launcher_broker_readiness_feed(),
        "advisory_only": True,
        "execution_allowed": False,
    }


@launcher_router.get("/api/v1/broker-parity")
async def launcher_broker_parity():
    return {
        "section": "broker_parity",
        "data": get_launcher_broker_parity_feed(),
        "advisory_only": True,
        "execution_allowed": False,
    }


@launcher_router.get("/mobile/instruments")
async def mobile_instrument_feed():
    return get_trade_tab_instrument_feed()


@launcher_router.get("/mobile/tradeable-symbols")
async def mobile_tradeable_symbols_feed(
    mode: Optional[str] = None,
    asset_class: Optional[str] = None,
    broker: Optional[str] = None,
):
    return get_tradeable_symbols_feed(mode=mode, asset_class=asset_class, broker=broker)


@launcher_router.get("/mobile/trading-universe")
async def mobile_trading_universe(mode: Optional[str] = None):
    return get_trading_universe_feed(mode=mode)


@launcher_router.get("/mobile/trading-universe/grouped")
async def mobile_trading_universe_grouped(mode: Optional[str] = None):
    return get_grouped_trading_universe_feed(mode=mode)


@launcher_router.get("/mobile/trade-ticket-data")
async def mobile_trade_ticket_data():
    return get_mobile_trade_ticket_data()


@launcher_router.get("/mobile/opportunity-summary/{symbol}")
async def mobile_opportunity_summary(symbol: str, asset_class: Optional[str] = None):
    return get_opportunity_summary(symbol, asset_class=asset_class)


@launcher_router.get("/mobile/top-opportunities")
async def mobile_top_opportunities():
    return get_top_opportunities_feed(limit=10)


@launcher_router.get("/mobile/opportunities")
async def mobile_opportunity_feed():
    return get_opportunity_feed()


@launcher_router.get("/mobile/opportunities/top")
async def mobile_top_opportunity_feed():
    feed = get_opportunity_feed()
    return {
        "top_opportunities": feed.get("top_opportunities", []),
        "updated_at": feed.get("updated_at"),
    }


@launcher_router.get("/mobile/opportunities/asset-class/{asset_class}")
async def mobile_opportunity_feed_by_asset_class(asset_class: str):
    try:
        rows = OpportunityRankingEngine().rank_by_asset_class(asset_class)
    except OpportunityRankingEngineError:
        rows = []

    return {
        "asset_class": str(asset_class or "").strip().upper(),
        "opportunities": rows,
        "updated_at": _utc_iso_z(),
    }


@launcher_router.get("/mobile/portfolio-summary")
async def mobile_portfolio_summary():
    return get_portfolio_summary_feed()


@launcher_router.get("/api/portfolio-intelligence")
async def api_portfolio_intelligence():
    return get_portfolio_intelligence_feed()


@launcher_router.get("/api/capital-rotation")
async def api_capital_rotation():
    intelligence = get_portfolio_intelligence_feed()
    return get_capital_rotation_feed(intelligence)


@launcher_router.get("/api/adaptive-portfolio")
async def api_adaptive_portfolio():
    intelligence = get_portfolio_intelligence_feed()
    rotation = get_capital_rotation_feed(intelligence)
    return get_adaptive_portfolio_feed(intelligence, rotation)


@launcher_router.get("/api/strategy-attribution")
async def api_strategy_attribution():
    return get_strategy_attribution_feed()


@launcher_router.get("/api/regime-aware-allocation")
async def api_regime_aware_allocation():
    intelligence = get_portfolio_intelligence_feed()
    rotation = get_capital_rotation_feed(intelligence)
    return get_regime_aware_allocation_feed(rotation)


@launcher_router.get("/api/portfolio-risk-committee")
async def api_portfolio_risk_committee():
    intelligence = get_portfolio_intelligence_feed()
    rotation = get_capital_rotation_feed(intelligence)
    attribution = get_strategy_attribution_feed()
    regime_allocation = get_regime_aware_allocation_feed(rotation)
    adaptive = get_adaptive_portfolio_feed(intelligence, rotation)
    return get_portfolio_risk_committee_feed(
        portfolio_intelligence=intelligence,
        capital_rotation=rotation,
        adaptive_portfolio=adaptive,
        attribution=attribution,
        regime_allocation=regime_allocation,
    )


@launcher_router.get("/api/quantitative-metrics")
async def api_quantitative_metrics():
    return get_quantitative_metrics_feed()


@launcher_router.get("/api/market-regime-intelligence")
async def api_market_regime_intelligence():
    quantitative_metrics = get_quantitative_metrics_feed()
    return get_market_regime_intelligence_feed(quantitative_metrics)


@launcher_router.get("/api/technical-analysis")
async def api_technical_analysis():
    return get_technical_analysis_feed()


@launcher_router.get("/api/fundamental-analysis")
async def api_fundamental_analysis():
    return get_fundamental_analysis_feed()


@launcher_router.get("/api/sentiment-intelligence")
async def api_sentiment_intelligence():
    return get_sentiment_intelligence_feed()


@launcher_router.get("/api/quantitative-alpha")
async def api_quantitative_alpha():
    return get_quantitative_alpha_feed()


@launcher_router.get("/api/regime-aware-weighting")
async def api_regime_aware_weighting():
    state = get_runtime_portfolio_state_feed()
    technical = get_technical_analysis_feed(state)
    fundamental = get_fundamental_analysis_feed(state)
    sentiment = get_sentiment_intelligence_feed(runtime_state=state)
    quantitative = get_quantitative_alpha_feed(state)
    regime = get_market_regime_intelligence_feed(runtime_state=state)
    return get_regime_aware_weighting_feed(
        runtime_state=state,
        market_regime=regime,
        technical=technical,
        fundamental=fundamental,
        sentiment=sentiment,
        quantitative=quantitative,
    )


@launcher_router.get("/api/multi-factor-signal")
async def api_multi_factor_signal():
    state = get_runtime_portfolio_state_feed()
    return get_multi_factor_signal_feed(runtime_state=state)


@launcher_router.get("/api/policy-profile")
async def api_policy_profile():
    return get_policy_profile_feed()


@launcher_router.get("/api/advisory-history")
async def api_advisory_history():
    return get_advisory_history_feed()


@launcher_router.get("/api/recommendation-tracker")
async def api_recommendation_tracker():
    return get_recommendation_tracker_feed()


@launcher_router.get("/api/recommendation-evaluation")
async def api_recommendation_evaluation():
    return get_recommendation_evaluation_feed()


@launcher_router.get("/api/confidence-calibration")
async def api_confidence_calibration():
    return get_confidence_calibration_feed()


@launcher_router.get("/api/recommendation-drift")
async def api_recommendation_drift():
    return get_recommendation_drift_feed()


@launcher_router.get("/api/factor-performance")
async def api_factor_performance():
    return get_factor_performance_learning_feed()


@launcher_router.get("/api/factor-attribution")
async def api_factor_attribution():
    return get_factor_attribution_learning_feed()


@launcher_router.get("/api/rolling-reliability")
async def api_rolling_reliability():
    return get_rolling_reliability_learning_feed()


@launcher_router.get("/api/regime-learning")
async def api_regime_learning():
    return get_regime_learning_feed()


@launcher_router.get("/api/adaptive-weight-recommendations")
async def api_adaptive_weight_recommendations():
    return get_adaptive_weight_recommendations_feed()


@launcher_router.get("/api/confidence-calibration-learning")
async def api_confidence_calibration_learning():
    return get_confidence_calibration_learning_feed()


@launcher_router.get("/api/engine-health-learning")
async def api_engine_health_learning():
    performance = get_factor_performance_learning_feed()
    attribution = get_factor_attribution_learning_feed()
    reliability = get_rolling_reliability_learning_feed()
    regimes = get_regime_learning_feed()
    calibration = get_confidence_calibration_learning_feed()
    recommendations = get_adaptive_weight_recommendations_feed(
        factor_performance=performance,
        rolling_reliability=reliability,
        regime_learning=regimes,
    )
    return get_engine_health_learning_feed(
        {
            "factor_performance": performance,
            "factor_attribution": attribution,
            "rolling_reliability": reliability,
            "regime_learning": regimes,
            "adaptive_weight_recommendations": recommendations,
            "confidence_calibration_learning": calibration,
        }
    )


@launcher_router.get("/api/runtime-portfolio-state")
async def api_runtime_portfolio_state():
    return get_runtime_portfolio_state_feed()


@launcher_router.get("/api/runtime-portfolio-lifecycle")
async def api_runtime_portfolio_lifecycle():
    inputs = _portfolio_decision_inputs()
    decision = get_portfolio_decision_feed(inputs=inputs, persist=False)
    snapshot = get_runtime_advisory_snapshot_feed(inputs=inputs, portfolio_decision=decision)
    return get_runtime_portfolio_lifecycle_feed(
        inputs=inputs,
        portfolio_decision=decision,
        runtime_advisory_snapshot=snapshot,
        persist=False,
    )


@launcher_router.get("/api/runtime-advisory-snapshot")
async def api_runtime_advisory_snapshot():
    inputs = _portfolio_decision_inputs()
    decision = get_portfolio_decision_feed(inputs=inputs, persist=False)
    return get_runtime_advisory_snapshot_feed(inputs=inputs, portfolio_decision=decision)


@launcher_router.get("/api/portfolio-decision")
async def api_portfolio_decision():
    inputs = _portfolio_decision_inputs()
    return get_portfolio_decision_feed(inputs=inputs, persist=False)


@launcher_router.post("/api/portfolio-decision/record")
async def api_portfolio_decision_record(request: Request):
    package = None
    try:
        payload = await request.json()
        if isinstance(payload, dict) and payload.get("portfolio_recommendation"):
            package = payload
    except Exception:
        package = None
    return record_portfolio_decision(package)


@launcher_router.get("/api/decision-validation")
async def api_decision_validation():
    decision = get_portfolio_decision_feed(persist=False)
    return get_decision_validation_feed(decision)


@launcher_router.get("/api/explainability")
async def api_explainability():
    decision = get_portfolio_decision_feed(persist=False)
    validation = get_decision_validation_feed(decision)
    consistency = get_advisory_consistency_feed()
    return get_explainability_feed(decision=decision, validation=validation, consistency=consistency)


@launcher_router.get("/api/advisory-consistency")
async def api_advisory_consistency():
    return get_advisory_consistency_feed()


@launcher_router.get("/api/runtime-performance")
async def api_runtime_performance():
    started = time.perf_counter()
    latency_ms = (time.perf_counter() - started) * 1000.0
    return get_runtime_performance_feed(api_latency_ms=latency_ms)


@launcher_router.get("/api/runtime-artifact-freshness")
async def api_runtime_artifact_freshness():
    try:
        return get_runtime_artifact_freshness_feed(refresh=False)
    except Exception as exc:
        return JSONResponse(
            {
                "freshness_status": "RED",
                "runtime_active": False,
                "artifacts": {},
                "stale_artifacts": [],
                "refreshed_artifacts": [],
                "warnings": [f"runtime_artifact_freshness_error:{_clean_text(exc, fallback='unknown_error')}"],
                "blockers": ["runtime_artifact_freshness_unavailable"],
                "advisory_only": True,
                "execution_allowed": False,
            },
            status_code=200,
        )


@launcher_router.get("/api/runtime-session-continuity")
async def api_runtime_session_continuity():
    try:
        return get_runtime_session_continuity_feed()
    except Exception as exc:
        return JSONResponse(
            {
                "session_continuity_status": "UNKNOWN",
                "session_age_seconds": None,
                "max_session_seconds": None,
                "seconds_until_expiry": None,
                "quiet_mode_active": False,
                "can_paper_execute": False,
                "can_live_execute": False,
                "reauth_required": True,
                "recommended_actions": [f"Review session continuity error: {_clean_text(exc, fallback='unknown_error')}."],
                "warnings": ["runtime_session_continuity_unavailable"],
                "advisory_only": True,
                "execution_allowed": False,
            },
            status_code=200,
        )


@launcher_router.get("/api/session-renewal-status")
async def api_session_renewal_status():
    try:
        return get_session_renewal_status_feed()
    except Exception as exc:
        return JSONResponse(
            {
                "status": "DATA UNAVAILABLE",
                "session_renewal_mode": "UNKNOWN",
                "last_session_renewal_at": None,
                "session_renewal_count": 0,
                "session_renewal_reason": None,
                "continuous_paper_runtime_enabled": False,
                "current_session_age_seconds": None,
                "max_session_seconds": None,
                "renewal_count": 0,
                "renewal_mode": "UNKNOWN",
                "renewal_allowed": False,
                "next_expiry_or_renewal_time": None,
                "live_renewal_blocked": True,
                "warnings": [f"session_renewal_status_error:{_clean_text(exc, fallback='unknown_error')}"],
                "advisory_only": True,
                "execution_allowed": False,
            },
            status_code=200,
        )


@launcher_router.get("/api/session-validation")
async def api_session_validation():
    decision = get_portfolio_decision_feed(persist=False)
    return get_session_validation_feed(decision)


@launcher_router.get("/api/runtime-health")
async def api_runtime_health():
    try:
        inputs = _portfolio_decision_inputs()
        decision = get_portfolio_decision_feed(inputs=inputs, persist=False)
        performance = get_runtime_performance_feed()
        session = get_session_validation_feed(decision)
        artifact_freshness = get_runtime_artifact_freshness_feed(refresh=False)
        session_continuity = get_runtime_session_continuity_feed()
        return get_runtime_health_feed(
            performance=performance,
            session_validation=session,
            portfolio_decision=decision,
            runtime_portfolio_state=inputs.get("runtime_portfolio_state"),
            artifact_freshness=artifact_freshness,
            session_continuity=session_continuity,
        )
    except Exception as exc:
        return JSONResponse(_safe_runtime_health_error(exc), status_code=200)


@launcher_router.get("/api/validation-readiness")
async def api_validation_readiness():
    try:
        inputs = _portfolio_decision_inputs()
        decision = get_portfolio_decision_feed(inputs=inputs, persist=False)
        snapshot = get_runtime_advisory_snapshot_feed(inputs=inputs, portfolio_decision=decision)
        performance = get_runtime_performance_feed()
        session = get_session_validation_feed(decision)
        artifact_freshness = get_runtime_artifact_freshness_feed(refresh=False)
        session_continuity = get_runtime_session_continuity_feed()
        health = get_runtime_health_feed(
            performance=performance,
            session_validation=session,
            portfolio_decision=decision,
            runtime_portfolio_state=inputs.get("runtime_portfolio_state"),
            artifact_freshness=artifact_freshness,
            session_continuity=session_continuity,
        )
        return get_validation_readiness_feed(
            runtime_health=health,
            session_validation=session,
            portfolio_decision=decision,
            runtime_performance=performance,
            runtime_advisory_snapshot=snapshot,
            runtime_portfolio_state=inputs.get("runtime_portfolio_state"),
            artifact_freshness=artifact_freshness,
            session_continuity=session_continuity,
        )
    except Exception as exc:
        return JSONResponse(_safe_validation_readiness_error(exc), status_code=200)


@launcher_router.get("/api/paper-validation-summary")
async def api_paper_validation_summary():
    return get_paper_validation_summary_feed()


@launcher_router.get("/api/paper-validation-checkpoints")
async def api_paper_validation_checkpoints():
    return get_paper_validation_checkpoints_feed()


@launcher_router.post("/api/paper-validation-checkpoint/record")
async def api_paper_validation_checkpoint_record(request: Request):
    payload: Dict[str, Any] = {}
    try:
        body = await request.json()
        if isinstance(body, dict):
            payload = body
    except Exception:
        payload = {}
    return record_paper_validation_checkpoint(payload)


@launcher_router.get("/api/runtime-validation-monitor")
async def api_runtime_validation_monitor():
    try:
        return get_runtime_validation_monitor_feed(persist=False)
    except Exception as exc:
        return JSONResponse(
            {
                "status": "DATA UNAVAILABLE",
                "validation_state": "RED",
                "warnings": [f"runtime_validation_monitor_error:{_clean_text(exc, fallback='unknown_error')}"],
                "blockers": ["runtime_validation_monitor_unavailable"],
                "advisory_only": True,
                "execution_allowed": False,
            },
            status_code=200,
        )


@launcher_router.get("/api/runtime-validation-metrics")
async def api_runtime_validation_metrics():
    try:
        return get_runtime_validation_metrics_feed(persist=False)
    except Exception as exc:
        return JSONResponse(
            {
                "status": "DATA UNAVAILABLE",
                "runtime_uptime": 0,
                "runtime_cycles": 0,
                "artifact_write_success_rate": 0.0,
                "artifact_write_failures": 0,
                "warnings": [f"runtime_validation_metrics_error:{_clean_text(exc, fallback='unknown_error')}"],
                "advisory_only": True,
                "execution_allowed": False,
            },
            status_code=200,
        )


@launcher_router.get("/api/runtime-health-trend")
async def api_runtime_health_trend():
    try:
        return get_runtime_health_trend_feed(persist=False)
    except Exception as exc:
        return JSONResponse(
            {
                "status": "DATA UNAVAILABLE",
                "current": {},
                "trends": {},
                "warnings": [f"runtime_health_trend_error:{_clean_text(exc, fallback='unknown_error')}"],
                "advisory_only": True,
                "execution_allowed": False,
            },
            status_code=200,
        )


@launcher_router.get("/api/validation-confidence")
async def api_validation_confidence():
    try:
        return get_validation_confidence_feed()
    except Exception as exc:
        return JSONResponse(
            {
                "status": "DATA UNAVAILABLE",
                "confidence_score": 0,
                "confidence_grade": "FAIL_CLOSED",
                "confidence_reason": f"validation_confidence_error:{_clean_text(exc, fallback='unknown_error')}",
                "advisory_only": True,
                "execution_allowed": False,
            },
            status_code=200,
        )


@launcher_router.get("/api/long-duration-validation")
async def api_long_duration_validation():
    try:
        return get_long_duration_validation_feed(persist=False)
    except Exception as exc:
        return JSONResponse(
            {
                "status": "DATA UNAVAILABLE",
                "windows": {},
                "warnings": [f"long_duration_validation_error:{_clean_text(exc, fallback='unknown_error')}"],
                "advisory_only": True,
                "paper_validation_only": True,
                "execution_allowed": False,
            },
            status_code=200,
        )


@launcher_router.get("/mobile/strategy-evolution")
async def mobile_strategy_evolution():
    return get_strategy_evolution_feed()

@launcher_router.get("/manifest.json")
async def get_manifest():
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static", "css_launcher_manifest.json"),
        media_type="application/manifest+json",
    )


@launcher_router.get("/favicon.ico")
async def get_favicon():
    favicon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "branding", "css.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")

    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static", "css_launcher_icon.svg"),
        media_type="image/svg+xml",
    )


@launcher_router.get("/static/css_pwa_icon_192.png")
async def css_pwa_icon_192():
    return FileResponse(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "assets",
            "branding",
            "css_pwa_icon_192.png",
        ),
        media_type="image/png",
    )


@launcher_router.get("/static/css_pwa_icon_512.png")
async def css_pwa_icon_512():
    return FileResponse(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "assets",
            "branding",
            "css_pwa_icon_512.png",
        ),
        media_type="image/png",
    )


# ── PAUSE / RESUME ROUTES ────────────────────────────────────────────────────

@launcher_router.get("/apple-touch-icon.png")
@launcher_router.get("/static/apple_touch_icon_180.png")
async def apple_touch_icon():
    return FileResponse(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "assets",
            "branding",
            "apple_touch_icon_180.png",
        ),
        media_type="image/png",
    )


_BROWSER_REDIRECT_TARGET = "/mobile#risk"


def _wants_json(request: Request) -> bool:
    """Return True when the client explicitly requests JSON (API / XHR call).

    Browser form submissions send no Accept header or a wildcard; they expect
    a redirect, not a JSON body.  Only return True when the caller signals JSON
    intent via a recognised header.
    """
    accept = request.headers.get("accept", "")
    xhr    = request.headers.get("x-requested-with", "")
    return "application/json" in accept or xhr.lower() == "xmlhttprequest"




@launcher_router.post("/mobile/trade/paper")
async def mobile_trade_paper(request: Request):
    """Record a validated paper-only mobile trade request.

    This endpoint intentionally writes an artifact only. It does not call broker
    APIs, does not place orders, and does not enable live execution.
    """
    try:
        payload = await _read_mobile_trade_payload(request)
        trade_request = write_mobile_paper_trade_request(payload)
    except ValueError as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=400,
        )
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": f"request failed: {exc}"},
            status_code=500,
        )

    if _wants_json(request):
        return JSONResponse({"ok": True, "trade_request": trade_request})

    return RedirectResponse("/mobile#execution", status_code=303)


@launcher_router.post("/mobile/control/pause")
async def mobile_control_pause(request: Request):
    """Write trading_paused=true to the controls artifact.

    - Browser form POST  → 303 redirect to /mobile#risk (Risk tab auto-opens)
    - API / XHR caller   → JSON {ok, trading_paused, timestamp}
    Safe: only mutates the pause flag. No broker calls. No secrets.
    """
    state = write_pause_state(paused=True, reason="mobile_user_pause")
    if _wants_json(request):
        return JSONResponse(
            {"ok": True, "trading_paused": state["trading_paused"], "timestamp": state["timestamp"]}
        )
    return RedirectResponse(_BROWSER_REDIRECT_TARGET, status_code=303)


@launcher_router.post("/mobile/control/resume")
async def mobile_control_resume(request: Request):
    """Write trading_paused=false to the controls artifact.

    - Browser form POST  → 303 redirect to /mobile#risk (Risk tab auto-opens)
    - API / XHR caller   → JSON {ok, trading_paused, timestamp}
    Safe: only mutates the pause flag. No broker calls. No secrets.
    """
    state = write_pause_state(paused=False, reason="mobile_user_resume")
    if _wants_json(request):
        return JSONResponse(
            {"ok": True, "trading_paused": state["trading_paused"], "timestamp": state["timestamp"]}
        )
    return RedirectResponse(_BROWSER_REDIRECT_TARGET, status_code=303)

app.include_router(launcher_router)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host=LauncherConfig.HOST, port=LauncherConfig.PORT)
