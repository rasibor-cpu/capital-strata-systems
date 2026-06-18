"""NON-CANONICAL RETIREMENT CANDIDATE.

ARP-011 quarantine marker: this root dashboard is not the current CSS
dashboard authority. Use scripts/css_live_dashboard.py for the canonical live
dashboard path. This file is retained only for historical audit traceability.
"""

from __future__ import annotations

_RETIREMENT_CANDIDATE_MESSAGE = (
    "css_live_dashboard_v5.py is a non-canonical retirement candidate. "
    "Use scripts/css_live_dashboard.py for the canonical CSS live dashboard."
)

if __name__ == "__main__":
    raise SystemExit(_RETIREMENT_CANDIDATE_MESSAGE)

import sys, time, random, json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.execution.position_manager import PositionManager
from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_position_manager import FuturesPositionManager
from backend.scanner.options_chain_adapter import OptionsChainAdapter
from backend.options.options_position_manager import OptionsPositionManager
from backend.options.options_intelligence_engine import OptionsIntelligenceEngine
from backend.options.option_pricing_calibration_engine import OptionPricingCalibrationEngine
from backend.options.option_expiry_parser_engine import OptionExpiryParserEngine

# =========================
# STATE FILES
# =========================

STATE_DIR = PROJECT_ROOT / "artifacts"
STATE_DIR.mkdir(exist_ok=True)

FILES = {
    "crypto_pnl": STATE_DIR / "crypto_pnl.json",
    "fx_pnl": STATE_DIR / "fx_pnl.json",
    "options_pnl": STATE_DIR / "options_pnl.json",
    "futures_pnl": STATE_DIR / "futures_pnl.json",

    "crypto_trades": STATE_DIR / "crypto_trades.json",
    "fx_trades": STATE_DIR / "fx_trades.json",
    "options_trades": STATE_DIR / "options_trades.json",
    "futures_trades": STATE_DIR / "futures_trades.json",

    "crypto_wins": STATE_DIR / "crypto_wins.json",
    "fx_wins": STATE_DIR / "fx_wins.json",
    "options_wins": STATE_DIR / "options_wins.json",
    "futures_wins": STATE_DIR / "futures_wins.json",

    "futures_bias": STATE_DIR / "futures_symbol_bias.json",
    "futures_loss": STATE_DIR / "futures_loss_streak.json"
}

# =========================
# SYMBOLS
# =========================

SYMBOLS = ["BTC-USD","ETH-USD","SOL-USD","XRP-USD","ADA-USD",
           "DOGE-USD","AVAX-USD","LINK-USD","LTC-USD","BCH-USD"]

FX_SYMBOLS = ["EUR_USD","GBP_USD","USD_JPY","USD_CHF",
              "AUD_USD","USD_CAD","NZD_USD",
              "EUR_GBP","EUR_JPY","GBP_JPY"]

FUTURES_SYMBOLS = ["ES","NQ","CL","GC"]

OPTION_SYMBOLS = ["AAPL-C","SPY-C","QQQ-C"]

# =========================
# ENGINE CONSTANTS
# =========================

CYCLE_SLEEP = 8
BLEED_GOVERNOR_RATIO = 0.25

# =========================
# SAFE LOAD / SAVE
# =========================

def load_json(path, default):
    try:
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else default.copy()
    except Exception as e:
        print(f"[LOAD ERROR] {path}: {e}")
    return default.copy()

