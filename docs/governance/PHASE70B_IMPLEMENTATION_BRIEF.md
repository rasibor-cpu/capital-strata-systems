# Phase 70B – Legal Acceptance Framework Implementation Brief

## Objective

Implement a legal-risk acceptance framework within the existing CSS authentication system while preserving all existing authentication, session, RBAC, governance, and runtime behavior.

## PCNRASS Constraints

Allowed files:

* dashboard/auth/css_sign_on.py
* dashboard/auth/css_sign_on_smoke_test.py

Optional schema evolution:

* data/users.json

Forbidden changes:

* Broker adapters
* Runtime orchestration
* Execution engines
* Dashboard rendering
* PnL engines
* Profitability engines
* Cost engines
* Replay systems
* Event bus
* Governance framework

## Required Features

### Disclosure Version Authority

```python
CURRENT_LEGAL_DISCLOSURE_VERSION = "1.0"
```

### User Record Extension

Backward-compatible support for:

```json
{
  "legal_acceptance": {
    "accepted": false,
    "version": null,
    "accepted_at": null
  }
}
```

### Acceptance Verification

New authentication-stage function:

```python
verify_or_collect_legal_acceptance()
```

Responsibilities:

* Detect missing acceptance.
* Detect disclosure version mismatch.
* Record acceptance.
* Preserve existing login flow.

### Session Metadata

Persist:

```json
{
  "legal_acceptance_version": "1.0",
  "legal_acceptance_required": false
}
```

### Tests

Cover:

* Accepted user
* Unaccepted user
* Version mismatch user

## Required Flow

authenticate_credentials()
→ verify_or_collect_legal_acceptance()
→ save_users()
→ persist_login_session()
→ dashboard access

## Success Criteria

* Existing authentication behavior preserved.
* Existing RBAC preserved.
* Existing session persistence preserved.
* Existing password ageing preserved.
* Existing lockout controls preserved.
* No runtime, broker, execution, or dashboard regressions.
