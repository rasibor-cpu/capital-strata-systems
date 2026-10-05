# PAPS-001 — Project Artifact Preservation Standard

**Status:** Approved portfolio-wide governance standard  
**Applies to:** This repository and all project work performed by human or AI contributors.

## Purpose

Prevent completed work from becoming undiscoverable, being mistakenly declared missing, or being unnecessarily regenerated.

## Canonical-record rule

Work is not considered complete until every retained artifact is:

1. stored in its designated canonical project-repository location, or, where repository storage is prohibited or unsuitable, recorded in a repository manifest that identifies the approved secure external location;
2. entered in the applicable artifact/provenance manifest;
3. associated with the relevant project/version/work item;
4. committed on the authorized branch; and
5. pushed to the canonical remote repository.

An artifact that was generated but has not completed this chain must be reported as **GENERATED — NOT PRESERVED**, not **COMPLETED**.

## Covered artifacts

This standard applies to source code and ancillary work, including artwork, images, icons, audio, video, presenter assets, prompts, scripts, workbooks, manuscripts, PDFs/DOCX files, reports, screenshots, test evidence, QA evidence, manifests, generated game assets, build/release evidence intended for retention, and similar project materials.

## Repository structure

Use clearly named canonical directories appropriate to the project, including where relevant:

- `art/`
- `audio/`
- `video/`
- `docs/`
- `prompts/`
- `manifests/`
- `qa/`
- `evidence/`
- `reports/`
- project-specific asset directories

Do not create empty directories merely for conformity. Use the structure that fits the project while keeping retained artifacts discoverable.

## External generation services

External AI and media services are generation tools, not systems of record.

Artifacts created with external services must be preserved in the canonical repository before the associated task is considered complete.

Where relevant, the manifest must record:

- artifact ID/name;
- purpose;
- repository path;
- project/component;
- source/generator;
- model/tool where known;
- generation date;
- prompt or prompt reference where appropriate;
- rights/licensing status;
- approval/review status;
- superseded/replacement relationship;
- applicable version/release/work item.

## Search-before-regenerate rule

No contributor may declare an artifact genuinely missing or regenerate it merely because it is not immediately visible.

Before declaring an artifact missing, check, as applicable:

1. canonical asset directories;
2. artifact/provenance manifests;
3. relevant repository branches and history;
4. embedded assets in canonical documents/packages;
5. documented external staging locations.

Only after this reconciliation may the status become **GENUINELY MISSING**.

## Versioning and replacement

Do not silently overwrite approved or historically significant assets when preservation matters.

Use versioning, archival paths, or manifest relationships so that draft, approved, superseded, and production assets can be distinguished.

## Sensitive, licensed, secret, or oversized material

Do not force material into Git when repository storage would be unsafe, unlawful, contractually prohibited, or technically inappropriate.

Examples include credentials, secrets, PHI, restricted licensed source material, and unsuitable large binaries.

Instead:

- store the material only in an approved secure location;
- keep secrets and PHI out of repository history;
- add a non-sensitive manifest/provenance record when appropriate;
- identify the approved storage location without exposing protected information.

## Start-of-tranche requirement

Before new production work begins, contributors must inventory the relevant canonical repository locations and manifests sufficiently to avoid duplicating existing work.

## End-of-tranche artifact reconciliation

Every work tranche must finish with an artifact reconciliation:

**generated → stored → manifested → committed → pushed**

Report exceptions explicitly.

## Completion statuses

Use these statuses consistently:

- **COMPLETED — PRESERVED**
- **GENERATED — NOT PRESERVED**
- **EXISTING — NEEDS REVIEW**
- **APPROVED**
- **SUPERSEDED / ARCHIVED**
- **GENUINELY MISSING**
- **EXTERNAL SECURE STORAGE — MANIFESTED**
- **BLOCKED**

## Repository inventory

Maintain a machine-readable project inventory that maps important information sources and artifacts to their canonical locations, provenance, status, and ownership/review state.

The inventory must be reconciled against the full repository before regeneration or major release decisions.

## Enforcement

PAPS-001 is a release/readiness and project-reporting control.

A claimed accomplishment without a preserved canonical artifact or an approved manifested external-storage exception must not be reported as fully complete.