def save_json(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[SAVE ERROR] {path}: {e}")

# =========================
# INITIAL STATE LOAD
# =========================

crypto_pnl = load_json(FILES["crypto_pnl"], {s:0.0 for s in SYMBOLS})
fx_pnl = load_json(FILES["fx_pnl"], {s:0.0 for s in FX_SYMBOLS})
options_pnl = load_json(FILES["options_pnl"], {})
futures_pnl = load_json(FILES["futures_pnl"], {s:0.0 for s in FUTURES_SYMBOLS})

crypto_trades = load_json(FILES["crypto_trades"], {s:0 for s in SYMBOLS})
fx_trades = load_json(FILES["fx_trades"], {s:0 for s in FX_SYMBOLS})
options_trades = load_json(FILES["options_trades"], {})
futures_trades = load_json(FILES["futures_trades"], {s:0 for s in FUTURES_SYMBOLS})

crypto_wins = load_json(FILES["crypto_wins"], {s:0 for s in SYMBOLS})
fx_wins = load_json(FILES["fx_wins"], {s:0 for s in FX_SYMBOLS})
options_wins = load_json(FILES["options_wins"], {})
futures_wins = load_json(FILES["futures_wins"], {s:0 for s in FUTURES_SYMBOLS})

futures_bias = load_json(FILES["futures_bias"], {s:1.0 for s in FUTURES_SYMBOLS})
futures_loss = load_json(FILES["futures_loss"], {s:0 for s in FUTURES_SYMBOLS})

# =========================
# HELPERS
# =========================

def get_total_pnl():
    return round(
        sum(crypto_pnl.values()) +
        sum(fx_pnl.values()) +
        sum(options_pnl.values()) +
        sum(futures_pnl.values()), 4
    )

def snapshot_pnl():
    return {
        "CRYPTO": sum(crypto_pnl.values()),
        "FX": sum(fx_pnl.values()),
        "OPTIONS": sum(options_pnl.values()),
        "FUTURES": sum(futures_pnl.values()),
    }
  # =========================
# ENGINE LOGIC (V2–V4 RESTORED)
# =========================

BIAS_NEUTRAL = 1.0
BIAS_MIN = 0.35
BIAS_MAX = 2.25
BIAS_DECAY_RATE = 0.06

BIAS_REWARD_MULT = 1.10
BIAS_LOSS_PENALTY_1 = 0.88
BIAS_LOSS_PENALTY_2 = 0.78
BIAS_LOSS_PENALTY_3 = 0.68

REGIMES = ["TREND", "MEAN_REVERSION", "MOMENTUM", "NEUTRAL"]

VOL_STATES = {
    "HIGH_VOL_EXPANDING": 1.30,
    "LOW_VOL_COMPRESSED": 0.70,
    "NORMAL_VOL": 1.00,
    "BREAKOUT_EXPANSION": 1.40,
}

SWEEP_STATES = {
    "SWEEP_UP_REVERSAL": 0.65,
    "SWEEP_DOWN_REVERSAL": 0.65,
    "CLEAN_BREAKOUT": 1.25,
    "NO_SWEEP": 1.00,
}

CAPITAL_MULTIPLIERS = {
    "BLOCK": 0.0,
    "REDUCE": 0.5,
    "ALLOW": 1.0,
    "PRIORITIZE": 1.5,
}

# =========================
# BIAS SYSTEM
# =========================

def clamp_bias(v):
    return max(BIAS_MIN, min(BIAS_MAX, v))


def apply_bias_decay():
    for symbol, current in list(futures_bias.items()):
        if current > BIAS_NEUTRAL:
            current -= ((current - BIAS_NEUTRAL) * BIAS_DECAY_RATE)
        elif current < BIAS_NEUTRAL:
            current += ((BIAS_NEUTRAL - current) * BIAS_DECAY_RATE)

        futures_bias[symbol] = clamp_bias(current)


def update_reinforcement(symbol, pnl):
    current = futures_bias.get(symbol, BIAS_NEUTRAL)

    if pnl > 0:
        futures_loss[symbol] = 0
        current *= BIAS_REWARD_MULT
    else:
        futures_loss[symbol] += 1
        streak = futures_loss[symbol]

        if streak >= 3:
            current *= BIAS_LOSS_PENALTY_3
        elif streak == 2:
            current *= BIAS_LOSS_PENALTY_2
        else:
            current *= BIAS_LOSS_PENALTY_1

    futures_bias[symbol] = clamp_bias(current)


def weighted_score(raw_score, symbol):
    return raw_score * futures_bias.get(symbol, BIAS_NEUTRAL)

# =========================
# PROBABILITY ENGINE
# =========================

class PreTradeProbabilityEngine:

    def estimate(
        self,
        *,
        regime_conf: float,
        vwap_mult: float,
        vol_mult: float,
        sweep_mult: float,
        raw_score: float
    ) -> Tuple[float, float, float, bool]:

        regime_component = regime_conf * 0.30
        vwap_component = min(vwap_mult / 1.5, 1.0) * 0.20
        vol_component = min(vol_mult / 1.4, 1.0) * 0.15
        sweep_component = min(sweep_mult / 1.25, 1.0) * 0.15
        score_component = min(raw_score / 20.0, 1.0) * 0.20

        prob_positive = (
            regime_component +
            vwap_component +
            vol_component +
            sweep_component +
            score_component
        )

        prob_positive = max(0.05, min(0.95, prob_positive))
        prob_negative = 1.0 - prob_positive

        expected_value = (prob_positive * raw_score) - (prob_negative * 8.0)

        execute = prob_positive >= 0.58 and expected_value > 0

        return (
            round(prob_positive, 4),
            round(prob_negative, 4),
            round(expected_value, 4),
            execute
        )


pt_engine = PreTradeProbabilityEngine()

# =========================
# MARKET STATE GENERATORS (SIMULATION)
# =========================

def detect_regime(symbol, asset_class):
    state = random.choice(REGIMES)
    confidence = round(random.uniform(0.45, 0.95), 2)

    if state == "MOMENTUM":
        risk_mult = 1.25
        priority = "PRIORITIZE"
    elif state == "TREND":
        risk_mult = 1.10
        priority = "ALLOW"
    elif state == "MEAN_REVERSION":
        risk_mult = 0.90
        priority = "REDUCE"
    else:
        risk_mult = 0.70
        priority = "BLOCK"

    return {
        "state": state,
        "confidence": confidence,
        "risk_mult": risk_mult,
        "priority": priority,
        "capital_mult": CAPITAL_MULTIPLIERS[priority]
    }


def compute_vwap_state(symbol):
    distance_pct = round(random.uniform(-3.0, 3.0), 2)
    slope = random.choice(["RISING", "FLAT", "FALLING"])

    if distance_pct > 0 and slope == "RISING":
        state = "ABOVE_RISING"
        mult = 1.25
    elif distance_pct < 0 and slope == "FALLING":
        state = "BELOW_FALLING"
        mult = 0.75
    else:
        state = "NEUTRAL"
        mult = 1.00

    return {
        "state": state,
        "mult": mult,
        "distance_pct": distance_pct
    }


def compute_volatility_state(symbol):
    state = random.choice(list(VOL_STATES.keys()))
    return {"state": state, "mult": VOL_STATES[state]}


def compute_liquidity_sweep(symbol):
    state = random.choice(list(SWEEP_STATES.keys()))
    return {"state": state, "mult": SWEEP_STATES[state]}

# =========================
# BLEED GOVERNOR (FIXED SNAPSHOT)
# =========================

def get_bleed_governor_state(
    asset_class: str,
    snapshot: Optional[Dict[str, float]] = None
) -> Tuple[bool, float, float, float]:

    pnl_map = snapshot if snapshot else snapshot_pnl()

    asset_pnl = float(pnl_map.get(asset_class, 0.0))

    if asset_pnl >= 0:
        return False, 0.0, 0.0, 0.0

    other_positive = sum(
        pnl for k, pnl in pnl_map.items()
        if k != asset_class and pnl > 0
    )

    if other_positive <= 0:
        return False, abs(asset_pnl), 0.0, other_positive

    limit = BLEED_GOVERNOR_RATIO * other_positive
    loss_abs = abs(asset_pnl)

    frozen = loss_abs > limit

    return frozen, round(loss_abs,4), round(limit,4), round(other_positive,4)
    # =========================
# EXECUTION + DISPLAY LAYER
# =========================

def execute_trade(candidate, broker, position_managers):
    asset_class = candidate.get("asset_class")
    symbol = candidate.get("symbol")
    size = candidate.get("size", 1)

    try:
        if asset_class == "crypto":
            position_managers["crypto"].open_position(symbol, size)

        elif asset_class == "fx":
            position_managers["fx"].open_position(symbol, size)

        elif asset_class == "futures":
            position_managers["futures"].open_position(symbol, size)

        elif asset_class == "options":
            position_managers["options"].open_position(symbol, size)

        return True, "executed"

    except Exception as e:
        return False, str(e)


def display_dashboard(state, broker_name, engine_mode, cycle, pnl_snapshot):
    print("\n" + "=" * 80)
    print(f"CSS LIVE DASHBOARD V5 | Cycle: {cycle}")
    print("=" * 80)

    print(f"Broker: {broker_name}")
    print(f"Engine Mode: {engine_mode}")
    print(f"Balance: {round(state.balance, 2)}")

    print("\n--- PnL Snapshot ---")
    print(f"Realized: {round(pnl_snapshot.get('realized', 0), 2)}")
    print(f"Unrealized: {round(pnl_snapshot.get('unrealized', 0), 2)}")
    print(f"Total: {round(pnl_snapshot.get('total', 0), 2)}")

    print("\n--- Open Positions ---")
    for pos in state.open_positions:
        print(f"{pos}")

    print("\n--- Trade History Count ---")
    print(len(state.trade_history))

    print("=" * 80)


# =========================
# MAIN LOOP
# =========================

def run_dashboard():

    broker_name = select_broker()
    engine_mode = select_engine_mode()

    broker = initialize_broker(broker_name)

    state = AccountState()
    state.load()

    orchestrator = TradeDecisionOrchestrator()
    pnl_engine = PnLEngine()

    position_managers = {
        "crypto": PositionManager(),
        "fx": PositionManager(),
        "futures": FuturesPositionManager(FuturesSimAdapter()),
        "options": OptionsPositionManager(OptionsChainAdapter()),
    }

    cycle = 0

    print("\nSystem initialized. Awaiting login readiness...")

    while True:
        cycle += 1

        print(f"\n[Cycle {cycle}] Running market scan...")

        candidates = []

        for symbol in ["BTC-USD", "ETH-USD", "EURUSD", "AAPL", "SPY"]:
            data = load_runtime_asset(symbol)

            decision = orchestrator.evaluate_trade(
                symbol=symbol,
                data=data,
                mode=engine_mode
            )

            if decision.get("approved"):
                candidates.append(decision)

        # =========================
        # EXECUTION CONTROL
        # =========================

        executed = 0
        max_per_cycle = 4

        for c in candidates:
            if executed >= max_per_cycle:
                break

            success, msg = execute_trade(c, broker, position_managers)

            if success:
                executed += 1
                state.trade_history.append(c)

        # =========================
        # PnL UPDATE
        # =========================

        pnl_snapshot = pnl_engine.compute(state)

        state.balance += pnl_snapshot.get("delta", 0)

        # =========================
        # SAVE STATE
        # =========================

        state.save()

        # =========================
        # DISPLAY
        # =========================

        display_dashboard(
            state,
            broker_name,
            engine_mode,
            cycle,
            pnl_snapshot
        )

        # =========================
        # CONTROLLED LOOP
        # =========================

        input("\nPress ENTER to proceed to next cycle...")
        time.sleep(2)


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    run_dashboard()

# ============================================================
# CSS LIVE DASHBOARD V5 — PART 4
# ADVANCED ENHANCEMENTS LAYER
# ============================================================

def sync_live_balance(state, broker):
    """
    Safely sync account balance from connected broker.
    Falls back to persisted state balance if broker balance is unavailable.
    """
    try:
        if broker is None:
            return False

        if hasattr(broker, "get_balance"):
            live_balance = broker.get_balance()

            if live_balance is not None:
                live_balance = float(live_balance)

                if live_balance > 0:
                    state.balance = live_balance
                    return True

        return False

    except Exception as e:
        print(f"[WARN] Balance sync failed: {e}")
        return False


def estimate_execution_cost(symbol, price):
    """
    Lightweight execution-cost estimate.
    Preserves existing external cost engine if already present elsewhere.
    """
    try:
        price = float(price or 0)

        if price <= 0:
            return 0.0

        spread = price * 0.0005
        slippage = price * 0.0003
        fee = price * 0.0002

        return round(spread + slippage + fee, 6)

    except Exception:
        return 0.0


def log_trade_diagnostics(symbol, decision):
    """
    Prints visible decision diagnostics so dashboard is not silent.
    """
    print(f"\n[DIAGNOSTIC] {symbol}")

    if not decision:
        print(" → No decision returned")
        return

    print(f" → Approved: {decision.get('approved')}")
    print(f" → Asset Class: {decision.get('asset_class')}")
    print(f" → Score: {decision.get('score')}")
    print(f" → Confidence: {decision.get('confidence')}")
    print(f" → Regime: {decision.get('regime')}")
    print(f" → Reason: {decision.get('reason')}")


def rank_candidates(candidates):
    """
    Rank approved candidates by score and confidence.
    Does not force trades.
    """
    try:
        return sorted(
            candidates,
            key=lambda x: (
                float(x.get("score", 0) or 0),
                float(x.get("confidence", 0) or 0),
            ),
            reverse=True,
        )
    except Exception:
        return candidates


def compute_performance_metrics(trade_history):
    """
    Computes simple win/loss/expectancy metrics from stored trade history.
    Safe when pnl field is absent.
    """
    wins = 0
    losses = 0
    pnl_total = 0.0

    for trade in trade_history:
        pnl = float(trade.get("pnl", 0) or 0)
        pnl_total += pnl

        if pnl > 0:
            wins += 1
        elif pnl < 0:
            losses += 1

    closed_trades = wins + losses

    win_rate = (wins / closed_trades) * 100 if closed_trades > 0 else 0.0
    expectancy = pnl_total / closed_trades if closed_trades > 0 else 0.0

    return {
        "wins": wins,
        "losses": losses,
        "closed_trades": closed_trades,
        "win_rate": round(win_rate, 2),
        "expectancy": round(expectancy, 2),
        "total_pnl": round(pnl_total, 2),
    }


def extract_signal_metrics(data):
    """
    Extracts useful signal visibility fields from market data.
    """
    if not isinstance(data, dict):
        return {
            "price": None,
            "vwap": None,
            "momentum": None,
            "pressure": None,
        }

    return {
        "price": data.get("price") or data.get("close"),
        "vwap": data.get("vwap"),
        "momentum": data.get("momentum"),
        "pressure": data.get("pressure_score"),
    }


def display_signal_metrics(symbol, data):
    """
    Optional per-symbol visibility helper.
    """
    metrics = extract_signal_metrics(data)

    print(f"\n[SIGNAL] {symbol}")
    print(f" → Price: {metrics.get('price')}")
    print(f" → VWAP: {metrics.get('vwap')}")
    print(f" → Momentum: {metrics.get('momentum')}")
    print(f" → Pressure: {metrics.get('pressure')}")


def display_dashboard(state, broker_name, engine_mode, cycle, pnl_snapshot, metrics):
    """
    Enhanced dashboard display.
    Replaces earlier display_dashboard only.
    """

    print("\n" + "=" * 90)
    print(f"CSS LIVE DASHBOARD V5 | Cycle: {cycle}")
    print("=" * 90)

    print(f"Broker: {broker_name}")
    print(f"Engine Mode: {engine_mode}")
    print(f"Balance: {round(float(state.balance or 0), 2)}")

    print("\n--- PnL ---")
    print(f"Realized: {round(float(pnl_snapshot.get('realized', 0) or 0), 2)}")
    print(f"Unrealized: {round(float(pnl_snapshot.get('unrealized', 0) or 0), 2)}")
    print(f"Total: {round(float(pnl_snapshot.get('total', 0) or 0), 2)}")

    print("\n--- Performance ---")
    print(f"Wins: {metrics.get('wins', 0)} | Losses: {metrics.get('losses', 0)}")
    print(f"Closed Trades: {metrics.get('closed_trades', 0)}")
    print(f"Win Rate: {metrics.get('win_rate', 0)}%")
    print(f"Expectancy: {metrics.get('expectancy', 0)}")
    print(f"Total PnL: {metrics.get('total_pnl', 0)}")

    print("\n--- Open Positions ---")
    if getattr(state, "open_positions", None):
        for pos in state.open_positions:
            print(pos)
    else:
        print("No open positions")

    print("\n--- Trade History Count ---")
    print(len(getattr(state, "trade_history", [])))

    print("=" * 90)


# ============================================================
# P4 SAFE MAIN LOOP INSERTS
# ============================================================

"""
Insert these into run_dashboard():

1. At the START of each cycle, before scanning:

    balance_synced = sync_live_balance(state, broker)
    if balance_synced:
        print("[BALANCE] Live broker balance synced.")
    else:
        print("[BALANCE] Using persisted account balance.")

2. During symbol scan, after loading data:

    display_signal_metrics(symbol, data)

3. After orchestrator decision:

    log_trade_diagnostics(symbol, decision)

4. After collecting candidates:

    candidates = rank_candidates(candidates)

5. Before executing each candidate:

    price = c.get("price") or c.get("close") or 0
    c["estimated_cost"] = estimate_execution_cost(c.get("symbol"), price)

6. After PnL update:

    metrics = compute_performance_metrics(state.trade_history)

7. Replace display call with:

    display_dashboard(
        state,
        broker_name,
        engine_mode,
        cycle,
        pnl_snapshot,
        metrics
    )
"""

# ============================================================
# CSS LIVE DASHBOARD V5 — P5 FULL HARDENING LAYER
# ============================================================

import time
import json
from datetime import datetime


# ============================================================
# 1. TRADE LIFECYCLE ENGINE
# ============================================================

def update_trade_lifecycle(state):
    """
    Manage open trades: update pnl and close positions when exit conditions are met.
    """

    updated_positions = []

    for pos in state.open_positions:

        entry_price = pos.get("entry_price", 0)
        current_price = pos.get("current_price", entry_price)
        size = pos.get("size", 1)

        pnl = (current_price - entry_price) * size
        pos["pnl"] = pnl

        # Track holding duration
        pos["hold_time"] = pos.get("hold_time", 0) + 1

        exit_reason = evaluate_exit_conditions(pos)

        if exit_reason:
            pos["closed_at"] = datetime.utcnow().isoformat()
            pos["exit_reason"] = exit_reason

            state.trade_history.append(pos)
            audit_log("TRADE_CLOSE", pos)

        else:
            updated_positions.append(pos)

    state.open_positions = updated_positions


# ============================================================
# 2. SMART EXIT ENGINE
# ============================================================

def evaluate_exit_conditions(position):

    pnl = position.get("pnl", 0)
    entry_price = position.get("entry_price", 0)
    current_price = position.get("current_price", entry_price)

    vwap = position.get("vwap")
    momentum = position.get("momentum", 0)
    hold_time = position.get("hold_time", 0)

    # PROFIT TARGET (~1%)
    if pnl > entry_price * 0.01:
        return "target_hit"

    # STOP LOSS (~0.5%)
    if pnl < -entry_price * 0.005:
        return "stop_loss"

    # VWAP REVERSION
    if vwap and current_price < vwap:
        return "vwap_reversion"

    # MOMENTUM COLLAPSE
    if momentum < -0.3:
        return "momentum_loss"

    # TIME EXIT
    if hold_time > 300:
        return "time_exit"

    return None


# ============================================================
# 3. RISK GOVERNOR (CRITICAL CONTROL)
# ============================================================

def risk_governor(state):

    total_realized = sum([t.get("pnl", 0) for t in state.trade_history])
    total_open = sum([p.get("pnl", 0) for p in state.open_positions])

    equity = state.balance + total_open

    # DRAWDOWN CONTROL (10%)
    if equity < state.balance * 0.90:
        print("[RISK] Drawdown breach — trading halted")
        return False

    # BLEED CONTROL
    if total_open < -abs(total_realized) * 0.25:
        print("[RISK] Bleed threshold exceeded — trading paused")
        return False

    return True


# ============================================================
# 4. ADAPTIVE POSITION SIZING
# ============================================================

def adaptive_position_size(balance, confidence):

    base_size = balance * 0.01

    if confidence > 0.8:
        return base_size * 2

    elif confidence < 0.4:
        return base_size * 0.5

    return base_size


# ============================================================
# 5. REGIME-BASED TRADE LIMIT
# ============================================================

def regime_trade_limit(regime):

    if regime == "strong_trend":
        return 6

    elif regime == "neutral":
        return 3

    elif regime == "volatile":
        return 2

    return 4


# ============================================================
# 6. AUDIT LOGGER (JSONL TRAIL)
# ============================================================

def audit_log(event_type, payload):

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event_type,
        "data": payload,
    }

    try:
        with open("audit_logs/trades.jsonl", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"[AUDIT ERROR] {e}")


