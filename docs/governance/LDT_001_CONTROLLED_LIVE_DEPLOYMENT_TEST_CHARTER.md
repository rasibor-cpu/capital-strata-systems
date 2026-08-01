# LDT-001 — Controlled Live Deployment Test Charter and Preflight Design

**Programme:** CSS Controlled Live Deployment Programme
**Phase:** LDT-001 (planning / offline analysis / test design / documentation only)
**Candidate branch:** `css-rc-live-001-candidate`
**Candidate HEAD:** `fa35bb4f4b8f96b4b77bb74217b0fb0f35cf2204`
**Charter HEAD (original authoring):** `66e11d4f83600a7765b4e55afa33d19e301dd70e` on `css-unified-consolidation-2026-07-13`
**Revision:** MR-003G (2026-08-01) — aligned to consolidated candidate; **not** an RC-LIVE freeze
**Status:** CHARTER COMPLETE — **NO LIVE TEST AUTHORIZED** — **NOT FROZEN** — **NOT LIVE-READY**
**Date (local authoring):** 2026-07-31

**Companion artifacts:**

- `docs/governance/LDT_001_PREFLIGHT_GATE_MATRIX.json`
- `docs/governance/LDT_001_EVIDENCE_MANIFEST_SCHEMA.json`
- `tests/test_ldt001_controlled_live_deployment_charter.py`

**Candidate lineage (MR-003):** This candidate contains the unified RC tip, maintenance (`MW-001`…`MW-004`, `DIP-001`…`DIP-006`), MI-EXT-001, RC-001, and MR-002 governance. Decision Intelligence and Market Intelligence modules are present in the tree. Presence ≠ live authorization.

---

## 1. Executive summary

LDT-001 defines the governance, safety, evidence, authorization, abort, and rollback package for CSS’s **first controlled live micro-deployment test**.

This phase:

- Inventories certified and residual evidence relevant to a live micro-pilot.
- Designs the **smallest valid** live test scope.
- Records existing authoritative capital limits (Phase 152A CAD 20 governor).
- Publishes a mandatory preflight GO/NO-GO matrix.
- Specifies a founder-controlled authorization ceremony.
- Designs the future operator runbook, abort conditions, rollback plan, and evidence package.
- Adds **offline** tests only; does **not** alter production execution code.

**Explicit:** No live test is authorized by this document. No broker may be contacted under LDT-001. Broker execution must remain blocked until a future, separately approved execution phase after all GO gates pass. The consolidated candidate HEAD is **not** a designated freeze SHA and is **not** live-ready.

Charter-time aggregate preflight posture: **NO-GO** (material `NOT_TESTED` and `BLOCKED` gates remain). See §6 and the JSON matrix.

---

## 2. Scope and exclusions

### In scope

- Governance design and documentation.
- Offline inventory of existing modules, docs, and local evidence paths.
- Offline tests that exercise existing fail-closed governors/authority/kill-switch without live I/O.
- Evidence package schema and custody rules.

### Out of scope / forbidden in LDT-001

- Stopping, restarting, reloading, or modifying the currently running CSS endurance/desktop instance.
- Editing runtime-loaded production Python in the active working tree.
- Broker authentication or any network contact to Coinbase, OANDA, IBKR, or others.
- Submitting orders; enabling live mode; arming broker execution; changing execution flags.
- Editing `.env` or credentials; modifying risk limits or kill-switch defaults in production config.
- Committing or pushing.
- Regenerating historical certifications.
- Inventing or raising capital limits above Phase 152A ceilings.

### Working-tree safety

LDT-001 was authored in the same repository working tree as the active desktop runtime. Changes are limited to **new governance documents** and **offline tests**. Existing untracked runtime evidence is preserved and must not be deleted.

---

## 3. Certified baseline inventory

For each item: governing artifact, status, evidence, limitation, live relevance.

