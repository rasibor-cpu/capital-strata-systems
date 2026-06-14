# CSS Authority Remediation Master Plan

Authoritative branch: `css-evening-consolidation-2026-06-09`

Status: Authoritative remediation roadmap

Scope: Documentation only. This document does not change runtime behavior, execution behavior, broker behavior, dashboard behavior, authentication behavior, credential handling, or trading logic.

## Source Basis

This roadmap consolidates findings from:

1. Independent CSS repository inventory review.
2. Independent Enterprise Audit Report attributed to Claude and the post-Claude audit evidence retained in the repository.
3. Existing governance documents, including ARP-001 through ARP-011, Phase 100A through Phase 104B, and the CSS implementation tracker.
4. Existing certification documents under `certification/`.
5. Existing audit trackers and reconciliation reports.

Primary source emphasis is placed on the Claude audit themes identified for this phase:

* dual `CSSUnifiedTradeGate` implementations
* multiple PnL authorities
* multiple `RegimeGate` or regime-control authority surfaces
* broken or ambiguous canonical entry points
* open audit tracker findings
* security audit status
* backend path corruption and recursive directory nesting concerns
* missing CI/CD validation
* production readiness blockers

## 1 Executive Summary

Capital Strata Systems has matured significantly in governance, risk management, operational controls, certification structure, audit traceability, and multi-asset planning.

Completed remediation work has closed the most immediate safety findings from the earlier audit remediation program. AntiBleedGuard, live-toggle RBAC, live-arm enforcement, MarginTradeGate enforcement, compliance import remediation, session schema initialization, syntax/BOM cleanup, and non-destructive authority quarantine have all been documented and supported by targeted evidence.

However, major outstanding work remains before CSS can be considered institutionally production-ready.

Remaining work is grouped into four major programs:

1. Authority Remediation
2. Governance Closure
3. Certification Evidence
4. Production Readiness

This document becomes the authoritative remediation roadmap for resolving those remaining gaps.

The central conclusion is straightforward: CSS cannot advance toward production approval until authority ambiguity is resolved first. Governance closure follows, then certification evidence, then production approval.

## 2 Current CSS Maturity Assessment

### Strengths

CSS now has a mature governance foundation:

* Formal institutional certification framework exists.
* Certification evidence package structure exists.
* Governance, runtime, broker, risk, margin, security, recovery, operations, and dashboard certification registers exist.
* Original critical audit findings have been verified, remediated, documented, and captured in evidence packages.
* Controlled paper-trading evidence has been captured.
* Operations runbooks exist for startup, paper trading, emergency shutdown, recovery/restart, and incident response.
* Enterprise risk and multi-asset portfolio governance frameworks exist.
* Non-canonical authority surfaces have been mapped and partially quarantined.

CSS also has meaningful technical strengths:

* `AntiBleedGuard` is integrated into the canonical pre-execution safety path.
* `MarginTradeGate` is integrated into the execution gate path.
* `live_toggle` no longer depends on a hardcoded user identity.
* `live_arm` is part of the live authorization chain.
* The compliance circular import and session schema initialization gap were remediated.
* Controlled paper operation is supported by retained evidence.

### Weaknesses

The remaining weaknesses are mainly institutional-readiness gaps rather than isolated one-line defects:

* Authority ambiguity remains around trade gate, PnL, dashboard, risk, and regime-related surfaces.
* Multiple valid PnL layers exist, but their boundaries still require stronger canonicalization and evidence.
* Dashboard-local and backend trade gates coexist, creating audit ambiguity.
* Historical and retirement-candidate dashboard files remain in the repository.
* Some audit tracker items remain open or only partially closed.
* Security audit materials are inconsistent: one certification manual says security audit completed, while the security audit charter still describes an incomplete audit posture.
* Broker certification evidence remains incomplete.
* Dashboard certification evidence remains incomplete.
* Production CI/CD certification automation is not yet established.
* Backend path corruption and recursive directory nesting concerns require a formal repository-structure remediation phase.
* Production readiness evidence is not complete.

