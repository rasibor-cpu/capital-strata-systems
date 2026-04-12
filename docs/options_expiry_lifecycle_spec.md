# CSS Options Expiry Lifecycle – Master Specification
## Phase 1 Sandbox Expiry Governance Lock

### Purpose
Defines lifecycle rules for option contracts reaching expiry in CSS sandbox trading.

This governs:

- expiry day monitoring
- automatic contract closure
- worthless expiry write-off
- ITM simulated assignment handling
- expired position archival rules

---

## Supported Scope (Phase 1)

Strategies:
- Long CALL only
- Long PUT only

Underlyings:
- SPY
- QQQ
- AAPL

Sandbox only.

---

## Expiry State Definitions

Each option position must transition through:

1. OPEN
2. ACTIVE
3. EXPIRING_TODAY
4. EXPIRED_ITM
5. EXPIRED_OTM
6. CLOSED_ARCHIVED

---

## Rule 1: Expiry Detection

Trigger when:

expiry_days == 0

System must mark:
EXPIRING_TODAY

---

## Rule 2: Intraday Expiry Monitoring

On expiry day:
- continue mark-to-market valuation
- allow manual close before session end

Cutoff time:
15 minutes before market close

After cutoff:
no new option opens allowed for expiring contracts

---

## Rule 3: OTM Worthless Expiry

If option expires out-of-money:

CALL:
spot <= strike

PUT:
spot >= strike

Then:
- premium becomes full realized loss
- contract value = 0
- mark EXPIRED_OTM

---

## Rule 4: ITM Expiry Handling

If option expires in-the-money:

CALL:
spot > strike

PUT:
spot < strike

Then simulate intrinsic settlement:

Intrinsic Value =
abs(spot - strike) × contracts × 100

Then:
- realize intrinsic payout
- close contract automatically
- mark EXPIRED_ITM

---

## Rule 5: Auto Close and Archive

After expiry processing:

move position into archive ledger:
expired_positions_log

Then assign:
CLOSED_ARCHIVED

---

## Rule 6: Audit Logging Required

Every expiry event must log:

- symbol
- option_type
- strike
- expiry_date
- final spot price
- realized pnl
- expiry classification

---

## Future Phase Extensions

Later phases may support:
- short options expiry assignment
- spreads expiry netting
- broker live OCC assignment logic

Not included in Phase 1.

---

## Implementation Target

Future code target:

backend/app/options/options_expiry_engine.py

---

## Governance Status

Architecture locked.
Safe for Laptop 1 implementation.
No production execution path affected.
