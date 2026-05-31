# CSS Market-Facing Companion App Specification

Date: 2026-05-13
Status: Queued specification only
Related system: Capital Strata Systems (CSS)
Working product names: CSS Pulse, CSS Sentinel, CSS Intelligence Hub

## 1. Product Purpose

The CSS market-facing companion app is a public or controlled-access product surface for marketing, investor education, client demonstrations, and lead generation. It is not the CSS trading engine and must not be treated as an operational execution console.

The companion app should communicate that CSS is a governance-first capital intelligence and execution-control ecosystem, not a simple trading bot. Its purpose is to:

- Market CSS with institutional positioning.
- Demonstrate governance intelligence and risk discipline.
- Support investor, partner, and client demos.
- Capture qualified leads and demo requests.
- Provide safe replay, sample, and demo views.
- Showcase auditability, operational controls, and market-state awareness.
- Protect proprietary execution logic, broker integrations, alpha logic, and private account data.

## 2. App Boundaries

The companion app must remain outside the CSS Core execution boundary.

It must not:

- Execute trades.
- Place, modify, cancel, approve, or route orders.
- Expose live broker credentials, tokens, account identifiers, or private balances.
- Expose alpha logic, proprietary decision rules, production scoring thresholds, or execution models.
- Allow public users to control CSS Core, runtime modes, broker selection, kill switches, or governance gates.
- Provide direct access to live account state unless explicitly sanitized and approved through a future governance process.

All public or demo views must be safe by design, with sample data or sanitized exported data only.

## 3. MVP Features

The MVP should focus on explaining CSS clearly and safely while demonstrating enough institutional depth to support serious conversations.

Required MVP features:

- Public landing page with clear CSS positioning.
- CSS value proposition section.
- Governance-first messaging and visual narrative.
- Market regime demo dashboard using sample or sanitized data.
- Risk posture demo showing exposure, drawdown, alerts, and guardrails.
- Replay/demo viewer showing safe trade-lifecycle examples without exposing decision logic.
- Auditability showcase explaining traceability from signal to governance decision to replay record.
- Lead capture/contact form.
- Investor/demo request page.
- Safe sample data mode for all demos.

MVP content should avoid claims of guaranteed returns, automated profit, secret signals, or retail-bot language.

## 4. Future Features

Future releases may include:

- Controlled-access client portal.
- Institutional demo workspace with curated sample scenarios.
- Subscription analytics packages.
- Advisory onboarding flows.
- AI-generated market commentary using approved public or sanitized data.
- CSS Sentinel risk alerts for watchlist-style market/risk intelligence.
- CSS Pulse intelligence feed for market regime, risk posture, and governance commentary.
- Downloadable investor packs, governance summaries, and sanitized audit reports.
- Demo scenario builder for non-production walkthroughs.

Any future integration with CSS Core must be explicitly approved, sanitized, read-only, and governed by a strict API boundary.

## 5. Architecture

CSS Core remains private and operationally isolated. The companion app consumes only sanitized, exported, delayed, synthetic, or demo data.

Architecture principles:

- CSS Core remains the private trading, governance, broker, accounting, and execution-control system.
- The companion app has no direct broker access.
- The companion app has no trading controls.
- The companion app has a separate deployment path from CSS Core.
- The companion app should not share runtime credentials with CSS Core.
- Demo data should be generated or exported through a controlled sanitization pipeline.
- A future API gateway may be considered only after strict sanitization, authentication, rate limiting, audit logging, and governance review.

Initial data sources should be:

- Static sample payloads.
- Sanitized replay exports.
- Sanitized dashboard snapshots.
- Synthetic market regime examples.
- Approved public market data where licensing permits.

## 6. Branding

Brand posture should be institutional, disciplined, and trust-centered.

Preferred language:

- Governance-first capital intelligence.
- Execution-control ecosystem.
- Risk-aware decision infrastructure.
- Audit-ready operating discipline.
- Controlled capital intelligence.
- Institutional visibility, traceability, and oversight.

Avoid:

- Get-rich-quick claims.
- Retail trading bot framing.
- Guaranteed profit language.
- Secret signal marketing.
- Overstated AI autonomy.
- Language implying public users can control live trading.

The working names should be evaluated as follows:

- CSS Pulse: strongest for market intelligence, awareness, and updates.
- CSS Sentinel: strongest for risk monitoring, alerting, and governance posture.
- CSS Intelligence Hub: strongest for institutional demos and broad product narrative.

## 7. Security And Governance

The companion app must follow a fail-closed security posture.

Requirements:

- Public demo data only unless an approved controlled-access mode is created.
- No secrets, tokens, broker credentials, private keys, account IDs, or private account data.
- No live execution path.
- No direct broker calls.
- No private production strategy parameters.
- No production account balances or positions unless fully sanitized and explicitly approved.
- Clear disclaimers that demonstrations are informational and not investment advice.
- Audit-safe messaging and screenshots.
- Lead forms must avoid collecting sensitive financial credentials.
- Any future authenticated portal must use separate identity, RBAC, logging, and session governance.

Security review must happen before any production deployment or CSS Core connectivity.

## 8. Suggested Tech Direction

Start with a lightweight web app and keep the implementation separate from CSS Core.

Recommended direction:

- Phase A through C can use static HTML/CSS or a minimal web app.
- A future React or Next.js build may be appropriate after wireframes and content direction are approved.
- CSS visual language can be reused carefully, but execution-console controls must not be reused in ways that imply live control.
- Implementation should live in a separate repository or a separate `/companion-app` directory only after explicit approval.
- Do not couple the companion app to CSS Core runtime imports.
- Do not reuse broker, execution, auth, or governance runtime modules directly.

The first technical artifact after this spec should be wireframes, not runtime integration.

## 9. Roadmap

Phase A: Product spec

- Define purpose, boundaries, positioning, MVP, and architecture.
- Confirm preferred product name and primary audience.

Phase B: Wireframes

- Create landing page, demo dashboard, replay viewer, and demo request page wireframes.
- Validate messaging and visual hierarchy before implementation.

Phase C: Static demo landing page

- Build a static, non-connected page using approved sample content.
- Include value proposition, governance positioning, and lead capture placeholder.

Phase D: Replay/demo dashboard

- Add safe replay and demo dashboard views using static or sanitized sample data.
- No CSS Core runtime dependency.

Phase E: Lead capture

- Add contact/demo request workflow through a safe form provider or controlled backend endpoint.
- Include consent, privacy, and anti-spam controls.

Phase F: Investor/demo portal

- Add controlled-access demo workspace if justified.
- Require separate auth, audit logging, and sanitized demo data pipeline.

## 10. Deliverables And Next Steps

Current deliverable:

- Specification document only.
- No implementation.
- No CSS Core runtime changes.

Recommended next steps:

- Choose the working product name for the first public concept.
- Define target audience priority: investors, institutional clients, advisory clients, or public brand awareness.
- Draft wireframes for the landing page, replay/demo dashboard, and investor/demo request page.
- Define approved sample datasets for public demo use.
- Create a companion-app build directive only after wireframes and data boundaries are approved.

Recommended commit message:

`docs: queue CSS market companion app product specification`
