# Phase 114C Mobile Icon Start URL Fix

**Date:** 2026-06-21
**Environment:** Control Branch `css-evening-consolidation-2026-06-09`

## Objective
Fix mobile PWA launcher install behavior so the home-screen icon opens the working CSS mobile launcher page directly, bypassing the 404 error on `/launcher/`.

## Issue Description
During Phase 114B, the launcher manifest `start_url` was pointing to `/launcher/`, which was not a registered route. This caused the Android home screen icon to launch to a 404 Not Found error page. 

## Resolutions Implemented
1. **Manifest Update**: 
   - `start_url` changed to `/mobile-launcher`.
   - `scope` set to `/`.
2. **Compatibility Route**: 
   - `/launcher/` was added to `css_mobile_launcher.py` returning the same 200 OK `mobile_launcher.html` page to gracefully handle existing installed icons without requiring a 307 redirect.
3. **Favicon Fallback**:
   - `/favicon.ico` was explicitly mapped to return `static/css_launcher_icon.svg` to prevent spurious 404 logs from mobile browsers aggressively probing for favicons.

## Important Note for Mobile Users
If you installed the CSS Launcher icon to your phone prior to this fix, the old icon may still try to target the old `start_url` or use old cached rules.
**Action Required:** You must delete the old icon and reinstall it from the new working URL:
`http://<Laptop1-IP>:8765/mobile-launcher`

## Validation
Unit tests have been successfully updated to prove:
- `GET /launcher/` returns 200 OK.
- `GET /favicon.ico` returns 200 OK (SVG format).
- Manifest explicitly contains `start_url: "/mobile-launcher"` and `scope: "/"`.
