# MR-002 — RC-LIVE Freeze Checklist

**Programme:** CSS Enterprise Merge Readiness
**Workstream:** MR-002
**Companion:** `docs/governance/MR_002_ENTERPRISE_MERGE_READINESS.md`
**Matrix:** `docs/governance/MR_002_MERGE_MATRIX.json`
**Status:** Checklist ready for operator sign-off (`MR_002_READY_FOR_REVIEW`)

**Active runtime (DO NOT TOUCH):**
`C:\rasib\source\capital-strata-systems` @ `css-unified-consolidation-2026-07-13` / `66e11d4f83600a7765b4e55afa33d19e301dd70e`

**MI documentation branch (this package):**
`css-market-intelligence-external-sources-001` / `3c7a6b61de2f7784e794b9f186a440d0f50392b2`

This checklist does **not** authorize merge, cherry-pick, runtime access, broker access, live trading, commit, or push by itself. It defines the evidence required before an RC-LIVE freeze SHA may be declared.

---

## A. Pre-freeze identity

| # | Check | Owner | Pass criteria | ☐ |
| --- | --- | --- | --- | --- |
| A1 | Integration worktree isolated from endurance runtime | Release governor | Separate worktree/path; runtime path untouched | ☐ |
| A2 | RC parent SHA recorded | Release governor | Parent includes `66e11d4f83600a7765b4e55afa33d19e301dd70e` or post-MR-001 successor recorded | ☐ |
| A3 | MI-EXT tip recorded | MI owner | `3c7a6b61de2f7784e794b9f186a440d0f50392b2` or successor with identical safety invariants | ☐ |
| A4 | Freeze SHA candidate computed | Release governor | Full 40-char SHA written below | ☐ |
| A5 | Working tree clean for freeze scope | Release governor | No staged/unstaged freeze-scope drift; local noise explicitly excluded | ☐ |
| A6 | Remote parity for freeze branch | Release governor | Ahead/behind origin documented (0/0 after intentional push by authorized operator) | ☐ |

**Freeze SHA candidate:** `________________________________`
**Freeze branch / tag:** `________________________________`
**Freeze timestamp (UTC):** `________________________________`

---

## B. Freeze SHA criteria (mandatory)

| # | Criterion | Pass criteria | ☐ |
| --- | --- | --- | --- |
| B1 | Immutable identity | Tip SHA == recorded freeze SHA | ☐ |
| B2 | Ancestry honesty | Descendant of RC tip or recorded post-MR-001 parents | ☐ |
| B3 | MI-EXT content present | `backend/intelligence/external_events/` + `MI_EXT_001_*` + fixtures/tests | ☐ |
| B4 | Advisory-only invariants | Schema/code enforce `advisory_only=true`, `execution_allowed=false` | ☐ |
| B5 | Live network fail-closed | Online validation unauthorized; live adapter blocked | ☐ |
| B6 | No endurance mutation | Attestation that runtime worktree/process was not modified for freeze | ☐ |
| B7 | Offline certification green | CP-MR002-03 and CP-MR002-04 pass on freeze SHA | ☐ |
| B8 | Drift policy acknowledged | Any post-freeze commit invalidates continuous RC-LIVE certification | ☐ |
| B9 | DIP claim honesty | If DIP absent, freeze notes state learning deferred / awaiting MR-001 | ☐ |
| B10 | MC honesty | Freeze notes state MI-EXT Mission Control panels not activated (unless later certified) | ☐ |

---

## C. Decision Intelligence gate

| # | Check | Decision | ☐ |
| --- | --- | --- | --- |
| C1 | MR-001 status decided | LAND / DEFER / WAIVE-LEARNING-CLAIM (circle one) | ☐ |
| C2 | If LAND: DIP-001…006 present on freeze ancestry | Modules + DIP governance docs present | ☐ |
| C3 | If DEFER: MI learning contract remains design-only | `ABSENT_UNTIL_MR_001` acknowledged in freeze notes | ☐ |
| C4 | Auto-allocation remains false | No capital auto-move authority | ☐ |
| C5 | MC-006 remains read-only | No execution language in DI projections | ☐ |

**MR-001 decision record:** `________________________________`
**Decision approver:** `________________________________`

---

## D. Market Intelligence gate

| # | Check | Pass criteria | ☐ |
| --- | --- | --- | --- |
| D1 | Charter present | `MI_EXT_001_EXTERNAL_EVENTS_AND_SOURCE_PROVENANCE_CHARTER.md` | ☐ |
| D2 | Catalogue integrity | `MI_EXT_001_SOURCE_CATALOGUE.json` integrity hash validated by tests | ☐ |
| D3 | Event schema constants | `advisory_only` const true; `execution_allowed` const false | ☐ |
| D4 | No parallel MI engine | Overnight MI / Phase 138 not forked | ☐ |
| D5 | GIE bridge optional/fail-safe | Bridge does not invent timestamps; no second store/scheduler | ☐ |
| D6 | Fixture-only wave-1 | Approved fixture root only; no credentials in event payloads | ☐ |
| D7 | Tier dominance | Lower tiers cannot override Tier 1 contradictions | ☐ |
| D8 | Static execution boundary | AST/static tests prove no gate/broker/sizing imports | ☐ |

