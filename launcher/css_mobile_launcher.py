import os
import json
import datetime
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
            "status": "UNKNOWN",
            "last_heartbeat": "None",
            "message": "Supervisor state missing",
        }

    try:
        with open(state_file, "r") as f:
            state = json.load(f)

        heartbeat = (
            state.get("last_heartbeat")
            or state.get("last_heartbeat_at")
            or "None"
        )

        return {
            "status": state.get("status", "UNKNOWN"),
            "last_heartbeat": heartbeat,
            "failure_count": state.get("failure_count", 0),
            "restart_count": state.get("restart_count", 0),
        }

    except Exception as e:
        return {
            "status": "ERROR",
            "last_heartbeat": "None",
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
    summary = {
        "runtime_mode": session.get("engine_mode", "UNKNOWN"),
        "current_cycle": session.get("cycle_number", 0),
        "last_update": session.get("start_time", "None")
    }
    
    supervisor = get_supervisor_summary()
    summary["supervisor_status"] = supervisor.get("status", "UNKNOWN")
    summary["last_heartbeat"] = supervisor.get("last_heartbeat", "None")
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

def get_engine_summary() -> Dict[str, Any]:
    state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    session = state.get("session", {})
    
    summary = {
        "engine_mode": session.get("engine_mode", "UNKNOWN"),
        "current_strategy": session.get("strategy", "DEFAULT"),
        "trade_gate_status": "OPEN" if session.get("engine_mode") == "LIVE" else "SIMULATED",
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
        }
        for row in symbol_rows
    ]

    return {
        "status": "OK",
        "mode": normalized_mode,
        "count": len(symbols),
        "symbols": symbols,
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

    opportunities = list(opportunity_feed.get("top_opportunities", []))
    positions = list(account.get("positions", [])) if isinstance(account, dict) else []

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
            learning_records=[],
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
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

def build_mobile_dashboard_context() -> Dict[str, Any]:
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
        "trade_ticket_defaults": trade_ticket_defaults,
        "ticket_asset_classes": ["CRYPTO", "FOREX", "INDICES", "FUTURES", "OPTIONS"],
        "opportunity_feed": get_opportunity_feed(),
        "health": {
            "backend_available": get_mobile_launcher_status() == "ONLINE",
            "supervisor_status": get_supervisor_summary().get("status", "UNKNOWN"),
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

@launcher_router.get("/manifest.json")
async def get_manifest():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "css_launcher_manifest.json"))

@launcher_router.get("/favicon.ico")
async def get_favicon():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "css_launcher_icon.svg"), media_type="image/svg+xml")


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
