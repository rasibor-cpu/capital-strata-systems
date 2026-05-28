# CSS Branch Classification Registry

## Purpose
Defines the official classification and lifecycle role of major Capital Strata Systems branches.

## Canonical Branch
| Branch | Classification | Role |
|---|---|---|
| main | AUTHORITATIVE | Official institutional baseline |
| consolidation/pcnrass-mainline | ACTIVE | Canonicalization and consolidation branch |

## Protected Branches
| Branch | Classification | Role |
|---|---|---|
| phase1-persistence-foundation | PROTECTED | Infrastructure genesis branch |
| salvage-phase1-persistence-foundation | PROTECTED | Disaster recovery and salvage branch |

## Active / Reference Branches
| Branch | Classification | Role |
|---|---|---|
| phase65b-pnl-governance-integration | ACTIVE | PnL governance integration |
| phase57-regime-governance-foundation | ACTIVE | Regime governance foundation |
| codex/build-css-profitability-analytics-foundation | REFERENCE | Analytics foundation |
| codex/implement-opportunity-normalization-foundation | REFERENCE | Opportunity normalization foundation |
| codex/fix-remaining-test-failures-for-phase-54 | REFERENCE | Phase 54 safety fixes |

## Archive / Recovery Branches
| Branch | Classification | Role |
|---|---|---|
| css-profit-baseline-reference | ARCHIVE | Historical profit/PnL baseline |
| recover-full-dashboard-2056 | ARCHIVE | Dashboard recovery anchor |
| css-pnl-recovery-clean-2026-04-25 | ARCHIVE | PnL recovery checkpoint |
| css-pnl-optimization-v2 | ARCHIVE | Historical optimization branch |
| css-pnl-optimization-v2-local-backup | ARCHIVE | Local safety backup |

## Experimental / Review Branches
| Branch | Classification | Role |
|---|---|---|
| css-claude-engine | EXPERIMENTAL | Isolated Claude-generated modules |
| css-audit-fix-phaseA | REVIEW | Audit remediation branch |
| css-phase2-coinbase-init-fix | REVIEW | Coinbase initialization stabilization |
| phase52_visual_validation | REVIEW | Visual validation branch |

## Governance Rules
1. No direct development on archived branches.
2. Protected branches must not be deleted.
3. Experimental branches are reference-only unless reviewed.
4. All merges into main require PCNRASS confirmation.
5. Dashboard logic must remain render-only.
6. Execution, governance, PnL, and broker authority must remain centralized.