### Current Readiness State

Current CSS readiness state:

```text
Controlled development: READY
Controlled paper operation: APPROVED WITH EVIDENCE
Controlled certification evidence collection: READY
Restricted live-read broker evidence: NOT YET CERTIFIED
Limited production candidate: NOT READY
Institutional production: NOT READY
```

CSS should continue development and controlled paper evidence collection. It should not be treated as production-approved until authority ambiguity, governance closure, certification evidence, broker evidence, security recertification, CI/CD validation, and production readiness exit criteria are complete.

## 3 Tier 1 - Authority Remediation Program

Tier 1 resolves the authority ambiguity called out by the independent repository inventory, Claude audit themes, ARP-006, ARP-007, ARP-009, ARP-011, the dashboard certification register, and the implementation tracker.

Authority remediation must come first because all later certification depends on being able to state which implementation owns each decision.

### 3.1 Trade Gate Canonicalization

#### Issues

* Multiple `CSSUnifiedTradeGate` implementations exist.
* `backend/governance/css_unified_trade_gate.py` is mapped as the canonical backend authority.
* `scripts/css_live_dashboard.py` contains a dashboard-local `CSSUnifiedTradeGate` support authority.
* Build, backup, and archive files contain additional non-canonical gate definitions.
* ARP-009 lists B-07 as `PARTIALLY_CLOSED`.
* ARP-011 added non-canonical warnings but did not remove or merge duplicate authority surfaces.

#### Risk

Future contributors, tests, scripts, or auditors may patch or execute a non-canonical gate and believe they have changed the runtime authority.

#### Target

Single authoritative trade gate.

The target state should define:

* one canonical backend trade gate authority
* one documented dashboard display/support boundary
* import regression tests proving canonical resolution
* retirement plan for build, backup, and archive gate definitions

#### Future Phase

`PHASE 105A - Trade Gate Canonicalization`

### 3.2 PnL Authority Canonicalization

#### Issues

* Multiple PnL authorities or PnL-adjacent surfaces exist.
* `engine/performance/pnl_tracker.py` is mapped as the engine loop PnL tracker.
* `scripts/css_live_dashboard.py` owns dashboard open-position mark-to-market state.
* `backend/app/accounting/pnl_engine.py` acts as an accounting observer/snapshot path.
* `backend/app/persistence/...` owns durable PnL persistence.
* `engine/reporting/...` owns reporting-oriented PnL outputs.
* Dashboard certification evidence still requires proof that displayed PnL is consistent with accounting/PnL authority.
* Repository reconciliation materials identified dashboard PnL as not fully proven ledger-derived.

#### Risk

Multiple PnL surfaces can produce inconsistent reporting, audit uncertainty, and unclear financial truth during certification.

#### Target

Single authoritative PnL source.

The target state should define:

* canonical financial-truth PnL authority
* dashboard display contract
* accounting observer boundary
* persistence boundary
* reporting boundary
* reconciliation tests and evidence

#### Future Phase

`PHASE 105B - PnL Authority Canonicalization`

### 3.3 Regime Gate Canonicalization

#### Issues

* Regime-control concepts appear across roadmap, specifications, scanner/intelligence materials, and risk governance.
* The independent audit theme identifies multiple `RegimeGate` or regime authority surfaces.
* CSS lacks a final authoritative register identifying the single runtime regime authority and support-only regime consumers.

#### Risk

Conflicting regime decisions can alter risk posture, signal eligibility, or strategy behavior depending on which surface is used.

#### Target

Single regime authority.

The target state should define:

* canonical regime gate or regime decision owner
* data inputs and outputs
* integration relationship to scanner, strategy, risk, and execution gates
* dashboard visibility boundary

#### Future Phase

`PHASE 105C - Regime Gate Canonicalization`

### 3.4 Entry Point Canonicalization

#### Issues

