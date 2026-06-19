# Phase 123 Notification Providers Plan

## Objective
Extend Phase 120 Alert Service so CSS alerts can later be delivered outside the terminal.

## Supported Future Channels
- Console/log provider
- Email provider
- Telegram provider
- SMS provider
- Mobile push provider

## Provider-Neutral Architecture
Define:
AlertService
→ NotificationRouter
→ ProviderAdapter
→ External channel

## Safety Rules
- Notification failure must never execute trades.
- Notification failure must never bypass gates.
- Notification failure must never stop CSS.
- Notification credentials must never be committed.
- All providers must default OFF.
- Console provider remains default.

## Required Future Files
- engine/information/notification_router.py
- engine/information/providers/console_provider.py
- engine/information/providers/email_provider.py
- engine/information/providers/telegram_provider.py
- tests/engine/test_notification_router.py

## Environment Variables
Define placeholders only:
CSS_NOTIFY_EMAIL_ENABLED
CSS_NOTIFY_TELEGRAM_ENABLED
CSS_NOTIFY_SMS_ENABLED
CSS_NOTIFY_PUSH_ENABLED

## Alert Routing Rules
Critical alerts:
- emergency shutdown
- session expired
- broker unstable
- heartbeat lost
- recovery failed

Operational alerts:
- profit target reached
- trade blocked
- recovery attempt

## Delivery Requirements
- deduplicate repeated alerts
- rate-limit noisy alerts
- preserve local console output
- persist delivery attempts
- log failures safely

## Implementation Recommendation
Phase 123A should implement ConsoleProvider + NotificationRouter only.
External providers should come after security review.

## Acceptance Criteria
- design is broker-agnostic
- credentials are excluded from repo
- notification failure is fail-safe
- no runtime execution behavior changes
