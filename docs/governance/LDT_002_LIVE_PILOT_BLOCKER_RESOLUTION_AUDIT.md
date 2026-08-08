# LDT-002 — Live-Pilot Blocker Resolution Audit

**Programme:** CSS Controlled Live Deployment Programme
**Phase:** LDT-002 (offline audit only)
**Active branch:** `css-unified-consolidation-2026-07-13`
**Active HEAD:** `66e11d4f83600a7765b4e55afa33d19e301dd70e`
**Upstream parity at audit:** `0 0`
**Maintenance tip audited:** `origin/css-v1.0.1-maintenance` @ `9a9263c185680353fac9319577b4a1f82d3311dd`
**Merge-base (active ∩ maintenance):** `b0703f36096bf183514293ef9b83b6e7849bd087` (Phase 183J)
**Status:** AUDIT COMPLETE — **NO LIVE TEST AUTHORIZED**
**Runtime:** Not accessed, stopped, restarted, synchronized, or modified

---

## 1. Executive summary

LDT-001 blockers were re-audited against **Git refs and repository files only**.

Findings:

1. **MW-001…MW-004** and **DIP-001…DIP-006** exist on **`css-v1.0.1-maintenance` only**. They are **not** ancestors of the active consolidation HEAD and **must not be silently credited**.
2. **RC-003R FINAL** evidence is **not committed**; it is cited as local `%TEMP%` packages in maintenance docs. Phase 183J (remediation) is an ancestor of both tips.
3. **RC-004** has **no committed `docs/**/RC-004*` file**. It exists as an executive session record referenced by MW-001, approving paper baseline `b0703f3` with **`LIVE_TRADING_NOT_AUTHORIZED`**.
4. **AntiBleed min size 50** vs **Phase 152A CAD 20** is a **genuine contradiction (class A)** on the live ExecutionGate path.
5. **No live FX conversion is authorized**. Current approved policy is CAD identity-only for explicitly CAD-denominated authoritative exposure; non-CAD and unit-only live exposure remain fail-closed.
6. Authorization TTL / single-use scoped token is **PARTIALLY_SUPPORTED** (arm/disarm + confirmation exist; no TTL, no scope binding, state can persist across restart via file).
7. OANDA LIVE certification remains a **preflight NO-GO** gap (practice/read-only offline code present; LIVE not certified).
8. Current untimed runtime may provide **observational stability evidence only** — **not** OV-002 certification credit and **not** automatic 48h credit without the OV-002 monitor/manifest/checkpoint contract.

**Updated aggregate preflight posture:** **NO-GO / BLOCKED** for live micro-pilot.

---

## 2. Workspace verification (frozen)

| Field | Value |
| --- | --- |
| Repository | `C:\rasib\source\capital-strata-systems` |
| Remote | `https://github.com/rasibor-cpu/capital-strata-systems.git` |
| Branch | `css-unified-consolidation-2026-07-13` |
| HEAD | `66e11d4f83600a7765b4e55afa33d19e301dd70e` |
| Upstream | `origin/css-unified-consolidation-2026-07-13` |
| Ahead/behind | `0 0` |
| Tracked dirty | No (untracked LDT docs/tests + prior local evidence only) |

STOP condition: not triggered.

---

## 3. Branch / certification lineage table

**Divergence facts (Git):**

- `maint_is_ancestor_of_active = NO`
- `active_is_ancestor_of_maint = NO`
- Commits on maintenance not in active: **9**
- Commits on active not in maintenance: **9** (includes RC-001 reporting remediation `66e11d4f`)

