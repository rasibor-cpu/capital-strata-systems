---
id: CSS-COW-001
status: READY
priority: 200
risk: HIGH
owner: UNCLAIMED
base_branch: css-v1.0.1-maintenance
starting_head: DISCOVER
commit_authority: FEATURE_BRANCH
push_authority: FEATURE_BRANCH
live_trading_authority: NONE
claim_environment: OPERATOR_LAPTOP_RUNTIME
cloud_agent_claim: FORBIDDEN
---

# CSS-COW-001 — Controlled Operating Window

## Objective

Start the **current canonical CSS as-is** in controlled/paper mode and keep it running for at least 24 hours using current/live market data. The run itself is operation, defect discovery, and certification evidence. See `docs/release/CSS_COW_001_CONTROLLED_OPERATING_WINDOW.md`.

## Cloud agents

Do **not** claim or start this task in a Cloud Agent environment. Stop and report `BLOCKED — OPERATOR_RUNTIME_REQUIRED`.

## Authority

- live trading / funded orders: NONE
- do not change UTG, AntiBleed, Capital Governor, TTL, live/paper defaults, or broker execution architecture to “make the window easier”
- SEV-1 safety-critical defects: controlled shutdown immediately
- SEV-2/SEV-3: repair and continue where safe; do not auto-invalidate the window

## Not this task

Phase 184A, 188+, 196, 197, 198, MI-EXT live ingestion, new FX live governor, new autonomous live authority.
