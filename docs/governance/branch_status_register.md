# CSS Branch Status Register

Date: 2026-05-28
Scope: Branch hygiene / canonical-lineage clarification
Status: Non-destructive documentation only

## Purpose

This register records the current branch-status understanding for Capital Strata Systems (CSS) and prevents unsafe branch deletion, retargeting, or force movement while recent laptop/Codex lineage remains unverified.

## Current GitHub-visible baseline

| Item | Current status |
|---|---|
| Repository | rasibor-cpu/capital-strata-systems |
| GitHub default branch | main |
| Current working assumption | main is the GitHub-visible fallback baseline |
| Canonical latest-state certainty | Not yet fully confirmed |
| Destructive branch cleanup allowed | No |

## Important caution

Recent governance/audit artifacts discussed during the K8B scope-separation and lineage-reconstruction work were not confirmed visible on `main` through the current GitHub connector check. Therefore, `main` must be treated as the current GitHub-visible fallback branch, but not yet as the fully verified latest CSS state.

## Branch-cleanup rule

Until the laptop/Codex/local branch lineage is verified:

1. Do not delete branches.
2. Do not force-push branches.
3. Do not retarget pull requests casually.
4. Do not assume a Codex workspace commit exists on `main` unless verified.
5. Do not treat branch absence from a connector search as proof that a branch is obsolete.
6. Preserve FBL/PCNRASS rollback points.
7. Prefer documentation and comparison before cleanup.

## Required verification before deeper cleanup

When back on laptop or full Git environment, run:

```bash
git branch -vv
git branch -r
git status
git log --oneline --decorate --graph --all -n 40
git tag --list "*FBL*" "*PCNRASS*" "*K8*" "*baseline*"
```

Then classify each branch as:

| Classification | Meaning |
|---|---|
| CANONICAL | Current authoritative development line |
| FBL/ROLLBACK | Protected rollback baseline |
| ACTIVE-INTEGRATION | Current or recent integration branch |
| AUDIT/REMEDIATION | Branch used for audit or repair work |
| EXPERIMENTAL | Safe but non-canonical exploration |
| UNKNOWN | Do not delete until inspected |
| DEAD | Safe to delete only after explicit confirmation |

## Current PCNRASS conclusion

Branch cleanup should proceed only as a controlled safety exercise. The immediate objective is to identify the canonical branch and protect rollback points, not to make the repository cosmetically clean.

No destructive branch operation is authorized by this register.