| Item | Branch | Commit hash | File paths | Ancestor of active? | Only on `css-v1.0.1-maintenance`? | Required action | Conflict with running baseline |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **RC-003R final acceptance** | Evidence cited on maintenance docs; package **not in Git** | Paper baseline SHA referenced: `b0703f36…` (Phase 183J); TEMP packages `%TEMP%\css_rc003r_final_evidence_*` | Mentions: `docs/governance/PHASE_183J_…` (both tips); MW-001 audit on maintenance | Phase 183J **YES**; FINAL package **N/A (not in repo)** | FINAL evidence **not on either branch** | **Re-certification** after freeze; archive FINAL into custody; do **not** credit TEMP-only packs | Active also has `66e11d4f` reporting changes after 183J — RC-003R must be re-run on eventual freeze |
| **RC-004 executive sign-off** | Referenced on maintenance | Tied to paper baseline `b0703f3`; **no dedicated commit artifact** | No `docs/**/RC-004*`; cited in `CSS_V1_0_1_MAINTENANCE_001_…md` | Sign-off record **not a Git tree object** | Sign-off narrative **maintenance-only** in MW-001 | **Re-issue / re-certify** sign-off on chosen freeze; cannot cherry-pick a missing file | Explicitly **`LIVE_TRADING_NOT_AUTHORIZED`** — does not unlock LDT |
| **MW-001** | `origin/css-v1.0.1-maintenance` | `7253dbc194809dcf3a09081e1b7a3fd3e57c1b86` | `docs/governance/CSS_V1_0_1_MAINTENANCE_001_RESIDUAL_RISK_AUDIT.md`; migration `005_pnl_snapshots_equity_peak.sql`; mobile peak resolution; tests | **NO** | **YES** (absent on active) | **Merge or cherry-pick + re-certify** on consolidation | Touches persistence/mobile risk inputs; must not apply to live runtime without regression |
| **MW-002** | `origin/css-v1.0.1-maintenance` | `3de9307394397c0dce43b419ce830dde9f3af77c` | `CSS_V1_0_1_MAINTENANCE_002_…md`; `dashboard/mission_control/active_broker_projection.py`; `tests/test_mw002_…` | **NO** | **YES** | **Merge/cherry-pick + re-certify** | MC projection changes — conflict risk with RC-001 reporting semantics on active |
| **MW-003** | `origin/css-v1.0.1-maintenance` | `5019a57452fb0cd0b1344d7a94cf22dcabec5e48` | `CSS_V1_0_1_MAINTENANCE_003_…md`; `engine/risk/canonical_volatility_price.py`; execution_gate / mobile tests | **NO** | **YES** | **Merge/cherry-pick + re-certify** | ExecutionGate sizing path — high live relevance |
| **MW-004** | `origin/css-v1.0.1-maintenance` | `c1b2f88b743e31cc94954b4a95b432cd5098183b` | `CSS_V1_0_1_MAINTENANCE_004_…md`; paper economics / orchestrator / mobile; `tests/test_mw004_…` | **NO** | **YES** | **Merge/cherry-pick + re-certify** | Paper ledger fidelity — paper gate dependency |
| **DIP-001** | `origin/css-v1.0.1-maintenance` | Doc introduced in `99498bbcc248ab2491a1b909c86c27b0b2f244b6` (commit message DIP-002) | `docs/governance/DIP_001_ENTERPRISE_DECISION_INTELLIGENCE_ARCHITECTURE.md` | **NO** | **YES** | **Merge/cherry-pick + re-certify** (docs/intel) | Advisory intel — not live unlock |
| **DIP-002** | `origin/css-v1.0.1-maintenance` | `99498bbcc248ab2491a1b909c86c27b0b2f244b6` | `DIP_002_TRADE_DNA_SCHEMA.md`; `backend/intelligence/trade_dna/*`; tests | **NO** | **YES** | **Merge/cherry-pick + re-certify** | Not live unlock; DIP-006 says live integration **NOT_READY** |
| **DIP-003** | `origin/css-v1.0.1-maintenance` | `6e408ca1f4e54b8e0dbe0a38ce5144bfff443366` | `DIP_003_…md`; capture/analytics modules; tests | **NO** | **YES** | **Merge/cherry-pick + re-certify** | Same |
| **DIP-004** | `origin/css-v1.0.1-maintenance` | `85a5ba1f03e7812042d2f61104e5d738b9bffa70` | `DIP_004_…md`; `backend/intelligence/edge_intelligence/*` | **NO** | **YES** | **Merge/cherry-pick + re-certify** | Same |
| **DIP-005** | `origin/css-v1.0.1-maintenance` | `6cfa8862c42ef118a249c7a47a63386c60bd9f77` | `DIP_005_…md`; enterprise intelligence suite | **NO** | **YES** | **Merge/cherry-pick + re-certify** | Same |
| **DIP-006** | `origin/css-v1.0.1-maintenance` | `9a9263c185680353fac9319577b4a1f82d3311dd` | `DIP_006_ENTERPRISE_READINESS_AND_CERTIFICATION.md`; `DIP_006_CERTIFICATION_MANIFEST.json` | **NO** | **YES** | **Merge/cherry-pick + re-certify**; manifest assessed_head `6cfa8862…` on maintenance | Manifest classifies `live_trading_integration: NOT_READY` |

**Silent-credit rule:** Certification evidence whose commit is **not** an ancestor of the live-pilot freeze SHA **cannot** be treated as PASS on the active baseline.

**This phase:** no merge, no cherry-pick.

---

## 4. AntiBleed versus CAD 20 — conclusion

### Definitions

