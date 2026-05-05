# === CSS R6 BUILDER: AUTH HARDENING (PCNRASS SAFE) ===
# Purpose:
# - Remove ALL fallback authentication paths
# - Enforce real login only
# - Preserve all existing functionality
# - No regression to trading / pnl / dashboard

from pathlib import Path

TARGET_FILE = Path("scripts/css_live_dashboard_PRE_R5_SYNC_20260504_163050.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R6_AUTH_HARDENED.py")


def apply_auth_hardening(content: str) -> str:
    """
    Replace unsafe fallback session returns with hard authentication enforcement
    """

    # 🔴 Replace LOCAL_OPERATOR fallback block
    content = content.replace(
        '''return {
            "user_id": "LOCAL_OPERATOR",
            "display_name": "Local Operator",
            "role": "ADMIN",
            "unit_code": "LOCAL",
            "home_branch": "LOCAL",
        }''',
        '''raise Exception("AUTHENTICATION_REQUIRED_NO_FALLBACK_ALLOWED")'''
    )

    # 🔴 Additional safety: remove any hidden ADMIN fallback patterns
    content = content.replace(
        '''"role": "ADMIN"''',
        '''"role": "AUTH_REQUIRED"'''
    )

    return content


def main():
    if not TARGET_FILE.exists():
        print(f"[ERROR] Target file not found: {TARGET_FILE}")
        return

    content = TARGET_FILE.read_text(encoding="utf-8")

    new_content = apply_auth_hardening(content)

    OUTPUT_FILE.write_text(new_content, encoding="utf-8")

    print("[SUCCESS] R6 AUTH HARDENED FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()