# V1 Historical Replay Engine

## Scope

Implemented a canonical historical replay layer that validates historical replay records and simulates the CSS intelligence pipeline without broker execution, live trading, UI changes, or runtime changes.

## Components

- `backend/validation/historical_replay_engine.py`
- `backend/validation/replay_models.py`
- `backend/validation/replay_statistics.py`

## Pipeline

Replay processing follows the canonical intelligence path:

1. Market Regime Engine
2. Strategy Intelligence
3. Capital Allocation
4. Position Sizing
5. Portfolio Correlation Guard
6. Adaptive Exit Engine
7. Intelligence Orchestrator

## Output

Replay decisions emit:

- `timestamp`
- `symbol`
- `market_regime`
- `selected_strategy`
- `allocation`
- `position_size`
- `risk_score`
- `confidence`
- `decision`
- `exit_plan`

## Statistics

Replay statistics aggregate candidate volume, approvals, blocks, confidence, allocation, and strategy/regime/decision distributions.

## Safety

Replay validation fails closed on invalid records, missing fields, unknown asset classes, and corrupt history.