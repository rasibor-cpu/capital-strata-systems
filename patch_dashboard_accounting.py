from pathlib import Path
import re

p = Path("scripts/css_live_dashboard.py")
s = p.read_text()

new_func = r'''
def route_execution(asset_class, symbol, signal_score, eff):
    global BROKER_ADAPTER, last_trade, futures_lifetime_total

    asset_class = str(asset_class).upper()

    if not allocation_allows_new_trade(asset_class):
        return False

    side = determine_trade_side(signal_score)
    units = estimate_units(asset_class, signal_score)

    executed = False
    order_id = "SIM"
    status = "SIM_FILLED" if execution_metrics.get("mode") == "SIM" else "PAPER_FILLED"

    if BROKER_ADAPTER is not None:
        try:
            result = BROKER_ADAPTER.place_order(
                symbol=symbol,
                units=units,
                side=side,
                order_type="MARKET",
            )
            normalized = normalize_order_result(result)
            print(f"[BROKER EXECUTED] {symbol} -> {result}")

            if normalized.get("ok", False):
                executed = True
                order_id = normalized.get("order_id") or f"PAPER-{symbol}"
                status = normalized.get("status") or status
                execution_metrics["orders_sent"] += 1
            else:
                execution_metrics["orders_blocked"] += 1
                return False

        except Exception as e:
            print(f"[BROKER ERROR] {e}")
            execution_metrics["orders_blocked"] += 1
            return False
    else:
        print("[PAPER ROUTE] No BROKER_ADAPTER -> simulation")
        executed = True
        execution_metrics["orders_sent"] += 1

    if not executed:
        return False

    pnl = round(random.uniform(-3.0, 7.0) * max(0.25, min(2.0, float(eff or 1.0))), 4)

    if float(signal_score) >= 15:
        pnl = round(pnl * 1.15, 4)
        execution_metrics["winner_run_active"] += 1

    if float(signal_score) < 11 and pnl < 0:
        pnl = round(pnl * 0.65, 4)
        execution_metrics["loser_cut_active"] += 1

    last_trade = f"{symbol} {pnl:+.4f}"

    if asset_class == "CRYPTO":
        crypto_pnl[symbol] += pnl
        crypto_trades[symbol] += 1
        if pnl > 0:
            crypto_wins[symbol] += 1

    elif asset_class == "FX":
        fx_pnl[symbol] += pnl
        fx_trades[symbol] += 1
        if pnl > 0:
            fx_wins[symbol] += 1

    elif asset_class == "FUTURES":
        futures_realized_pnl[symbol] += pnl
        futures_trade_count[symbol] += 1
        futures_lifetime_total += pnl
        if pnl > 0:
            futures_win_count[symbol] += 1
        update_reinforcement(symbol, pnl)

    register_cycle_entry(asset_class)

    update_fill_visibility(
        asset_class=asset_class,
        symbol=symbol,
        side=side,
        units=units,
        pnl_value=pnl,
        status=status,
        order_id=order_id,
        fill_price=0.0,
    )

    try:
        pos = Position(
            symbol=symbol,
            side="LONG",
            entry_price=float(eff or 1.0),
            current_price=float(eff or 1.0),
            quantity=1.0,
            instrument_spec=InstrumentSpec(
                symbol=symbol,
                asset_class=asset_class,
                multiplier=1.0,
            ),
            entry_cost=ExecutionCost(),
            estimated_exit_cost=ExecutionCost(),
        )
        CSS_POSITIONS.append(pos)
    except Exception as e:
        print(f"[POSITION TRACK WARN] {e}")

    print(f"[{asset_class} EXECUTED] {symbol} pnl={pnl:+.4f}")
    return True

'''

s2 = re.sub(
    r"def route_execution\(.*?\n(?=def load_json_state)",
    new_func + "\n",
    s,
    flags=re.S,
)

if s2 == s:
    raise SystemExit("route_execution replacement failed")

p.write_text(s2)
print("Dashboard accounting patch applied.")