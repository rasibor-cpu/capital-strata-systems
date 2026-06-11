# PHASE 85 — OPTIONS GREEKS DATA MODEL IMPLEMENTATION

## Executive Summary

Phase 85 implements the canonical Options Greeks data model defined by:

* PHASE80_OPTIONS_GREEKS_FRAMEWORK
* PHASE83_OPTIONS_GREEKS_IMPLEMENTATION_ROADMAP
* PHASE84_ENTERPRISE_TRADING_CAPABILITY_MATRIX

This phase introduces the foundational data structures required to support future options risk analytics, portfolio Greeks aggregation, strategy classification, and volatility intelligence.

This phase is intentionally limited to data model implementation.

No dashboard rendering changes are included.

No broker adapter changes are included.

No Black-Scholes calculations are included.

No live-trading permissions are expanded.

---

# Objective

Implement a canonical Greeks storage model that:

* supports options positions
* supports future portfolio aggregation
* preserves backward compatibility
* survives serialization and restoration
* remains broker-independent

---

# Canonical Greeks Structure

Required structure:

```python
{
    "delta": None,
    "gamma": None,
    "theta": None,
    "vega": None,
    "rho": None,
    "greeks_source": "UNKNOWN"
}
```

---

# Critical Rules

## Rule 1

Unknown Greeks must be:

```python
None
```

Not:

```python
0.0
```

Reason:

0.0 implies a calculated value.

None explicitly means unavailable.

---

## Rule 2

Valid Greeks sources:

```text
BROKER
MARKET_DATA
BLACK_SCHOLES
UNKNOWN
```

Any invalid value must normalize to:

```text
UNKNOWN
```

---

## Rule 3

Fail Closed

Missing Greeks data must not generate synthetic values.

If Greeks unavailable:

```python
{
    "delta": None,
    "gamma": None,
    "theta": None,
    "vega": None,
    "rho": None,
    "greeks_source": "UNKNOWN"
}
```

---

# Implementation Scope

## Required

### Canonical Helper

Create helper functions such as:

```python
default_option_greeks()

normalize_option_greeks()

attach_default_greeks_to_option_position()
```

Exact naming may vary.

---

### Options Position Integration

New options positions must support:

```python
delta
gamma
theta
vega
rho
greeks_source
```

---

### Legacy Position Compatibility

Existing option positions lacking Greeks must not fail.

Normalization must attach default Greeks structure.

---

### Serialization

Greeks fields must survive:

* save
* restore
* runtime persistence
* audit persistence

---

# Explicit Non-Scope

Do NOT implement:

* Dashboard Greeks
* Portfolio Greeks
* Greeks alerts
* Black-Scholes
* Volatility Alpha
* Strategy Classification
* Broker Greeks
* Market-data Greeks

These belong to later phases.

---

# Testing Requirements

Required tests:

## Test 1

New option position receives default Greeks.

---

## Test 2

Legacy option position normalizes correctly.

---

## Test 3

Non-options positions remain unchanged.

---

## Test 4

Serialization preserves Greeks.

---

## Test 5

UNKNOWN uses None values.

---

## Test 6

Invalid source normalizes to UNKNOWN.

---

## Test 7

Valid source values remain unchanged.

---

# Expected File Areas

Potential impact areas:

```text
engine/
backend/
positions/
accounting/
serialization/
tests/
```

Actual files depend on authoritative position architecture.

---

# Safety Requirements

Must preserve:

* PAPER/LIVE separation
* Broker authority controls
* Real balance authority controls
* Trade gates
* Capital governor protections

No trading behavior changes permitted.

---

# Deliverables

1. Canonical Greeks data model.
2. Position integration.
3. Backward compatibility support.
4. Serialization support.
5. Automated tests.
6. Implementation report.

---

# Commit Message

```text
Implement Phase 85 options Greeks data model
```

---

# Codex Delivery Requirements

Required reporting:

* Workspace verification
* Branch verification
* HEAD before changes
* Files changed
* Test results
* Commit hash
* Exact push result

Task is not complete unless push succeeds.

Robert must review before merge.

---

# Closeout Criteria

Phase 85 is complete when:

* Greeks fields exist in options positions.
* Legacy positions remain functional.
* Serialization preserves Greeks.
* Tests pass.
* Changes are committed and pushed to:

css-evening-consolidation-2026-06-09

STATUS: APPROVED FOR IMPLEMENTATION