---

## E. Mission Control gate

| # | Check | Pass criteria | ☐ |
| --- | --- | --- | --- |
| E1 | Read-only flags preserved | `execution_allowed=false`, `live_trading_blocked=true`, `broker_execution_armed=false`, `advisory_only=true` | ☐ |
| E2 | No MI-EXT panel activation against endurance | Explicit non-activation attestation | ☐ |
| E3 | No new mutating MC API routes from MI-EXT | GET-only posture preserved | ☐ |
| E4 | Source registry vs news provenance not conflated | Freeze notes distinguish section provenance from MI-EXT event provenance | ☐ |
| E5 | Known env blockers documented | cryptography/ReportLab gaps not mislabeled as MI defects | ☐ |

---

## F. Runtime / broker isolation (hard stops)

| # | Check | Pass criteria | ☐ |
| --- | --- | --- | --- |
| F1 | Runtime path untouched | `capital-strata-systems` endurance worktree not used for merge prep | ☐ |
| F2 | No broker login/session from MI prep | Operator attestation | ☐ |
| F3 | No order route / live arm changes | Diff excludes execution authority surfaces (or explains no-op) | ☐ |
| F4 | Kill-switch / rollback path known | RP-0 = `66e11d4f…` (or updated freeze parent) | ☐ |
| F5 | Rollback drill note | Reference `CSS_ROLLBACK_AND_RECOVERY_STANDARD.md` | ☐ |

**Hard stop:** Any FAIL in section F blocks RC-LIVE freeze.

---

## G. Certification evidence bundle

| # | Artifact | Location / command | ☐ |
| --- | --- | --- | --- |
| G1 | MR-002 readiness doc | `docs/governance/MR_002_ENTERPRISE_MERGE_READINESS.md` | ☐ |
| G2 | This checklist (signed) | `docs/governance/MR_002_RC_LIVE_FREEZE_CHECKLIST.md` | ☐ |
| G3 | Merge matrix JSON | `docs/governance/MR_002_MERGE_MATRIX.json` | ☐ |
| G4 | MI charter/schema/catalogue | `docs/governance/MI_EXT_001_*` | ☐ |
| G5 | Offline provenance tests | `pytest tests/test_mi_ext_001_external_events_provenance.py` | ☐ |
| G6 | Hardening tests | `pytest tests/test_mi_ext_001_hardening_review.py` | ☐ |
| G7 | Whitespace / conflict markers | `git diff --check` clean on freeze scope | ☐ |
| G8 | Freeze notes | Short note recording B9/B10/C1 outcomes | ☐ |

---

## H. RC-LIVE candidate workflow (operator sequence)

1. ☐ Complete sections A–G with no hard-stop failures.
2. ☐ Record freeze SHA / tag / UTC time in section A.
3. ☐ Announce freeze to programme owners (runtime owner, MI owner, DI owner, MC owner).
4. ☐ Begin RC-LIVE candidate observation **only after** freeze announcement.
5. ☐ Monitor for commit drift; if HEAD ≠ freeze SHA → **INVALIDATE** candidate and return to checklist.
6. ☐ Keep rollback points warm: RP-0 runtime baseline and freeze parent.
7. ☐ Do not enable controlled-online MI validation without a separate authorization record.
8. ☐ Do not claim Production Certification from this freeze alone.

---

## I. Rollback points (copy into freeze notes)

| ID | Ref | Purpose |
| --- | --- | --- |
| RP-0 | `66e11d4f83600a7765b4e55afa33d19e301dd70e` | Active runtime / pre-MI RC tip |
| RP-1 | same as RP-0 | Pre-MI parent |
| RP-2 | `3c7a6b61de2f7784e794b9f186a440d0f50392b2` | Known-good MI-EXT tip |
| RP-3 | *TBD post-MR-001* | Post-DIP integration rollback |
| RP-4 | *TBD freeze SHA* | RC-LIVE freeze rollback label |

---

## J. Sign-off

| Role | Name | Date (UTC) | Signature / ack |
| --- | --- | --- | --- |
| Release governor | | | |
| Market Intelligence owner | | | |
| Decision Intelligence owner | | | |
| Mission Control owner | | | |
| Runtime / endurance owner | | | |

**Freeze decision:** ☐ APPROVED as RC-LIVE candidate ☐ REJECTED ☐ DEFERRED

**Package signal (documentation review):** `MR_002_READY_FOR_REVIEW`
