# CSS simulated capital profiles — isolated candidate

Status: implementation candidate, **NOT RELEASED**, no live broker path added.

## User experience
Default standard simulated balance: CAD 100,000. Presets: small CAD 10,000, intermediate CAD 25,000, standard CAD 100,000, advanced CAD 250,000. Custom: CAD 1,000–1,000,000, with cents precision. Account resets must preserve an audit trail; this candidate does not yet implement a reset UI or an onboarding UI.

## Engineering trial
For the isolated two-track 48-hour trial use:

```sh
python tools/css_sim_cad146.py run --root artifacts/simulation/cad14600-20261016 --artifacts artifacts/calibration --operator YOUR_ID --hours 48 --capital-profile engineering
python tools/css_sim_cad146.py report --root artifacts/simulation/cad14600-20261016 --capital-profile engineering
```

Engineering capital: CAD 14,600. Reference: CAD 146. Report includes illustrative P&L scaling, 100:1, not executable results at CAD 146. Returns (%) are compared without scaling. The CLI default is engineering to preserve the intended internal trial; standard customer onboarding must explicitly select the standard profile.

Existing per-run metadata persists capital on restart; changing the profile against an existing root must not silently reset the balance. Use a new root for a new scenario.

**Governance unchanged:** Track A requires calibration approvals; Track B is research-only; R7 sign-on, AntiBleed CAD 50 minimum, R14F, consent, safety flags, position limits and data outage controls stay intact. Live orders disabled. No 48-hour run was started.

## Validation (branch `claude/css-sim-validation-20261016`)
Executed, see `tests/test_css_simulation_capital_profiles.py` and `tests/test_css_sim_validation.py`.
Changes made while validating:
- Customer paper accounts now actually default to CAD 100,000 (`PaperBook` default was CAD 10,000); existing accounts keep their persisted equity.
- Illustrative normalisation rounds half-up explicitly (the committed test expected −0.37; banker's rounding gave −0.36).
- Audited capital reset: `PaperBook.reset_account` (holder or SUPER_USER, reason required, no open positions, never pilot-envelope accounts, permitted capital only), with the prior account kept in a hash-chained log.
- The simulation now honours the ambient kill switch exactly like the canonical router (it previously passed an empty env).
- `run` refuses to resume a root with a different capital (no silent reset); report reference comparison no longer crashes on legacy CAD 146 runs.
- Report adds true max drawdown (from per-cycle equity), unrealized P&L, capital utilisation and per-instrument results.

Note: `.env.paper.example` sets `CSS_LIVE_ORDER_KILL_SWITCH=1`; with it, the canonical router and this simulation reject every entry. The operator must decide whether the paper trial runs with the kill switch clear.

Still outstanding: a capital-selection UI in onboarding, an HTTP endpoint for resets, a continuous host with market-data access, and operator sign-off.
