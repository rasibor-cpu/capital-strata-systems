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
- `agreement_session_id`;
- `run_binding`: a SHA-256 of the track's resolved, case-normalised root location **and** the run's random `run_id`. The `run_id` is generated before the review and written to `run.json` only after acceptance. It is the run the acceptance is valid for.

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
- the run directory was copied or moved, or a new run was created at the same path with old track state restored (`acceptance_from_another_run`; Grok audit A-M3 and F-1);
- the acceptance carries no run binding (`acceptance_not_bound_to_run`).

Runs started before `run_id` existed are bound by location only.

**Every decision re-checks the binding.** The router's `verify_active` refuses an acceptance from another run (`consent_run_binding_mismatch`). A read-only simulation (`report`) can never run `cycle()` (Grok F-2).
- the agreement version changes materially (`renewal_required`);
- the content or acknowledgement changes;
- the ledger is tampered with;
- the accepted settings differ.

**Re-acceptance does not restart a trial that already started.**

**Policy for new runs (owner decision, approved 2026-10-16):** each new isolated simulation `--root` requires one fresh final-screen acceptance. Consent is never reused across runs. A material change to the agreement version or content, or to the accepted trading settings, requires re-acceptance. The audit evidence (version, hash, operator, session, timestamp) and all fail-closed controls are preserved.

**Known limitation (Grok audit A-M2, open).** The consent ledger is an unkeyed SHA-256 chain, and the preference file is unsigned. Someone with write access to the run root can rewrite a record, recompute the chain and repoint the active settings; that includes forging a run binding. Accidental edits are detected; deliberate forgery by a local writer is not. The planned fix is to HMAC the entries with a key held outside the run root, or to anchor the chain head externally.

## Operator action (FINANCE)
**The FINANCE trial that is already running is out of scope for this change.** Its output shows:
- `run started_utc=2026-10-16T21:04:25.564210+00:00`;
- a scheduled end of `2026-10-18T21:04:25.564210+00:00`;
- monitoring observations at 21:07 and 21:12 UTC.

Leave it alone:
- **Do not** switch its worktree to this branch.
- **Do not** re-run, edit or reset its `run.json`, ledgers, capital or clock.
- **Do not** intervene before its status has been confirmed read-only, for example with `python tools/css_sim_cad146.py report --root <its root> --out <file>`.

**The code cannot restart a started run's clock.** The clock is restarted only when both conditions hold:
1. neither track was ever activated;
2. the journal has no cycle (no `HEARTBEAT`).

A running trial meets neither condition. `test_started_trial_is_never_reset_even_when_reacceptance_is_needed` covers this.

**Use this flow for the next new run.**
1. Choose a new `--root`.
2. Run preflight, then `run`.
3. Page through the agreement with Enter and type `ACCEPT` once. The clock starts at that acceptance.
