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
   - copy: the consented signed mandate (trader, scope, reauthorization) **and** the trader still ACTIVE in the dual-control registry for that asset class;
   - autonomous: CSS engine signals only;
   - assisted: CSS proposals or the user's own manual orders.
4. Personality eligibility, drawdown and daily-loss halts.
5. Sizing, only ever reduced: personality risk/position/symbol/total caps, mandate allocation, the existing
   capital governors (`CapitalAllocationGovernor` 5% single trade, 2% futures/options; `PortfolioGovernor`
   25% total, per-asset caps) and, for pilot-scope accounts, the CAD pilot envelope (§5a).
6. Counts: personality open-position limit; global cap of 10. Then the formal `UnifiedRiskExecutionGate` check.
7. TradeQualityScoringEngine and CAIE floors.
8. R14F (`backend/governance/r14f_profitability_gate.py`; parity with the dashboard is proven by executing its own functions).
9. Assisted mode stops here and creates a proposal. On approval, everything above re-runs.
10. `CanonicalExecutionIntegration`:
    - **R7** (real per-asset counts, session age, role, capital state);
    - **ExecutionGate**: AntiBleedGuard (net edge ≥ 25 bps, minimum size 50, per-follower cooldown), MarginTradeGate, RiskGovernor;
    - validation-only pipeline (rejects live).
11. Deterministic simulated fill; hash-chained attribution record.

### 5a. CAD pilot envelope (`backend/trading_profiles/pilot_envelope.py`)

- CAD 20 per parent including estimated fees (rounded up to the cent), CAD 40 aggregate, at most 2 concurrent parents.
- Fixed ceilings: `PilotEnvelopeConfig` can tighten but never raise them; malformed state, duplicates, non-CAD currency and fractional cents fail closed.
- Independent of, and in addition to, the canonical live caps in `backend/config/order_limit_config.py` (CAD 20 total, CAD 20 per position, 1 position), which are **unchanged** (asserted by test).
- AntiBleedGuard's minimum size (50) still rejects every pilot-sized order; nothing is relaxed (min-size exception stays disabled).

### 5b. Sign-in and route enforcement (`backend/trading_profiles/gatekeeper.py`)

- Sign-in lands on `/trading-profiles/onboarding` unless acceptance is valid and trading is not paused (unreadable stores fail closed).
- `POST /trade`, risk-increasing `POST /controls` (mode/engine-mode escalation, kill switch off, unknown values) and live-micro-pilot `configure`/`arm` return 403 `MANUAL_ACCEPTANCE_REQUIRED` without valid acceptance. Acceptance is necessary, never sufficient: the existing ticket and pilot governors still decide.
- Never blocked: kill-switch engagement, lowering modes, pause, disarm, mandate revocation, protective exits.

### 5c. Approved traders and the signal feed

- `trader_registry.py`: event-sourced, hash-chained with a head anchor (edits, deletions and truncation fail closed). **Ships empty.** SUPER_USER proposes (Ed25519 public key + asset scope); a **different** SUPER_USER approves. Suspend/revoke: one SUPER_USER, immediate. Reinstate after suspension: a different SUPER_USER. Revoked: new proposal required.
- `signal_feed.py`: canonical-JSON payload signed with the trader's key; registered trader + valid signature (else rejected without writing), then ACTIVE + scope, freshness ≤ 120 s (≤ 5 s future skew), replay protection; authenticated decisions go to a hash-chained ledger.
- Consent: copy-mode proposals and acceptances require an ACTIVE trader whose scope covers the mandate.

### 5d. Canonical paper router (`router.py`)

- `on_trader_signal` → feed → COPY followers with that trader's mandate; `on_css_engine_signal` → AUTONOMOUS (decide), ASSISTED (proposal), SIMULATED (no route); `decide_proposal`; `submit_manual_order` (needs a CSS market assessment, else rejected; assisted → proposal to confirm); `run_exit_cycle` (exempt from consent, pause and mandate state).
- Context fails closed: no current sign-on session, unknown or locked role, or unreadable safety flags reject the follower with a recorded reason. The R7 one-hour session rule applies to fan-out, so followers must have signed in within the last hour.
- `PaperBook`: persistent paper account (CAD, realized-PnL equity, peak, day start) and open positions per user.
- HTTP (mounted on the mobile app): `/paper/book`, `/proposals`, `/proposals/{id}/decision`, `/orders`, `/admin/traders[...]` (SUPER_USER), `/feed/signals` (signature-authenticated).

## 6. Integration status and open items (not claimed as done)

- **Not wired:** the legacy dashboard loop and the existing mobile ticket executor do not route through this layer (the ticket route is now gated by acceptance; its execution path is unchanged). No CSS engine process calls `on_css_engine_signal` yet, and the mobile router has no market-assessment provider, so manual paper orders through `/orders` are rejected (`manual_order_requires_css_market_assessment`).
- **Owner decisions:**
  - the parameter values in §2, in particular personalities whose position (6/8/10%) and total exposure (30/40%) exceed the existing capital governors (5% / 25%), which currently bind;
  - whether mobile paper accounts run under the pilot envelope (default off; on, AntiBleed's minimum size rejects every order);
  - which real traders, if any, to propose and approve, and custody of their signing keys;
  - the support contact; jurisdiction-specific legal review of the manual; mandate signing-key provisioning; the default reauthorization frequency.
- **Follow-up:** have the dashboard import the shared R14F module, so only one copy of the thresholds exists.
- **Profitability:** no profitability claim is made. Cost-adjusted out-of-sample evidence is still required.

## 7. Rollback

The change is additive:
- `backend/trading_profiles/`;
- `backend/governance/r14f_profitability_gate.py`;
- `docs/user/` (manual and manifest);
- `tools/build_css_manual_manifest.py`;
- tests;
- the router mount, sign-in redirect and route guards in `dashboard/mobile/mobile_app.py`;
- `.github/workflows/css118-validation.yml`.

To roll back, revert the branch commits, or remove the router mount. Data lives only under `artifacts/trading_profiles/` (hash-chained ledgers; archive rather than delete).
