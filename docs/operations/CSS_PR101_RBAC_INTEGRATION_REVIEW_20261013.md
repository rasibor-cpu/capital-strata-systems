# CSS PR #101 RBAC Integration Review — 2026-10-13

**Status:** Read-only finding-only review. No merge, no cherry-pick, no branch modification.
**Reviewed PR:** [#101](https://github.com/rasibor-cpu/capital-strata-systems/pull/101) (`css-operator-auth-2026-09-28`, head `6160410f4a196a7ac188bc41a4d9c59a4278f85e`, base `css-commercial-collections-2026-09-19` @ `653b45c06c5769c4a6a2e7daf925966079966a1c`)
**Candidate compared:** `governance/cad20-cross-asset-pilot-closeout` @ [`54db2ce4c15bc3e1311c21481211824121565aa2`](https://github.com/rasibor-cpu/capital-strata-systems/commit/54db2ce4c15bc3e1311c21481211824121565aa2)

## Summary

PR #101's head is **not an ancestor of** the CAD-20 candidate (verified with
`git merge-base --is-ancestor 6160410f… 54db2ce4…` → NO). This review compares
the PR's **base→head** diff (`653b45c0… → 6160410f…`) against the candidate and
finds that the PR's new operator-auth files are absent from the candidate and
that `backend/security/permissions.py` has diverged. This is a confirmed
presence/absence gap for the *named files*; it does not prove the absence of
equivalent authorization logic implemented elsewhere under different filenames.

## Methodology

- The PR's base (`653b45c0…`) was identified so the base→head diff can be
  isolated separately from inherited changes.
- File presence was verified with `git cat-file -e <candidate>:<path>`.
- `backend/security/permissions.py` was diffed directly between the PR head
  and the candidate.
- `live_arm`/`live_toggle` mutation routes were searched for on the candidate.

## Verified evidence

### Files introduced by PR #101 that are absent from the candidate

The following operator-auth files exist at PR #101's head but do **not** exist
at the CAD-20 candidate:

- `backend/app/auth/auth_audit.py`
- `backend/app/auth/operator_login_router.py`
- `backend/app/auth/session_dependency.py`

### `backend/security/permissions.py` diverges

A direct diff of `permissions.py` between PR #101's head and the candidate shows:

- **PR #101 adds** a `COMMERCIAL_ROLE_GRANTS` block (roles `FINCON`, `HEAD_FINCON`, `AUDIT`, `HEAD_AUDIT`, `COMPLIANCE`, `HEAD_COMPLIANCE`) with maker-checker commercial-collections actions, and the `COMMERCIAL_VIEW_ACTIONS` / `COMMERCIAL_ACTIONS` frozensets.
- **The CAD-20 candidate adds instead** a different set of report/brief/print permissions on the existing `ADMIN` and `SUPER_USER` roles (`executive_brief_print`, `reports_view`, `transaction_ticket_print`, etc.).

Net diff: 28 insertions / 49 deletions. These are two **divergent RBAC extensions**, not the same work. (Note: the commercial-permissions block visible at the PR head may partly originate from the PR's *base* branch
`css-commercial-collections-2026-09-19`; that base was not separately diffed here.)

### `live_arm` / `live_toggle` mutation routes

On the CAD-20 candidate:

- `backend/app/ops/live_arm.py` exists (the two-key REA_LIVE_ARM/REA_CONFIRM_LIVE latch).
- `backend/app/security/live_toggle.py` exists.
- **No `live_arm`/`live_toggle` mutation routes were found under `dashboard/runtime/`, `dashboard/web/`, or `backend/app/main.py`** on the candidate (`git grep` returned no matches).

Whether PR #101 adds such mutation routes was not traced file-by-file; its
84-file list does not include `backend/app/ops/live_arm.py` or
`backend/app/security/live_toggle.py` directly, but it does modify
`dashboard/runtime/api_bridge.py` and `dashboard/web/web_app.py`, which could
reference them.

## Findings

| # | Finding | Severity | Evidence |
|---|---|---|---|
| 1 | PR #101's new operator-auth modules (`auth_audit.py`, `operator_login_router.py`, `session_dependency.py`) are absent from the CAD-20 candidate | Medium–High (RBAC gap; presence/absence only) | `git cat-file -e` confirmed absence |
| 2 | `permissions.py` has diverged: PR #101 adds the commercial-collections FINCON/HEAD_FINCON roles; the candidate adds different report/brief permissions | Medium (merge-conflict risk / RBAC divergence) | Direct diff, 28+/49- |
| 3 | No `live_arm`/`live_toggle` mutation routes were found on the candidate's dashboard surface — this is consistent with the safety posture, not a defect | Informational | `git grep` returned no matches |
| 4 | Content parity of the shared auth files (`auth_router.py`, `token_store.py`, `css_sign_on.py`, `mobile_app.py`) was not verified | Evidence gap | Only presence checked |
| 5 | Route/dependency/negative-test review of live-arm/live-toggle/order-submission entry points on the candidate was **not performed** | Evidence gap | Out of scope for this minimal review |

## Recommendation (NOT applied)

The CAD-20 pilot closeout cannot be considered a complete authorization-perimeter
deliverable while PR #101's operator-auth modules are absent and `permissions.py`
has diverged. Two paths are possible, both requiring separate owner approval:

1. **Rebase/merge PR #101** into the CAD-20 candidate after reconciling the `permissions.py` divergence (FINCON/HEAD_FINCON commercial roles vs report/brief permissions). This is a substantial change.
2. **Defer PR #101** to a separate post-pilot workstream, and document the operator-auth gap as an open blocker in the release-gate register (CSS-062).

## Scope boundary

This review did not:
- inspect the full 84-file base→head diff of PR #101;
- diff the PR's base branch (`css-commercial-collections-2026-09-19`) separately
  to isolate which commercial-permission changes originate there;
- verify content parity of shared auth files;
- check negative tests for live-arm/live-toggle/order-submission routes on the candidate;
- merge, cherry-pick, or modify any branch.

This is a **presence/absence and file-level divergence** review, not a complete
route-level authorization audit. A complete CSS-062 review remains open.
