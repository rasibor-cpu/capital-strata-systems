# CSS Companion App — Wireframe Planning Boundary (Phase 55)

Status: PLANNING COMPLETE / IMPLEMENTATION NOT AUTHORIZED

## Product boundary

The companion app is separate from CSS Core. It may present educational,
market-facing, and sample/demo information, but it must not expose:

- broker credentials or tokens;
- real account identifiers or balances;
- direct broker API calls;
- order-entry controls;
- proprietary internal decision rules;
- fee-entitlement logic;
- live execution controls.

## Safe wireframe set

1. **Home / Market Brief**
   - demo market summary
   - educational risk banner
   - delayed/sample data label
2. **Ideas / Watchlist**
   - sample securities
   - non-personalized examples
   - probability/risk-range presentation
3. **Learn**
   - simulator/academy entry points
   - lessons and scenario progress
4. **Performance Education**
   - sample portfolio chart
   - drawdown explanation
   - benchmark comparison
5. **Safety / Disclosures**
   - simulation-only labels
   - no execution authority
   - data freshness/source labeling

## Safe sample-data contract

All wireframes must use synthetic, delayed, or explicitly demo-labeled data.
The contract must contain:

- `data_mode = DEMO | SYNTHETIC | DELAYED`
- `execution_allowed = false`
- `broker_execution_armed = false`
- `money_movement_allowed = false`
- `commercialization_attribution_allowed = false`
- `fee_entitlement_allowed = false`

## Nice-to-have backlog

Permitted future UX exploration, still separate from CSS Core:

- accessibility-first typography;
- dark/light appearance;
- notification preference mockups;
- saved educational watchlists;
- scenario-of-the-day;
- glossary/context help;
- shareable non-account educational cards.

No implementation work begins without a separate product directive.
