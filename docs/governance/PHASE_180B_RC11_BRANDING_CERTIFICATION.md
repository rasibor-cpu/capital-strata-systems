# Phase 180B — RC1.1 Branding Certification

## Certification status

**CERTIFIED FOR CONTROLLED DEPLOYMENT PREPARATION — GO**

The canonical branding implementation and bounded RC1 regression are verified.
Phase 180C.3 recovered the structurally corrupted `backend/app/main.py` from its
latest compiling historical base, preserved the legitimate read-only `/alerts`
route, and closed the compile gate. No service was restarted or deployed.

The runtime safety posture remains:

- `DISABLED`
- `BLOCKED`
- `FAIL_CLOSED`
- `ADVISORY_ONLY`

## Architecture

`backend.common.branding.CSSBrandService` is the single immutable authority for:

- the approved colour, monochrome, and watermark logo variants;
- favicon, Apple touch, 192 px, 512 px, and maskable assets;
- application and organization names;
- theme, background, surface, gold, platinum, and ink colours;
- PWA asset version `180a1` and versioned URLs;
- installable manifest generation;
- reusable HTML head metadata;
- report classification, confidentiality, header, footer, and watermark rules.

The service exposes only allow-listed assets. Presentation code resolves asset
paths and URLs by semantic keys; it does not construct filesystem paths.

## Phase 180A freeze

Phase 180A's approved source image, generated icon family, dimensions, visual
design, safe zone, and asset version were not changed. Static duplicate
manifests and the launcher wrapper SVG were removed from presentation authority.
The Brand Service now produces the manifests and supplies the approved PNG logo
directly.

Legacy favicon and static-icon HTTP routes remain as compatibility aliases, but
their files and media types resolve through the Brand Service.

## Brand Service consumers

The following active presentation boundaries now consume the canonical service:

- mobile FastAPI manifest, icon routes, PWA metadata, and service-worker asset list;
- desktop web manifest, icon routes, and reusable page head;
- launcher manifest, icon routes, landing page, and Jinja templates;
- enterprise shell and Mission Control home-brand rendering;
- mobile landing logo, names, and brand palette;
- paginated report builder and direct HTML rendering;
- shared one-page-at-a-time report viewer;
- Reports Center HTML/PDF renderer;
- Daily Executive Brief HTML/PDF renderer.

No trading, broker readiness, authentication, authorization, accounting, secret,
OAuth, or runtime authority was modified.

## Watermark architecture

The shared watermark standard is:

- approved canonical 512 px logo source;
- monochrome rendering;
- `0.055` HTML opacity;
- centered at 42% page width;
- proportional scaling with `object-fit: contain`;
- non-interactive and page-contained;
- print-colour adjustment enabled;
- behind report content through an isolated page stacking context.

The minimal PDF writer adds a centered, diagonal, low-contrast organization-name
watermark to each page before report text. It uses PDF drawing commands and does
not require network access, browser rendering, blocking I/O, or a new PDF
dependency.

## Executive document standard

Every canonical paginated document now carries a `branding` contract containing:

Header:

- Capital Strata Systems;
- report title;
- generation timestamp;
- classification.

Footer:

- current and total page number;
- document/report ID;
- runtime/CSS version;
- confidentiality banner.

The same contract is consumed by direct report HTML and the shared paginated
viewer. Reports Center and Daily Executive Brief PDF paths use the same
organization, confidentiality, and watermark authorities.

## Regression root causes and fixes

### Historical 22-failure set

The original 22-failure report was not reproducible at the start of Phase 180B.
The current focused baseline was green because the preceding verification work
had already corrected its grouped causes:

- report generation entering a readiness wait loop during viewer audit;
- templates comparing or formatting unavailable balance values as numbers;
- stale mobile-home and PWA asset assertions;
- inconsistent manifest and icon route declarations.

Phase 180B did not rewrite these subsystems.

### Report-render stall