# ============================================================
# 7. EXECUTION ENGINE (UPGRADED)
# ============================================================

def execute_trade(candidate, broker, position_managers, state):

    asset_class = candidate.get("asset_class")
    symbol = candidate.get("symbol")
    confidence = candidate.get("confidence", 0.5)

    size = adaptive_position_size(state.balance, confidence)

    try:
        if asset_class == "crypto":
            position_managers["crypto"].open_position(symbol, size)

        elif asset_class == "fx":
            position_managers["fx"].open_position(symbol, size)

        elif asset_class == "futures":
            position_managers["futures"].open_position(symbol, size)

        elif asset_class == "options":
            position_managers["options"].open_position(symbol, size)

        candidate["size"] = size
        candidate["opened_at"] = datetime.utcnow().isoformat()
        candidate["entry_price"] = candidate.get("price", 0)

        state.open_positions.append(candidate)

        audit_log("TRADE_OPEN", candidate)

        return True, "executed"

    except Exception as e:
        return False, str(e)


# ============================================================
# 8. MAIN LOOP INSERTIONS (MANDATORY)
# ============================================================

"""
Insert into your run_dashboard() loop:

-------------------------------------------------

# 1. BEFORE EXECUTION
if not risk_governor(state):
    print("[BLOCKED] Risk conditions not met")
    continue

-------------------------------------------------

# 2. REGIME LIMIT
if candidates:
    regime = candidates[0].get("regime", "neutral")
    max_per_cycle = regime_trade_limit(regime)

-------------------------------------------------

# 3. EXECUTION LOOP (UPDATED)
for c in candidates:

    if executed >= max_per_cycle:
        break

    success, msg = execute_trade(c, broker, position_managers, state)

    if success:
        executed += 1

-------------------------------------------------

# 4. AFTER EXECUTION
update_trade_lifecycle(state)

-------------------------------------------------

"""

# ============================================================
# END OF P5 MODULE
# ============================================================
