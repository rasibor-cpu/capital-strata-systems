# CSS-118 — AntiBleed minimum size vs CAD 20 pilot orders: paper-only exception design (FOR OWNER REVIEW)

**Status: design only. NOT implemented, NOT enabled.** Today every conflicting pilot order is
rejected (owner direction 6). Nothing in this branch relaxes AntiBleed; the existing live-pilot
min-size capability stays hard-disabled (`PILOT_MIN_SIZE_EXCEPTION_ENABLED = False`) and no
caller passes it.

## 1. The conflict (evidence)
Source: `docs/evidence/CSS118_ANTIBLEED_CAD20_EVIDENCE.json`, regenerated deterministically by
`python tools/antibleed_cad20_evidence.py` (pinned by `tests/test_css118_closeout_governance.py`).

| Finding | Evidence |
|---|---|
| Pilot-envelope orders are sized to ≤ CAD 20 incl. fees | 6/6 replayed orders sized CAD 19.99 |
| All are rejected by AntiBleed's minimum size (50) | 6/6 `execution_gate: anti_bleed_guard:trade_size_too_small`, including orders with 200 bps expected edge |
| AntiBleed's 25 bps net-edge rule ignores **fixed** per-order fees | At CAD 20 a CAD 0.05 fixed fee = 25 bps, raising the required expected move from 29 to 54 bps; CAD 0.10 → 79 bps |
| The `50` has no currency in code | `live_micro_pilot_governor` labels it `UNSPECIFIED`; the governed router uses account currency (CAD) |

Conclusion: the minimum size is a real protection. Below ~CAD 50, fixed costs dominate, and the
current net-edge rule cannot see them. A blanket CAD 20 exception would remove that protection.

## 2. Options for the owner
| Option | Effect | Risk |
|---|---|---|
| **A. Keep rejecting (current)** | No pilot-sized order ever fills (paper or live) | None added; the CAD 20 pilot cannot trade |
| **B. Raise the pilot ceiling to ≥ CAD 50** | Orders pass the size rule; other gates unchanged | Larger exposure per order; needs a separate owner decision on caps (CAD 20 per parent, CAD 40 aggregate stay binding until then) |
| **C. Paper-only governed exception (below)** | Paper evidence on CAD 20 economics under stricter, fee-aware rules | Paper results are hypothetical; must never leak to live |
| D. Lower the AntiBleed minimum globally | — | **Not recommended**: weakens a platform-wide control |

## 3. Option C design: paper-only, separately governed exception
1. **Scope:** `SIMULATED_PAPER_FILL` only. The capability is rejected at construction unless the
   route is the governed paper router *and* `broker_mode == "PAPER"`; it has no code path to
   `UnifiedExecutionPipeline` live modes, the live micro-pilot governor or any broker adapter.
2. **Authorization:** a dual-control, signed `PaperMinSizeException` record:
   - two distinct approvers (sponsor and risk), Ed25519, verified against an enrolment file;
   - bound to account, symbol set, pilot envelope, an expiry of 14 days or less and a maximum order count;
   - recorded in a hash-chained ledger that is anchored with the C6 anchoring.
3. **Stricter replacement rule, not a waiver:** the order must clear
   `expected_move_bps ≥ 25 + variable_cost_bps + fixed_fee_cad / notional × 10 000 + safety_margin_bps`.
   The fixed fee comes from a certified broker fee schedule in CAD. Edge, cooldown, R7, R14F,
   capital governors, the envelope and the kill switch all still apply unchanged.
4. **Audit:** every use records the exception id, the inputs and the fee-adjusted edge. Revocation
   is immediate and single-control.
5. **Exit criteria for any live discussion:** a minimum number of paper orders with a
   cost-adjusted, out-of-sample net result. That would be a separate owner decision; it is never
   automatic.

## 4. Owner decisions required
- Choose A, B or C. Until a decision is recorded, **A applies**.
- For C: name the approver roles and holders, the broker fee schedule (CAD), the safety margin,
  the maximum paper order count and the expiry.
- Certify the currency of AntiBleed's minimum size (CAD vs unspecified).
