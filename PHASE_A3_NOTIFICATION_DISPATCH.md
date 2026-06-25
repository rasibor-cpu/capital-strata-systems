# PHASE A3: Notification Dispatch

## Summary
This phase adds backend-only notification dispatch for canonical CRITICAL alerts.

## Scope
- Added `NotificationDispatcher` and `NotificationDispatcherError`.
- Added helper `dispatch_critical_alerts(repository, dispatcher)`.
- Supported channels:
  - FILE_LOG
  - CONSOLE_LOG
- No external email/SMS/API calls are performed in this phase.

## Rules Implemented
- Dispatches only CRITICAL alerts by default.
- Skips acknowledged alerts.
- Deduplicates notifications by `alert_id + channel`.
- Fails closed on invalid/corrupt notification storage.

## Notification Record Fields
- notification_id
- alert_id
- timestamp
- channel
- severity
- event_type
- source
- message
- status

## Test Coverage
- Critical alert dispatches.
- Warning/info do not dispatch by default.
- Acknowledged alert does not dispatch.
- Dedupe by `alert_id/channel`.
- FILE_LOG write behavior.
- CONSOLE_LOG acceptance.
- Corrupt storage fail-closed behavior.
