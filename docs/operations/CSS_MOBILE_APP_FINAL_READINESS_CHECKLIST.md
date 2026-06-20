# CSS Mobile App Final Readiness Checklist

## Overview
This checklist defines the final manual testing steps required before the CSS Mobile App is considered fully operational for day-to-day use by Robert.

## Startup
- [ ] Laptop IP address located via `ipconfig`.
- [ ] Mobile app started using `$env:CSS_MOBILE_LAN="true" ; python scripts/start_css_mobile_app.py`.
- [ ] Startup script prints safety warnings and network URL accurately.

## Phone Access & Validation
- [ ] Phone connected to the same local Wi-Fi network as laptop1.
- [ ] Navigated to printed URL in Safari / Chrome on the phone.
- [ ] **PWA Add-to-Home-Screen:** Successfully added the app to the phone's home screen for fullscreen PWA experience.
- [ ] **Login Test:** Reached login page and verified local authentication (no broker keys exposed).

## Navigation & Functionality Tests
- [ ] **Dashboard Page:** Verified uptime, runtime status, and cycle metrics load cleanly.
- [ ] **Positions Page:** Verified open paper positions display properly.
- [ ] **Broker Page:** Verified broker status and API connection health load correctly.
- [ ] **Controls Page:** Verified paper-trade buttons (Pause, Resume, Flatten) render cleanly on mobile.
- [ ] **Trade Page:** Verified execution logs and outcome ledgers are visible and properly scaled for a mobile screen.

## Safety Rules & Shutdown
- [ ] **Emergency Shutdown Test:** Pressed `Ctrl+C` in the terminal and verified the phone immediately loses connection.
- [ ] **Live Trade Prohibition:** Verified NO live arming capability is exposed via the mobile interface.
- [ ] **LAN Isolation:** Confirmed port 8090 is not forwarded on the router and remains strictly local.
