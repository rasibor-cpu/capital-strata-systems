# CSS Mission Control — Samsung S24 Physical UAT

Status: OPEN — REQUIRED FOR MOBILE UAT CLOSURE  
Device target: Samsung Galaxy S24 Ultra  
Scope: CSS Mission Control mobile shell and all operator-facing Mission Control pages  
Authority: Physical-device acceptance only. This document does not authorize trading, deployment, broker mutation, or execution.

## 1. Closure Rule

Mission Control mobile UAT MUST NOT be marked complete until the Samsung S24 Ultra has passed the physical-device checks below.

Automated responsive tests, desktop browser emulation, and terminal-rendered HTML are supporting evidence only. They do not substitute for physical-device validation.

## 2. Safety Preconditions

Before testing:

- Runtime remains DISABLED or approved read-only mode.
- Execution remains BLOCKED.
- Broker execution remains unarmed.
- Mission Control remains advisory/read-only.
- No credential values, API keys, tokens, secrets, full account identifiers, or private material may appear.
- Testing must not submit, cancel, modify, or simulate a live broker order through an execution-capable path.

## 3. S24 Connection

The launcher PC and S24 should be on the same trusted LAN.

Start the launcher using the canonical entry point:

```powershell
python -m launcher.css_mobile_launcher
```

The launcher must listen on a LAN-reachable interface. Determine the PC IPv4 address and browse from the S24 to:

```text
http://<PC-IP>:8765/mobile-launcher
```

Do not use `127.0.0.1` from the phone; that address refers to the phone itself.

## 4. Device-Level Acceptance Checks

For each test, record PASS / FAIL / BLOCKED and a short note.

| ID | Check | Acceptance |
| --- | --- | --- |
| S24-001 | Launcher opens | No blank page, crash, redirect loop, or desktop-only overflow |
| S24-002 | Mobile menu opens/closes | Tap targets respond reliably; no double-tap requirement |
| S24-003 | Native navigation | Every Mission Control link opens the intended route |
| S24-004 | Back navigation | Browser back returns to prior page without shell corruption |
| S24-005 | Portrait layout | No clipped cards, inaccessible controls, or unreadable tables |
| S24-006 | Landscape layout | Content remains usable after rotation |
| S24-007 | Scroll behavior | Vertical scrolling is smooth; no trapped or frozen regions |
| S24-008 | Jump links | Status/Risk/Evidence/etc. anchors scroll to the correct section |
| S24-009 | Disclosures | Evidence disclosures open and close with one tap |
| S24-010 | Touch cancellation | Normal taps are not swallowed by touch/pointer handlers |
| S24-011 | Text scaling | Browser text zoom does not make key safety state unreadable |
| S24-012 | Refresh | Refresh retains correct route and safe read-only posture |
| S24-013 | Screen lock/resume | Returning after lock/background does not corrupt the page |
| S24-014 | Network interruption | Lost/recovered Wi-Fi does not produce a misleading healthy state |
| S24-015 | Safety header | Runtime/Execution/Broker/Safety/Posture remain visible and accurate |
| S24-016 | Secret redaction | No credential/token/secret/account-identifying material appears |
| S24-017 | Screenshot policy | Mission Control screens behave according to the approved CSS screenshot policy |
| S24-018 | Accessibility/tap size | Menu, jump links, summaries, and navigation are comfortably tappable |
| S24-019 | No horizontal page sprawl | Main page does not require whole-page horizontal scrolling |
| S24-020 | Session/auth behavior | Authenticated pages remain correctly authorized; unauthorized state fails closed |

## 5. Required Page Sweep

Each route below must be opened on the physical S24 in portrait mode. At minimum verify page load, navigation, tap targets, disclosures, readable cards/tables, and fail-closed safety posture.

- Executive Overview
- Reports
- Runtime Operations
- Trade Operations
- Portfolio
- Market Intelligence
- Risk Command
- Options Income
- Broker Management
- Alerts and Incidents
- Certification and Readiness
- Audit and Explainability
- Learning and Performance
- Users and Governance
- System Configuration
- Documentation / Runbooks
- Credential Governance
- Enterprise Identity & Secrets
- Enterprise OAuth
- Executive Governance
- Production Readiness

## 6. High-Risk Regression Checks

### Broker Management
- Tier-1 broker summary is readable without page-wide horizontal scrolling.
- No OAuth handle, lease internals, token data, state hash, or account identifier is exposed.
- Selection editing is DISABLED.
- Onboarding changes are DISABLED.
- Execution is BLOCKED.

### Learning and Performance
- Raw committee objects are not dumped into the page.
- Runtime IDs, state hashes, and provenance blobs are absent from the visible mobile surface.
- Decision and recommendation content remains advisory only.

### Governance Pages
- Missing evidence is shown as EVIDENCE_MISSING rather than a reassuring zero.
- Explicitly empty evidence may show 0.
- Certification/readiness does not imply deployment authorization.

## 7. Physical UAT Completion Record

- Device:
- Android version:
- Browser and version:
- Test date/time:
- Branch:
- Commit:
- Launcher command:
- PC IPv4:
- Portrait sweep result:
- Landscape result:
- Navigation result:
- Disclosure/touch result:
- Redaction result:
- Screenshot-policy result:
- Network-interruption result:
- Overall result: PASS / FAIL / BLOCKED
- Open defects:
- Operator:
- Reviewer:

## 8. Closure Decision

Physical S24 mobile UAT can be closed only when:

1. all critical checks pass;
2. no secret/redaction defect exists;
3. navigation and touch interactions work on-device;
4. no safety posture is misrepresented;
5. any remaining cosmetic defects are explicitly accepted and non-blocking.

Until then:

```text
MISSION_CONTROL_CODE_TESTS = PASS
DESKTOP_BROWSER_UAT = PASS
S24_PHYSICAL_UAT = OPEN
PRODUCTION_CERTIFICATION = NOT_CERTIFIED
EXECUTION = BLOCKED
```
