# Phase 176G — Universal Plain-English PDF Reporting Standard

**Baseline:** `31e5d11b5f58eb434a93594c5999dd52e220776c` (Phase 176F)
**Branch:** `css-unified-consolidation-2026-07-13`
**Status:** Implemented — **DO NOT COMMIT** until explicitly approved.
**Date:** 2026-07-18

## Universal PDF policy

Every report with status `AVAILABLE` or `AVAILABLE_WITH_LIMITATIONS` and a
registered producer:

- declares `primary_human_format = PDF`
- includes `HTML` and `PDF` in `supported_formats`
- sets `pdf_required=true`, `pdf_supported=true`, `pdf_status=SUPPORTED`
- binds a family `narrative_adapter`

JSON/CSV/Markdown remain technical exports only.

Do not claim PDF support without producing a real `%PDF` artifact.

## Shared renderer

`CSSReportPDFRenderer` (`backend/reports_center/pdf_renderer.py`) reuses the
Phase 175 minimal PDF writer via `build_text_pdf()`.

Daily Executive Brief FINAL PDFs remain served by the Phase 175 distribution
API (`/api/v1/executive-brief/{date}/pdf`). Reports Center bridges to that path.

## Narrative adapters

`backend/reports_center/narrative.py` maps categories to family adapters and
translates internal codes in the main body. Raw codes appear only under
**Technical appendix**.

## PDF failure policy

| Class | Behavior |
|-------|----------|
| Canonical archive | Always preserved when generation succeeds |
| Advisory reports | May remain FINAL with `printable_status=PARTIAL`, `pdf_status=FAILED` |
| Official reports (e.g. DEB) | PDF failure blocks distribution claim; canonical object preserved |
| UI | Shows PDF failed / unavailable — never labels HTML fallback as native PDF |

## Archive / manifest

```
.../vNNN/report.json
         report.html   # plain-English HTML
         report.pdf    # plain-English PDF
         manifest.json # includes pdf.{filename,size,sha256,generated_at_utc,renderer_version,narrative_adapter,page_count}
```

## RBAC

PDF download uses the same print authorization as printable HTML
(`required_print_permission` / `reports_print_all`). No client-side grants.

## Safety

Unchanged: `advisory_only=true`, `execution_allowed=false`,
`live_trading_blocked=true`, `broker_execution_armed=false`.

## Rollback

Revert Phase 176G files (pdf_renderer, narrative, definition/catalogue PDF
fields, archive PDF attach, service/routes/UI, tests, this doc). Phase 175 DEB
PDF remains independently intact.
