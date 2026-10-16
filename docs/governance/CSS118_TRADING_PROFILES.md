# CSS-118 — Startup modes, risk personalities, mandates, user manual and mandatory risk acceptance

Status: **review-only implementation (paper/simulation). Not live-trading authorization.**
Integration parent: `24805875821747542b7ffa0007db6bcd583068db` (frozen CSS-065 candidate + #116 repair).
Safety boundary unchanged: `execution_allowed=false`, `live_trading_blocked=true`,
`broker_execution_armed=false`, `advisory_only=true`. PRODUCTION_GO=NO.

Owner decisions implemented (issue #118 comments of 2026-10-15 and 2026-10-16):
- the trading-profiles addendum;
- **four** startup modes and the non-bypassable consent gate;
- the User Operating Manual with scroll-gated, explicit risk acknowledgement;
- user-configurable limits that can only tighten (with the precedence below).

## 1. Startup operating modes (exactly four)

| Mode | Signals accepted | Decision authority | Route | Fills |
|---|---|---|---|---|
| Simulated Trading | any | practice only | canonical gates, then a no-route stub (the validation pipeline is not called) | simulated |
| CSS-Assisted Trading | CSS proposals (`CSS_AUTONOMOUS_ENGINE`) or the user's own manual orders (`USER_MANUAL:<user>`) | **the user approves or rejects every order** | proposal (no gate side effects), then on approval the full canonical chain re-runs | simulated |
| Copy a CSS Trader | the consented trader's signals | personality + limits within a signed mandate | canonical paper chain | simulated |
| CSS Autonomous Trading | `CSS_AUTONOMOUS_ENGINE` only | CSS, within the accepted settings | canonical paper chain | simulated |

Rules that apply to every mode:
- **No mode permits any live or broker order path** (`ModePermissions` invariant, tested).
- **Assisted proposals:**
  - bound to the user and session;
  - expire after 5 minutes;
  - single-use (replay rejected);
  - hash-protected against tampering;
  - an approval can never enlarge the approved size.
- **Migration:** saved three-mode preferences (schema v1) are read as a *previous selection* only. Those users have no active settings until they accept the agreement for the four-mode contract.

## 2. Risk personalities (exactly five) and user limits — proposed defaults for owner review

| | Safe | Conservative | Balanced | Aggressive | Ultra Aggressive |
|---|---|---|---|---|---|
| Asset classes | FX | FX, Crypto | FX, Crypto, Futures | all | all |
| Trade-quality recommendation | EXECUTE | EXECUTE, PREFERRED | EXECUTE, PREFERRED | EXECUTE, PREFERRED | EXECUTE, PREFERRED, WATCH |
| Min trade-quality score | 80 | 72 | 65 | 58 | 50 |
| Min probability | 0.66 | 0.62 | 0.58 | 0.55 | 0.53 |
| Min CAIE score | 130 | 120 | 110 | 100 | 90 |
| Margin state accepted | NORMAL | NORMAL | NORMAL | NORMAL, WARNING | NORMAL, WARNING |
| Risk per trade (% equity at stop) | 0.25 | 0.50 | 1.00 | 1.50 | 2.00 |
| Max stop distance % | 1.0 | 1.5 | 2.0 | 2.5 | 3.0 |
| Max position / symbol % equity | 2 | 4 | 6 | 8 | 10 |
| Max total exposure % equity | 5 | 10 | 20 | 30 | 40 |
| Max open positions | 2 | 3 | 5 | 7 | 8 |
| Daily-loss / drawdown halt % | 1 / 3 | 2 / 5 | 3 / 8 | 4 / 12 | 5 / 15 |
| Take profit (R) | 1.5 | 1.75 | 2.0 | 2.5 | 3.0 |
| Time stop (hours) | 24 | 48 | 72 | 120 | 168 |

**Precedence (most restrictive wins):**
1. platform eligibility and hard safety limits;
2. R7 / R14F / AntiBleedGuard, kill switch, margin, capital governor, pilot caps;
3. personality / mandate;
4. **user limits** (`limits.py`: tighten-only; a looser, unknown or malformed value is rejected, never clamped);
5. per-order approval (assisted mode).

**Other rules:**
- **Mandate scope** must fit within the personality's asset classes.
- **Sizing** is never raised to meet a gate minimum.
- **Legacy engine modes** (SAFE…EXPANSION) are untouched. `LEGACY_ENGINE_MODE_MAPPING = {}`, and R7/R14F use the engine mode in force.
- **The values in this table are proposed defaults, not approved production values.**

## 3. CSS User Operating Manual, Trading Assumptions and Risk Disclosure Agreement

**The document**
- **Location:** `docs/user/CSS_USER_OPERATING_MANUAL.md`, with 12 required pages:
  1. about
  2. modes
  3. personalities and limits
  4. gates, guarantees and assumptions
  5. instrument, cost and margin risks
  6. signals, copy-trading and autonomy
  7. operations, outages and security
  8. pausing and kill switch
  9. tax and regulatory
  10. scenarios
  11. glossary
  12. support and acknowledgement
- **Controlled manifest:** `CSS_USER_OPERATING_MANUAL.manifest.json` holds the version, effective date, file and per-page SHA-256 and the change history. Each history entry has a `material` flag.
  - `tools/build_css_manual_manifest.py` issues new versions and never rewrites an existing one.
- **Integrity:** `manual.py` verifies the file against the manifest and **fails closed** on any mismatch.
- **Legal review pending:** the text says that acceptance is not a waiver of non-waivable duties (fraud, negligence, statutory protections), and that jurisdiction-specific review is required before any public or live use.
- **Placeholder:** the support contact is a placeholder for the owner to complete.

**The acknowledgement** is the owner's exact text (`ACKNOWLEDGEMENT_TEXT`, verified by a test). It is never pre-checked.

## 4. Consent gate (server-enforced; client scroll gating is UX only)

1. **Propose:** `POST /changes` creates a PENDING change with the exact effective settings, risk implications and an immutable **policy hash**, covering mode, personality, limits and mandate terms. Nothing is active yet.
2. **Open review:** `POST /consent/reviews` opens a review bound to the **authenticated session** and the **manual version and hash**.
3. **Review pages:** for every page, the server **presents** it (`GET …/pages/{id}`). The client then reports it **reviewed**, with the page hash and one of these methods:
   - `scroll_bottom`
   - `keyboard_end`
   - `screen_reader_end`
   - `non_scrollable_presented`

   A page can't be marked reviewed before it was presented, or with a stale page hash.
4. **Accept:** `POST /consent/reviews/{id}/accept` requires:
   - every page reviewed in this session;
   - `acknowledgement_checked` exactly `true` (strings, 1 and the like are rejected);
   - the exact acknowledgement hash;
   - the current manual version and hash;
   - the policy hash the user was shown.

   It also rejects a tampered pending change, a replay, an expired change or review, another session, and another user.
5. **Transactional activation:**
   - first, an `ACCEPTED` record is appended to a SHA-256 hash-chained ledger;
   - then the copy mandate (if any) is signed and stored;
   - then the active settings are written, referencing the ledger record.

   A failure part-way through leaves nothing active.
6. **Revalidation at every decision** (`verify_active`): the trade is rejected if consent is missing, the ledger is broken, the settings were tampered with, the policy or mandate doesn't match, or a later **material** manual version requires renewal. A non-material update does not require renewal.
7. **Receipts and history:**
   - receipt and document history: `GET /consent/receipts`;
   - receipt download: `GET /consent/receipts/{id}/download`;
   - the manual, at any time: `GET /manual`, `GET /manual/pages/{id}` and `GET /manual/download?format=md|txt` (the plain-text format is the accessible alternative).
8. **Emergency risk reduction never needs consent:**
   - `POST /emergency/pause`;
   - `POST /mandates/{id}/revoke`;
   - protective exits;
   - kill switches.

   Resuming, and reauthorizing a mandate, do require valid consent.

**Onboarding UI** (`/trading-profiles/onboarding` on the mobile app). It has four steps: settings, exact summary and implications, page-by-page reader, and acknowledgement.
- **The reader:**
  - each page is a focusable scroll region with an end-of-page marker (reached by scrolling into view, or by keyboard or screen-reader focus);
  - "Next" is disabled until the end of the page is reached;
  - a non-scrollable page counts once presented, so no scroll is forced;
  - progress is announced through `aria-live` regions.
- **The acknowledgement:** the checkbox starts **unchecked**, and stays disabled until every page is reviewed. "Accept" is disabled until the box is checked; unchecking disables it again.
- **Always available:** "Pause new trading now" is shown at the top of the page.
- **Layout:** responsive (390 px width tested), supports dark mode and reduced motion.

## 5. Gate order for every trade (simulated / assisted / copy / autonomous)

1. Safety: observed safety-flag verdict SAFE, live-order and global kill switches, known engine mode.
2. **Consent:** active accepted settings, not paused, `verify_active` passes; personality tightened by the user's limits.
3. Authority:
   - copy: the consented signed mandate (trader, scope, reauthorization);
   - autonomous: CSS engine signals only;
   - assisted: CSS proposals or the user's own manual orders.
4. Personality eligibility, drawdown and daily-loss halts.
5. Sizing and exposure caps; personality open-position limit; global cap of 10.
6. TradeQualityScoringEngine and CAIE floors.
7. R14F (`backend/governance/r14f_profitability_gate.py`; parity with the dashboard is proven by executing its own functions).
8. Assisted mode stops here and creates a proposal. On approval, everything above re-runs.
9. `CanonicalExecutionIntegration`:
   - **R7** (real per-asset counts);
   - **ExecutionGate**: AntiBleedGuard (net edge ≥ 25 bps, minimum size 50, per-follower cooldown), MarginTradeGate, RiskGovernor;
   - validation-only pipeline (rejects live).
10. Deterministic simulated fill; hash-chained attribution record.

## 6. Integration status and open items (not claimed as done)

- **Not wired yet:**
  - no trader-signal feed or trader registry exists (`trader_id` is free text);
  - the legacy dashboard loop and the mobile ticket path are unchanged and do not use this layer (the owner places them out of scope until canonical-routing tests exist);
  - the mobile sign-in does not yet redirect to onboarding. The gate is enforced server-side wherever this layer is used.
- **Owner decisions:**
  - the parameter values in §2;
  - the support contact;
  - jurisdiction-specific legal review of the manual;
  - signing-key provisioning and custody;
  - the default reauthorization frequency.
- **Ceilings that don't exist in code:** CAD40 aggregate and "two concurrent parents" are absent, so they cannot be enforced here. CAD20 exists, and this layer never reaches live.
- **Follow-up:** have the dashboard import the shared R14F module, so only one copy of the thresholds exists.
- **Profitability:** no profitability claim is made. Cost-adjusted out-of-sample evidence is still required.

## 7. Rollback

The change is additive:
- `backend/trading_profiles/`;
- `backend/governance/r14f_profitability_gate.py`;
- `docs/user/` (manual and manifest);
- `tools/build_css_manual_manifest.py`;
- tests;
- one router mount in `dashboard/mobile/mobile_app.py`.

To roll back, revert the branch commits, or remove the router mount. Data lives only under `artifacts/trading_profiles/` (hash-chained ledgers; archive rather than delete).
