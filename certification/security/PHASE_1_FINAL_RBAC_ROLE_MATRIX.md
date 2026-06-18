# Phase 1 Final RBAC Role Matrix

## Purpose

This artifact records the final Phase 1 RBAC role matrix for security and governance certification review. It is documentation-only and does not change authentication, authorization, runtime behavior, broker behavior, execution behavior, trading logic, dashboard behavior, credentials, thresholds, or risk logic.

## Repository Verification

| Item | Evidence |
| --- | --- |
| Target branch | `css-evening-consolidation-2026-06-09` |
| Evidence assembly HEAD | `a652ac31e756b87f08dd3aeecdb962d097a5a043` |
| Remote | `origin https://github.com/rasibor-cpu/capital-strata-systems.git` |
| Source references reviewed | `backend/security/permissions.py`; `backend/app/security/live_toggle.py`; `backend/app/security/access_control.py`; `engine/security/access_control.py`; `tests/test_live_toggle_rbac.py`; `tests/dashboard/test_permission_matrix.py` |

## RBAC Authority Summary

| Role | Certification Function | Trading Submission | Trade Approval | Live Execution Authority | User/Admin Authority | Audit Visibility | Certification Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `SUPER_USER` | Highest privileged operational/security role | Supported by permission engine and mobile control tests | Supported where explicit approval permissions exist | Requires `SUPER_USER` or explicit live permission, plus live-arm confirmation | Supported for mobile controls and user management | Supported | Captured for Phase 1; final reviewer acceptance required |
| `ADMIN` | User administration and operational support | Not a trading role | Not a trading approval role | Not live-authorized by role alone | User-management capabilities referenced | Supports reporting/audit visibility | Captured as admin role, not live execution authority |
| `TRADER` | Trade entry/submission role | Allowed to submit/place trades in non-live permission matrix | Not an approval authority by role alone | Denied unless explicit live execution permission is present and live-arm is confirmed | Not user-management authority | Limited by role | Captured; live denial covered by tests |
| `TREASURY` | Treasury trade/position role | Allowed for trading workflows in permission matrix | Not final approval authority by role alone | Denied unless explicit live execution permission is present and live-arm is confirmed | Not user-management authority | Position and scanner visibility referenced | Captured |
| `HEAD_TREASURY` | Treasury approval/supervision role | Allowed for trading workflows | `approve_trade` supported | Denied unless explicit live execution permission is present and live-arm is confirmed | Not user-management authority | Reporting/position visibility referenced | Captured |
| `AUDIT` | Audit review role | Denied for trade submission | Not trade approval authority | Not live-authorized | Not user-management authority | Audit logs and reports supported | Captured |
| `HEAD_AUDIT` | Senior audit review role | Not a trading role | Supports approval actions outside live execution authority | Not live-authorized | Not user-management authority | Audit logs, reports, user view supported | Captured |
| `RISK` | Risk review role | Not a trading role | Not trade approval authority | Not live-authorized | Not user-management authority | Risk/report visibility referenced | Captured |
| `HEAD_RISK` | Risk approval/supervision role | Not a trading role | Approval and limit override permissions referenced | Not live-authorized by role alone | Not user-management authority | Risk/report visibility referenced | Captured |
| `COMPLIANCE` | Compliance review role | Not a trading role | Not trade approval authority | Not live-authorized | Not user-management authority | Compliance/report visibility referenced | Captured |
| `HEAD_COMPLIANCE` | Compliance approval/supervision role | Not a trading role | Approval/override permissions referenced | Not live-authorized by role alone | Not user-management authority | Compliance/report visibility referenced | Captured |
| `TECH` | Technical support role | Not a trading role | Not trade approval authority | Not live-authorized | Not user-management authority | System log visibility referenced | Captured |
| `HEAD_TECH` | Technical supervision role | Not a trading role | Not trade approval authority | Not live-authorized by role alone | Not user-management authority | System log/report visibility referenced | Captured |
| `VIEWER` | Read-only viewer role | Denied for trade submission | Not approval authority | Not live-authorized | Not user-management authority | Report visibility only | Captured |

## Live Execution Boundary

| Control | Evidence | Certification Meaning |
| --- | --- | --- |
| Default engine mode blocks live execution | `backend/app/security/live_toggle.py`; `tests/test_live_toggle_rbac.py::test_live_toggle_blocks_test_mode_even_for_super_user` | Live execution is blocked in TEST mode even for privileged users. |
| Hardcoded user ID is not authority | `tests/test_live_toggle_rbac.py::test_hardcoded_user_id_is_no_longer_required`; `tests/test_live_toggle_rbac.py::test_unauthorized_user_is_blocked` | Role/permission authority replaces user-ID-only authorization. |
| Missing context fails closed | `tests/test_live_toggle_rbac.py::test_missing_context_fails_closed` | Lack of authenticated/audit context does not permit live execution. |
| Non-privileged role without live permission is denied | `tests/test_live_toggle_rbac.py::test_non_super_user_without_live_permission_is_blocked` | Trading role alone is not live execution authority. |
| Explicit live permission still requires live-arm | `backend/app/security/live_toggle.py`; `tests/test_live_toggle_rbac.py` | Authorization and live-arm are both required. |
| Live toggle does not set broker execution flags | `tests/test_live_toggle_rbac.py::test_live_toggle_does_not_enable_broker_execution_flag` | RBAC authorization does not mutate broker execution configuration. |

## Certification Result

| Gap | Prior Status | Phase 1 Closure Status | Remaining Need |
| --- | --- | --- | --- |
| GAP-SECURITY-002: Final RBAC matrix | Open | Captured by this artifact | Security/governance reviewer acceptance |
| GOV-GAP-003: RBAC role matrix | Open | Captured by this artifact | Governance reviewer acceptance |

## Recommendation

Accept this matrix as the Phase 1 RBAC evidence artifact for controlled PAPER-mode certification review. It does not approve production live trading. Production certification still requires legal/risk acceptance, approved broker read-only evidence, operations signoff, governance signoff, and Robert final approval.
