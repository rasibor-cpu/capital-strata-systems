# Audit Remediation Priority Matrix

## Purpose

This matrix converts ARP-001 verification results into remediation priorities. It is documentation-only and does not modify runtime, execution, broker, dashboard, risk, margin, security, authentication, authorization, credential, or trading logic.

## Priority Definitions

| Priority | Name | Meaning |
| --- | --- | --- |
| P0 | Critical Safety | Blocks live or production readiness because a safety control is disconnected or unable to block exposure. |
| P1 | Security | Live authorization, identity, credential, RBAC, or access-control issue. |
| P2 | Runtime Stability | Parse/import/runtime reproducibility issue that can crash a component or break clean-clone execution. |
| P3 | Governance Consolidation | Multiple authority implementations or unclear canonical ownership. |
| P4 | Technical Debt | Legacy cleanup, documentation cleanup, or non-canonical code hygiene. |

## Matrix

| Priority | Finding | Classification | Remediation Theme | Rationale |
| --- | --- | --- | --- | --- |
| P0 Critical Safety | B-04 MarginTradeGate not enforced | VERIFIED | Wire margin gate into approved trade permission path | Margin cannot currently block new exposure in canonical path. |
| P0 Critical Safety | B-01 AntiBleedGuard disconnected | VERIFIED | Integrate or explicitly retire anti-bleed guard | Cost/bleed protection cannot affect trade approval. |
| P0 Critical Safety | B-09 live_arm disconnected | VERIFIED | Integrate two-key live arming into live boundary | Live arming exists but cannot block live execution. |
| P1 Security | B-02 hardcoded live user ID | VERIFIED | Replace hardcoded identity with RBAC/SUPER_USER policy | Live authorization is tied to `user_id == "1369"` rather than role/permission controls. |
| P2 Runtime Stability | B-06 syntax/BOM failures | PARTIALLY VERIFIED | Fix canonical syntax failure and normalize BOMs | One canonical syntax failure exists; BOM prefixes should be normalized for tooling stability. |
| P2 Runtime Stability | B-10 dashboard import target untracked | PARTIALLY VERIFIED | Track source module or remove non-canonical import | Clean clone of HEAD lacks `backend/data/coinbase_historical_downloader.py`. |
| P2 Runtime Stability | B-03 duplicate dashboard functions | PARTIALLY VERIFIED | Determine canonical status of `css_live_dashboard_v5.py` | Tracked root dashboard file shadows duplicate functions if used. |
| P3 Governance Consolidation | B-07 multiple CSSUnifiedTradeGate definitions | PARTIALLY VERIFIED | Declare canonical gate and remove/wrap duplicates | Backend gate is likely canonical, but dashboard/build definitions can drift. |
| P3 Governance Consolidation | B-08 multiple RiskGovernor definitions | PARTIALLY VERIFIED | Declare canonical risk governor and deprecate variants | Execution/tests use `engine/risk`, but other definitions remain. |
| P4 Technical Debt | B-05 compliance circular import | NOT VERIFIED | Monitor or clean package exports later | Import failure did not reproduce; package coupling remains a design smell. |

## Recommended Remediation Order

1. P0/P1 live safety bundle:
   * B-02
   * B-09
   * B-04
   * B-01

2. P2 runtime reproducibility bundle:
   * B-06
   * B-10
   * B-03

3. P3 governance consolidation bundle:
   * B-07
   * B-08

4. P4 watchlist cleanup:
   * B-05

## Notes

The priority order intentionally separates verification from remediation. Robert should review this matrix before any code-changing remediation phase begins.
