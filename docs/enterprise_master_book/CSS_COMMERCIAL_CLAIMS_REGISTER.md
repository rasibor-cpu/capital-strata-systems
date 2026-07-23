# CSS Commercial Claims Register

**Document ID:** EMB-CR-001
**Master Book version:** 0.1.0-framework
**Effective date:** 2026-07-22
**Repository baseline:** `34503b155d6e1274863d0b137e23b145d2901e1e`
**Branch:** `css-unified-consolidation-2026-07-13`
**Approval status:** DRAFT — seed register for CEP-001

Authority references:

* `docs/release/CSS_CANONICAL_RELEASE_STATUS.md`
* `docs/release/RC001_EXECUTIVE_SUMMARY.md`
* `docs/release/CSS_PRODUCTION_CERTIFICATION_READINESS_ASSESSMENT.md`
* `docs/release/CSS_OV001_OAT_COMPLETION_REPORT.md`

**Current release posture (binding):** controlled paper / advisory / read-only may be claimed within scope; production certification **NO-GO / NOT CERTIFIED**; commercial readiness **NO-GO**; live trading **NO-GO / blocked**.

---

## Register columns

| Column | Meaning |
| --- | --- |
| Claim ID | Stable identifier |
| Proposed claim | Candidate commercial statement |
| Capability | Product area |
| Status classification | Evidence classification |
| Repository evidence | Primary evidence source |
| Restrictions | Hard limits on use of the claim |
| Approved wording | Safe wording if approved |
| Prohibited wording | Wording that must not be used |
| Approval status | `DRAFT` / `APPROVED` / `REJECTED` / `WITHDRAWN` |

---

## Seed claims

