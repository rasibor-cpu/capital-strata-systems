---
id: CSS-PKG-D-001
status: REVIEW
priority: 150
risk: LOW
owner: Cursor Cloud Agent CSS-PKG-D-001
base_branch: css-v1.0.1-maintenance
starting_head: d53e6658267ab4fe281c7be58a2fad1a6412eef7
claimed_branch: css-package-d-governance-hygiene
claimed_starting_head: d53e6658267ab4fe281c7be58a2fad1a6412eef7
claimed_at_utc: 2026-08-19T18:59:40Z
review_ready_at_utc: 2026-08-19T19:05:00Z
commit_authority: FEATURE_BRANCH
push_authority: FEATURE_BRANCH
pr_authority: DRAFT_TO_MAINTENANCE
live_trading_authority: NONE
---

# CSS-PKG-D-001 — Repository / Governance Hygiene

## Objective

One consolidated repository/governance cleanup after CSS-CONSOL-CERT-001. Clean stale PR/task/release metadata and prepare for the next implementation package. Do not change runtime, broker, execution, TTL, AntiBleed, Capital Governor, UTG, live/paper, credentials, or live-network behavior.

## Authority

- commit/push only on `css-package-d-governance-hygiene`
- draft PR targeting `css-v1.0.1-maintenance` permitted
- merge not permitted by this agent
- close stale PRs without merging when evidence is conclusive
- do not delete branches
- do not change GitHub default branch
- do not merge maintenance into `main`
- do not install dependencies / redesign dotenv imports

## Validation

- `python3 -m pytest tests/test_ldt002_live_pilot_blocker_resolution_audit.py tests/test_mr001_branch_consolidation_plan.py -q` — **15 passed / 0 failed**
- `git diff --check` on this package — to be confirmed at commit

## Outputs

- `docs/release/CSS_PKG_D_001_GOVERNANCE_HYGIENE.md`
- `docs/governance/CSS_BRANCH_DISPOSITION_REGISTER.md`
- `docs/governance/CSS_DOTENV_CI_ENVIRONMENT_ACTION.md`
- `docs/release/CSS_CANONICAL_RELEASE_STATUS.md` (HEAD vs evidence-SHA split; posture labels unchanged)
- `agent_tasks/STATUS.md`
- Landed task files moved REVIEW → COMPLETE
- Stale PRs #50, #51, #52, #54, #56 closed without merge

## Safety

- live trading authority: NONE
- no runtime/broker/execution/TTL/gate changes
- no credential access
- no orders
- no branch deletes