| Control | Authoritative definition | Units | Scope |
| --- | --- | --- | --- |
| Phase 152A | `max_position_size` / `max_live_test_capital` ≤ **CAD 20.00**; currency hard-coded **CAD** | CAD notional | **Live** orders only (`LiveMicroPilotGovernor.evaluate_order`) |
| AntiBleedGuard | `minimum_profitable_trade_size` default **50.0** | Untyped float `trade_size` | Invoked from **ExecutionGate** with **`notional`** as `trade_size` |
| Live authority | Requires both `capital_governor_pass` and `anti_bleed_guard_pass` | Boolean evidence | Live AND-gate |

### Code path (live)

1. Live order notional must be ≤ **CAD 20** or Phase 152A rejects (`max_position_size_breached`).
2. Downstream `ExecutionGate._evaluate_anti_bleed(... notional=...)` passes that notional into `AntiBleedGuard.evaluate(trade_size=notional)`.
3. AntiBleed rejects when `trade_size < 50.0` (`trade_size_too_small`).
4. Offline proof: size **20** → reject; size **50** → approve (edge inputs held constant).

### Classification

**A. Genuinely contradictory** for the LDT live micro-pilot path.

Not B (different units): ExecutionGate feeds the same **notional** number into AntiBleed; Phase 152A labels it CAD; AntiBleed does not convert currencies — it compares the raw notional to 50.

Not C (different paths): Both are required on the live authority / execution path for live requests.

Not D (stale): Both are current defaults on active HEAD; Phase 152A docs and `order_limit_config` remain authoritative ceilings.

### Live-pilot status

**BLOCKED** until a future governed remediation. LDT-002 does **not** weaken either control.

### Governance-compatible options only (do not implement here)

1. **Defer live pilot** until a dedicated governance phase defines a **pilot-scoped, asset-class-specific** AntiBleed profile that still meets fee-bleed intent **and** remains ≤ CAD 20 — with founder approval, tests, and evidence (may still be rejected if it weakens AntiBleed without compensating controls).
2. **Raise the CAD capital envelope above AntiBleed min** only via a **new** Phase that explicitly supersedes 152A ceilings (currently **forbidden** to raise in LDT).
3. **Keep NO-GO indefinitely** for real-money micro-pilot under CAD 20 while paper certification continues.

No option that silently disables AntiBleed or silently exceeds CAD 20 is acceptable.

---

## 5. Currency-conversion authority — conclusion

### Current approved contract

- Phase 152A live-pilot ceilings remain denominated in **CAD**.
- No FX conversion is authorized for live-pilot capital or risk gating in the current baseline.
- Identity comparison is permitted only when authoritative exposure amount and authoritative exposure currency are both explicit and the currency is **CAD**.
- Non-CAD exposure, missing currency, ambiguous currency, unsupported currency, unit-only exposure, broker/account-currency substitution, inferred instrument currency, accounting FX-cache fallback, inverse-rate fallback, and cross-rate fallback all fail closed before downstream approval.

### What exists

- `backend/runtime/live_pilot_currency_authority.py` enforces the current CAD identity-only contract.
- `backend/app/fx_daily_rates.py` remains an accounting/reporting helper and is **not** authorized for live-pilot gating.
- Broker/account currency fields remain read-only observational data only and must not substitute for authoritative order-exposure currency.

### Status

**BLOCKED** / **NO-GO** for any non-CAD or unit-only live exposure.

The current baseline still does **not** authorize OANDA unit-based live orders, Coinbase USD exposure, inverse conversion, triangulation, or any live FX rate use.

---

## 6. Authorization TTL — conclusion

| Capability | Present? | Evidence |
| --- | --- | --- |
| SUPER_USER + confirmation `EXECUTE` | Yes | Phase 152A |
| Manual arm / disarm | Yes | `arm()` / `disarm()`; audit events |
| `armed_at` timestamp recorded | Yes | state JSON |
| TTL / auto-expiry enforcement | **No** | `evaluate_order` does not check age |
| Single-use token | **No** | Arm flag is reusable until disarm |
| Scope binding (broker/instrument/notional) | **No** | Arm is global pilot flag |
| Non-persistence across restart | **Partial** | Defaults DISARMED if state file missing; **persists ARMED if state file survives restart** |
| Revocation | Yes | disarm / auto-disarm on limit breach |
| Replay prevention | **Partial** | Audit log only; no nonce/token |
| Founder approval evidence binding | **Partial** | Operator audit + external sign-off registers; not cryptographic single-use |

**Classification: `PARTIALLY_SUPPORTED`**

**Smallest bounded future remediation (design only):** add `expires_at` (short TTL) + clear on process start unless `persist_arm_across_restart` explicitly approved; bind arm payload to broker/instrument/max_notional hash; reject evaluate when expired; require re-ceremony. Do **not** implement in LDT-002.

Gate posture: **BLOCKED** (ceremony incomplete) / TTL support **NOT_TESTED** as a PASS criterion until remediated.

