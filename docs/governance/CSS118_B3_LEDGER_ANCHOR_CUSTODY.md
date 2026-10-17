# CSS-118 B3 — Ledger anchoring production custody design

**Status: design complete; no production key enrolled. Ledgers report `UNANCHORED` until owner enrollment.**

Implementation already present: `backend/trading_profiles/ledger_anchor.py`,
`tools/verify_css_ledger_anchors.py`, tests in `tests/test_css118_ledger_anchor.py`.

## Production design (ready for owner approval)

### 1. Key custody
- Algorithm: Ed25519.
- Production private key: **offline signer or HSM**; never in git, CI secrets for signing, or developer workstations with network write access to production ledgers.
- Development/test keys only under `CSS_LEDGER_ANCHOR_SIGNING_KEY` in isolated labs.
- Dual control: key ceremony with two SUPER_USER witnesses; ceremony receipt stored offline.

### 2. Public key publication
- Publish verifying public key via an owner-controlled channel independent of the CSS host
  (e.g. signed release notes + immutable object store).
- Verifier (`tools/verify_css_ledger_anchors.py`) needs only: ledger files, public key, optional external statement.

### 3. Checkpoint cadence
- Recommended: every 100 ledger appends **or** every 15 minutes while the paper/live process runs, whichever first.
- Emergency checkpoint on kill-switch activation and on process shutdown.

### 4. External statements
- After each checkpoint, export a statement (checkpoint hash + public key id + UTC time) to
  independent storage the CSS host cannot rewrite.
- Rollback of the anchor log itself is already detected by the chained verifier.

### 5. Enrollment gate
Production key enrollment requires a separate written owner authorization naming:
custody location, public-key publication URL, cadence, and the release candidate commit.

Until that authorization: `PRODUCTION_GO=NO` for anchoring enrollment.
