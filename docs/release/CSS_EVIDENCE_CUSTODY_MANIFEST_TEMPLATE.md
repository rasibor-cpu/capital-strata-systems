# CSS Evidence Custody Manifest Template

**Remediation:** AR-002  
**Use:** Copy this template for every Class B certification artefact.

```text
evidence_id:           CSS-EVD-YYYYMMDD-NNN
title:                 <short title>
remediation_ids:       AR-XXX
audit_refs:            Master Audit §X / RB-XXX
gate:                  Release Gate 2
git_branch:            css-unified-consolidation-2026-07-13
git_sha:               <full sha from git rev-parse HEAD>
worktree_state:        CLEAN | INVENTORIED
worktree_inventory:    <relative path or N/A>
command:               <exact command line>
exit_code:             <integer>
started_at_utc:        YYYY-MM-DDTHH:MM:SSZ
finished_at_utc:       YYYY-MM-DDTHH:MM:SSZ
operator_role:         R-QA | R-OPS | R-CERT | ...
approver_role:         R-CERT | R-EXEC | N/A
artifact_path:         <path to primary output>
artifact_sha256:       <hash>
related_paths:         <comma-separated repo paths>
notes:                 <optional>
```

## Worktree inventory (when INVENTORIED)

Attach a file containing:

```text
inventory_id:   CSS-WTI-YYYYMMDD-NNN
git_sha:        <full sha>
captured_at:    <ISO-8601>
command:        git status --short
entries:
  M <path>
  ?? <path>
  ...
disposition:
  <path>: INCLUDE_IN_CANDIDATE | EXCLUDE_FROM_CLAIM | DEFER_TO_AR-XXX
```

Untracked `.venv/`, `__pycache__/`, and credential files must be marked `EXCLUDE_FROM_CLAIM`.
