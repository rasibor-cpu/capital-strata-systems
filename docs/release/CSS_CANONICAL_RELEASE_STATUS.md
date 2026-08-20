# CSS Canonical Release Status

**Document type:** Canonical release authority

- Posture labels effective: 2026-07-21 (AR-001)
- Package D metadata reconciliation: 2026-08-19 (CSS-PKG-D-001)
- Package D merge reconciliation: 2026-08-20 (RSM-P1-03; PR #62 landed)
- This page does not re-run or re-issue certification evidence.

This document is the **sole active release-status authority** for Capital Strata Systems until superseded by a later Gate 2 / Phase 181 verified certification package bound to a **freeze SHA**.

Where any older release, readiness, or certification document conflicts with this page on **GO / NO-GO posture**, **this page prevails**. CSS-CONSOL-CERT-001 and CSS-PKG-D-001 prevail for *task lifecycle / merge state / remaining work packages* only; they do not override Phase 181 `NOT CERTIFIED`.

---

## Canonical development line vs evidence-bound SHAs

These are **different** facts. Do not collapse them.

| Kind | Ref | Meaning |
| --- | --- | --- |
| **Current canonical development branch** | `css-v1.0.1-maintenance` | Authoritative engineering line. Recent PRs #53–#62 target this branch. |
| **Current canonical development HEAD** (landed maintenance) | `2b39141e18fcfa2f1ee2dfcf7806061ab42e79f5` | Merge PR #62 (CSS-PKG-D-001). Not a production-certification freeze. |
| **Package D start HEAD** (historical) | `d53e6658267ab4fe281c7be58a2fad1a6412eef7` | Merge PR #61 (CSS-CONSOL-CERT-001). Starting SHA for Package D work; **superseded as current HEAD** by PR #62. |
| **GitHub default branch** | `main` @ `faf1485dd88d7056bbd8f7f891cb47caf7685603` | Stale Phase 113Y. **Not** canonical. Do not develop on it. Admin retarget recommended (see branch disposition register). |
| **Last Gate 2 / AR-001 evidence-bound baseline** | `4ea738d86c167373deccbe4edf217e929de4414d` on `css-unified-consolidation-2026-07-13` | Historical SHA that bound the 2026-07-21 release-status remediation. **Not** current HEAD. |
| **Last controlled-paper operational proof** | OP-003 / `docs/release/CSS_V1_REMAINING_BLOCKERS.md` | Historical `CERTIFIED_CONTROLLED_PAPER_OPERATION`. **Not** re-proven on `d53e665` or `2b39141e`. |
| **Last offline post-merge cert pass** | CSS-CONSOL-CERT-001 @ `fc7a6c99` (merged as `d53e665` via PR #61) | Offline regression + backlog. **Not** production certification. |
| **Next operating milestone** | **COW-001** | Start canonical CSS as-is for ≥24h controlled operation. Charter: `docs/release/CSS_COW_001_CONTROLLED_OPERATING_WINDOW.md`. Not started. Not a certification result. |
| **Phase 181 production certification** | `runtime_reports/phase181_certification/CERTIFICATION_SUMMARY.md` | **`NOT_CERTIFIED`** until a new freeze SHA has verified observations. |

Historical evidence is **not** rewritten onto `d53e665` or `2b39141e`. OP-003 GO is not a new certification of the current SHA.

---

## Current authoritative posture

| Claim surface | Status | Authority |
| --- | --- | --- |
| Controlled paper / advisory / read-only operation | **GO** — historical `CERTIFIED_CONTROLLED_PAPER_OPERATION` (OP-003). Not re-certified on current HEAD. | `docs/release/CSS_V1_REMAINING_BLOCKERS.md` |
| Production certification | **NO-GO** — `NOT CERTIFIED` | Phase 181 summary |
| Commercial readiness | **NO-GO** | `CSS_V1_MASTER_COMPLETION_AUDIT.md` §9 |
| Live trading / live micro-pilot execution | **NO-GO** — blocked | Safety locks below |
| Broker execution armed | **false** | Safety locks |
| Advisory-only | **true** | Safety locks |
| Release Gate 2 | **IN PROGRESS** | `docs/release/CSS_RELEASE_GATE_2_PLAN.md` |
| Next operating milestone | **COW-001 — not started** | `docs/release/CSS_COW_001_CONTROLLED_OPERATING_WINDOW.md` |

### Required safety posture (unchanged)

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

Posture label: `DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY`

---

## What may be claimed

1. CSS may be operated as **controlled paper / advisory / read-only** software under existing fail-closed controls, under the historical OP-003 proof (not a new SHA-bound recert).
2. Mission Control read-only certification and RC1.1 branding/reporting baseline remain valid within their documented scopes.
3. Historical RC1 paper/controlled-release engineering work remains historical evidence only.
4. Canonical **development** happens on `css-v1.0.1-maintenance`. Landed HEAD is `2b39141e` (PR #62, CSS-PKG-D-001 merged). `d53e665` is the historical Package D *start* SHA (PR #61), not current HEAD.
5. Package D has landed. The next milestone is **COW-001**: start the current canonical system as-is in controlled/paper mode for ≥24 hours. That run is not production certification until its observations are recorded.

## What must not be claimed

1. CSS is **not** production-certified.
2. CSS is **not** commercially ready.
3. CSS is **not** live-trading ready.
4. A historical “GO / 100% / Certified Ready” scorecard does **not** override current Phase 181 `NOT CERTIFIED`.
5. Uncommitted Phase 181A / 182A worktree material is **not** released capability.
6. Untracked `runtime_reports/` packages are **not** release proof unless SHA-bound under Gate 2 evidence custody (AR-002).
7. Current maintenance HEAD is **not** automatically an evidence freeze SHA.
8. CSS-CONSOL-CERT-001 offline pass is **not** production certification.
9. COW-001 is **not** complete, **not** a smoke-test substitute for operation, and **not** live-trading authorization.

---

## Next operating milestone (COW-001)

**Start the current canonical CSS as-is in controlled mode and keep it running.**

Authority: `docs/release/CSS_COW_001_CONTROLLED_OPERATING_WINDOW.md`

- Minimum 24 hours; do not stop at 24h if healthy; continue to 48/72h when practical.
- Live/current market data within existing safe support — **not** funded live execution.
- Defects do not auto-invalidate the window except SEV-1 safety-critical (immediate controlled shutdown).
- Do not start Phase 184A / 188+ / 196 / 197 / 198 or MI-EXT live ingestion as the next activity.

Cloud Agents must not start COW-001 (`BLOCKED — OPERATOR_RUNTIME_REQUIRED`).

## Supersession table

| Document | Historical claim | Supersession | Effective |
| --- | --- | --- | --- |
| `docs/release/RC1_FINAL_PRODUCTION_CERTIFICATION.md` | GO / 100% / Certified Ready for controlled pilot; live pilot language | **SUPERSEDED** for production / live-pilot authority. Retained as historical RC1-era artifact only. | 2026-07-21 · AR-001 |
| `docs/release/RC1_PRODUCTION_READINESS_REPORT.md` | GO / 100% readiness; Phase 162 live validation ready | **SUPERSEDED** for production readiness authority. | 2026-07-21 · AR-001 |
| `docs/governance/CSS_VERSION_1_RELEASE_NOTES.md` | “Only remaining work” is live validation / micro-pilot / production cert | **AMENDED**: remaining production blockers are enumerated by Master Audit + Gate 2 register; live validation alone is insufficient. | 2026-07-21 · AR-001 |
| `docs/release/RC1_FINAL_ENTERPRISE_CERTIFICATION_REPORT.md` | `READY_FOR_CONTROLLED_RC1_RELEASE` (paper) | **HISTORICAL — IN SCOPE AS PAPER/CONTROLLED ONLY**. Does not grant Production Certification. | 2026-07-21 · AR-001 |
| `docs/release/RC11_FINAL_ACCEPTANCE_AND_DEPLOYMENT_RECORD.md` | RC1.1 branding/reporting acceptance | **ACTIVE within RC1.1 scope only**. Does not grant Production Certification. | Remains scoped |
| `docs/release/CSS_V1_REMAINING_BLOCKERS.md` | Controlled paper certified | **ACTIVE** for historical controlled-paper posture. Not a current-SHA recert. | Remains active |
| `CSS_V1_MASTER_COMPLETION_AUDIT.md` | Overall V1 61%; production NO-GO | **ACTIVE** evidence authority for Gate 2. | Remains active |
| `runtime_reports/phase181_certification/CERTIFICATION_SUMMARY.md` | `NOT CERTIFIED` | **ACTIVE** production-certification result until replaced by verified SHA-bound evidence (AR-011). | Remains active |
| `docs/governance/branch_status_register.md` (2026-05-28) | `main` as GitHub-visible fallback / canonical uncertain | **SUPERSEDED for current branch classification** by `docs/governance/CSS_BRANCH_DISPOSITION_REGISTER.md`. Retained as historical caution. | 2026-08-19 · CSS-PKG-D-001 |

---

## Gate 2 next authority chain

1. `docs/release/CSS_AUDIT_REMEDIATION_REGISTER.md`
2. `docs/release/CSS_RELEASE_GATE_2_PLAN.md`
3. `docs/release/CSS_RELEASE_BLOCKER_MATRIX.md`
4. `docs/release/CSS_REMEDIATION_PRIORITY_QUEUE.md`
5. `docs/governance/CSS_REPOSITORY_OWNERSHIP_REGISTER.md` *(AR-003)*
6. `docs/release/CSS_EVIDENCE_CUSTODY_STANDARD.md` *(AR-002)*
7. Root entry point: `README.md` *(AR-004)*
8. Branch disposition: `docs/governance/CSS_BRANCH_DISPOSITION_REGISTER.md` *(CSS-PKG-D-001)*

Production Certification may become GO only after Critical Gate 2 blockers are CLOSED/WAIVED and Phase 181 is re-run with verified observations (not fixtures) on an explicit freeze SHA. COW-001 is the intended path to generate **current-SHA operational observations**; it does not by itself flip Phase 181 to CERTIFIED.

---

*AR-001 remediation artifact; CSS-PKG-D-001 reconciled development-HEAD metadata; RSM-P1-03 recorded PR #62 merge. This page does not authorize deployment, restart, broker authentication, or live trading.*
