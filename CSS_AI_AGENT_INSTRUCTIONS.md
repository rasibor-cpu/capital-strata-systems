# Capital Strata Systems (CSS) – Canonical AI Coding Agent Instructions

## Purpose

This document defines the mandatory operating rules for any AI coding agent (ChatGPT, Codex, Gemini CLI, Claude, Cursor, or similar) contributing to Capital Strata Systems (CSS).

These instructions are authoritative. Agents must preserve the existing architecture and extend it rather than replacing it.

---

# Repository

Canonical repository:

```
C:\rasib\source\capital-strata-systems
```

Primary branch:

```
css-evening-consolidation-2026-06-09
```

Never create alternative architectures.

Never rewrite working subsystems without explicit approval.

---

# Development Philosophy

CSS is an institutional-grade autonomous multi-asset trading platform.

The objectives are:

* capital preservation
* sustained compounded returns
* autonomous operation
* institutional governance
* deterministic behaviour
* complete auditability
* fail-safe execution

Every change must improve one or more of these objectives.

---

# Architectural Principles

Agents SHALL:

* extend existing modules
* reuse existing services
* preserve public interfaces whenever possible
* write deterministic code
* prefer composition over duplication
* fail closed rather than fail open
* maintain backward compatibility unless instructed otherwise

Agents SHALL NOT:

* duplicate existing engines
* bypass risk controls
* replace canonical modules
* introduce hidden state
* disable existing tests
* delete existing governance logic

---

# Canonical Runtime Pipeline

Market Data

↓

Signal Generation

↓

Strategy Intelligence

↓

Autonomous Decision Engine (ADE)

↓

Risk Governor

↓

Unified Trade Gate

↓

Broker Execution

↓

Runtime Supervisor

↓

Monitoring / Dashboard

---

# Existing Canonical Components

Examples include:

* Strategy Ranking Engine
* Runtime Supervisor
* AntiBleedGuard
* Unified Trade Gate
* Risk Governor
* Portfolio Analytics
* Mobile Launcher
* Dashboard
* Recovery Framework
* Broker Adapters

Agents should integrate with these components rather than introducing parallel implementations.

---

# Coding Standards

* Python 3.12
* Type hints where practical
* Small focused commits
* Comprehensive unit tests
* Clear logging
* No dead code
* No commented-out production logic

---

# Testing Requirements

Before considering work complete:

* Existing tests must continue to pass.
* New functionality must include tests.
* Existing behaviour must remain unchanged unless explicitly requested.

---

# Git Workflow

Before starting:

* git status
* confirm clean working tree

After changes:

* run relevant tests
* inspect git diff
* commit logically
* push only after verification

Never force-push unless explicitly instructed.

---

# Phase 129+

Phase 129 introduces institutional strategy intelligence.

Future work shall build on:

* Strategy Intelligence
* Autonomous Decision Engine
* Portfolio Optimizer
* Capital Allocation
* Adaptive Learning
* Regime Detection
* Executive Decision Logging

These are extensions—not replacements—of the existing CSS architecture.

---

# Success Criteria

Every contribution should leave CSS:

* safer
* more deterministic
* better tested
* easier to audit
* more maintainable
* closer to institutional production readiness