* Historical, support, backup, and retirement-candidate startup paths remain in the repository.
* `css_live_dashboard_v5.py` is a retirement candidate and has a direct-execution guard.
* Earlier reconciliation materials identified broken startup/import paths, including broker bootstrap and intelligence orchestrator concerns.
* The dashboard and engine paths are documented, but the production startup path is not yet declared as a single final entry point.

#### Risk

Operators or automation could start CSS through the wrong script, bypassing the intended certification path or triggering stale imports.

#### Target

Single production startup path.

The target state should define:

* canonical paper startup path
* canonical production-candidate startup path
* explicitly unsupported paths
* direct-execution guards or operator-facing warnings for retirement candidates
* CI checks proving canonical entry points import and start in safe mode

#### Future Phase

`PHASE 105D - Entry Point Canonicalization`

### 3.5 Repository Structure Remediation

#### Issues

* The Claude audit theme identifies backend path corruption and recursive directory nesting concerns.
* Existing repository reconciliation materials identify broken package paths, missing broker registry paths, and split broker/bootstrap behavior.
* Historical, generated, backup, and archive-like files remain near active code paths.
* Some evidence and docs show duplicated or nested documentation paths.

#### Risk

Path ambiguity can create import failures, duplicate module identities, broken clean-clone startup behavior, and audit confusion.

#### Target

Single clean repository structure.

The target state should define:

* active source tree boundaries
* archive tree boundaries
* documentation tree boundaries
* generated artifact boundaries
* no recursive source nesting in active paths
* package import validation in CI

#### Future Phase

`PHASE 105E - Repository Structure Remediation`

## 4 Tier 2 - Governance Closure Program

Tier 2 closes governance ambiguity after authority remediation is complete.

### 4.1 Audit Tracker Closure

#### Issues

* ARP-009 marks B-03, B-07, B-08, and B-10 as `PARTIALLY_CLOSED`.
* ARP-011 added markers but did not perform destructive cleanup or final retirement.
* The implementation tracker still lists several high-priority planned items, including audit viewer completion, replay harness, WebSocket migration, release checklist automation, persistent sessions, database-backed users, and alerting.

#### Target

All audit tracker findings should have one of these final states:

* `CLOSED`
* `ACCEPTED_RISK`
* `DEFERRED_WITH_OWNER`
* `OUT_OF_SCOPE`

No production-facing finding should remain ambiguous.

#### Future Phase

`PHASE 106A - Audit Tracker Closure`

### 4.2 Security Audit Re-Certification

#### Issues

* `docs/certification/docs/security/CSS_SECURITY_AUDIT_CHARTER.md` states that production deployment is prohibited if the security audit remains incomplete.
* Another certification document references security audit completion.
* This creates an evidence conflict that must be resolved before production readiness claims.
* Credential security and broker credential non-disclosure evidence remain pending in certification registers.

#### Target

One final security audit status.

The target state should define:

* whether the security audit is complete, incomplete, or requires recertification
* finding register status
* remediation verification status
* credential handling evidence status
* production security gate status

#### Future Phase

`PHASE 106B - Security Audit Re-Certification`

### 4.3 Governance Authority Register

#### Issues

Authority mapping exists across ARP documents, but CSS still needs a concise standing register for ongoing governance.

#### Target

Create an authority register for:

* Trade Gate
* PnL Engine
* Regime Gate
* Dashboard Runtime
* Broker Authority

The register should include canonical file, support files, prohibited duplicates, test evidence, owner, certification status, and last review date.

#### Future Phase

`PHASE 106C - Governance Authority Register`

## 5 Tier 3 - Certification Evidence Program

Tier 3 captures proof that the canonicalized system behaves as governed.

### 5.1 Broker Certification Evidence

#### Issues

Broker evidence remains incomplete for:

* selected broker display
* broker mode display
* paper/practice broker evidence
* live read-only broker evidence
* real balance and capital sync
* OANDA production certification
* Coinbase production certification
* IBKR scope decision

#### Future Phase

`PHASE 107A - Broker Certification Evidence`

