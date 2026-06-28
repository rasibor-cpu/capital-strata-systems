# Capital Strata Systems (CSS)

# Canonical AI Coding Agent Instructions

Version 2.0
Status: CANONICAL

---

# Purpose

This document defines the mandatory operating rules for every AI coding agent contributing to Capital Strata Systems (CSS).

It applies equally to:

* ChatGPT
* Codex
* Gemini CLI
* Claude
* Cursor
* VS Code AI assistants
* Any future automated coding agent

This document is authoritative.

---

# Project Vision

Capital Strata Systems (CSS) is an institutional-grade autonomous multi-asset trading platform.

Its objectives are:

* Preserve capital
* Produce sustained compounded returns
* Operate autonomously
* Maintain institutional risk governance
* Remain deterministic
* Be completely auditable
* Fail safely under abnormal conditions

Every contribution shall improve one or more of these objectives.

---

# Canonical Repository

Repository

C:\rasib\source\capital-strata-systems

Primary Branch

css-evening-consolidation-2026-06-09

Never create alternative repositories.

Never introduce competing architectures.

---

# Development Philosophy

Agents SHALL:

* Extend existing components.
* Reuse existing services.
* Preserve architecture.
* Prefer composition over duplication.
* Fail closed.
* Maintain deterministic behaviour.
* Maintain backward compatibility whenever practical.
* Produce small logical commits.

Agents SHALL NOT:

* Replace canonical subsystems.
* Duplicate engines.
* Bypass governance.
* Disable safety controls.
* Introduce hidden state.
* Remove tests.
* Delete production logic without approval.

---

# Canonical Runtime Architecture

Market Data

↓

Signal Generation

↓

Strategy Intelligence

↓

Autonomous Decision Engine (ADE)

↓

Portfolio Optimizer

↓

Capital Governor

↓

Risk Governor

↓

Unified Trade Gate

↓

Broker Execution

↓

Runtime Supervisor

↓

Monitoring

↓

Dashboard

Every enhancement shall integrate into this architecture.

---

# Canonical CSS Components

Existing canonical components include:

* Strategy Ranking Engine
* Runtime Supervisor
* AntiBleedGuard
* Unified Trade Gate
* Risk Governor
* Portfolio Analytics
* Strategy Intelligence
* Dashboard
* Mobile Launcher
* Recovery Framework
* Broker Adapters
* Authentication
* Audit Logging

Agents shall extend these components whenever possible.

---

# Coding Standards

* Python 3.12
* Type hints where appropriate
* Clear logging
* Deterministic behaviour
* Small focused commits
* No dead code
* No commented-out production code
* No duplicated logic

---

# Testing Standards

Every implementation shall include:

* Unit tests
* Integration tests where appropriate
* Regression protection

Existing tests must continue to pass.

---

# Git Workflow

Before beginning:

* git status
* Confirm clean working tree
* Confirm correct branch
* Check for remote updates

After development:

* Review git diff
* Run tests
* Stage only intended files
* Commit logically
* Push only after verification

Never force-push unless explicitly authorized.

---

# Phase 129 Roadmap

Current direction:

Phase 129A
Autonomous Decision Engine Architecture

Phase 129B
Portfolio Optimizer

Phase 129C
Capital Allocation Engine

Phase 129D
Adaptive Learning Engine

Phase 129E
Executive Decision Logging

Future phases shall build on—not replace—the existing Strategy Intelligence Foundation.

---

# Agent Verification Checklist (Mandatory)

Every coding agent SHALL complete these steps before making changes.

## Repository Verification

* Verify repository location.
* Verify current branch.
* Run git status.
* Ensure clean working tree unless instructed otherwise.
* Check for incoming remote commits.

## Architecture Verification

* Read this document.
* Search the repository for existing implementations.
* Extend canonical modules.
* Avoid duplicate functionality.
* Preserve public interfaces.

## Development Verification

Before committing:

* Run relevant tests.
* Verify existing tests still pass.
* Review full git diff.
* Remove temporary code.
* Remove debugging statements.
* Remove unused imports.
* Add tests for new functionality.

## Governance Verification

Every implementation must preserve:

* Risk Governor
* Unified Trade Gate
* Runtime Supervisor
* AntiBleedGuard
* Recovery Framework
* Audit logging
* Deterministic execution
* Fail-closed behaviour

No implementation may weaken or bypass these controls without explicit approval.

## Git Verification

Before pushing:

* Review staged files.
* Confirm commit message quality.
* Confirm only intended files are included.
* Verify repository cleanliness.
* Push only after successful verification.

Never force-push unless explicitly authorized.

---

# Code Review Principles

Every change should answer:

* Is this extending existing architecture?
* Is this deterministic?
* Is it fully testable?
* Is it institutionally defensible?
* Is it easier to maintain?
* Does it reduce operational risk?

If any answer is "No", revise the implementation.

---

# Definition of Done

A task is complete only when:

* Code is implemented.
* Tests pass.
* Documentation is updated where appropriate.
* Logging is appropriate.
* Auditability is preserved.
* Repository is clean.
* Changes are committed.
* Changes are pushed.
* CSS has moved closer to institutional production readiness.

---

# Guiding Principle

Capital Strata Systems is not a collection of scripts.

It is an institutional autonomous trading platform.

Every contribution must make CSS:

* safer
* smarter
* more deterministic
* easier to audit
* easier to maintain
* more profitable through disciplined architecture rather than unnecessary complexity.
