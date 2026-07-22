# Capital Strata Systems (CSS)

Controlled-paper / advisory trading and operations platform.

## Canonical release status (authoritative)

**Read this first:** [`docs/release/CSS_CANONICAL_RELEASE_STATUS.md`](docs/release/CSS_CANONICAL_RELEASE_STATUS.md)

| Claim | Status |
| --- | --- |
| Controlled paper / advisory / read-only | **GO** |
| Production certification | **NO-GO** (`NOT CERTIFIED`) |
| Commercial readiness | **NO-GO** |
| Live trading | **NO-GO** (fail-closed) |

Safety posture: `execution_allowed=false` · `live_trading_blocked=true` · `broker_execution_armed=false` · `advisory_only=true`

Where older RC1 “GO / 100%” documents conflict with the canonical status page, **the canonical status page prevails**.

## Release Gate 2

Gate 2 remediation is active. Execution authority:

- [`docs/release/CSS_AUDIT_REMEDIATION_REGISTER.md`](docs/release/CSS_AUDIT_REMEDIATION_REGISTER.md)
- [`docs/release/CSS_RELEASE_GATE_2_PLAN.md`](docs/release/CSS_RELEASE_GATE_2_PLAN.md)
- [`docs/release/CSS_RELEASE_BLOCKER_MATRIX.md`](docs/release/CSS_RELEASE_BLOCKER_MATRIX.md)
- [`docs/release/CSS_REMEDIATION_PRIORITY_QUEUE.md`](docs/release/CSS_REMEDIATION_PRIORITY_QUEUE.md)

Evidence custody: [`docs/release/CSS_EVIDENCE_CUSTODY_STANDARD.md`](docs/release/CSS_EVIDENCE_CUSTODY_STANDARD.md)

## Completion audit

Evidence-based V1 completion status:

- [`CSS_V1_MASTER_COMPLETION_AUDIT.md`](CSS_V1_MASTER_COMPLETION_AUDIT.md)

## Ownership

Repository domain and Critical AR owners:

- [`docs/governance/CSS_REPOSITORY_OWNERSHIP_REGISTER.md`](docs/governance/CSS_REPOSITORY_OWNERSHIP_REGISTER.md)
- Path review domains: [`.github/CODEOWNERS`](.github/CODEOWNERS)

## What this repository is not

- Not a production-certified live trading system
- Not commercially ready on current evidence
- Not authorized for live order placement without a separate approved programme

## Documentation map

| Area | Location |
| --- | --- |
| Release / Gate 2 | `docs/release/` |
| Governance | `docs/governance/` |
| Operations | `docs/operations/` |
| Architecture | `docs/architecture/` |
| Docs index | `docs/README.md` |
