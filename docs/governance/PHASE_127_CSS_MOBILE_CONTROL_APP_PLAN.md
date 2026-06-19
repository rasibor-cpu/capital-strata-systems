# Phase 127 CSS Mobile Control App Plan

## 1. Objective
Design a mobile-first CSS control and monitoring app for use from Robert's phone while the CSS server runs on laptop1.

## 2. Mobile App Scope
- runtime status
- PnL summary
- open positions
- latest alerts
- supervisor health
- session status
- broker mode
- emergency pause/stop

## 3. Safety Rules
- mobile app must be read-only by default
- no live execution approval from mobile in v1
- emergency stop allowed
- no broker secrets exposed to mobile
- no credentials stored on phone
- all actions require authenticated session

## 4. Server Requirements
- laptop1 must remain powered on
- CSS dashboard/server must bind safely
- LAN-only access first
- no public internet exposure until security review

## 5. Mobile Screens
- Home / System Health
- PnL Dashboard
- Positions
- Alerts
- Session / Runtime
- Emergency Controls

## 6. Future Implementation Files
- dashboard/mobile/mobile_app.py
- dashboard/mobile/mobile_routes.py
- dashboard/mobile/templates/
- tests/mobile/test_mobile_dashboard.py

## 7. Security Requirements
- password/session authentication
- LAN-only default
- no exposed API keys
- CSRF protection for control actions
- emergency stop requires confirmation

## 8. Recommended Phase 127A
Implement read-only mobile dashboard first.

## 9. Recommended Phase 127B
Add emergency pause/stop controls.

## 10. Recommended Phase 127C
Add notification integration.