| Item | Governing file / module | Status | Evidence | Limitation | Live relevance |
| --- | --- | --- | --- | --- | --- |
| RC-002B paper-environment certification | `docs/release/RC002B_PAPER_ENVIRONMENT_CERTIFICATION.md` | PRESENT — paper env gate | Profile flags, fail-closed authority claims | Does not authorize live | Paper baseline before any live arming |
| Phase 183J paper acceptance | `docs/governance/PHASE_183J_PAPER_ACCEPTANCE_ROUTE_CERTIFICATION.md` | PRESENT — defect remediated | Route/threshold fix documented | RC-003R re-run still required | Unblocks paper path through Unified Trade Gate; not live |
| RC-003R final acceptance | — | **NOT_FOUND** | Mentions in 183J only | No signed paper-order acceptance pack | **Preflight gap** |
| RC-004 executive release sign-off | — | **NOT_FOUND** | Sign-off **templates** only (`docs/operations/CSS_MICRO_LIVE_PILOT_SIGN_OFF_REGISTER_2026.md`, entries `NOT_STARTED`) | No executive live release | **Hard governance gap** |
| MW-001…MW-004 | maintenance tip `9a9263c1…` merged via MR-003 `d43ed196…` | **PRESENT** on candidate (ancestral) | MW audit docs + equity peak / MC projection / vol price / paper ledger | Still requires pilot re-certification on any future freeze | Paper/MC/gate residuals — **not** live unlock |
| DIP-001…DIP-006 | maintenance tip `9a9263c1…` merged via MR-003 `d43ed196…` | **PRESENT** on candidate (ancestral) | Trade DNA / Edge / Enterprise Intelligence + DIP-006 manifest | DIP-006 `live_trading_integration: NOT_READY` | Advisory Decision Intelligence — **not** live unlock |
| MI-EXT-001 / MR-002 | MI tip `81d48bfc…` merged via MR-003 `fa35bb4f…` | **PRESENT** on candidate (ancestral) | `backend/intelligence/external_events/*`; MR-002 docs | Advisory / fixture-only; online validation unauthorized | Market Intelligence lineage present — **not** live unlock |
| RC-001 broker-reporting consistency | Commit `66e11d4f…` (ancestral) | PRESENT on candidate | Reporting-only remediation | Does not enable live execution | Improves diagnostic honesty for preflight; not live authority |
| Endurance (OV-002 / ER-001) | OV-002 historical packages; ER-001 sealed local package `runtime_reports/operational_validation/er001_20260801T034921Z_closeout/` (gitignored) | OV-002 residuals remain; ER-001 observational PASS with limitations | ER-001 classifications recorded in ER-001 plan | No OV-002 certification claimed | Continuity residual = **NO-GO for endurance-backed live claims** |
| Phase 152A live micro-pilot governor | `backend/runtime/live_micro_pilot_governor.py`; `docs/governance/PHASE_152A_LIVE_MICRO_PILOT_CAPITAL_GOVERNOR.md`; `backend/config/order_limit_config.py` | PRESENT — guard only; `pilot_enabled=false` | Unit tests `tests/test_phase152a_live_micro_pilot_capital_governor.py` | Does not certify brokers or start a pilot | **Authoritative capital ceiling** for first live test |
| Live authority | `backend/runtime/live_execution_authority.py` | PRESENT — fail-closed | Empty evidence → `BLOCKED` | All AND-conditions required | Primary live AND-gate |
| Kill switch | `engine/execution/live_order_kill_switch.py`; mobile/web kill-switch controls | PRESENT — engaged by env/control | `CSS_LIVE_ORDER_KILL_SWITCH` blocks | Operator drill still required on pilot runtime | Must clear only under ceremony |
| RBAC (live) | `backend/security/permissions.py`; `backend/app/security/live_toggle.py`; Phase 152A SUPER_USER + `EXECUTE` | PRESENT | Code + tests | Role alone insufficient | Arm/config/disarm require SUPER_USER |
| Unified Trade Gate | `backend/governance/css_unified_trade_gate.py` | PRESENT | Phase 110A/105F docs + tests | Separate from ExecutionGate path history | Authority condition |
| Risk Governor | `engine/risk/risk_governor.py` (canonical) | PRESENT | Code; legacy copies quarantined | Use canonical path only | Downstream sizing/drawdown; does not raise 152A ceilings |
| AntiBleedGuard | `backend/app/risk/anti_bleed_guard.py` | PRESENT | Defaults: min edge 25 bps; **min trade size 50** | **Conflicts with CAD 20 pilot** | Authority condition; **BLOCKED** until governed alignment |
| Margin Gate | `engine/risk/margin_trade_gate.py` | PRESENT — fail-closed | ARP-002D | Needs valid margin snapshot | Authority condition |
| Broker quarantine | IBKR placeholder quarantine; OANDA live-write firewall tests; ARP-007/011 | PRESENT | `backend/brokers/ibkr/ibkr_adapter.py` PLACEHOLDER | Quarantine ≠ readiness | Keeps IBKR out of pilot |
| Order-size limits | `order_limit_config.py` + Phase 152A | PRESENT | CAD 20 / daily 2 / session 4 / 1 position / ≤10 orders/session | LDT operational script further restricts to **1 entry + 1 exit** | Hard envelope |
| Account/position reconciliation | `backend/reconciliation/position_reconciliation.py`; broker reconciliation services | PRESENT | Read-only compare helpers | Needs authenticated live evidence | Required post-trade / abort path |

