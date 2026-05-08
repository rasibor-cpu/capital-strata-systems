# CSS Numeric Boundary Policy

CSS preserves accounting precision until values intentionally cross into a
presentation or transport boundary.

## Numeric Types By Layer

| Layer | Numeric Type |
|---|---|
| Ledger/accounting | Decimal |
| Execution cost calculation | Decimal preferred |
| Risk sizing | float acceptable but must not be accounting truth |
| Dashboard state | float/string serialization acceptable |
| Render contracts/UI | float/string only |
| API/mobile output | JSON-safe float/string only |

## Rules

- `engine.ledger.pnl_engine.PnLEngine` is the canonical PnL authority.
- Decimal must be preserved through ledger/accounting work.
- Float conversion is allowed at dashboard, rendering, API, and mobile
  boundaries for JSON-safe presentation.
- Risk sizing may use floats, but risk sizing outputs must not become the
  source of accounting truth.
- Presentation builders may summarize PnL, but they must be fed from canonical
  ledger/accounting state in production/live mode.
- UI and mobile views must display serialized values only; they must not
  calculate or override canonical PnL.
