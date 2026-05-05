from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R9C_LIVE_MODE_FIXED.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R10B_AUTH_FIRST.py")


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    text = INPUT_FILE.read_text(encoding="utf-8")

    auth_line = "SESSION_USER_CTX = authenticate_startup_user()"
    mode_line = "GLOBAL_BROKER_MODE = select_global_broker_mode()"

    if auth_line not in text:
        raise RuntimeError("Auth startup line not found. No output written.")

    if mode_line not in text:
        raise RuntimeError("Global broker mode line not found. No output written.")

    auth_index = text.index(auth_line)
    mode_index = text.index(mode_line)

    if auth_index < mode_index:
        print("[INFO] Auth already occurs before broker mode. Copying input to output.")
        OUTPUT_FILE.write_text(text, encoding="utf-8")
        print(f"Output: {OUTPUT_FILE}")
        return

    # Remove the mode line from its current pre-auth location.
    text = text.replace(mode_line, "", 1)

    # Insert mode selection immediately after successful authentication.
    text = text.replace(
        auth_line,
        auth_line + "\n\n" + mode_line,
        1,
    )

    OUTPUT_FILE.write_text(text, encoding="utf-8")

    print("[SUCCESS] R10B AUTH-FIRST FLOW FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()