Exact historical cause: the Daily Executive Brief report producer called the
executive orchestrator with readiness waiting enabled. The orchestrator slept in
its retry loop while report-viewer and catalogue audits expected a single-shot,
read-only producer.

The narrow correction already present on entry uses `persist=False` and
`wait_for_readiness=False`. Phase 180B verified this path through focused report
tests and the bounded RC1 suite. No recursive template, asset lookup, watermark,
service-worker, PDF, deadlock, or circular-import stall was observed.

### Phase 180B regression corrections

1. A Phase 177 financial-reporting UI test still required a human-facing card to
   expose a raw API endpoint. The implementation correctly used the RC1.1
   paginated viewer. The assertion was narrowed to require the human viewer URL
   and prohibit API links inside that card.
2. Initial launcher Brand Service migration used the mobile shell cache default.
   The launcher has a distinct certified shell cache contract. Manifest
   generation now accepts the launcher cache identifier while retaining one
   canonical manifest provider.

## Tests executed

- Focused changed-file compile: exit `0`.
- Phase 180B branding/PWA/launcher/report audit: `18 passed`.
- Report/PDF/viewer regression: `49 passed`.
- Launcher/mobile/PWA regression: `99 passed`.
- Balance and financial-reporting regression: `67 passed`.
- Bounded RC1 regression including Phase 180B: `205 passed`.

All test commands exited `0`. The only test warning is the existing Starlette
`TestClient` deprecation warning.

## Compile status

Full command:

`python -m compileall backend dashboard launcher tests -q`

Phase 180C.3 command:

`python -m compileall backend dashboard tests`

Result: exit `0`.

Targeted validation also passed:

- `python -m py_compile backend/app/main.py`: exit `0`;
- direct `backend.app.main` import: exit `0`;
- focused main/API recovery suite: `14 passed`;
- authoritative RC1.1 suite: `205 passed`.

## Performance impact

- Brand configuration is instantiated once as an in-process immutable singleton.
- Manifest and metadata generation are deterministic in-memory operations.
- Asset delivery remains `FileResponse` based and allow-listed.
- HTML watermark rendering uses one cached, versioned image per report page.
- PDF watermarking adds a small fixed drawing sequence per page.
- No blocking I/O, readiness wait, network request, or runtime activation was added.

## Backward compatibility

- Phase 180A asset version and approved files are unchanged.
- Existing favicon, Apple touch, and legacy static-icon aliases remain available.
- Existing report document fields remain intact; the branding field is additive.
- Existing PDF APIs remain compatible; watermark input is optional.
- Launcher and mobile start URLs retain their certified contracts.

## Files changed by Phase 180B

- `backend/common/branding/__init__.py`
- `backend/common/branding/models.py`
- `backend/common/branding/service.py`
- `backend/broker_reporting/page_layout.py`
- `backend/executive_intelligence/print_report.py`
- `backend/reports_center/pdf_renderer.py`
- `dashboard/enterprise_shell/mobile_landing.py`
- `dashboard/enterprise_shell/shell.py`
- `dashboard/mission_control/theme.py`
- `dashboard/mobile/mobile_app.py`
- `dashboard/reports_viewer/paginated_viewer.py`
- `dashboard/web/web_app.py`
- `launcher/css_mobile_launcher.py`
- `launcher/templates/mobile_dashboard.html`
- `launcher/templates/mobile_launcher.html`
- `tests/test_css_icon_pwa_assets.py`
- `tests/test_css_mobile_launcher.py`
- `tests/test_phase177_financial_reporting.py`
- `tests/test_phase180a_mobile_pwa_icon_remediation.py`
- `tests/test_phase180b_branding_certification.py`

Duplicate static manifest and launcher wrapper assets ceased to be canonical
inputs; the repository status determines whether their removal is represented
as a deletion or as removal of prior untracked work.

## Deployment recommendation

**GO for controlled commit, push, and Desktop pull preparation.**

Desktop deployment remains operator-controlled. Pull and validation may proceed
only after the accepted commit is pushed; this certification does not authorize
a service restart or any live execution capability.
