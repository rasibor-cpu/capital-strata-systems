# CSS Legacy Archive Hygiene Recommendations

## Purpose

This document identifies legacy/archive folders that should remain untouched during Phase 151 but should be moved to an archive branch after final review.

## Archive Candidates

- `CSS-CLAUDE/`
- `css-gemini/`
- `chatgpt_legacy_backup/`
- `archive/dashboard_versions/`

## Production Import Assessment

Phase 151 checked active code/test/runtime roots for references to these archive paths. No production runtime imports from these folders were identified.

The only active-root reference found was `pytest.ini`, which lists `css-gemini` as an ignored collection path. Historical documentation and evidence files reference these folders for audit context only.

## Recommendation

Do not delete these folders in the live-readiness branch. After Phase 151 review, create an archive branch or repository tag containing these folders, then remove them from the production branch through a dedicated repository hygiene change with:

- before/after import scan evidence
- pytest collection evidence
- production launcher smoke evidence
- explicit rollback path

## Live Validation Boundary

Live broker validation, Live micro-pilot, and Production operational certification remain separate from archive hygiene.

Archive hygiene should not block engineering-complete review if no active production imports exist. It must be closed before production operational certification if repository size, scanner noise, or authority ambiguity remains material.
