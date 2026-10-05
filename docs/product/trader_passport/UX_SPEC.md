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
  cards and option grids. Desktops (≥64rem) put a sticky illustration beside the content, limit question width to
  44rem, show three-column Passport cards and align the action bar to the right.

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
  Passport" screen, the Passport, the results view, the attribution education screen and the error summary
  (S24 emulation). The conditional Leverage and margin and Auto check steps are scanned on a second path.
- Phase 2: a real `<form>`, so Enter submits a step; a linked error summary when a step has more than one error;
  per-question "Why we ask" disclosure; resume banner announced with `role=status`.

## Content rules

- No earnings claims, income-replacement language, testimonials, user counts, scarcity, countdowns or rising-only
  charts (forbidden phrases are tested).
- The expectations illustration shows a range of outcomes including losses.
- The results view labels sample data as not real.
- The Passport always states it grants no execution authority and isn't legal acceptance.

## Illustrations

All are hand-authored SVG, created 2026-10-05 for this work, with no external sources (see `ARTIFACT_REGISTER.json`):
`css-mark`, `compass`, `toolkit`, `capacity_vs_tolerance`, `modes`, `range`, `two_ledgers`, `passport`, and in phase 2
`two_paths` (CSS idea vs your idea → the dashboard's CSS / your own / combined split).
Decorative images use `alt=""`; the results chart is an SVG with `role=img` and a label, plus a data table.

## Phase 2 UX review (before → after)

Reviewed from the phase-1 screenshots (`evidence/phase1_before/`). New captures are in `evidence/phase2_after/`.

| Area | Before (phase 1) | After (phase 2) |
|---|---|---|
| Hierarchy | Welcome was a block of paragraphs; mode explanations were buried in prose | Interstitials use `points` cards (icon, title, one line) and a highlighted callout for the risk statement |
| Whitespace / measure | Desktop questions stretched across 64rem; the action button spanned the full width | Questions capped at 44rem; the primary button is right-aligned with a fixed minimum width on tablet and desktop |
| Typography | Option detail and help text competed with prompts | Help, "Why we ask" and errors have distinct size, weight and colour roles |
| Touch targets | ≥44px everywhere (tested) | Unchanged, and extended to the rank "Clear" and error-summary links (≥44px) |
| Progress | Step count only | Step count plus group in `aria-valuetext`; "Got it, continue" on explanation screens |
| Selected states | Teal border and tick | Unchanged (passed review); the rank shows "n of 3 chosen" and has a Clear control |
| Illustrations | No visual for attribution | `two_paths.svg`: CSS idea vs your idea → CSS / your own / combined results |
| Conditional questions | Shown without explanation | Each question's "Why we ask" says, for leverage, that it appears only because the answers involve leveraged markets |
| Keyboard | Enter did nothing; Continue had to be clicked | Real form: Enter submits from any field (tested) |
| Fixed-button obstruction | Scroll padding only | Unchanged scroll padding; the inline error now sits directly under its control |
| Errors | Inline errors only; with several errors, the user had to scroll to find each one | Linked error summary (several errors), inline error placed before "Why we ask", focus on the first invalid control |
| Back / resume | Silent resume | "Welcome back" banner with step x of N; "Reviewing your answers" banner when editing a completed Passport |
| Repetition | "(optional)" appeared twice where the prompt already said it | Shown once |
| Final Passport | List of cards with LOW/MODERATE meters and raw question ids under "Why?" | Six dimensions with Foundation/Developing/Experienced scales; strengths tagged by source; areas to develop; starting mode; risk; markets and engagement; learning plan; "Why?" lists the question prompt and answer; authority and suitability statements first |
| Results view | Four equal tiles | Three headline numbers (CSS-attributable, independent, combined) plus the four-origin chart and table, with a no-guarantee / responsibility statement |

Known limitation: full-page screenshots capture the fixed action bar at its viewport position, so in long captures
it appears over mid-page content. On a device it stays pinned to the bottom of the screen.

## Limits

S24 is emulated (360×780 CSS px, DPR 3, touch). No physical device was used. The UI hasn't been reviewed by a human
designer or by users.