Historical micropilot packages (`docs/governance/MICRO_LIVE_PILOT_AUTHORIZATION.md`, Phase 115/118 packages) exist as **context only**. Numeric limits older than Phase 152A are **superseded** by the CAD 20 governor.

---

## 4. Recommended broker and instrument

### Comparison (offline only — no broker contact)

| Candidate | Evidence | Verdict |
| --- | --- | --- |
| **OANDA** practice / live-read-only | Strongest OV-001 practice read-check evidence; `oanda_readiness.py` / live-read-only adapters; RC-002B `OANDA_ENV=practice`; LIVE label **not** certified | **Preferred engineering candidate** for first micro-pilot *after* LIVE env certification |
| **Coinbase** live-read-only | Market path partial; OV-001 account AUTH_FAILED residual; crypto unit size/volatility harder under CAD 20 | Secondary / deferred |
| **IBKR** | `IMPLEMENTATION_STATUS = "PLACEHOLDER"`, `ibkr_ready=False` | **Excluded** |

### LDT-001 proposed pilot scope (design only)

| Dimension | Bound |
| --- | --- |
| Broker | **OANDA** only |
| Account | **One** designated live account (identity recorded at future freeze; not contacted in LDT-001) |
| Asset class | **FX** only |
| Instrument | **EUR_USD** only |
| Entry orders | **Maximum one** |
| Exit orders | **Maximum one** |
| Pyramiding | **Forbidden** (Phase 152A hard) |
| Averaging down | **Forbidden** (Phase 152A hard) |
| Simultaneous positions | **Forbidden** (`max_concurrent_positions=1` and operational zero-before-entry) |
| Overnight | **Forbidden** unless separately approved in writing |
| Autonomous capital reallocation | **Forbidden** |
| Strategy expansion mid-pilot | **Forbidden** |

**Rationale:** FX unit size can fit under CAD 20 (historical micropilot preflight notes cite OANDA EUR_USD micro notional within budget). Coinbase large crypto notionals and OV-001 account residual make it less safe for first money. IBKR is not implementable.

**Currency conversion:** FX quotes vs CAD pilot ceilings — conversion source is **`NOT_AVAILABLE`** unless an approved deterministic converter already exists at execution time. Until then, notional must be proven ≤ CAD 20 by an approved method or the pilot remains NO-GO.

---

## 5. Capital limits

Authoritative ceilings (stricter of conflicting controls wins; none may be raised in LDT-001):

