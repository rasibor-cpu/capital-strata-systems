import random

balance = 200.0
cycle = 0

# --- STATE TRACKING ---
last_cycle_pnl = 0.0
equity_peak = 200.0
drawdown = 0.0
consecutive_wins = 0
consecutive_losses = 0

# --- OFFENSIVE SCALING CONFIG ---
ELITE_MOMENTUM = 0.80
STRONG_MOMENTUM = 0.72
ELITE_EDGE = 0.040
STRONG_EDGE = 0.032

NORMAL_SIZE = 1.00
STRONG_SIZE = 1.20
ELITE_SIZE = 1.40


def generate_assets():
    return [
        ("CRYPTO", "BTC-USD"),
        ("CRYPTO", "ETH-USD"),
        ("FX", "EURUSD"),
        ("FX", "GBPUSD"),
        ("FUTURES", "NQ"),
        ("FUTURES", "ES"),
        ("OPTIONS", "SPY_CALL"),
        ("OPTIONS", "QQQ_PUT"),
    ]


def compute_rank_score(edge, momentum):
    return (edge * 0.6) + (momentum * 0.4)


def classify_trade(edge, momentum):
    if edge >= 0.03 and momentum >= 0.65:
        return "VALID"
    elif momentum > 0.8:
        return "VALID (MOMENTUM OVERRIDE)"
    elif edge >= 0.028 and momentum >= 0.6:
        return "VALID (SOFT EDGE)"
    elif edge < 0.012:
        return "SOFT EDGE FAIL"
    elif momentum < 0.5:
        return "WEAK MOMENTUM"
    else:
        return "LOW EDGE"
def compute_risk_modifier():
    global last_cycle_pnl, consecutive_wins, consecutive_losses, drawdown

    modifier = 1.0

    if last_cycle_pnl > 5:
        modifier *= 0.75

    if last_cycle_pnl < 0:
        modifier *= 0.7

    if consecutive_wins >= 3:
        modifier *= 0.8

    if consecutive_losses >= 2:
        modifier *= 0.6

    if drawdown > 10:
        modifier *= 0.5

    return round(modifier, 4)


def compute_offensive_size(edge, momentum):
    """
    Phase 9.7:
    increase size only for high-quality conditions
    and only when the system is healthy.
    """
    global drawdown, consecutive_losses

    if drawdown >= 5 or consecutive_losses > 0:
        return NORMAL_SIZE, "DEFENSIVE"

    if edge >= ELITE_EDGE and momentum >= ELITE_MOMENTUM:
        return ELITE_SIZE, "ELITE"

    if edge >= STRONG_EDGE and momentum >= STRONG_MOMENTUM:
        return STRONG_SIZE, "STRONG"

    return NORMAL_SIZE, "NORMAL"


def smart_exit(edge, momentum, risk_modifier, size_multiplier):
    """
    Phase 9.7 exit engine with controlled offensive scaling.
    """

    effective_scale = risk_modifier * size_multiplier
    win_probability = 0.5 + (momentum - 0.5)

    if random.random() < win_probability:
        if momentum > 0.8:
            pnl = edge * momentum * 120 * effective_scale
            exit_type = "extended_profit_lock"
        elif momentum > 0.7:
            pnl = edge * momentum * 100 * effective_scale
            exit_type = "profit_lock"
        else:
            pnl = edge * momentum * 80 * effective_scale
            exit_type = "light_profit_exit"
    else:
        if momentum >= 0.65:
            pnl = random.uniform(-0.5, 0.5) * effective_scale
            exit_type = "controlled_breakeven"
        elif momentum >= 0.55:
            pnl = -random.uniform(0.5, 2.0) * effective_scale
            exit_type = "controlled_loss"
        else:
            pnl = -random.uniform(2.0, 6.0) * effective_scale
            exit_type = "hard_loss"

    return round(pnl, 2), exit_type


def select_candidates():
    assets = generate_assets()
    candidates = []

    for asset_class, symbol in assets:
        edge = round(random.uniform(0.005, 0.05), 4)
        momentum = round(random.uniform(0.35, 0.9), 3)

        classification = classify_trade(edge, momentum)

        print(f"{asset_class} | {symbol}")
        print(f"Edge: {edge} | Momentum: {momentum}")
        print(classification)

        if "VALID" in classification:
            rank_score = compute_rank_score(edge, momentum)
            candidates.append((rank_score, asset_class, symbol, edge, momentum, classification))

    candidates.sort(reverse=True)
    return candidates
def run_cycle():
    global balance, cycle
    global last_cycle_pnl, equity_peak, drawdown
    global consecutive_wins, consecutive_losses

    cycle += 1
    print("\n" + "=" * 60)
    print(f"Cycle {cycle}")
    print("=" * 60)

    candidates = select_candidates()

    print("\n--- TOP TRADES (SMART RANKED) ---")
    for c in candidates[:3]:
        print(
            f"{c[2]} | Edge: {c[3]} | Momentum: {c[4]} | "
            f"RankScore: {round(c[0],4)} | Tag: {c[5]}"
        )

    risk_modifier = compute_risk_modifier()
    print(f"\nRisk Modifier Applied: {round(risk_modifier, 2)}")

    trades_taken = 0
    cycle_pnl = 0.0

    for c in candidates[:2]:
        _, asset_class, symbol, edge, momentum, classification = c

        size_multiplier, mode = compute_offensive_size(edge, momentum)

        pnl, exit_type = smart_exit(edge, momentum, risk_modifier, size_multiplier)

        balance += pnl
        cycle_pnl += pnl
        trades_taken += 1

        print(
            f"\nTRADE: {symbol} | Mode: {mode} | "
            f"Size: {round(size_multiplier,2)} | Exit: {exit_type} | PnL: {pnl}"
        )

        if pnl > 0:
            consecutive_wins += 1
            consecutive_losses = 0
        elif pnl < 0:
            consecutive_losses += 1
            consecutive_wins = 0

    if balance > equity_peak:
        equity_peak = balance

    drawdown = equity_peak - balance
    last_cycle_pnl = cycle_pnl

    print("\n--- SUMMARY ---")
    print(f"Trades Taken: {trades_taken}")
    print(f"Cycle PnL: {round(cycle_pnl,2)}")
    print(f"Balance: {round(balance,2)}")
    print(f"Equity Peak: {round(equity_peak,2)}")
    print(f"Drawdown: {round(drawdown,2)}")
    print(f"Win Streak: {consecutive_wins} | Loss Streak: {consecutive_losses}")


def run():
    print("CSS PHASE 9.7 — OFFENSIVE SCALING ENGINE")

    while True:
        run_cycle()
        input("Press Enter to continue...")


if __name__ == "__main__":
    run()