---

## 7. OANDA live-read-only certification gap

### Present offline (active tree)

| Area | Module / tests |
| --- | --- |
| Credential diagnostics | `broker_credential_diagnostics.py` / OANDA token+account checks |
| Readiness | `oanda_readiness.py` |
| Live-read-only adapter | `oanda_live_read_only_adapter.py` |
| Auth trace | `oanda_authentication_trace.py` |
| Connectivity certificate | `oanda_connectivity_certificate.py` |
| Operational validation harness | `oanda_live_read_only_operational_validation.py` |
| Firewall / write quarantine tests | `tests/test_oanda_live_firewall.py` |
| Phase tests | `test_phase154a_*`, `test_phase155b_*`, `test_phase165b_*`, margin adapter tests |
| RC-002B | `OANDA_ENV=practice` certified for paper env — **not LIVE** |

### Still required before OANDA passes LDT preflight (C8 etc.)

**Offline / custody**

1. Designated freeze SHA with OANDA LIVE profile documented (not practice masquerading as live).
2. Redacted credential diagnostics PASS on that freeze.
3. Written non-claims: practice evidence ≠ LIVE certification.

**Later controlled online (future phase — not LDT-002)**

4. Authentication success against LIVE.
5. Connection + account/balance load.
6. Market-data freshness for EUR_USD.
7. Broker-state projection consistent with RC-001 reporting semantics.
8. Order quarantine still blocking writes until ceremony.
9. Reconciliation snapshot clean (zero unexpected positions/orders).
10. Archived evidence per LDT-001 manifest.

Until then: gate **C8 = BLOCKED**, aggregate **NO-GO**.

---

## 8. Endurance-credit classification

| Credit type | Allowed for current untimed runtime? | Reason |
| --- | --- | --- |
| Observational stability evidence | **YES** (narrative only) | Supervisor uptime/heartbeats may be recorded as observation |
| Formal **48-hour stability credit** | **NO** (not automatic) | No LDT/OV termination contract, checkpoint schedule, or sealed manifest for this instance |
| Formal **OV-002 certification credit** | **NO** | OV-002 Attempt 2 finished with residuals; Phase 181 `NOT_CERTIFIED`; **no** `css_ov002_72h_endurance` monitor on current run; missing OV-002 RUN_META/checkpoints for this supervisor generation |

**Missing for credit:** OV-002 (or successor) monitor process, `RUN_META.json` with `target_hours`, periodic snapshots/checkpoints, `RUN_STATUS` lifecycle, freeze SHA lock, invalidation watch, and executive acceptance.

Do not stop or modify the current run under LDT-002.

---

## 9. Freeze-SHA designation rule

Do **not** designate `66e11d4f…` as live-ready.

Future live-pilot candidate SHA may be selected only after **all** of:

1. Controlled endurance closeout / evidence archive (if used).
2. Required maintenance merges or cherry-picks (MW/DIP as approved) **or** explicit waiver.
3. Blocker remediation (AntiBleed/CAD, FX contract, TTL, OANDA LIVE preflight).
4. Focused + broad regression certification on the candidate.
5. Clean checkout of that SHA on the pilot host.
6. Exact remote parity (`0 0`) on the freeze branch.
7. Founder freeze record (SHA, branch, date, non-claims).

Until then: freeze SHA = **NOT_DESIGNATED**.

---

## 10. Updated blocker classifications (machine)

| Blocker ID | Classification | Notes |
| --- | --- | --- |
| BLK-LINEAGE-MW-DIP | `BLOCKED` | Non-ancestor maintenance commits |
| BLK-RC003R-FINAL | `NOT_TESTED` / custody gap | TEMP-only FINAL; re-certify on freeze |
| BLK-RC004-SIGNOFF | `BLOCKED` for live | Paper sign-off only; live not authorized |
| BLK-ANTIBLEED-CAD20 | `BLOCKED` | Contradiction class A |
| BLK-FX-CONVERSION | `BLOCKED` | Same-currency-only CAD identity contract approved; non-CAD and unit-only live exposure remain blocked |
| BLK-AUTH-TTL | `PARTIALLY_SUPPORTED` → gate `BLOCKED`/`NOT_TESTED` | No TTL/single-use/scope |
| BLK-OANDA-LIVE | `BLOCKED` | LIVE not certified |
| BLK-ENDURANCE-CREDIT | `NOT_APPLICABLE` as OV-002 PASS | Observation only |
| BLK-FREEZE-SHA | `NOT_TESTED` | Not designated |

**Aggregate:** **NO-GO**

---

## 11. Explicit non-authorization

LDT-002 does not authorize live trading, merges, cherry-picks, broker contact, arming, kill-switch clearance, or freeze designation.
