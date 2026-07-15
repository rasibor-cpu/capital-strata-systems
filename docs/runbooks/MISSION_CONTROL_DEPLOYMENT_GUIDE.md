# Mission Control Deployment Guide

## Purpose

Mission Control deploys as part of the existing CSS dashboard host.

## Deployment Checklist

- Use the approved branch and commit.
- Run Mission Control regression tests.
- Run dashboard, runtime, and broker regression tests.
- Run compile validation for Mission Control modules.
- Confirm no generated runtime reports are staged.
- Confirm the final certification document is present.

## Route Surface

Mission Control exposes read-only pages and GET-only API routes. Do not add
write-capable routes to the Mission Control router.

## Post-Deployment Validation

Open the Executive Overview, Runtime Operations, Broker Management, Users and
Governance, System Configuration, Audit and Explainability, and Certification
and Readiness pages. Confirm source, freshness, runtime id, and hash evidence
are present where applicable.
