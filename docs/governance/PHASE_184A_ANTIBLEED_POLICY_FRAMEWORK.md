# PHASE 184A — AntiBleed Policy Framework

## Status

Framework implementation on `css-rc-live-001-candidate`.

**Does not authorize live trading.**

**Does not weaken AntiBleed.**

**Does not modify Phase 152A capital ceilings.**

## Architecture

AntiBleed thresholds are no longer embedded as ad-hoc constructor defaults only.
They are expressed as **immutable policy profiles** selected exclusively from a
**governed execution context** before `ExecutionGate` evaluates a trade.

```
Governed execution context
        │
        ▼
AntiBleedPolicyResolver.resolve(...)
        │
        ▼
Immutable AntiBleedPolicy
        │
        ▼
ExecutionGate (first safety gate)
   1. AntiBleedGuard.evaluate(..., policy=resolved)
   2. MarginTradeGate
   3. Canonical pricing
   4. Compounding
   5. Position sizing
   6. RiskGovernor
```

## Policy Model

Each profile is a frozen `AntiBleedPolicy` with:

| Field | Meaning |
|---|---|
| `minimum_profitable_trade_size` | Floor on notional/`trade_size` |
| `minimum_required_net_edge_bps` | Floor on net edge after costs |
| `cooldown_minutes` | Per-symbol cooldown after approval |
| `maximum_symbol_frequency` | Documented max trades/symbol/cycle |
| `require_complete_microstructure_inputs` | Completeness requirement (always enforced fail-closed) |
| `allow_dev_override` | Dev override posture (blocked in live-like envs) |

Registry profiles (immutable; no runtime edit; no env override):

| Profile | Min size | Net edge bps | Cooldown | Completeness | Dev override |
|---|---|---|---|---|---|
| `STANDARD` | 50.0 | 25.0 | 10 | required | false |
| `MICRO_PILOT` | 20.0 | 25.0 | 10 | required | false |
| `PAPER` | 50.0 | 25.0 | 10 | required | false |
| `BACKTEST` | 50.0 | 25.0 | 10 | required | false |

## Selection Rules

`AntiBleedPolicyResolver` maps **only** governed context tokens:

| Context | Profile |
|---|---|
| `LIVE_MICRO_PILOT` / `MICRO_PILOT` | `MICRO_PILOT` |
| `PAPER` / `PAPER_TRADING` | `PAPER` |
| `BACKTEST` / `BACKTESTING` | `BACKTEST` |
| otherwise / missing | `STANDARD` |

Selection **must not** depend on broker, account size, user input, capital,
environment variables, or magic constants outside the governed token.

## Safety Rationale

- Edge floor remains **25 bps** on every profile (not weakened).
- Completeness remains **fail-closed** (missing inputs still reject).
- Dev override remains **false** on shipped profiles and blocked in live-like envs.
- `STANDARD` retains historical min size **50** for non-pilot paths.
- `MICRO_PILOT` min size **20** exists solely to align with Phase 152A CAD 20
  ceiling without changing Phase 152A code or limits.

## Interaction With Phase 152A

Phase 152A (`LiveMicroPilotGovernor`, CAD 20 capital/position, daily/session loss,
concurrency, order limits) is **unchanged**.

The LDT-003 contradiction (CAD 20 vs AntiBleed min 50) is addressed **only** by
selecting `MICRO_PILOT` when the governed context is `LIVE_MICRO_PILOT`.

Phase 152A remains the post-gate live capital governor. AntiBleed remains first.

## Why AntiBleed Remains First

Fee-bleed and micro-trade inefficiency must be rejected before margin sizing and
RiskGovernor consume notional. Reordering would allow economically invalid
candidates deeper into the stack. Phase 184A forbids reordering.

## Why Live Remains Blocked

- Live execution authority still requires `anti_bleed_guard_pass` (AND-gate).
- Mobile live still requires a real `LiveMicrostructureProvider` result; the
  default `UnavailableLiveMicrostructureProvider` returns `None` →
  `missing_anti_bleed_input:*` fail-closed (no fabricated microstructure).
- Phase 152A still requires pilot enabled, armed, SUPER_USER, confirmation.
- Broader LDT blockers (FX, OANDA LIVE, auth TTL, founder GO/NO-GO, freeze SHA)
  remain outside this phase.

## Live Microstructure Provider

Interface: `backend/app/risk/live_microstructure_provider.py`

- Explicit provider contract for live expected-move / fee / spread / slippage.
- Default implementation is unavailable and returns `None`.
- No silent defaults. No fake values. No `dev_force_allow` bypass on live path.

## Migration Strategy

1. Default / unspecified context → `STANDARD` (backward compatible with min 50).
2. Mobile paper tickets pass `anti_bleed_context="PAPER"`.
3. Mobile live tickets pass `anti_bleed_context="LIVE_MICRO_PILOT"` and consult
   the microstructure provider (fail-closed if unavailable).
4. Existing unit tests that construct `AntiBleedGuard(...)` with legacy kwargs
   continue to work via immutable custom policy construction at init time.
5. Future phases may add profiles only through governance; never via env vars.

## Future Extension

- Certified live microstructure providers (broker-sourced spreads/fees).
- Additional governed contexts (e.g. endurance paper soak) with new profiles.
- Explicit currency tagging on size floors (separate FX phase).

## Non-Goals

- Does not enable live trading.
- Does not raise Phase 152A capital ceilings.
- Does not disable AntiBleed, Margin, Kill Switch, RBAC, or live authority AND-gates.
- Does not commit or push authorization.
