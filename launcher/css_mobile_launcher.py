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
from backend.validation.session_checkpoint_store import SessionCheckpointStore
from backend.validation.validation_readiness_engine import ValidationReadinessEngine
import uvicorn

app = FastAPI(title=LauncherConfig.TITLE, version=LauncherConfig.VERSION)
launcher_router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


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

    now = datetime.datetime.utcnow().isoformat() + "Z"
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
        "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
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
    last_update = _clean_text(session.get("start_time"), fallback=datetime.datetime.utcnow().isoformat() + "Z")
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
    names = [
        "css_session_state_pcnrass.json",
        "css_account_state_pcnrass.json",
        "css_session_recovery.json",
        "css_account_state_pcnrass_BACKUP.json",
    ]
    snapshot: Dict[str, Any] = {}
    latest_mtime = 0.0
    for name in names:
        path = os.path.join(LauncherConfig.ARTIFACTS_DIR, name)
        if os.path.exists(path):
            mtime = os.path.getmtime(path)
            latest_mtime = max(latest_mtime, mtime)
            age = max(0.0, now - mtime)
            snapshot[name] = {"age_seconds": age, "stale_after_seconds": 300, "stale": age > 300}
        else:
            snapshot[name] = {"age_seconds": None, "stale_after_seconds": 300, "stale": True}
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
) -> Dict[str, Any]:
    decision = portfolio_decision or get_portfolio_decision_feed(persist=False)
    perf = performance or get_runtime_performance_feed()
    session = session_validation or get_session_validation_feed(decision)
    return RuntimeHealthAggregator().aggregate(
        performance=perf,
        session_validation=session,
        supervisor_status=get_supervisor_summary(),
        portfolio_decision=decision,
    )


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
) -> Dict[str, Any]:
    decision = portfolio_decision or get_portfolio_decision_feed(persist=False)
    snapshot = runtime_advisory_snapshot or get_runtime_advisory_snapshot_feed(portfolio_decision=decision)
    performance = runtime_performance or get_runtime_performance_feed()
    session = session_validation or get_session_validation_feed(decision)
    health = runtime_health or get_runtime_health_feed(
        performance=performance,
        session_validation=session,
        portfolio_decision=decision,
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
    return datetime.datetime.utcnow().isoformat() + "Z"


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
        "last_update": datetime.datetime.utcnow().isoformat() + "Z",
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
        rows = OpportunityRankingEngine().top_opportunities(limit=limit)
    except OpportunityRankingEngineError:
        rows = []
    except Exception:
        rows = []

    def _color(row: Dict[str, Any]) -> str:
        score = float(row.get("opportunity_score", 0.0) or 0.0)
        confidence = float(row.get("confidence", 0.0) or 0.0)
        if score >= 70 and confidence >= 0.65:
            return "GREEN"
        if score >= 45 and confidence >= 0.45:
            return "AMBER"
        return "RED"

    decorated = []
    for index, row in enumerate(rows[:limit], start=1):
        entry = dict(row)
        entry["rank"] = int(row.get("rank") or index)
        entry["signal_color"] = _color(row)
        decorated.append(entry)

    return {
        "status": "OK",
        "count": len(decorated),
        "top_opportunities": decorated,
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
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
            "last_update": datetime.datetime.utcnow().isoformat() + "Z",
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
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
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
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
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
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
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
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
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
        "timestamp_open": str(raw.get("timestamp_open") or raw.get("opened_at") or datetime.datetime.utcnow().isoformat() + "Z"),
        "timestamp_close": str(raw.get("timestamp_close") or raw.get("closed_at") or datetime.datetime.utcnow().isoformat() + "Z"),
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
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
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
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        }

    return {
        **evolution,
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
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
    
    if latest_mtime > 0:
        age = datetime.datetime.now().timestamp() - latest_mtime
        staleness = "ACTIVE" if age < 60 else "STALE"
    else:
        staleness = "OFFLINE"
        
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
    runtime_health = get_runtime_health_feed(
        performance=runtime_performance,
        session_validation=session_validation,
        portfolio_decision=portfolio_decision,
    )
    recommendation_history = _load_recommendation_evaluation_history()
    recommendation_evaluation = get_recommendation_evaluation_feed(recommendation_history)
    confidence_calibration = get_confidence_calibration_feed(recommendation_history)
    recommendation_drift = get_recommendation_drift_feed(recommendation_history)
    validation_readiness = get_validation_readiness_feed(
        runtime_health=runtime_health,
        session_validation=session_validation,
        portfolio_decision=portfolio_decision,
        runtime_performance=runtime_performance,
        runtime_advisory_snapshot=runtime_advisory_snapshot,
    )
    paper_validation_summary = get_paper_validation_summary_feed()
    strategy_evolution = get_strategy_evolution_feed()

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
        "runtime_portfolio_state": runtime_portfolio_state,
        "runtime_advisory_snapshot": runtime_advisory_snapshot,
        "advisory_history": advisory_history,
        "portfolio_decision": portfolio_decision,
        "decision_validation": decision_validation,
        "advisory_consistency": advisory_consistency,
        "explainability": explainability,
        "runtime_performance": runtime_performance,
        "session_validation": session_validation,
        "runtime_health": runtime_health,
        "recommendation_evaluation": recommendation_evaluation,
        "confidence_calibration": confidence_calibration,
        "recommendation_drift": recommendation_drift,
        "validation_readiness": validation_readiness,
        "paper_validation_summary": paper_validation_summary,
        "strategy_evolution": strategy_evolution,
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
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
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
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
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


@launcher_router.get("/api/runtime-portfolio-state")
async def api_runtime_portfolio_state():
    return get_runtime_portfolio_state_feed()


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


@launcher_router.get("/api/session-validation")
async def api_session_validation():
    decision = get_portfolio_decision_feed(persist=False)
    return get_session_validation_feed(decision)


@launcher_router.get("/api/runtime-health")
async def api_runtime_health():
    inputs = _portfolio_decision_inputs()
    decision = get_portfolio_decision_feed(inputs=inputs, persist=False)
    performance = get_runtime_performance_feed()
    session = get_session_validation_feed(decision)
    return get_runtime_health_feed(
        performance=performance,
        session_validation=session,
        portfolio_decision=decision,
    )


@launcher_router.get("/api/validation-readiness")
async def api_validation_readiness():
    inputs = _portfolio_decision_inputs()
    decision = get_portfolio_decision_feed(inputs=inputs, persist=False)
    snapshot = get_runtime_advisory_snapshot_feed(inputs=inputs, portfolio_decision=decision)
    performance = get_runtime_performance_feed()
    session = get_session_validation_feed(decision)
    health = get_runtime_health_feed(
        performance=performance,
        session_validation=session,
        portfolio_decision=decision,
    )
    return get_validation_readiness_feed(
        runtime_health=health,
        session_validation=session,
        portfolio_decision=decision,
        runtime_performance=performance,
        runtime_advisory_snapshot=snapshot,
    )


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

if __name__ == "__main__":
    uvicorn.run(app, host=LauncherConfig.HOST, port=LauncherConfig.PORT)
