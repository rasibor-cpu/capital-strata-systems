# RC-004 — Operational Posture and Executive Governance Package

**Programme:** CSS Release Candidate / Controlled Live Programme
**Artifact ID:** RC-004
**Phase completing package:** Phase 192
**Candidate branch:** `css-rc-live-001-candidate`
**As-of HEAD (governance refresh):** `84a0e893385a624a8ebb5dfffd53f35ce4b30ba7`
**Paper baseline SHA (historical acknowledgment):** `b0703f36096bf183514293ef9b83b6e7849bd087` (Phase 183J / merge-base)
**Status:** **COMMITTED GOVERNANCE PACKAGE** — paper / operational posture only
**Execution authority:** **DENIED**

### LIVE_TRADING_NOT_AUTHORIZED

This package **does not** authorize live trading, live order submission, live arming,
kill-switch clearance for live money, broker write paths, or designation of an
RC-LIVE freeze SHA. Any claim that RC-004 unlocks live execution is **false**.

Companion machine artifact: `docs/governance/RC_004_POSTURE_MATRIX.json`
Evaluator (Phase 189): `backend/app/brokers/multi_broker_readiness/rc004.py`
Registry entity: `governance:RC004` (Phase 191 / refreshed Phase 192)

---

## 1. Purpose

RC-004 defines the **operational postures** under which CSS may be discussed,
certified, or operated without implying live money authority. It closes the
historical gap called out by LDT-001/002 and Phase 190: previously RC-004 existed
only as an executive session narrative (paper baseline `b0703f3…`) with **no**
committed `docs/**/RC-004*` artifact.

This document is that committed artifact. It **reaffirms** paper acknowledgment
and **explicitly denies** live unlock.

---

## 2. Posture definitions

| Posture | Meaning | Allowed | Forbidden |
| --- | --- | --- | --- |
| **Operational** | Governance, docs, offline tests, registry, fail-closed safety code | Read repo; run offline suites; maintain governance | Broker auth for live money; order submit; freeze designation by implication |
| **Paper** | Paper / practice trading under RC-002B / Phase 183J lineage | Paper routes, paper evidence, paper AntiBleed `PAPER` profile | Treating practice evidence as LIVE certification |
| **Read-only** | Controlled online or offline **GET-only** market/account observation | Phase 187A/188 OANDA RO framework; Phase 189 RO TTL (`READ_ONLY_OPERATIONAL`) after precheck | Write methods; live execution; confusing RO TTL with live-authority TTL |
| **Live** | Real-money order path | **Nothing under RC-004** | All live submission, arming, and live unlock claims |

### 2.1 Explicit posture statements

| Field | Value |
| --- | --- |
| `operational_posture` | `GOVERNANCE_ACTIVE` |
| `paper_posture` | `ACKNOWLEDGED_BASELINE` (SHA `b0703f3…`) — re-certify on any future freeze |
| `read_only_posture` | `FRAMEWORK_READY` / controlled online **READY_AFTER_PRECHECK** (creds + precheck; not unconditional GO) |
| `live_posture` | `LIVE_TRADING_NOT_AUTHORIZED` |
| `execution_authority` | `false` |
| `order_submission_allowed` | `false` |
| `live_arming_allowed` | `false` |

---

## 3. Execution authority

| Control | RC-004 binding |
| --- | --- |
| `execution_authority` | **false** (hard) |
| Live Execution Authority module | Remains fail-closed (`BLOCKED` without full ceremony) |
| Phase 152A `pilot_enabled` | Must remain false until a **future** founder-approved live phase |
| Kill switch | Must remain engaged for live money until that future phase |
| Broker write adapters | Out of scope for RC-004 unlock |

RC-004 **cannot** flip `execution_authority` to true. A separate founder-approved
live-execution phase, freeze SHA, TTL ceremony, and GO matrix are required.

---

## 4. Authorization TTL dependency

Terminology must stay distinct (Phase 189 / 190 / 192 alignment):

| Term | Scope | RC-004 relation |
| --- | --- | --- |
| **Phase 189 Read-only operational TTL** | Controlled RO session window (`READ_ONLY_OPERATIONAL`) | May support RO precheck; **not** live authority |
| **Live authority TTL** | Scoped/expiring live-authority lease with single-use consumption and revocation | **IMPLEMENTED / RESOLVED by Phase 196-R2**; this removes `BLK-AUTH-TTL` only and does not unlock RC-004 live execution |
| **Execution authority** | Boolean AND-gate for live submit | Always false under RC-004 |

RC-004 **depends** on correct TTL vocabulary: RO TTL must never be cited as live
authorization TTL. Phase 196-R2 subsequently implemented the separate live-authority
lease/TTL control. That resolves `BLK-AUTH-TTL` but does **not** change RC-004's
explicit `LIVE_TRADING_NOT_AUTHORIZED` posture or grant execution authority.

---

## 5. Freeze dependency

| Rule | Statement |
| --- | --- |
| Freeze SHA designated? | **NO** |
| Candidate HEAD as freeze? | **FORBIDDEN** — `84a0e893…` is governance refresh HEAD only |
| RC-004 unlocks freeze? | **NO** |
| Dependency | Any future live pilot **requires** an explicit founder freeze record after blockers clear |

---

## 6. Founder approval dependency

| Approval class | Status under RC-004 |
| --- | --- |
| Paper baseline acknowledgment (historical) | Acknowledged at `b0703f3…` with live denied |
| Controlled online RO precheck | Requires operator/founder precheck; not granted by this doc alone |
| Live micro-pilot GO | **NOT ISSUED** |
| Production live | **NOT ISSUED** |

---

## 7. Lineage and supersession

| Item | Classification |
| --- | --- |
| Pre-192 executive session RC-004 narrative (MW-001 citation) | **SUPERSEDED** as custody form; substance (paper OK / live denied) **RETAINED** |
| Phase 189 `evaluate_rc004_readiness` | **ALIGNED** — live always false |
| LDT-001 inventory row “RC-004 NOT_FOUND” | **SUPERSEDED** by this package (live unlock still absent) |
| Phase 190 “RC-004 committed artifact MISSING” | **HISTORICAL** (correct at Phase 190); closed by Phase 192 |
| Sign-off templates under `docs/operations/CSS_MICRO_LIVE_PILOT_SIGN_OFF_REGISTER_2026.md` | **TEMPLATES ONLY** — not live GO |

---

## 8. Release-readiness implication

RC-004 alone does **not** move Internal Freeze, Pilot, or Production to GO.
See Phase 192 release-readiness matrix in `PHASE_192_LDT_REFRESH_AND_RC004.md`.

---

## 9. Non-claims

- No broker authentication performed by publishing this document.
- No CSS restart, merge, or live enablement.
- No freeze SHA designation.
- No OV-002 or endurance certification credit.
- DIP live integration remains **NOT_READY**.
- IBKR remains roadmap-excluded / blocked per 177C Rev B.
