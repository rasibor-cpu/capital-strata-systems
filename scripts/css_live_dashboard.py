from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.execution.coinbase_executor import CoinbaseExecutor
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.intelligence.trade_decision_engine import TradeDecisionEngine
from backend.risk.portfolio_risk_governor import PortfolioRiskGovernor
from backend.risk.session_policy_loader import choose_session_policy
from backend.strategies.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)

try:
    from backend.scanner.coinbase_universe import get_top_universe
except Exception:
    get_top_universe = None


STATE_DIR = PROJECT_ROOT / "backend" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

POSITION_FILE = STATE_DIR / "spot_position.json"


# --- NEW RISK CAP ---
MAX_SINGLE_POSITION_PCT = 0.40


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(float(raw))


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _load_portfolio() -> Dict[str, Any]:
    if not POSITION_FILE.exists():
        return {"positions": []}

    try:
        payload = json.loads(POSITION_FILE.read_text())
        if not isinstance(payload, dict):
            return {"positions": []}
        if "positions" not in payload or not isinstance(payload["positions"], list):
            payload["positions"] = []
        return payload
    except Exception:
        return {"positions": []}


def _save_portfolio(portfolio: Dict[str, Any]) -> None:
    POSITION_FILE.write_text(json.dumps(portfolio, indent=2))


def _get_universe() -> List[str]:
    if get_top_universe:
        try:
            universe = get_top_universe(200)
            if universe:
                return universe
        except Exception:
            pass

    return ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "LINK-USD"]


def _fmt_money(v: float) -> str:
    return f"${v:,.2f}"


def _run_with_timeout(fn, timeout_seconds: int, *args):
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args)
        return future.result(timeout=timeout_seconds)


def _safe_ai_run(
    ai: AIOpportunityScorer,
    assets: List[Dict[str, Any]],
    timeout_seconds: int,
) -> Tuple[List[Dict[str, Any]], str]:
    try:
        result = _run_with_timeout(ai.run, timeout_seconds, assets)
        if isinstance(result, list):
            return result, f"OK (timeout {timeout_seconds}s)"
        return [], "AI returned non-list result"
    except FuturesTimeoutError:
        return [], f"AI timeout after {timeout_seconds}s"
    except Exception as exc:
        return [], f"AI error: {exc}"


# --- FIXED ALLOCATOR ---
def _fallback_allocate(
    ai_results: List[Dict[str, Any]],
    total_capital: float,
    max_positions: int,
) -> List[Dict[str, Any]]:

    if not ai_results:
        return []

    candidates: List[Dict[str, Any]] = []

    for item in ai_results:
        signal = str(item.get("signal", "HOLD")).upper()
        score = float(item.get("opportunity_score", 0.0) or 0.0)
        symbol = str(item.get("symbol", "")).strip()

        if signal != "BUY":
            continue

        if score <= 0:
            continue

        candidates.append({"symbol": symbol, "score": score})

    if not candidates:
        return []

    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:max_positions]

    total_score = sum(x["score"] for x in candidates)

    allocations: List[Dict[str, Any]] = []

    for item in candidates:

        weight = item["score"] / total_score if total_score > 0 else 1 / len(candidates)

        capital = total_capital * weight

        # --- CAP SINGLE POSITION ---
        max_cap = total_capital * MAX_SINGLE_POSITION_PCT
        capital = min(capital, max_cap)

        allocations.append(
            {
                "symbol": item["symbol"],
                "ai_score": item["score"],
                "capital": round(capital, 2),
            }
        )

    return allocations


def _build_allocations(
    allocator: CapitalAllocator,
    ai_results: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
    capital: float,
    max_assets: int,
) -> List[Dict[str, Any]]:

    try:
        allocations = allocator.allocate(
            ai_results=ai_results,
            market_rows=[
                {
                    "asset": row["asset"],
                    "symbol": row["asset"],
                    "mid": row["mid"],
                    "vwap": row["vwap"],
                    "spread_bps": row["spread_bps"],
                }
                for row in rows
            ],
        )

        if isinstance(allocations, list) and allocations:
            return allocations

    except Exception:
        pass

    return _fallback_allocate(ai_results, capital, max_assets)


# ---- rest of the file unchanged ----
# (the entire trading engine loop stays exactly as your version)