### 5.2 Live Execution Blocking Evidence

#### Issues

Broker certification registers still require proof that:

* unauthorized live execution is blocked
* live execution requires explicit authorization
* unknown broker or margin state fails safely
* read-only broker evidence does not place orders
* credential failure falls back safely

#### Future Phase

`PHASE 107B - Live Execution Blocking Evidence`

### 5.3 Credential Security Evidence

#### Issues

Credential security evidence must prove that logs, screenshots, reports, docs, and commits do not expose:

* passwords
* API keys
* tokens
* account identifiers
* broker credentials
* secret material

#### Future Phase

`PHASE 107C - Credential Security Evidence`

### 5.4 Recovery and Restart Certification

#### Issues

Runbooks exist, but recovery evidence must still prove:

* session restart behavior
* database validation
* legal acceptance reachability
* dashboard recovery
* paper-trading recovery
* safe handling of ambiguous state

#### Future Phase

`PHASE 107D - Recovery and Restart Certification`

### 5.5 Multi-Day Controlled Paper Run

#### Issues

Phase 103A captured a controlled paper run, but institutional readiness requires longer-duration evidence.

#### Future Phase

`PHASE 107E - Multi-Day Controlled Paper Run`

### 5.6 Dashboard Certification Evidence

#### Issues

Dashboard certification register still requires evidence for:

* runtime dashboard capture
* broker status visibility
* position visibility
* realized and unrealized PnL visibility
* asset-class visibility
* audit/event visibility
* dashboard separation of responsibility
* no credential display

#### Future Phase

`PHASE 107F - Dashboard Certification Evidence`

## 6 Tier 4 - Production Readiness Program

Tier 4 turns the remediated and certified system into a production-candidate package.

### 6.1 Continuous Certification Pipeline

#### Issues

The implementation tracker identifies release checklist automation as planned and high priority. Missing CI/CD validation remains a production readiness blocker.

#### Target

Automated certification pipeline for:

* syntax certification
* security tests
* governance/legal acceptance tests
* margin gate tests
* risk governor tests
* AntiBleedGuard tests
* session initialization tests
* canonical import checks
* authority duplication checks

#### Future Phase

`PHASE 108A - Continuous Certification Pipeline`

### 6.2 Enterprise Risk Limits Framework

#### Issues

The enterprise risk model exists, but numerical production limits are not implemented or approved in that phase.

#### Target

Approved institutional risk limits for:

* position limits
* asset-class limits
* sector limits
* daily loss limits
* weekly loss limits
* maximum drawdown limits
* margin utilization limits

#### Future Phase

`PHASE 108B - Enterprise Risk Limits Framework`

### 6.3 Margin Certification Program

#### Issues

Margin engine, margin adapters, margin trade gate, and margin dashboard visibility exist, but live broker margin evidence and full margin certification remain incomplete.

#### Target

Complete margin certification covering:

* simulated margin behavior
* live-read margin retrieval
* broker fallback behavior
* margin state classification
* margin trade-gate enforcement
* dashboard visibility
* evidence retention

#### Future Phase

`PHASE 108C - Margin Certification Program`

### 6.4 Multi-Asset Portfolio Data Contract

#### Issues

The multi-asset portfolio architecture is documented, but unified position, exposure, PnL, and margin data contracts are not yet production-certified.

#### Target

Canonical portfolio data contract covering:

* equities
* ETFs
* FX
* crypto
* futures
* options
* future fixed income
* future commodities

#### Future Phase

`PHASE 108D - Multi-Asset Portfolio Data Contract`

### 6.5 Certification Review Board Package

#### Issues

Evidence exists across many folders, but final production approval requires a reviewable package with sign-off structure.

#### Target

Certification review package containing:

* governance evidence
* test evidence
* runtime evidence
* dashboard evidence
* broker evidence
* risk evidence
* margin evidence
* recovery evidence
* security evidence
* operations evidence
* Robert final review disposition

#### Future Phase

