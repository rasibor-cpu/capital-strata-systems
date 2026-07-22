# CSS Version 1.0 Release Notes

> **AMENDED — AR-001 (2026-07-21)**  
> Active release posture is defined by `docs/release/CSS_CANONICAL_RELEASE_STATUS.md`.  
> Production certification is currently **NOT CERTIFIED**. Controlled paper remains GO.

## Release Type

Version 1.0 is an engineering-completion release candidate for Capital Strata Systems. It is not a production live-trading approval.

## Engineering Highlights

- Completed dashboard ecosystem coverage across desktop, web, mobile, and launcher surfaces.
- Restored risk-aware top opportunity display, compact trade summary, Session Command Centre, and advanced intelligence visibility.
- Preserved canonical runtime data preference with explicit unavailable states when canonical evidence is absent.
- Maintained adaptive intelligence as advisory, governed, and fail-closed.
- Maintained institutional portfolio management as advisory and governed.
- Preserved live-mode safeguards across Unified Trade Gate, Margin Gate, RBAC, Capital Governor, AntiBleedGuard, kill switches, emergency stops, broker validation, and execution authorization.
- Certified full pytest collection and regression execution as the required Version 1 engineering evidence.

## Known Production Boundary

**Amended (AR-001):** Production deployment is **not** limited to the three items below. The Master Completion Audit and Release Gate 2 register identify additional Critical blockers (synthetic execution acceptance, lifecycle integrity, health fail-open scoring, institutional catalogue honesty, notifications, CI/CD, endurance/DR evidence, release-authority reconciliation, and others).

Historical wording retained for traceability only:

1. Live broker validation
2. Live micro-pilot
3. Production operational certification

Authoritative remaining work: `CSS_V1_MASTER_COMPLETION_AUDIT.md` and `docs/release/CSS_AUDIT_REMEDIATION_REGISTER.md`.

## Safety Notice

This release must not be used to infer live broker readiness. LIVE mode remains fail-closed without explicit live validation and production approval.

