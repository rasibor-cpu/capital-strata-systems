from pathlib import Path
from datetime import datetime
import re

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

if not TARGET.exists():
    raise FileNotFoundError(f"Dashboard file not found: {TARGET}")

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_R2_SUPERUSER_LIVE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

old_block = '''# Live mode remains conservative unless the repo explicitly supports it.
for _method_name in [
    "can_use_live_broker_mode",
    "can_execute_live_trading",
]:
    if not hasattr(access_control, _method_name):
        setattr(access_control, _method_name, _pcnrass_deny_live)
'''

new_block = '''# PCNRASS R2:
# SUPER_USER may enter live broker mode for real balance visibility.
# Live execution remains separately controlled by broker gates, env flags,
# live-order switches, and order-specific protections.
def _pcnrass_live_mode_permission(role=None, *args, **kwargs):
    role_value = str(role or "").strip().upper()
    return _PCNRASSPermissionResult(role_value == "SUPER_USER")


def _pcnrass_live_execution_permission(role=None, *args, **kwargs):
    role_value = str(role or "").strip().upper()
    live_orders_enabled = (
        str(os.getenv("COINBASE_ENABLE_LIVE_ORDERS", "")).strip().lower()
        in {"1", "true", "yes", "y", "on"}
    )
    return _PCNRASSPermissionResult(role_value == "SUPER_USER" and live_orders_enabled)


# Allow SUPER_USER to select live mode so real broker balances can be fetched.
access_control.can_use_live_broker_mode = _pcnrass_live_mode_permission

# Keep actual live execution more restrictive.
access_control.can_execute_live_trading = _pcnrass_live_execution_permission
'''

if old_block not in text:
    raise RuntimeError("Expected RBAC live-mode block not found. No file modified.")

text = text.replace(old_block, new_block, 1)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS R2 BUILDER COMPLETE]")
print(f"Target updated: {TARGET}")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")