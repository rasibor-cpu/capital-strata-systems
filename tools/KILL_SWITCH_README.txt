CSS KILL SWITCH (LIVE trading emergency stop)

Kill switch file:
  tools\KILL_SWITCH.flag

If this file EXISTS:
  - LIVE orders are blocked immediately.

Activate:
  PowerShell:
    New-Item -ItemType File -Force tools\KILL_SWITCH.flag

Deactivate:
  PowerShell:
    Remove-Item tools\KILL_SWITCH.flag

This is the fastest "stop trading now" control.