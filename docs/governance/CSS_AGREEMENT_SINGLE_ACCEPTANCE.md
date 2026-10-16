# Operating agreement: single final acceptance

**Simulation and paper only. Live trading is NOT authorized.**

## Problem
`tools/css_sim_cad146.py run` asked for an exact `yes` after every one of the 12 pages. It did this separately for each of the two simulation tracks, so the operator confirmed **24 times**. Any other answer (for example `y`) aborted activation.

The old flow also wrote `run.json` (the 48-hour start time) **before** the agreement was accepted. An aborted activation therefore left a "started" run behind.

## New flow
**Model.** `backend/trading_profiles/agreement_review.py` holds `AgreementReview`. It does not depend on any particular interface: the CLI uses it now, and web or mobile can use it later.

**Navigation.** The reader moves freely with Next and Previous. A page counts as reviewed once it has been displayed in full and the reader moves past it. Nothing is accepted page by page.

**One acceptance.** It is offered on a final screen, only after all 12 pages have been reviewed. The screen shows:
- the agreement id, version and content SHA-256;
- the operator;
- the operating mode, risk personality and limits;
- the policy hash;
- the acknowledgement text.

**Two tracks, one review.** A single review feeds both tracks' consent ledgers: one display, one acceptance, recorded in each ledger with the same `agreement_session_id`. The review refuses to start if the ledgers differ in agreement content or settings.

**CLI controls**
- Enter or `n`: next page.
- `p`: previous page.
- `q`: quit; this records a decline.
- On the final screen: type `ACCEPT`, `p` to go back, or `d` to decline.

Unrecognised input, including `y` and `yes`, is explained and re-prompted; it never aborts the run. Closed input (EOF) and interruptions are recorded as a decline.

**Start order:** agreement accepted → `run.json` written → the 48-hour clock starts. A declined review leaves no started run.

**Recorded in each ACCEPTED ledger record** (hash-chained):
- the agreement version and SHA-256;
- the per-page hashes, review method and timestamps;
- the acceptance timestamp;
- `operator_id`;
- the operating mode, risk personality, limits and policy hash;
- the acknowledgement hash;
- `agreement_session_id`.

The simulation journal adds an `AGREEMENT_ACCEPTED` event. A decline produces a `DECLINED` ledger record.

## Unchanged protections
`ConsentService` still enforces every check server side:
- the review is bound to the session;
- a page cannot be reviewed before it is presented;
- page and manual hashes must match;
- incomplete reviews are rejected (`pages_not_reviewed`);
- the acknowledgement is required;
- stale proposals and reviews expire (`change_expired`, `review_expired`; 30 minutes and 2 hours);
- an altered manual is rejected (`manual_version_mismatch`, `manual_changed_restart_review`);
- tampered or mismatched settings are rejected (`pending_change_tampered`, `policy_hash_mismatch`);
- replay is refused.

At every decision, `verify_active` still checks the chain, the policy, renewal and tampering.

Also unchanged:
- R7 (one-hour operator sign-on, re-attested by `attest`; never automatic);
- R14F, AntiBleedGuard and ExecutionGate;
- the live kill switch, which preflight requires to be engaged;
- `CSS_SIM_ENTRY_HALT` and the global emergency stop;
- the preflight, the calibration gates and capital (CAD 14,600).

## When the agreement is shown again
**Not shown on restart or resume** while the acceptance in both track ledgers is still valid, that is, when `verify_active` passes and the accepted policy matches the simulation's settings.

**Shown again when:**
- the agreement version changes materially (`renewal_required`);
- the content or acknowledgement changes;
- the ledger is tampered with;
- the accepted settings differ.

**Re-acceptance does not restart a trial that already started.**

**Policy for new runs:** a new `--root` is a new isolated ledger and needs its own single acceptance. This is a policy choice; carrying an acceptance across runs would need an owner decision on its validity period.

## Operator action (FINANCE)
1. **Check the aborted run directory.** If the aborted activation left a `run.json`, check whether its directory contains `track_a/consent_ledger.jsonl` with an `ACCEPTED` record. Under the old flow, it will not.
2. **Re-run the same `run` command and `--root` on this branch.** Preflight runs first. You then page through the agreement and type `ACCEPT` once.
   - Because no cycle had ever run and neither track was ever activated, the trial clock starts at acceptance.
   - `run.json` records `clock_restarted_reason=activation_never_completed` and the old `aborted_started_utc`.
   - Capital and calibration artifacts are not touched.
3. **Alternatively, start with a new `--root`.**
