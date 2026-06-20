# CSS Mobile App Runbook

## Overview
This runbook provides instructions for securely launching and accessing the CSS Mobile App for monitoring and paper-trade controls while the CSS server runs on the primary laptop (laptop1).

## Startup Instructions

### 1. Local-Only Mode (Default)
By default, the mobile app binds to `127.0.0.1` and is only accessible from the laptop itself.

```powershell
python scripts/start_css_mobile_app.py
```

### 2. Phone Access Mode (LAN)
To access the app from your phone on the local Wi-Fi network, enable LAN binding.

```powershell
$env:CSS_MOBILE_LAN="true"
python scripts/start_css_mobile_app.py
```

## How to Find the Phone URL

When running in LAN mode, the script will automatically print the correct IP address (e.g., `http://192.168.x.x:8090`).
If you need to manually find the laptop IP:
1. Open PowerShell on the laptop.
2. Run `ipconfig`.
3. Look for the "IPv4 Address" under your primary Wi-Fi adapter.
4. On your phone browser, enter `http://<LAPTOP_IP>:8090`.

## Safety Rules

1. **Read-Only / Paper-Only Use:** The mobile app should primarily be used for monitoring positions, PnL, and alerts. Paper-trade controls are permitted.
2. **Do Not Arm Live:** Never arm live execution mode directly from the mobile browser over the phone.
3. **LAN Only:** Do not expose port 8090 to the public internet via router port-forwarding or tunnels.
4. **Shutdown:** Press `Ctrl+C` in the terminal to safely shut down the mobile server.

## Broker Isolation
The mobile startup script explicitly does not log, expose, or transmit broker API keys. Authentication is managed by the underlying laptop process.
