# Phase 127A Mobile Dashboard + Paper Trade Controls Plan

## 1. Objective
Build a mobile-first CSS interface for monitoring and controlled paper-trade interaction while CSS runs on laptop1.

## 2. Mobile Dashboard
- runtime health
- cycle count
- uptime
- supervisor status
- PnL
- open positions
- latest alerts
- broker mode
- engine mode

## 3. Paper Trade Controls
Allow only:
- paper open test trade
- paper close selected position
- paper flatten all
- paper pause/resume auto-cycle

## 4. Prohibited In Phase 127A
- no live broker order placement
- no live capital deployment
- no mobile live-mode arming
- no API keys exposed to phone
- no public internet access

## 5. Emergency Controls
- emergency pause
- emergency flatten paper positions
- emergency stop auto-cycle

## 6. Security Rules
- authenticated session required
- LAN-only access
- CSRF protection
- confirmation required for every action
- all mobile actions must be logged
- no broker credentials returned to browser

## 7. Future Live Trading Rule
Live mobile trading may only be considered after:
- Phase 123 notification implementation
- key rotation certification
- micro-live review
- explicit separate approval

## 8. Recommended Implementation Files
- dashboard/mobile/mobile_app.py
- dashboard/mobile/mobile_routes.py
- dashboard/mobile/mobile_state_adapter.py
- dashboard/mobile/templates/
- tests/mobile/test_mobile_dashboard.py
- tests/mobile/test_mobile_paper_controls.py

## 9. Acceptance Criteria
- phone can view CSS status
- phone can view PnL
- phone can view positions
- phone can view alerts
- phone can trigger paper-only controls
- phone cannot execute live trades
- all control actions are logged
