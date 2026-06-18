# Phase 70B – Legal Acceptance Framework Implementation

## Branch

phase70b-legal-acceptance

## Objective

Implement a legal-risk acceptance framework within the existing CSS authentication architecture.

## PCNRASS Requirements

Preserve:

* existing login
* existing GUI login
* existing console login
* existing RBAC
* existing lockout controls
* existing password ageing
* existing session persistence
* existing user management
* existing smoke tests

No regression permitted.

## Allowed Files

* dashboard/auth/css_sign_on.py
* dashboard/auth/css_sign_on_smoke_test.py

Optional schema evolution only:

* data/users.json

## Forbidden Files

Do not modify:

* broker adapters
* execution engines
* runtime orchestration
* dashboard rendering
* profitability engines
* PnL engines
* replay systems
* event bus
* governance modules

## Required Implementation

### Disclosure Version Authority

Add:

```python
CURRENT_LEGAL_DISCLOSURE_VERSION = "1.0"
```

### User Record Extension

Support:

```json
{
  "legal_acceptance": {
    "accepted": false,
    "version": null,
    "accepted_at": null
  }
}
```

Must remain backward compatible.

### Acceptance Verification

Implement:

```python
verify_or_collect_legal_acceptance()
```

Responsibilities:

* detect missing acceptance
* detect version mismatch
* collect acceptance
* update user record
* save user record

### Session Persistence

Persist:

```json
{
  "legal_acceptance_version": "1.0",
  "legal_acceptance_required": false
}
```

### Required Flow

authenticate_credentials()
→ verify_or_collect_legal_acceptance()
→ save_users()
→ persist_login_session()
→ dashboard access

## Tests Required

Cover:

* accepted user
* unaccepted user
* version mismatch user

## Success Criteria

* existing authentication preserved
*
