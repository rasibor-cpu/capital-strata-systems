# CSS-118 B1 — Calibrated signal producer (paper / research)

**PRODUCTION_GO=NO.** This work does not authorize live trading, enroll production keys,
or subscribe CSS to a production market-data contract.

## What landed

| Component | Path | Role |
|---|---|---|
| Replay bar source | `backend/trading_profiles/market_bar_source.py` | Authorized CSV OHLC only; fail closed |
| Calibration artifact | `backend/trading_profiles/engine_loop_calibration.py` | Maps EngineLoop strength → probability + R14F `signal_score` |
| Walk-forward | `backend/trading_profiles/calibration_walk_forward.py` | Train/test split; actual OOS metrics; disable on failure |
| Enablement registry | `backend/trading_profiles/strategy_enablement.py` | Missing/disabled ⇒ not routable |
| Paper runner | `backend/trading_profiles/calibrated_signal_runner.py` | Bars → EngineLoop → `CssEngineSignalBridge` → paper router |
| CLI | `tools/run_b1_calibration_walk_forward.py` | Persist artifact + enablement from a CSV |

Provenance remains **only** `ENGINE_LOOP_CALIBRATED`. Legacy random candidates stay refused.

## Strategy

`engine_loop_ma_momentum_v1` — MA(20) momentum aligned with `engine/strategy/signal_engine.py`.
Costs applied in OOS: fee + spread + slippage (default 1 bps each).

**Pass criteria (all required):** OOS trades ≥ 5, OOS expectancy (net of costs) > 0,
OOS max drawdown < 25%. Failure disables the strategy and sets `approved_for_routing=False`.

Observed metrics are recorded in the artifact. No projected or fabricated profitability.

## Owner decisions still required

1. Approve a **live / licensed market-data** source for non-replay operation (Coinbase and/or OANDA read-only scanners are candidates; synthetic scanner prices are forbidden).
2. Review and formally accept any calibration artifact before operational paper shadow use beyond engineering fixtures.
3. Live trading, CAD pilot, and endurance remain under separate release authorization.

## Limitations

- Replay CSV quality bounds all calibration claims.
- MA momentum is a single, empirically tested baseline — not a multi-strategy catalogue.
- Autonomous / Assisted users receive engine signals only while an approved, enabled artifact is loaded into a paper runner with `css_signal_sink` wired.