`PHASE 108E - Certification Review Board Package`

## 7 Lower Priority Remediation

Lower priority work should follow after Tier 1 through Tier 4 items are under control.

### Governance Index Consolidation

CSS has many governance documents across `docs/governance/`, `docs/operations/`, `docs/certification/`, `certification/`, and roadmap folders. A consolidated index would reduce review friction.

### Historical Artifact Retirement

Historical dashboards, build scripts, backup files, and archive-like materials should be retired only after import proof and Robert approval.

### Reporting Requirements Expansion

Institutional reporting requirements should be expanded for:

* daily portfolio reports
* risk reports
* exposure reports
* capital allocation reports
* margin reports
* executive summaries

### Evidence Retention Policy

CSS needs a final evidence retention policy for:

* controlled paper evidence
* broker evidence
* security evidence
* audit logs
* dashboard screenshots
* runtime captures
* production approval records

### Future Asset Class Scope Register

Fixed income and commodities are identified as future asset classes. They should be added to a formal scope register so they are not mistaken for current production capability.

## 8 Recommended Execution Order

Recommended sequence:

1. `PHASE 105A - Trade Gate Canonicalization`
2. `PHASE 105B - PnL Authority Canonicalization`
3. `PHASE 105C - Regime Gate Canonicalization`
4. `PHASE 105D - Entry Point Canonicalization`
5. `PHASE 105E - Repository Structure Remediation`
6. `PHASE 106A - Audit Tracker Closure`
7. `PHASE 106B - Security Audit Re-Certification`
8. `PHASE 106C - Governance Authority Register`
9. `PHASE 107A - Broker Certification Evidence`
10. `PHASE 107B - Live Execution Blocking Evidence`
11. `PHASE 107C - Credential Security Evidence`
12. `PHASE 107D - Recovery and Restart Certification`
13. `PHASE 107E - Multi-Day Controlled Paper Run`
14. `PHASE 107F - Dashboard Certification Evidence`
15. `PHASE 108A - Continuous Certification Pipeline`
16. `PHASE 108B - Enterprise Risk Limits Framework`
17. `PHASE 108C - Margin Certification Program`
18. `PHASE 108D - Multi-Asset Portfolio Data Contract`
19. `PHASE 108E - Certification Review Board Package`
20. Lower priority governance index, artifact retirement, reporting, evidence retention, and future asset-class scope phases.

## 9 Production Readiness Exit Criteria

CSS may not be considered production-ready until all of the following conditions are satisfied:

1. A single canonical trade gate is declared, enforced, and tested.
2. PnL authority boundaries are canonicalized and reconciled.
3. Regime authority is canonicalized.
4. A single approved startup path exists for production-candidate operation.
5. Repository path corruption and recursive nesting concerns are remediated or formally closed.
6. All audit tracker findings are closed, accepted, or explicitly deferred with owner and approval.
7. Security audit status is reconciled and recertified.
8. Broker evidence is captured for approved broker scope.
9. Live execution blocking evidence is captured and retained.
10. Credential security evidence is captured and retained.
11. Recovery and restart evidence is captured and retained.
12. Multi-day controlled paper evidence is captured and reviewed.
13. Dashboard certification evidence is captured and reviewed.
14. Continuous certification pipeline is active for push and pull request validation.
15. Enterprise risk limits are defined and approved.
16. Margin certification evidence is complete for approved scope.
17. Multi-asset portfolio data contract is defined.
18. Certification review board package is complete.
19. Robert has reviewed and approved production readiness.
20. No Critical or High unresolved production blockers remain.

## 10 Conclusion

CSS has moved from fragmented remediation into a structured certification path. The remaining work is no longer just about adding features; it is about making authority, evidence, and production approval unambiguous.

Authority ambiguity must be resolved first.

Governance closure follows.

Certification evidence follows.

Production approval is the final stage.

Until those steps are complete, CSS should remain in controlled paper operation, controlled certification evidence collection, and tightly bounded development.