| Claim ID | Proposed claim | Capability | Status classification | Repository evidence | Restrictions | Approved wording | Prohibited wording | Approval status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CR-001 | CSS provides an Options Income capability within Mission Control | Options Income Engine | `DELIVERED` | Canonical status (Mission Control scoped capabilities); Mission Control / options pages in repository | Advisory / controlled-paper scope only; not a live income guarantee | CSS includes an Options Income workspace for governed oversight in controlled paper / advisory operation | “Guaranteed options income”; “live options trading enabled”; “fully automated income engine” | DRAFT |
| CR-002 | Mission Control is the primary operational control surface | Mission Control | `DELIVERED` | `docs/release/CSS_CANONICAL_RELEASE_STATUS.md` (Mission Control read-only certification within scope); RC-001 runtime confirmation | Read-only / advisory posture; not production certification | Mission Control provides governed operational visibility for controlled paper / advisory CSS operation | “Production-ready Mission Control”; “fully certified institutional control centre” | DRAFT |
| CR-003 | Coinbase is integrated for CSS broker workflows | Coinbase integration | `VALIDATED_READ_ONLY` | Canonical broker safety posture; OV-001 / broker validation programme docs; fail-closed execution blocked | Read-only / controlled validation only; live trading blocked; do not claim complete crypto brokerage coverage | Coinbase integration is supported for controlled, fail-closed, non-executing / read-oriented validation under CSS broker controls | “Live Coinbase trading enabled”; “complete Coinbase support”; “production-certified Coinbase execution” | DRAFT |
| CR-004 | OANDA is integrated for CSS broker workflows | OANDA integration | `VALIDATED_READ_ONLY` | Same authority chain as CR-003; OANDA adapter and validation programme artefacts | Read-only / controlled validation only; live trading blocked | OANDA integration is supported for controlled, fail-closed, non-executing / read-oriented validation under CSS broker controls | “Live OANDA trading enabled”; “complete FX broker coverage”; “production-certified OANDA execution” | DRAFT |
| CR-005 | CSS provides executive reporting outputs | Executive Reporting | `DELIVERED` | RC1.1 branding/reporting baseline; Reports Center / executive reporting modules; RC-001 executive API confirmation (advisory) | Advisory scope; report families and limitations must be stated; not all reports are universally available | CSS provides executive reporting for governed advisory / controlled-paper operation within documented report families | “All reports available”; “production-ready financial reporting suite”; “GAAP/IFRS certified statements” | DRAFT |
| CR-006 | CSS provides Executive Intelligence | Executive Intelligence | `PILOT` | Phase 182A foundation present in repository baseline; commercial readiness still NO-GO under canonical status | Do not present as production-certified intelligence product; keep pilot / foundation framing until Master Book Volume 8 approval | CSS includes an Executive Intelligence foundation for advisory insight generation within controlled scope | “AI-powered institutional decision engine”; “fully automated executive intelligence”; “production-certified EI” | DRAFT |
| CR-007 | CSS provides institutional-grade reporting | Institutional Reporting | `NOT_CERTIFIED` | Canonical commercial readiness NO-GO; production certification NOT CERTIFIED; reporting exists but institutional certification claim is unsupported | May describe delivered report families; may not claim institutional certification | CSS provides structured management and financial reporting artefacts under advisory / controlled-paper operation | “Institutionally certified reporting”; “audit-ready for all institutions”; “complete institutional reporting” | DRAFT |
| CR-008 | CSS is governed by a formal governance framework | Governance Framework | `DELIVERED` | Release gates, ownership register, fail-closed controls, governance docs under `docs/governance/` and `docs/release/` | Governance existence ≠ production certification | CSS operates under a documented fail-closed governance framework with release-gate discipline | “Fully certified governance”; “regulatory approval complete” | DRAFT |
| CR-009 | CSS maintains an audit and remediation framework | Audit Framework | `DELIVERED` | `docs/release/CSS_AUDIT_REMEDIATION_REGISTER.md`; Gate 2 remediation artefacts | Audit framework ≠ completed production certification | CSS maintains an audit remediation register and evidence-linked release controls | “Fully audited and certified”; “all audit findings closed for production” | DRAFT |
| CR-010 | CSS provides broker management capabilities | Broker Management | `DELIVERED` | Mission Control broker pages; broker environment profiles; fail-closed execution posture | Management visibility and controlled configuration ≠ live trading authority | CSS provides broker management and readiness visibility under fail-closed, execution-blocked controls | “All brokers supported”; “live broker execution ready” | DRAFT |
| CR-011 | CSS includes market intelligence capabilities | Market Intelligence | `PILOT` | Repository market/intel subsystems and advisory market-data contracts in branch history | Scope and maturity vary; not a certified alpha product | CSS includes advisory market-intelligence components for governed decision support | “Guaranteed market predictions”; “complete market coverage”; “live trading signals certified” | DRAFT |
| CR-012 | CSS includes a learning engine | Learning Engine | `PILOT` | Analytics / learning pipeline modules in repository | Learning outputs are advisory; no performance guarantees | CSS includes learning and analytics components that inform advisory workflows | “Self-improving profitable AI”; “guaranteed learning-driven returns” | DRAFT |
| CR-013 | CSS provides a mobile dashboard | Mobile Dashboard | `DELIVERED` | RC-001 runtime confirmation (mobile dashboard reachable); mobile launcher / dashboard artefacts; RC1.1 branding scope | Advisory / controlled-paper operation; LAN/mobile deployment constraints apply | CSS provides a mobile dashboard for governed operational visibility in controlled deployments | “Fully certified mobile trading app”; “live trading from mobile enabled” | DRAFT |
| CR-014 | CSS is production certified | Production Certification | `NOT_CERTIFIED` | `docs/release/CSS_CANONICAL_RELEASE_STATUS.md`; Phase 181 `NOT CERTIFIED`; production readiness assessment NO-GO until operational validation path completes | Absolute prohibition on production-certified claims | CSS is **not** production-certified at the current baseline | “Production-ready”; “production certified”; “certified for production deployment” | DRAFT |
| CR-015 | CSS supports live trading | Live Trading | `NOT_CERTIFIED` | Canonical status: live trading / live micro-pilot **NO-GO**; `execution_allowed=false`; `live_trading_blocked=true` | Live trading must not be commercially offered or implied | Live trading is blocked. CSS currently supports controlled paper / advisory / read-only operation only | “Live trading enabled”; “ready for live markets”; “execution armed” | DRAFT |
| CR-016 | CSS is ISO 27001 / ISO 9001 ready | ISO readiness | `FUTURE` | Certification Volume 9 roadmap intent; no current ISO certification evidence in canonical release status | Roadmap only; no ISO certificate claim | ISO 27001 and ISO 9001 are future certification roadmap items, not current certifications | “ISO certified”; “ISO 27001 ready”; “ISO compliant today” | DRAFT |

---

## Cross-cutting commercial claim

| Claim ID | Proposed claim | Capability | Status classification | Repository evidence | Restrictions | Approved wording | Prohibited wording | Approval status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CR-017 | CSS is commercially ready for general sale | Commercial readiness | `NOT_CERTIFIED` | Canonical release status: Commercial readiness **NO-GO** | Commercial Readiness Programme may prepare materials; it does not change release status | CSS commercial readiness remains **NO-GO** under canonical release status; CEP work prepares governed materials only | “Commercially ready”; “available for purchase as a production platform” | DRAFT |

---

## Usage rules

1. Do not publish any claim with `Approval status = DRAFT` externally.
2. Reclassify claims when canonical release status or SHA-bound evidence changes.
3. Prefer the approved wording column over free-form marketing text.
4. If evidence is ambiguous, classify more conservatively (`NOT_CERTIFIED`, `PILOT`, or `PLANNED`).

---

## Related documents

* [CSS_ENTERPRISE_MASTER_BOOK_GOVERNANCE.md](CSS_ENTERPRISE_MASTER_BOOK_GOVERNANCE.md)
* [CSS_MASTER_BOOK_WRITING_STANDARD.md](CSS_MASTER_BOOK_WRITING_STANDARD.md)
* [../release/CSS_CANONICAL_RELEASE_STATUS.md](../release/CSS_CANONICAL_RELEASE_STATUS.md)
