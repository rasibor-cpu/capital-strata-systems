# CSS trade-origin attribution (policy TO-1.0.0)

Source: `backend/app/trade_origin/`. Purpose: the customer can always answer "how much came from CSS recommendations?"
and "how much came from trades I chose myself?", and every figure traces back to evidence.

## Origins

| Origin | Meaning |
|---|---|
| `CSS_RECOMMENDED` | Order created from a CSS Trade Card through the governed CSS workflow, matching the card within tolerance |
| `CSS_RECOMMENDED_MODIFIED` | Same, but the user materially changed size, order type, limit, stop or target (deviations recorded) |
| `USER_INDEPENDENT` | No recommendation referenced, **even if the order looks identical to a recommendation** |
| `UNATTRIBUTED_REVIEW_REQUIRED` | A reference that can't be verified: unknown recommendation, fingerprint mismatch, expired, different symbol or side, outside the CSS workflow, or legacy records with no origin |

## Classification (once, at order creation)

1. No `recommendation_id`: **USER_INDEPENDENT**.
2. Reference not created through the CSS workflow: **REVIEW**.
3. Recommendation not in the registry: **REVIEW**.
4. Card fingerprint (SHA-256 of every field the user saw) differs: **REVIEW**.
5. User action outside the card's validity window: **REVIEW**.
6. Symbol or side differs: **REVIEW**.
7. Any change beyond tolerance: **MODIFIED** (deviations listed). Otherwise **CSS_RECOMMENDED**.

Material-change tolerances: size ±1%; limit, stop and target ±0.25%; removing a stop or target, or changing order
type, is always material. These are owner-reviewable policy values. They only decide recommended vs modified; nothing
ever turns a user trade into a CSS trade.

`OriginEvidence` is a frozen dataclass. `OriginLedger` records it once per order and refuses a different second
classification.

## Lifecycle

recommendation → user action → order → fill → **lot** → partial close → final close → journal → performance →
commercial-attribution inputs.

- Fills are refused for orders without a recorded origin.
- Each opening order is its own lot, carrying that order's evidence; lots of different origins are never merged.
- Realised P&L belongs to the **lot's** origin. The closing order's own origin is kept on the journal entry.
- A close that names only a symbol is allowed only if all open lots share one origin and recommendation; otherwise
  it is refused so a person chooses the lot.
- Duplicate fills and over-closes are refused.

## Performance

`segregate()` returns four segments (realised, unrealised, closed trades, wins, losses, open positions, win rate) and
a total. `check_totals()` enforces total = sum of segments. Missing marks are listed, never assumed. Headline figures:
CSS recommended, CSS including modified, user independent, under review.

**Commercial attribution and billing are not changed.** The module supplies segregated figures only. How modified
and under-review trades are treated is decided by the existing approved CSS commercial-attribution rules. No such rules
file was found in the repository on 2026-10-05, so the owner must confirm the reference.
