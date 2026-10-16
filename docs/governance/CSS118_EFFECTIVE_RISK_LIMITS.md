# CSS-118 — Effective risk limits (B2 / B7)

**PRODUCTION_GO=NO.** Capital governors remain binding. Personality values that exceed
governors are capped. AntiBleed minimum remains CAD 50.

## Capital governors (binding ceilings)

| Control | Ceiling |
|---|---|
| Single-trade allocation | **5%** of equity (`DEFAULT_MAX_SINGLE_TRADE_ALLOCATION_PCT = 0.05`) |
| Aggregate portfolio exposure | **25%** of equity |
| Futures / options single-trade | **2%** where applicable |
| AntiBleed minimum notional | **CAD 50** (no CAD 20 exception enabled) |
| Volatility sizing | **Reduce-only** (never enlarges beyond approved size) |

## Risk personalities — stated vs effective position / exposure

| Personality | Stated max position % | Effective (governor) | Stated max exposure % | Effective (governor) |
|---|---|---|---|---|
| Safe | 2% | 2% | 5% | 5% |
| Conservative | 4% | 4% | 10% | 10% |
| Balanced | 6% | **5%** | 20% | 20% |
| Aggressive | 8% | **5%** | 30% | **25%** |
| Ultra Aggressive | 10% | **5%** | 40% | **25%** |

Owner decision B7: **keep governors binding** (current state). Lowering personality
display values to match governors is optional cosmetics; it is not required for safety.

## AntiBleed CAD 20 pilot (B2)

Evidence: `docs/evidence/CSS118_ANTIBLEED_CAD20_EVIDENCE.json` — 6/6 CAD 20 pilot orders
rejected with `anti_bleed_guard:trade_size_too_small`.

Design options: `docs/governance/CSS118_ANTIBLEED_PAPER_EXCEPTION_DESIGN.md`.

**Engineering default until owner records a choice: Option A (reject).** The CAD 20
pilot exception is not enabled and must not be activated without explicit owner approval
plus completed validation.
