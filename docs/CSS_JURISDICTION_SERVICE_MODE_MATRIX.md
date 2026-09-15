# CSS Jurisdiction / Service-Mode Approval Matrix

Status: CONTROL FRAMEWORK — NOT A LEGAL OPINION

CSS must not infer that approval for one service mode or jurisdiction applies to
another. Discover, Confirm, and Auto are separate regulatory/commercial modes.

## Service modes

- DISCOVER — recommendation discovery / decision-support presentation only.
- CONFIRM — customer reviews and affirmatively confirms a proposed action.
- AUTO — automated execution or equivalent delegated authority. This mode
  requires the highest level of regulatory, contractual, execution, broker, and
  production-control approval.

## Required evidence per jurisdiction and mode

Each jurisdiction/mode pair must have an immutable approval record with:

- jurisdiction code;
- service mode;
- approval status;
- approval/reference identifier;
- approval timestamp where approved;
- supporting legal/regulatory evidence references.

Valid statuses:

- PENDING
- APPROVED
- RESTRICTED
- PROHIBITED

Only APPROVED means the service mode may be treated as permitted for that
jurisdiction. Missing evidence is not approval.

## Launch rule

A jurisdiction may launch only the modes individually approved for it. For
example, DISCOVER approval does not authorize CONFIRM or AUTO.

AUTO additionally requires separate execution-authority controls and must never
be enabled merely because commercialization, billing, trial conversion, or
payment-collection controls are green.

## Current state

No jurisdiction/service-mode combination should be treated as legally approved
until external counsel/regulatory review evidence is recorded. This framework
exists to preserve that fail-closed posture.
