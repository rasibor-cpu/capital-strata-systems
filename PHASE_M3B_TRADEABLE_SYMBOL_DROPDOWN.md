# CSS M3B - Trade Tab Tradeable Symbol Dropdown

## Objective
Trade tab symbol dropdown now lists only symbols that are tradeable in the current CSS mode.

## Core Changes
- Added canonical API in `InstrumentUniverse`:
  - `tradeable_symbols(mode="paper", asset_class=None, broker=None)`
- Added mode-aware feed endpoint:
  - `GET /mobile/tradeable-symbols`
  - Optional filters: `mode`, `asset_class`, `broker`
- Trade tab and execution selector dropdowns now use tradeable-symbol feed data.
- Added server-side fallback rendering for tradeable symbol options when JavaScript is unavailable.
- Added empty state option when no symbols are available:
  - `NO TRADEABLE SYMBOLS AVAILABLE`
- Opportunity table `Use` action is blocked for symbols not tradeable in current mode.

## Tradeability Rules Applied
A symbol is included only when all conditions are true:
- `tradable == true`
- mode is paper/practice: `paper_supported == true`
- mode is live: `live_supported == true`
- `status` in `{ACTIVE, PAPER_ACTIVE}`
- not marked fail-closed discovery (`metadata.fail_closed != true`)

## Safety Constraints Preserved
- No automatic trade execution.
- No RBAC bypass.
- No risk gate bypass.
- No live/paper control bypass.
- No broker execution permission changes.

## Validation Coverage
Tests were added/updated to verify:
- universe may contain non-tradeable entries
- paper tradeable filtering excludes non-tradeable/live-only/fail-closed symbols
- `/mobile/tradeable-symbols` returns mode-appropriate payload
- dropdown server-render uses only tradeable symbols
- dropdown excludes non-tradeable entries
- opportunity `Use` is blocked for non-tradeable symbols
- selection behavior remains prefill-only with no trade execution