| Control | Limit | Source |
| --- | --- | --- |
| Max live test capital | **CAD 20.00** | Phase 152A / `order_limit_config` |
| Max position size | **CAD 20.00** | Phase 152A |
| Max concurrent positions | **1** | Phase 152A |
| Max orders per session (code ceiling) | **10** | Phase 152A |
| LDT operational order budget | **1 entry + 1 exit** | This charter (stricter operational bound; does not raise code ceiling) |
| Daily loss limit | **CAD 2.00** | Phase 152A |
| Session loss limit | **CAD 4.00** | Phase 152A |
| Max total pilot loss | **CAD 4.00 session / CAD 2.00 daily** (stricter applicable) | Phase 152A |
| Live default notional ceiling | **USD 1.00** | `order_limit_config.live_order_default_notional_usd` (legacy secondary; does not override CAD 20 authority) |
| Broker legacy secondary | Coinbase/OANDA labeled legacy USD guards | Secondary only if live armed separately |
| Pyramiding / averaging down | **false** | Phase 152A hard reject |
| Manual arming | Required; confirmation word **`EXECUTE`**; role **`SUPER_USER`** | Phase 152A |
| Auto-disarm on limit breach | **true** | Phase 152A |
| Banked-profit protection | Use existing profit-protection / risk modules if present; **do not invent new limits** | Inventory: treat unproven rules as NOT_TESTED at preflight |
| Max tolerated spread/slippage | **NOT_AVAILABLE** as a single published CAD/bps authority for LDT — record measured values; abort if operator-approved pilot envelope (to be set ≤ existing gate edges, including AntiBleed 25 bps net-edge floor) is breached | AntiBleedGuard default `minimum_required_net_edge_bps=25.0` |
| Max position duration | **Intraday only** for LDT-001 (no overnight unless separate approval) | This charter |
| Max attempts | **One** bounded entry attempt in the authorized window; no retry storm | This charter |
| Kill-switch conditions | Env `CSS_LIVE_ORDER_KILL_SWITCH` or mobile kill controls engaged → block | `live_order_kill_switch.py` |
| Session expiry | Session continuity / quiet-mode observers; expired session → NO-GO / abort | `runtime_session_continuity.py` |
| CAD↔quote FX conversion | **NOT_AVAILABLE** unless approved deterministic source exists | This charter |

**Conflict note:** AntiBleedGuard default `minimum_profitable_trade_size=50` is **stricter against small pilots** and conflicts with CAD 20 — charter-time Safety gate **BLOCKED**. Resolution requires a future governed remediation (out of LDT-001 production-code scope).

---

## 6. Preflight GO/NO-GO matrix

Full machine-readable matrix: `docs/governance/LDT_001_PREFLIGHT_GATE_MATRIX.json`.

**Rule:** Any `FAIL`, `BLOCKED`, or material `NOT_TESTED` ⇒ **NO-GO**.

### Summary (charter-time)

| Category | Posture |
| --- | --- |
| A Repository | Mix PASS / NOT_TESTED — live freeze commit not designated |
| B Runtime | NOT_TESTED for dedicated pilot runtime |
| C Broker | C8 **BLOCKED** (LIVE mode not certified); others mostly NOT_TESTED |
| D Portfolio | NOT_TESTED |
| E Safety | E5 AntiBleed **BLOCKED**; E8 authority BLOCKED-until-auth **PASS**; others mixed |
| F Evidence | Design PASS; freeze artifacts NOT_TESTED |

**Aggregate: NO-GO. No live test authorized.**

Classification vocabulary: `PASS` | `FAIL` | `BLOCKED` | `NOT_TESTED` | `NOT_APPLICABLE`.

---

## 7. Founder authorization ceremony

Design only — **do not activate** in LDT-001.

### Required sequence

1. Explicit founder approval recorded in-session (name, UTC timestamp, charter/run ID).
2. Exact binding of **broker = OANDA**, **instrument = EUR_USD**, **max notional ≤ CAD 20**, and test objective (one entry / one exit micro-live connectivity+fill proof).
3. Confirmation: account has **zero unexpected positions** and **no stale orders** (read-only evidence attached).
4. Confirmation: kill switch functional (engage → block proven; then clear only under this ceremony).
5. Confirmation: every mandatory preflight gate is `PASS` or `NOT_APPLICABLE` (no FAIL/BLOCKED/material NOT_TESTED).
6. Final display of the **proposed order** (symbol, side, size, notional CAD, time-in-force, client order id) before authorization.
7. Single-use authorization mechanism:
   - Prefer existing Phase 152A arm + live authority AND-gate + confirmation word `EXECUTE`.
   - **Gap:** dedicated single-use token with TTL is **not** fully implemented as a separate primitive; treat arm state + short window + mandatory disarm as the equivalent until a future phase adds an explicit token.
8. Automatic expiry: disarm at test end **or** after a short defined window (recommended ≤ **30 minutes** armed window unless a future governance doc sets otherwise). Authority must not outlive the window.
9. **No persistence of live authority across restart** unless separately approved. After restart, `pilot_armed` must be false and `live_authority_state=BLOCKED` until the full ceremony repeats.

