# Trader Passport UX specification

Original CSS design. The owner's benchmark screenshots set the interaction-quality bar only. No competitor artwork,
wording, layout or branding was copied, and no external fonts, images or icon sets are used.

## Visual system

- **Look:** dark, layered "strata" identity (the CSS mark is three stacked bands); navy surfaces, with teal (CSS),
  gold (your own trades), violet (modified) and coral (losses/attention).
- **Type:** the system UI font stack, rem-based throughout; headings scale with `clamp()`.
- **Layout:** one principal decision per screen; a fixed Back/Continue bar with 52px buttons; option cards at least
  48px tall.
- **Progress:** "Step x of N", where N counts only the steps visible for that user; group label; `role=progressbar`
  with `aria-valuetext`.
- **Responsive:** phone portrait first (≤48rem). Landscape phones shrink the illustrations. Tablets use two-column
  cards. Desktops (≥64rem) put the illustration beside the content, three-column Passport cards and four results tiles.

## Contrast (computed, WCAG 2.x)

| Token | on bg #0a1020 | on surface #141f3a | on surface-2 #1a2747 |
|---|---|---|---|
| text #eef3fb | 17.01 | 14.65 | 13.23 |
| muted #a9b6cf | 9.28 | 7.99 | 7.21 |
| teal #42d9b8 | 10.70 | 9.21 | 8.31 |
| gold #f4c25b | 11.48 | 9.88 | 8.92 |
| coral #ff8f7a | 8.54 | 7.35 | 6.64 |
| violet #a7a1ff | 8.29 | 7.14 | 6.45 |

Primary button ink on teal is 8.68:1. All pairings exceed AA (4.5:1).

## Accessibility

- One `h1` per step, focused on change.
- `fieldset`/`legend` groups; every input has a label.
- Errors are linked with `aria-describedby`, marked `aria-invalid`, announced in an `aria-live` region, and focus moves to
  the first error.
- Native radios and checkboxes stay keyboard-operable; the rank control is buttons with `aria-pressed` and position labels.
- Skip link; landmarks (header, main, nav); the scrollable table is a focusable labelled region.
- Scroll padding keeps focused controls clear of the fixed bar (WCAG 2.2 Focus Not Obscured).
- `prefers-reduced-motion` removes all animation and transitions. `forced-colors` support.
- Text scales to 200% without horizontal overflow (tested).
- axe-core 4.14 (WCAG 2.0/2.1 A/AA + best practice): **0 violations** on all 22 steps of the tested path, the "build my
  Passport" screen, the Passport and the results view (S24 emulation). The conditional Leverage and margin and Auto check steps are scanned on a second path.

## Content rules

- No earnings claims, income-replacement language, testimonials, user counts, scarcity, countdowns or rising-only
  charts (forbidden phrases are tested).
- The expectations illustration shows a range of outcomes including losses.
- The results view labels sample data as not real.
- The Passport always states it grants no execution authority and isn't legal acceptance.

## Illustrations

All are hand-authored SVG, created 2026-10-05 for this work, with no external sources (see `ARTIFACT_REGISTER.json`):
`css-mark`, `compass`, `toolkit`, `capacity_vs_tolerance`, `modes`, `range`, `two_ledgers`, `passport`.
Decorative images use `alt=""`; the results chart is an SVG with `role=img` and a label, plus a data table.

## Limits

S24 is emulated (360×780 CSS px, DPR 3, touch). No physical device was used. The UI hasn't been reviewed by a human
designer or by users.
