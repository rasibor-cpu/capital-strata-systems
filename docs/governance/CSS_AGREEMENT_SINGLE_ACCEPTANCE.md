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

## Authenticated consent (Grok audit A-M2)
The consent ledger's SHA-256 chain detects accidents, but on its own it does not authenticate anything: a local writer could rewrite a record, recompute the chain and repoint the active settings. Simulation consent is therefore **signed with keys the run folder never holds** (`backend/trading_profiles/consent_signing.py`).

**What is signed and checked at every decision (`verify_active`; fails closed on any failure):**
1. **The active ACCEPTED record.** Every ledger entry carries an Ed25519 signature over its `entry_hash`. The key must be known and not revoked (`consent_ledger_signature_invalid`).
2. **The active-acceptance pointer.** `consent_active_pointer.json` binds the user, the record hash, the policy hash and the run binding, and is signed separately. Repointing or editing it is refused (`consent_active_pointer_*`).
3. **External anchoring.** After every append, a `ledger_anchor` checkpoint over the consent ledger is signed. It reuses the existing Ed25519 checkpoint format, canonical JSON and prefix commitment. Its statement is written to the key directory, **outside the run root**.
   - Verification requires that every checkpoint's digest and chain linkage hold.
   - The latest checkpoint must be signed by a valid key and must equal the external statement.
   - The ledger must still begin with exactly the anchored prefix, and the active record must lie inside it.
   - Truncation, rollback, a rewritten prefix or a deleted statement are refused (`consent_anchor_*`, `consent_ledger_truncated`, `consent_ledger_anchored_prefix_modified`).

### Key custody (Windows DPAPI, per user)
**Location.** `%LOCALAPPDATA%\CapitalStrata\consent-signing\`. It can be overridden with `CSS_CONSENT_KEY_DIR`, which still uses DPAPI.
- Each key's private seed is stored as `<key_id>.ed25519.dpapi`, encrypted with `CryptProtectData` in the **current user's** scope. It is called in-process, with no UI and no subprocess, so the seed never crosses a process boundary.
- `registry.json` holds public keys and their status.
- `anchors\` holds the external checkpoint statements.

**Placement.** The key directory may not be inside, equal to, or contain the simulation root or a track root; otherwise the run is refused (`consent_key_dir_overlaps_run_root`). No key material is written to the run folder, and a test scans every file in the run for the seed.

**Explicit account binding.** Each key records the Windows account (`DOMAIN\user`) and the machine it was created for, and the same identity is the DPAPI entropy.
- Another account gets `consent_key_account_mismatch`.
- Editing the registry's account field does not help: the seed still decrypts only for the original account (`consent_key_unavailable`).

**Other platforms.** There is no DPAPI, so the simulation refuses to start (`consent_signing_unavailable`). Tests use a SYNTHETIC test-only backend that production code never sees.

**No hard-coded keys, no key output.** Keys are generated on first use. Nothing logs, prints or reprs key material, and errors carry stable reason codes only.

### Operator procedures
All of these run on FINANCE under the operator's own Windows account: `python tools/css_sim_cad146.py keys <action>`.

| Action | Effect |
|---|---|
| `keys status` | Shows the key directory, account, machine and the active `key_id`. It creates the first key if none exists. |
| `keys rotate --reason "..."` | Creates a new ACTIVE key; the previous one becomes RETIRED. A RETIRED key still verifies what it signed and never signs again, so existing acceptances stay valid. **Rotate at least every 90 days, and whenever the operator account changes.** |
| `keys revoke --key-id <id> --reason "..."` | Compromise response. The key is marked REVOKED and its protected seed is deleted. Everything it signed stops verifying, so each affected run needs one fresh acceptance. A started trial's clock is never reset. |
| `keys export-public --out <file>` | **Backup.** Exports the public verification registry: public keys, their status history and the account each is bound to. Keep it with the run evidence so historical acceptances stay verifiable. |

**Backup and recovery policy.** The private seed is **deliberately not exportable**. DPAPI per-user blobs are recoverable only by the same Windows user profile.
- If the profile or key is lost, run `keys rotate`, or let a new key be created, and then re-accept once per affected run.
- Losing a signing key never needs a restore, because consent is per run and can always be given again.
- Back up `registry.json` and the `anchors\` folder (via `keys export-public`, plus a file copy) together with the run evidence.

**Migration.** An acceptance made before signing existed (unsigned) is not current under the new code. The next start presents the agreement once. As always, re-acceptance never restarts a started trial's clock, and **the running FINANCE trial is not touched by this change**.

**Residual risk.** Malware running as the operator's own Windows account can use DPAPI exactly as the operator can. Host and account security (EDR, no shared accounts, locked sessions) remain operator controls. The external statement sits in the same user profile. For stronger independence, also publish `keys export-public` and each run's latest statement off-host, for example as a GitHub comment or in owner email.

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