### Existing controls to reuse (documentation)

- Phase 152A `arm` / `disarm` / `write_config` with SUPER_USER + `EXECUTE`.
- `evaluate_live_execution_authority` AND-conditions.
- Sign-off register template: `docs/operations/CSS_MICRO_LIVE_PILOT_SIGN_OFF_REGISTER_2026.md` (does not itself authorize trading).

---

## 8. Test runbook (future execution — placeholders only)

All broker/runtime mutation steps are **future**. Commands marked:

`FUTURE_EXECUTION_COMMAND — DO NOT RUN`

1. Controlled shutdown of the endurance instance
   `FUTURE_EXECUTION_COMMAND — DO NOT RUN` — approved controlled shutdown procedure only under founder order.
2. Evidence archive of endurance/pre-pilot state into custody path.
3. Load certified commit (designated LDT freeze SHA — **not yet assigned**).
   `FUTURE_EXECUTION_COMMAND — DO NOT RUN` — `git checkout <LDT_FREEZE_SHA>`.
4. Fresh startup of single-tree CSS.
   `FUTURE_EXECUTION_COMMAND — DO NOT RUN` — `launch_css.bat` (or approved launcher).
5. Select **live-read-only** validation first (execution still blocked).
6. Broker / account / market-data checks (read-only).
   `FUTURE_EXECUTION_COMMAND — DO NOT RUN` — approved read-only readiness scripts only.
7. Produce GO/NO-GO report from the matrix; **stop** on any discrepancy.
8. Founder authorization ceremony (§7).
9. Submit **one** bounded entry (≤ CAD 20, EUR_USD).
   `FUTURE_EXECUTION_COMMAND — DO NOT RUN` — governed submission path only after authority AUTHORIZED.
10. Verify acknowledgement; verify fill **or** governed rejection.
11. Reconcile broker vs CSS state.
12. Manage/close position via **one** exit (or governed emergency close process on abort).
13. Verify exit; reconcile realized P&L, fees, slippage, quantity.
14. Revoke authority / disarm pilot.
15. Confirm **zero** open positions.
16. Archive evidence per §11 schema.
17. Return system to **paper / DISABLED** mode.
   `FUTURE_EXECUTION_COMMAND — DO NOT RUN`.

---

## 9. Abort conditions

Abort immediately (no further submissions) on any of:

- Authentication inconsistency
- Stale or missing market data
- Balance mismatch
- Position mismatch
- Unexpected open order
- Spread/slippage / net-edge breach vs approved envelope
- Partial fill without governed handling
- Order rejection with ambiguous state
- Heartbeat loss
- Supervisor restart / unexpected process death
- Critical alert
- Duplicate order risk
- Session expiry
- Any live-authority contradiction (`AUTHORIZED` without ceremony evidence, or armed after restart without re-ceremony)
- Any unrecognized broker response
- Any breach of CAD 20 / loss limits / one-entry-one-exit operational bound

---

## 10. Rollback plan

Governed actions only — **no uncontrolled emergency trading commands**.

1. Invoke kill switch (block further submissions).
   `FUTURE_EXECUTION_COMMAND — DO NOT RUN` — engage approved kill-switch control / env.
2. Block further submissions at authority and pilot disarm layers.
3. Inspect broker state through **approved read-only** path only.
4. Close position **only** through the governed emergency / single-exit process if a position exists.
   `FUTURE_EXECUTION_COMMAND — DO NOT RUN`.
5. Revoke live authority; disarm Phase 152A pilot; confirm `live_authority_state=BLOCKED`.
6. Reconcile CSS vs broker; archive evidence (including abort reason).
7. Return to paper / DISABLED mode.
8. Declare pilot **`NOT_CERTIFIED`**.

---

## 11. Evidence package

Schema: `docs/governance/LDT_001_EVIDENCE_MANIFEST_SCHEMA.json`.

**Custody root:** `runtime_reports/operational_validation/ldt001_<UTC_START>/`
**Run ID:** `LDT001-<YYYYMMDDTHHMMSSZ>`
**Hash:** SHA-256 per artifact; deterministic sorted `MANIFEST.json`
**Redaction:** required for credentials; mask account ids; forbid PEM/token material
**Git:** local custody by default; do not commit secrets

