# Phase 70B – Legal Acceptance Framework Implementation

## Branch

phase70b-legal-acceptance

---

# Objective

Implement a legal-risk acceptance framework within the existing CSS authentication architecture.

The implementation must preserve all existing authentication, session, governance, and runtime behavior while introducing a controlled legal-acceptance workflow.

---

# PCNRASS Requirements

The following capabilities must remain fully operational and unchanged:

* existing console login
* existing GUI login
* existing RBAC
* existing lockout controls
* existing password ageing
* existing session persistence
* existing user management
* existing smoke tests

No regression is permitted.

---

# Allowed Files

Implementation work is restricted to:

* dashboard/auth/css_sign_on.py
* dashboard/auth/css_sign_on_smoke_test.py

Optional schema evolution only:

* data/users.json

No other production files may be modified.

---

# Forbidden Files

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
* accounting modules
* reporting modules
* intelligence modules

---

# Required Implementation

## Disclosure Version Authority

Add:

```python
CURRENT_LEGAL_DISCLOSURE_VERSION = "1.0"
```

This must be the single authority used for acceptance validation.

Future version changes must automatically trigger re-acceptance.

---

## User Record Extension

Support the following structure:

```json
{
  "legal_acceptance": {
    "accepted": false,
    "version": null,
    "accepted_at": null
  }
}
```

Requirements:

* backward compatible
* existing users load safely
* existing user data preserved
* no migration required

---

## Acceptance Verification Function

Implement:

```python
verify_or_collect_legal_acceptance()
```

Responsibilities:

* detect missing acceptance
* detect outdated acceptance version
* present acceptance workflow
* collect acceptance
* update user record
* persist acceptance

---

## Session Persistence

After successful acceptance:

Persist:

```json
{
  "legal_acceptance_version": "1.0",
  "legal_acceptance_required": false
}
```

alongside existing session metadata.

---

# Required Authentication Flow

```text
load_users()
        ↓
authenticate_credentials()
        ↓
verify_or_collect_legal_acceptance()
        ↓
save_users()
        ↓
persist_login_session()
        ↓
dashboard access
```

This flow must be implemented without altering existing authentication behavior.

---

# User Access Rules

Users with valid acceptance:

* dashboard access allowed
* existing permissions unchanged

Users without valid acceptance:

* acceptance workflow required
* access controlled according to policy
* acceptance recorded before session completion

---

# Testing Requirements

Add smoke-test coverage for:

### Accepted User

* login succeeds
* session persists
* acceptance metadata present

### Unaccepted User

* acceptance workflow triggered
* acceptance stored
* login completes

### Version Mismatch User

* re-acceptance required
* updated version stored
* login completes

---

# Success Criteria

Implementation is successful only if all of the following are true.

## Authentication Preservation

* existing console login works
* existing GUI login works
* existing RBAC works
* existing lockout controls work
* existing password ageing works
* existing session persistence works
* existing user management works

## Acceptance Behavior

* missing acceptance detected
* outdated acceptance detected
* acceptance captured
* acceptance stored
* acceptance version stored
* acceptance timestamp stored

## Session Persistence

Session metadata correctly records:

```json
{
  "legal_acceptance_version": "1.0",
  "legal_acceptance_required": false
}
```

after successful acceptance.

## Backward Compatibility

* existing users load safely
* no migration required
* no user data loss

## Non-Regression

No changes permitted to:

* broker behavior
* execution behavior
* runtime orchestration
* dashboard rendering
* profitability logic
* PnL logic
* replay systems
* event bus behavior

---

# Required Final Report

Codex must provide:

## Files Modified

List all files modified.

## Functions Added

List all functions added.

## Tests Added

List all tests added.

## Validation Results

Provide:

* test results
* smoke-test results
* compilation results

## PCNRASS Compliance Statement

Confirm:

* only approved files modified
* no forbidden files modified
* authentication preserved
* no runtime regression introduced

---

# Completion Standard

The assignment is not complete until:

* implementation is finished
* tests pass
* PCNRASS compliance is confirmed
* final report is produced
* no forbidden files are modified
