# CSS trade-origin attribution (policy TO-2.0.0)

Source: `backend/app/trade_origin/model.py`, `lifecycle.py`, `performance.py`. Purpose: the customer can always answer
"how much came from CSS recommendations?" and "how much came from trades I chose myself?". Every figure traces back
to immutable evidence.

## The four states

| Code | Customer label | Meaning |
|---|---|---|
| `CSS_RECOMMENDED` | CSS Recommended | Created from a specific CSS recommendation version through the governed CSS workflow, with no deviation or only non-material ones |
| `CSS_RECOMMENDED_MODIFIED` | CSS Recommended — Modified by You | Same provenance, but with at least one material deviation (each one recorded) |
| `USER_INDEPENDENT` | Your Own Trade | The order references no CSS recommendation. This holds **even if it looks identical to one**: there is no fuzzy or similarity matching |
| `ORIGIN_UNDER_REVIEW` | Origin Under Review | The evidence can't settle it: unknown or missing recommendation version, fingerprint mismatch, reference outside the CSS workflow, a deviation whose treatment is an undecided policy value, a thesis break before its disposition is decided, or legacy records with no origin |

The TO-1.0.0 name `UNATTRIBUTED_REVIEW_REQUIRED` (never deployed) is read as `ORIGIN_UNDER_REVIEW`.

## Classification (once, at order creation)

1. No `recommendation_id` → **USER_INDEPENDENT**.
2. Reference not created through the CSS workflow, version missing, version not on record, or card fingerprint
   (SHA-256 of the card as shown) differs → **UNDER REVIEW**.
3. Otherwise each deviation from the recommendation's **own envelope** is assessed (below) and resolved in this
   order:
   1. THESIS_BREAK → `thesis_break_disposition`, or REVIEW while that is undecided.
   2. POLICY_PENDING → REVIEW.
   3. Expired → `expired_disposition` (default MODIFIED).
   4. Any MATERIAL → MODIFIED.
   5. Otherwise CSS_RECOMMENDED.

## Material-deviation framework

Materiality is measured against the Trade Card's own validity envelope (entry zone, maximum fill slippage, stop
tolerance, leverage, validity window), not against global constants. Where a card is silent, a policy fallback
applies. If that fallback is undecided (`None`), the order goes to review instead of being guessed.

| Field | Non-material | Material | Policy field (default) |
|---|---|---|---|
| Instrument / direction | — | THESIS_BREAK | `thesis_break_disposition` (**TBD** → review) |
| Validity window | inside `issued_at`–`valid_until` | executed after expiry | `expired_disposition` (MODIFIED, per directive) |
| Size | smaller (less exposure) | larger than recommended beyond the allowance | `size_decrease_is_material` (False); `size_increase_allowance` (0.0 = any increase is material; owner may raise) |
| Leverage | ≤ recommended | above recommended beyond the allowance | `leverage_increase_allowance` (0.0) |
| Entry (limit) | inside the card's entry zone, or better than it | worse than the zone | `entry_fallback_tolerance_bps` when the card has no zone (**TBD** → review) |
| Fill price | inside the zone or within the card's `max_slippage_bps` | adverse slippage beyond it | `fill_slippage_fallback_bps` when the card has none (**TBD** → review) |
| Stop | tightened; widened within the card's `stop_tolerance_bps` | removed; widened beyond the tolerance | `stop_widening_fallback_bps` (0.0 = any widening is material when the card is silent) |
| Target | — | — | `target_change_material` (**TBD** → review) |

The defaults are conservative and none is an arbitrary threshold: a zero allowance means "any increase in risk is
material", and every other number comes from the card itself. `MaterialityPolicy.pending_decisions()` lists the
four TBD fields. The policy snapshot and its SHA-256 are stored on every record.

## Evidence record (immutable)

Each `AttributionRecord` is a frozen dataclass written once to the append-only `OriginLedger`. It holds:
- order id, user key, origin, reason, determination time and stage;
- instrument and side;
- a snapshot of the full order (requested parameters, action time, leverage);
- a snapshot of the full recommendation (id, version, card id, entry zone, slippage limit, stop and tolerance,
  target, leverage, validity);
- the deviations, each with field, severity, recommended value, executed value and note;
- the policy snapshot, version and fingerprint.

`reproduce(record)` recomputes the origin and deviations from the record alone (tested for six scenarios). A second,
different record for the same order is refused.

## State machine

```
            classify (system)
order ─────────────────────────┬──────────────┬───────────────┬──────────────────────┐
                               ▼              ▼               ▼                      ▼
                       CSS_RECOMMENDED  CSS_..._MODIFIED  USER_INDEPENDENT   ORIGIN_UNDER_REVIEW
                         │  │ system:fill_check   │        (terminal)            │
                         │  └────────► MODIFIED   │                              │ reviewer: + reason + evidence
                         └── system ──► REVIEW ◄── system                        ▼
                                                                   CSS_RECOMMENDED / MODIFIED / USER_INDEPENDENT
```

| From | To | Who | Requires |
|---|---|---|---|
| CSS_RECOMMENDED | MODIFIED, UNDER_REVIEW | `system:<component>` (e.g. fill check) | reason; fill checks attach the deviation |
| CSS_RECOMMENDED_MODIFIED | UNDER_REVIEW | `system:<component>` | reason |
| ORIGIN_UNDER_REVIEW | any of the other three | `reviewer:<id>` | reason **and** evidence (e.g. ticket) |
| USER_INDEPENDENT | — | nobody | terminal: a user's own trade is never re-attributed to CSS |

Every transition is appended with its time, actor, reason and evidence. The original record is never changed.
`current()` is the last state, and `history()` returns the full chain. The system can never upgrade a trade to a
CSS state; only a named reviewer with evidence can resolve a review. There is no retroactive silent reassignment.

## Lifecycle

recommendation → order → fill (fill check) → **lot** → partial close → final close → journal → performance →
commercial ledgers.

- A fill is refused when its order has no recorded origin.
- Each opening order is its own lot. Lots of different origins are never merged.
- A lot's origin is the ledger's **current** state for its opening order, so a resolved review flows through the
  recorded transition.
- Realised P&L belongs to the lot being closed. The closing order's own origin is kept on the journal entry.
- A symbol-only close is refused if open lots differ in origin or recommendation.
- Duplicate fills and over-closes are refused.
- Journal entries record, as they stood at that moment: origin, recommendation id and version, and policy version.

## Performance

`segregate()` returns:
- the four segments: realised, unrealised, closed, wins, losses, open positions, win rate;
- `views`: CSS-attributable (recommended + modified, with the components still shown), independent, under review,
  and combined;
- a headline.

`check_totals()` enforces combined = sum of segments. Missing marks are listed, never assumed. Commercial treatment
is covered in `COMMERCIAL_ATTRIBUTION.md`.
