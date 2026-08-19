# CSS Branch Disposition Register

**Document type:** Governance / repository hygiene
**Task:** CSS-PKG-D-001
**Date (UTC):** 2026-08-19
**Canonical development HEAD at register:** `d53e6658267ab4fe281c7be58a2fad1a6412eef7`
**Destructive operations in this package:** none (no branch deletes; no default-branch change)

This register supersedes `docs/governance/branch_status_register.md` (2026-05-28) for **current** classification. The older file is retained as a historical caution against unverified deletion.

Classifications:

| Class | Meaning |
| --- | --- |
| CANONICAL | Authoritative development line. New work bases here. |
| MERGED/HISTORICAL | Landed via PR; keep for audit; do not develop further. |
| PRESERVE FOR REFERENCE | Do not merge wholesale; needed as historical/design reference. |
| STALE/SUPERSEDED | Replaced by a later recovery. Do not merge. |
| WRONG BASE | Targets or contains work vs stale `main`. Do not merge onto canonical. |
| DO NOT DEVELOP | Open/historical line that must not receive new product work. |

Branches were **not** deleted.

## Required branches

| Branch | Tip (2026-08-19) | Classification | Notes |
| --- | --- | --- | --- |
| `css-v1.0.1-maintenance` | `d53e6658` Merge PR #61 | **CANONICAL** | Required base for new work. |
| `main` | `faf1485d` Phase 113Y | **WRONG BASE** / **DO NOT DEVELOP** | GitHub default (stale). See default-branch decision. |
| `css-rc-live-001-candidate` | `fbff1180` Phase 198 | **PRESERVE FOR REFERENCE** | Do not wholesale merge. Live-architecture fork (184A/188+/196/197/198). |
| `css-market-intelligence-external-sources-001` | `81d48bfc` MR-002 | **PRESERVE FOR REFERENCE** / **WRONG BASE** for PRs | Historical MI-EXT/RC freeze line. PR #52 closed without merge. |
| `feature/css-world-event-intelligence` | `f5c8ecf1` | **PRESERVE FOR REFERENCE** | Codex priority lineage; not the current MI-EXT recovery. Do not treat as live-ingestion authority. |
| `css-tai-002-runtime-validation` | `3a1d76ec` | **STALE/SUPERSEDED** | Replaced by R2. PR #54 closed without merge. |
| `css-tai-002-runtime-validation-r2` | `f7257726` | **MERGED/HISTORICAL** | PR #57. |
| `css-rclive-w1-autonomous-supervisor` | `9178f4ca` | **MERGED/HISTORICAL** | PR #58. |
| `css-mi-ext-001-recovery-r2` | `bb434599` | **MERGED/HISTORICAL** | PR #59. |
| `css-rclive-offline-market-readiness-consolidated` | `b51e605c` | **MERGED/HISTORICAL** | PR #60. |
| `css-consol-cert-001` | `4deb7ec3` | **MERGED/HISTORICAL** | PR #61 merge commit is `d53e6658` on maintenance. |

## Additional notable refs (not deleted)

| Branch | Classification | Notes |
| --- | --- | --- |
| `css-unified-consolidation-2026-07-13` | **PRESERVE FOR REFERENCE** | Historical RC-001 / Gate 2 line. Freeze SHA `66e11d4f` is **not** current HEAD. Tip has since moved (`2dc58d8d`). |
| `css-agent-orchestration-v1` | **MERGED/HISTORICAL** | TAI-001 / PR #53. |
| `css-agent-dispatcher-v1` | **MERGED/HISTORICAL** | AOD-001 / PR #55. |
| `css-agent/access-check-92e6` | **STALE/SUPERSEDED** | PR #56 closed (empty access-check vs `main`). |
| `css-agent/dev-environment-setup-ef97` | **WRONG BASE** | PR #50 closed (`AGENTS.md` vs `main`; maintenance already has governance AGENTS.md). |
| `css-agent/healthchecker-plus-cursor-setup-a78b` | **WRONG BASE** / off-product | PR #51 closed (HealthChecker+ / foot-pain fixture pack vs `main`). |

## Default-branch decision (not executed)

**Recommendation: A. RETARGET DEFAULT TO `css-v1.0.1-maintenance`**

| Option | Risk | Effect on agent mistakes |
| --- | --- | --- |
| **A. Retarget default to maintenance** | Low: no history rewrite; `main` remains as a stale archive ref | **Best.** Clones and implicit base become canonical. |
| B. Merge maintenance into `main` first | High: huge merge onto Phase 113Y; forbidden in this package | Does not reduce confusion until complete; can pollute `main`. |
| C. Keep `main` as default with warning | Lowest operational change, **does not** stop wrong-base PRs | We already closed #50/#51/#52/#56 that targeted `main`. |

This package **did not** change the GitHub default branch (no authorized admin API action).

**Exact human/admin action:**

1. GitHub → `rasibor-cpu/capital-strata-systems` → Settings → General → Default branch.
2. Switch default from `main` to `css-v1.0.1-maintenance`.
3. Do **not** merge maintenance into `main` as part of that switch.
4. Protect `css-v1.0.1-maintenance` if not already protected.
5. Leave `main` in place as a historical ref until a later owner decision.

## Cleanup still forbidden here

- Do not delete any of the listed branches.
- Do not force-push.
- Do not merge `css-rc-live-001-candidate` wholesale.
- Do not fast-forward `main`.
