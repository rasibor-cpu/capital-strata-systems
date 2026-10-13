# CSS CI Failure Diagnosis — 2026-10-13

**Status:** Read-only diagnosis. No code merged, no workflow dispatched.
**Audited commit:** `main` HEAD `df566eee3fa2aeee65925ebc26ac193c2221d27e`
**Affected workflow:** `.github/workflows/css_governance.yml`

## Verified finding

The latest three `css_governance.yml` runs on `main` all conclude `failure` with
zero test-step execution. GitHub's run view reports the cause directly:

> This run likely failed because of a workflow file issue.
> (Run `37266933353`, head SHA `df566eee3fa2aeee65925ebc26ac193c2221d27e`)

The workflow file at that SHA is malformed. Its `on:` block renders as:

```yaml
'on':
push:
branches:
- main
pull_request:

jobs:
```

Two YAML errors are visible:

1. **Missing indentation under `push:`** — `branches:` and `- main` are at the
   same indentation as `push:`, so `push:` becomes a scalar and the filter is
   invalid.
2. **`pull_request:` has no value** — it is a null mapping with no `branches:`
   filter, which combined with (1) makes the trigger structure undefined.

The result is that the `jobs.css-validation` never executes. This is a
**workflow-file defect**, not a test failure.

## Historical consistency

The five most recent `css_governance.yml` runs on `main` (from `gh run list`) are:

| Run ID | headSha | conclusion | event |
|---|---|---|---|
| `37266933353` | `df566eee…` | failure | push |
| `34767147770` | `df566eee…` | failure | push |
| `34270950560` | `df566eee…` | failure | push |
| `28731274576` | `faf1485d…` | failure | push |
| `27738418229` | `faf1485d…` | failure | push |

All five share the same conclusion. The older `faf1485d…` runs predate the
`QT-005` restructure, but the workflow file is malformed at both SHAs.

## What is NOT established

- Whether any specific Python test fails at `main` HEAD — the workflow never
  reaches a test step.
- Whether the AI Governance Sweep workflow (`.github/workflows/ai-governance-sweep.yml`)
  has the same defect at `main` HEAD. That workflow was inspected only on the
  CAD-20 candidate branch, where it is well-formed. Its `main`-HEAD state at
  `df566eee` was not individually re-verified during this audit.

## Proposed fix (NOT applied during this read-only audit)

Correct the YAML in `.github/workflows/css_governance.yml`:

```yaml
on:
  push:
    branches:
      - main
      - css-unified-consolidation-2026-07-13
  pull_request:
    branches:
      - main
      - css-unified-consolidation-2026-07-13
  workflow_dispatch:
```

This matches the structure that already exists on
`governance/cad20-cross-asset-pilot-closeout` @ `54db2ce4…`, where the
`css_governance.yml` is well-formed and would run if the branch matched its
filter. The CAD-20 branch is still excluded by its `on.push.branches` filter,
which is why the separate `css_candidate_pilot_ci.yml` (added on
`css-agent/paper-auth-cad-ci-rbac-2026-10-13`) covers it.

## Limitation

GitHub's "log not found" response prevented direct step-log retrieval; the
diagnosis is based on the workflow file at the audited SHA and GitHub's own
"workflow file issue" annotation. The exact failing line of the YAML parser is
not captured here.