Required artifacts include workspace verification, commit/manifest hashes, environment fingerprint, redacted credential diagnostics, broker auth, account/market snapshots, live-authority snapshot, all gate decisions, order request, acknowledgement, fill/rejection, reconciliation, close result, realized P&L, fees/slippage, alerts, supervisor state, zero-position confirmation, authority revocation, operator approval record, and the deterministic evidence manifest.

---

## 12. Success criteria

A future live pilot may be considered **technically successful but still `NOT_CERTIFIED` for production** only if all hold:

- All mandatory preflight gates PASS / NOT_APPLICABLE before arming.
- Founder ceremony completed and archived.
- At most one entry and one exit executed under CAD 20 and loss ceilings.
- Broker and CSS reconciliation clean (or discrepancies fully explained and accepted as abort).
- Authority revoked; zero open positions; kill switch re-engaged as required.
- Complete redacted evidence package with matching `MANIFEST.json` hashes.
- System returned to paper / DISABLED.

Production certification, Phase 181, and broader release claims remain **out of scope**.

---

## 13. Failure criteria

Any of:

- Any abort condition in §9.
- Any FAIL/BLOCKED gate ignored.
- Limit breach (capital, loss, concurrency, pyramiding, overnight without approval).
- Authority persists across restart without re-ceremony.
- Missing or non-redacted mandatory evidence.
- Ambiguous broker state after order attempt.

Disposition: **`NOT_CERTIFIED`** + incident package.

---

## 14. Open blockers

Authoritative lineage and classifications: `docs/governance/LDT_002_LIVE_PILOT_BLOCKER_RESOLUTION_AUDIT.md`.

1. **RC-003R FINAL** — not committed (TEMP custody only per maintenance audit); Phase 183J ancestor `b0703f3` is shared; **re-certify** on freeze (`BLK-RC003R-FINAL`).
2. **RC-004** — no committed `RC-004*` doc; executive paper sign-off cited for `b0703f3` with **`LIVE_TRADING_NOT_AUTHORIZED`**; live unlock **absent** (`BLK-RC004-SIGNOFF`).
3. **MW/DIP/MI lineage** — **RESOLVED on candidate** (`BLK-LINEAGE-MW-DIP` cleared for `css-rc-live-001-candidate` after MR-003 merges). Modules are ancestral; live re-certification on a future freeze remains required.
4. **OV-002 / endurance credit** — ER-001 sealed observational result only; **OV-002 certification not claimed** (`BLK-ENDURANCE-CREDIT`).
5. **OANDA LIVE** not certified (practice/read-only ≠ live) (`BLK-OANDA-LIVE`).
6. **AntiBleedGuard min trade size 50** vs **Phase 152A CAD 20** — **genuine contradiction (class A)** on ExecutionGate notional path (`BLK-ANTIBLEED-CAD20`) → live pilot **BLOCKED**.
7. **CAD FX conversion** — no LDT-approved deterministic contract; `fx_daily_rates` cache file absent (`BLK-FX-CONVERSION`).
8. **Authorization TTL** — `PARTIALLY_SUPPORTED` (arm/disarm exist; no TTL, no single-use scoped token; arm state may persist via file across restart) (`BLK-AUTH-TTL`).
9. LDT **freeze SHA** **NOT_DESIGNATED** — candidate HEAD `fa35bb4f…` must **not** be treated as freeze or live-ready (`BLK-FREEZE-SHA`).
10. Founder GO/NO-GO for live arming **not issued**.
11. Live pilot must not run on the endurance host — dedicated pilot runtime after controlled shutdown + fresh start only.

---

## 15. Explicit statement — no live test authorized

**LDT-001 does not authorize live trading, broker execution, order submission, credential use against live venues, kill-switch clearance for trading, or Phase 152A arming in production.**

Any future live micro-pilot requires a separate founder-approved execution phase after blockers are cleared and the GO/NO-GO matrix evaluates to GO on a dedicated certified freeze.

---

## Document control

| Field | Value |
| --- | --- |
| Document ID | LDT-001 |
| Classification | Governance / planning |
| Live authorization | **NONE** |
| Production code changed | **None** (docs + offline tests only) |
