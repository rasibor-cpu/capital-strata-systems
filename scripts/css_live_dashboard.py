import random
import time

balance = 200.0
cycle = 0


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
def smart_exit(edge, momentum):
    """
    Phase 9.5 Profit Extraction Engine
    """

    win_probability = 0.5 + (momentum - 0.5)

    if random.random() < win_probability:
        # WIN PATH

        if momentum > 0.8:
            # STRONG TREND → maximize profit
            pnl = edge * momentum * 120 * random.uniform(1.0, 1.4)
            exit_type = "extended_profit_lock"

        elif momentum > 0.7:
            pnl = edge * momentum * 100 * random.uniform(0.9, 1.2)
            exit_type = "profit_lock"

        else:
            pnl = edge * momentum * 80 * random.uniform(0.8, 1.1)
            exit_type = "light_profit_exit"

    else:
        # LOSS PATH

        if momentum >= 0.65:
            # controlled drawdown instead of flat breakeven
            pnl = random.uniform(-0.5, 0.5)
            exit_type = "controlled_breakeven"

        elif momentum >= 0.55:
            pnl = -random.uniform(0.5, 2.0)
            exit_type = "controlled_loss"

        else:
            pnl = -random.uniform(2.0, 6.0)
            exit_type = "hard_loss"

    return round(pnl, 2), exit_type
def run_cycle():
    global balance, cycle

    cycle += 1
    print("\n" + "=" * 60)
    print(f"Cycle {cycle}")
    print("=" * 60)

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
            candidates.append((rank_score, asset_class, symbol, edge, momentum))

    candidates.sort(reverse=True)

    print("\n--- TOP TRADES (SMART RANKED) ---")
    for c in candidates[:3]:
        print(f"{c[2]} | Edge: {c[3]} | Momentum: {c[4]} | RankScore: {round(c[0],4)}")

    trades_taken = 0
    cycle_pnl = 0

    for c in candidates[:2]:
        _, asset_class, symbol, edge, momentum = c

        pnl, exit_type = smart_exit(edge, momentum)

        balance += pnl
        cycle_pnl += pnl
        trades_taken += 1

        print(f"\nTRADE: {symbol} | Exit: {exit_type} | PnL: {pnl}")

    print("\n--- SUMMARY ---")
    print(f"Trades Taken: {trades_taken}")
    print(f"Cycle PnL: {round(cycle_pnl,2)}")
    print(f"Balance: {round(balance,2)}")


def run():
    print("CSS PHASE 9.5 — PROFIT EXTRACTION UPGRADE ENGINE")

    while True:
        run_cycle()
        input("Press Enter to continue...")


if __name__ == "__main__":
    run()