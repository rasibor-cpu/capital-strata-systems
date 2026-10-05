# Commercial attribution ledgers (CA-1.0.0-draft)

Source: `backend/app/trade_origin/commercial.py`. This is accounting machinery only. **It does not change CSS's
commercial economics, compute any fee by default, move money, or integrate with any payment system.**

## Principle preserved

CSS compensation relates to profitable, CSS-attributable trading, subject to the existing profitability and
loss-recovery controls. The owner has stated a concept of **20%** of profitable CSS-attributable trading. It is
recorded as `OWNER_STATED_FEE_CONCEPT = 0.20`, for documentation only, and is not applied. Nothing here alters that
concept or any existing hurdle.

The repository was searched on 2026-10-05 and no implementation of a fee, hurdle or loss-recovery rule was found.
`engine/risk/profit_tier_engine.py`'s 20% is a take-profit tier, not a fee. The owner must therefore point to the
authoritative definition before any policy is approved.

## Four separate ledgers

Each realised close is booked to exactly one ledger, by its lot's **current** origin:

| Ledger | In the CSS-attributable base? |
|---|---|
| `CSS_RECOMMENDED` | Yes |
| `CSS_RECOMMENDED_MODIFIED` | **Owner decision** (`modified_treatment`): EXCLUDE / INCLUDE / SEPARATE. Undecided → excluded and reported separately |
| `USER_INDEPENDENT` | **Never.** This is a hard rule, asserted in code and never shown as CSS profit |
| `ORIGIN_UNDER_REVIEW` | **Never while under review.** Once a reviewer resolves it (an evidenced transition), the result appears in the resolved ledger from the next statement |

`statement()` returns:
- each ledger's realised P&L and entry count;
- the included and excluded ledgers, each exclusion with its reason;
- the base;
- every entry (lot, closing order, fill, time, P&L);
- the policy version and its pending decisions;
- `fee` and `fee_status`.

## Fee calculation is gated

A fee is computed only when all of these hold:
- `approved=True` with an `approval_ref`;
- `fee_rate` is set;
- `modified_treatment` is set;
- `loss_recovery` names a supported method.

Otherwise `fee` is `None` and `fee_status` reads, for example, `NOT_COMPUTED: fee_rate, loss_recovery,
modified_treatment, approval`.

Supported loss-recovery method: `HIGH_WATER_MARK`. Fees apply only to cumulative attributable profit above the
previous peak, so earlier attributable losses must be recovered first. Example (tested):
- prior peak 100;
- prior cumulative −150;
- this period +200, giving cumulative 50;
- chargeable profit 0, fee 0.

This is offered as a mechanism. Whether it matches CSS's existing control is an owner decision. Any other method
name is reported as `UNSUPPORTED_METHOD`, with no fee.

## What the customer sees

The results view shows:
- CSS-attributable P&L, independent P&L and the combined result as three headline numbers;
- the four ledgers in a table;
- the statement that CSS recommendations are not guaranteed profits and that the user remains responsible for every
  trade.

The figures are segregated. Fee bases are computed only under an approved commercial policy.

## Open decisions

| Decision | Default until decided |
|---|---|
| Treatment of `CSS_RECOMMENDED_MODIFIED` results | Excluded from the base, reported separately |
| Fee rate (owner-stated concept 20%) | Not applied |
| Loss-recovery method and its parameters (high-water mark? reset period? per-account?) | No fee computed |
| Statement period and settlement | None (statements can be produced for any period) |
| Approval record (who, when, reference) | No fee computed |
| Treatment of costs (commissions, financing) in the base | Realised P&L as booked by the lifecycle; cost handling TBD |
