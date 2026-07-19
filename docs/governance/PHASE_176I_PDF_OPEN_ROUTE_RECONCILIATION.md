# Phase 176I — PDF Open Route Reconciliation

**Branch:** `css-unified-consolidation-2026-07-13`

## Defect

Android (and any client) opening “Open PDF” could land on
`GET /mission-control/api/reports/{id}/pdf`, which returned **metadata JSON**
(`pdf_status`, `pdf_available`, `pdf_endpoint`) instead of PDF bytes.

## Remediation

- Mission Control **Open PDF** `<a>` → only `GET /api/v1/reports/{id}/pdf`
- Mobile **Open PDF** → same canonical href (unchanged path; marker added)
- MC legacy `/mission-control/api/reports/{id}/pdf` → **307 redirect** to canonical PDF
- Metadata moved to `/mission-control/api/reports/{id}/pdf-info` (“PDF status”)
- Canonical route headers: `Content-Type: application/pdf`,
  `Content-Disposition: inline`

No JavaScript navigation / `preventDefault` / `location.assign` for PDF open.
